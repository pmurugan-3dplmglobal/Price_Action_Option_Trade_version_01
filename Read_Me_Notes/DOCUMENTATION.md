# Trading Control Center — Documentation

## Overview

A multi-engine intraday trading system for Zerodha Kite that runs three independent trading programs, controlled via a single Flask web dashboard. Each engine detects bullish reversal patterns (ABCD, LL Sweep, Baby Candle, Harami) on Nifty/BankNifty options or Nifty 50 stocks, and executes trades with trailing stop-loss.

---

## System Architecture

```
  Browser (http://localhost:5050)
         |
    +----+----+
    |  app.py  |  Flask Dashboard (Control Center)
    |  port 5050|
    +----+----+
         |  manages subprocesses via start/stop API
         |
    +----+------+------+
    |           |       |
    v           v       v
  bull_index_trade_engine.py
  bull_nifty50_scanner_executor.py
  bull_nifty50_daily_scanner_export.py
    |           |       |
    +-----------+-------+---------> input/kite_access_token.txt (reads)
    |           |       |
    +-----------+-------+---------> input/program_config.json  (reads)
    |           |       |
    |           |       +---------> output/logs/daily_scanner.log
    |           +-----------------> output/logs/nifty50_scanner.log
    +---------------------------> output/logs/index_trade_engine.log
    |           |
    |           +---------.-----> output/monitor/stock_positions_state.json
    |           |
    +-----------+----------------> output/monitor/trade_journal.csv
```

### File Map

| File | Purpose |
|---|---|
| `app.py` | Flask web dashboard & process manager (the dashboard — formerly "trading_dashboard.py") |
| `bull_index_trade_engine.py` | Index options intraday engine (NIFTY & BankNifty) |
| `bull_nifty50_scanner_executor.py` | Nifty 50 stock scanner + executor |
| `bull_nifty50_daily_scanner_export.py` | Daily scanner (analysis only, exports to Excel) |
| `Kite_Access_Token_gen.py` | One-time token generator utility |
| `input/kite_access_token.txt` | API key + access token (JSON) |
| `input/program_config.json` | Global + per-engine configuration (also holds `api_key`/`api_secret`) |
| `output/monitor/trade_journal.csv` | Tab-delimited trade journal (all engines) |
| `output/monitor/stock_positions_state.json` | Active positions for crash recovery (nifty50 only) |
| `output/monitor/cycle_trades.json` | Temp storage of trades found in the current scan cycle |
| `output/monitor/executed_patterns.json` | Registry of already-executed patterns (dedup across cycles) |
| `output/logs/bull_index_trade_engine.log` | Index engine log |
| `output/logs/bull_nifty50_scanner.log` | Nifty 50 engine log |
| `output/logs/bull_daily_scanner.log` | Daily scanner log |

---

## Component Details

### 1. Control Center — `app.py`

Flask app on port 5050 with an auto-refreshing dashboard (every 5s).

**REST API Endpoints:**

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | Renders the HTML dashboard |
| `/api/status` | GET | Returns all live data: positions, journal, stats, logs, config, token status |
| `/api/token/check` | GET | Validates the saved access token |
| `/api/token/url` | GET | Returns the Kite Connect login URL |
| `/api/token/exchange` | POST | Exchanges OAuth request_token for access_token |
| `/api/backtest/mode` | GET/POST | Get or set global backtest mode |
| `/api/config/<prog_id>` | POST | Save configuration for a program |
| `/api/programs/<prog_id>/start` | POST | Start an engine as a subprocess |
| `/api/programs/<prog_id>/stop` | POST | Stop an engine subprocess |
| `/api/logs/clear` | POST | Truncate all three engine log files |

**Token Validation** (`check_token_valid`, line 165):
- Reads `input/kite_access_token.txt`
- Verifies `api_key` and `access_token` exist
- Checks token was generated today (tokens expire daily)

**Process Management:**
- Engines run as child subprocesses via `subprocess.Popen`
- Start propagates the global `_backtest` flag into the engine's config section
- Stop uses `taskkill /F /T /PID` on Windows, `SIGTERM` on Linux

---

### 2. Index Trade Engine — `index_trade_engine.py`

Scans NIFTY and BANKNIFTY index options for bullish reversal patterns and trades the ATM option contract.

**Config (from `program_config.json` → `["index"]`):**

| Key | Default | Description |
|---|---|---|
| `timeframe` | `3minute` | Candle timeframe (entry & anchor use the same value) |
| `lookback_days` | 100 | Historical lookback (capped per-interval by Kite limits) |
| `scan_interval` | 15 | Seconds between scan cycles |
| `risk_percent` | 1.0 | Risk per trade as % of capital |
| `capital` | 100000 | Capital in INR |

> Backtest vs live is controlled by the **global** `_backtest` flag (top of `program_config.json`), toggled from the dashboard. There is no per-engine `_backtest`.

**Scan Cycle Flow** (`execute_scan_cycle`, line 292):

```
1. Check market hours (skip if closed in live mode)
2. For each index (NIFTY, BANKNIFTY):
   a. Skip if already in ACTIVE_POSITIONS
   b. Fetch spot price (entry timeframe)
   c. Resolve ATM CE and PE option contracts
   d. Fetch CE & PE data for both entry + anchor timeframes
   e. Run 4 scanners in priority order:
      - ABCD Reversal Pattern
      - LL Liquidity Sweep
      - Baby Candle CRC
      - Bullish Harami
   f. Each scanner checks:
      - Left-side rule (higher-low validation)
      - Candle geometry constraints
      - Identifies T1/T2/T3 targets
      - Requires R:R >= 1.8
   g. If CE matches → open CE position
      If CE fails + PE matches → open PE position
```

**Pattern Scanner Logic:**

All four scanners share common utilities:
- `check_left_side_rule` (line 122): Validates the swing structure on the anchor timeframe — ensures the most recent swing low is higher than the previous swing low (higher-low formation).
- `find_negation_targets` (line 129): Identifies three price targets:
  - **T1**: A prior support/breaker level where price broke below the swing low and later recovered
  - **T2**: The highest high recorded before the lowest swing low
  - **T3**: A high of a swing point or bearish engulfing candle

**Execution** (lines 352-375):
- **Live mode**: `kite.place_order()` — MARKET buy, NFO, MIS
- **Backtest/dry mode**: Logs `DRY_CE` / `DRY_PE` to journal

**Risk Management** (`monitor_risk`, line 432):
```
For each active position:
  1. Fetch recent option price data
  2. Check if close < current SL → EXIT_SL (sell market order)
  3. Trail SL:
     - Stage 0 → T1 hit → SL moves to entry (breakeven)
     - Stage 1 → T2 hit → SL moves to T1
  4. T3 hit → EXIT_T3 (full target achieved)
```

**Log file:** `output/logs/index_trade_engine.log`

---

### 3. Nifty 50 Scanner + Executor — `nifty50_scanner_executor.py`

Scans all 47 Nifty 50 stocks, ranks setups by R:R, executes the single best trade, and manages it with trailing SL.

**Config (from `program_config.json` → `["nifty50"]`):**

| Key | Default | Description |
|---|---|---|
| `timeframe` | `15minute` | Candle timeframe (entry & anchor use the same value) |
| `lookback_days` | 200 | Historical lookback (capped per-interval by Kite limits) |
| `scan_interval` | 300 | Seconds between scan cycles |
| `risk_percent` | 1.0 | Risk per trade as % of capital |
| `capital` | 100000 | Capital in INR |

**Stock Registry** (line 42): 47 Nifty 50 constituent stocks with tokens, lot sizes, and strike steps. 10 high-liquidity "super stocks" scanned first.

**Scan Cycle Flow** (`execute_scan_cycle`, line 403):
```
1. Create scan order: SUPER_STOCKS first, then alphabetically
2. For each stock:
   a. Skip if already in ACTIVE_POSITIONS
   b. Fetch entry + anchor timeframe data
   c. Run 4 scanners (same patterns as index engine)
   d. Collect matches with their R:R ratios
3. Rank all setups by R:R descending
4. Execute the best setup:
   a. Calculate position size from risk %
   b. Resolve ATM Call option contract
   c. Record position + save to state file
   d. Live mode: LIMIT buy (ask + 0.5%)
   e. Backtest mode: Log DRY_BEST
```

**Risk loop** (line 541): Separate daemon thread, runs every 60 seconds — same trailing SL logic as index engine (BE → T1 → T3), but checks stock spot price (not option price).

**State Persistence:** Writes active positions to `output/monitor/stock_positions_state.json` for crash recovery. Restored on startup via `load_state()`.

**Execution Details:**
- Entry: LIMIT order at ask + 0.5% slippage buffer
- Exit: LIMIT order at bid - 0.5% slippage buffer
- Product: NRML (delivery-based), not MIS
- Variety: REGULAR

**Log file:** `output/logs/nifty50_scanner.log`

---

### 4. Daily Scanner Export — `nifty50_daily_scanner_export.py`

Analysis-only scanner — runs once, scans on `day` timeframe, exports results to Excel.

**Config (from `program_config.json` → `["daily"]`):**

| Key | Default | Description |
|---|---|---|
| `timeframe` | `day` | Candle timeframe |
| `lookback_days` | 500 | Historical data lookback (capped at 2000 for `day`) |

**Flow:**
```
1. Load token + sync instruments
2. For each of 47 Nifty 50 stocks:
   a. Fetch daily timeframe data
   b. Run 4 scanners (same patterns)
   c. Collect matches with R:R ratios + market data
3. Print sorted summary table
4. Export to Excel: scans_YYYYMMDD_HHMMSS.xlsx
```

**Key differences from other engines:**
- No live trading — purely analytical
- Single run, exits after scan
- No state file or journal write
- Both timeframes are `"day"`

**Log file:** `output/logs/daily_scanner.log`

---

### 5. Token Generator — `Kite_Access_Token_gen.py`

One-time utility to generate the daily access token.

**Flow:**
```
1. Initialize KiteConnect with API key
2. Print login URL to console
3. User opens URL in browser, logs in, gets redirected
4. User pastes the redirect URL into the console
5. Script extracts request_token
6. Calls kite.generate_session() to exchange for access_token
7. Saves api_key, access_token, generated_at to input/kite_access_token.txt
```

---

## Data Flow

### Token Flow

```
Kite_Access_Token_gen.py
    ↓  writes
input/kite_access_token.txt  {api_key, access_token, generated_at}
    ↓  read by
app.py (check_token_valid)  →  validates token exists & not expired
index_trade_engine.py (load_kite_session)  →  sets KiteConnect token
nifty50_scanner_executor.py (load_kite_session)  →  sets KiteConnect token
nifty50_daily_scanner_export.py (load_kite_session)  →  sets KiteConnect token
```

### Config Flow

```
Dashboard UI (Save Config button)
    ↓ POST /api/config/<prog_id>
app.py save_config()  →  writes input/program_config.json
    ↓
app.py start_program()  →  propagates _backtest flag, writes config
    ↓ subprocess
Engine load_program_config()  →  reads config, sets global variables
```

### Journal Flow

```
Engine entry/exit actions
    ↓ log_to_journal()
output/monitor/trade_journal.csv  (tab-delimited, all engines append)
    ↓ read by dashboard every 5s
app.py load_journal()  →  last 200 rows
    ↓
Dashboard Trade Journal tab (filterable by engine)
Dashboard Backtest tab (per-symbol stats)
```

---

## Configuration Reference

### `input/program_config.json`

```json
{
  "api_key": "<your Kite api_key>",
  "api_secret": "<your Kite api_secret>",
  "daily": {
    "timeframe": "day",
    "lookback_days": 500
  },
  "_backtest": false,            // Global backtest mode (false = live trading)
  "index": {                     // Index Trade Engine
    "timeframe": "3minute",
    "lookback_days": 100,
    "scan_interval": 15,
    "risk_percent": 1.0,
    "capital": 100000
  },
  "nifty50": {                   // Nifty 50 Scanner + Executor
    "timeframe": "15minute",
    "lookback_days": 200,
    "scan_interval": 300,
    "risk_percent": 1.0,
    "capital": 100000
  }
}
```

> `api_key`/`api_secret` live here (moved out of `app.py` source). `timeframe` is a single value used for both entry and anchor candles. There is no per-engine `_backtest`.

**Valid timeframe options:** `minute`, `3minute`, `5minute`, `10minute`, `15minute`, `30minute`, `60minute`, `day`

**Lookback limits (enforced by engine, per Kite historical API):**
- `minute`: max 60 days
- `3minute`: max 100 days
- `5minute`: max 100 days
- `10minute`: max 100 days
- `15minute`: max 200 days
- `30minute`: max 200 days
- `60minute`: max 400 days
- `day`: max 2000 days

---

## Backtest vs Live Mode

| Aspect | Backtest Mode (`_backtest: true`) | Live Mode (`_backtest: false`) |
|---|---|---|
| Order placement | Logged to journal only | Real Kite API orders |
| `LIVE_MARKET_DEPLOYMENT` | `False` | `True` |
| Market hours check | Skipped | Enforced |
| Index scan entry | Logs `DRY_CE` / `DRY_PE` | Places `BUY_CE` / `BUY_PE` market orders |
| Nifty50 scan entry | Logs `DRY_BEST` | Places LIMIT buy at ask+0.5% |
| Exit/liquidation | Skipped | Real sell order |

---

## Trade Journal Format

File: `output/monitor/trade_journal.csv` (tab-delimited)

| Column | Example | Description |
|---|---|---|
| Timestamp | `2026-07-09 09:15:30` | Event time |
| Symbol | `NIFTY` / `RELIANCE` | Trading symbol |
| Pattern | `Setup_1_ABCD` | Pattern that triggered |
| Timeframe | `minute/5minute` | Entry/Anchor TF |
| Action | `DRY_CE` / `BUY` / `EXIT_SL` | Event type |
| Status | `ACTIVE` / `CLOSED` | Position status |
| Entry | `25000.00` | Entry price |
| SL | `24900.00` | Stop-loss price |
| Target | `25200.00` | T3 target price |
| RR | `2.15` | Risk-reward ratio |
| Details | `T1 hit` | Additional info |
| P&L % | `+1.25` | Profit/loss (EXIT events) |

**Action values:** `DRY_CE`, `DRY_PE`, `DRY_BEST`, `BUY_CE`, `BUY_PE`, `BUY`, `EXIT_SL`, `EXIT_T3`, `TRAIL_BE`, `TRAIL_T1`

---

## Deployment

### Prerequisites
- Python 3.8+
- Zerodha Kite trading account
- Required packages: `flask`, `kiteconnect`, `pandas`, `openpyxl`

### Startup
```bash
python app.py
```
Opens at `http://localhost:5050`

### Steps
1. Open the dashboard
2. If token is missing/expired: click "Generate Token" → open the Kite login URL → paste the redirect URL → submit
3. Configure each engine via the dropdown/inputs under each program card
4. Click "Save Config", then "Start"
5. Monitor positions, journal, and logs in the live reports section

### Files Created
- `input/` — Token and config
- `output/logs/` — Per-engine log files
- `output/monitor/` — Journal CSV and position state JSON
- `logs/` — (legacy, unused)
