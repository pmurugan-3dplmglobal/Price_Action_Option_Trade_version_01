# Prod Code v01 — Project Documentation

## Project Structure

```
Prod_code_01/
├── app.py                                # Flask dashboard (Trading Control Center)
├── bull_index_trade_engine.py            # Index engine — NIFTY & BANKNIFTY options
├── bull_nifty50_scanner_executor.py      # Nifty 50 stock scanner + executor
├── bull_nifty50_daily_scanner_export.py  # Nifty 50 daily scanner (Excel export)
├── trade_db.py                           # JSON-based trade persistence
├── Kite_Access_Token_gen.py              # Token generator
├── launcher.py                           # Process launcher
├── test_anchor_scan.py                   # Anchor scan test
├── input/
│   └── program_config.json               # Global + per-engine configuration
├── output/
│   ├── logs/                             # Log files per engine
│   ├── monitor/                          # Runtime state files
│   │   ├── trades_db.json                # Persistent trade database
│   │   ├── trade_journal.csv             # Tab-separated journal (dashboard reads)
│   │   ├── executed_patterns.json        # Dedup registry (pattern keys)
│   │   ├── cycle_trades.json             # Temp per-cycle staged trades
│   │   └── stock_positions_state.json    # Nifty50 position state (only nifty50)
│   └── exports/                          # Monthly Excel exports
└── Read_Me_Notes/
    └── prod_doc_01.md                    # THIS FILE
```

---

## Engine Details

### 1. `bull_index_trade_engine.py` — Index Engine (NIFTY & BANKNIFTY)

**Purpose:** Scans weekly option contracts of NIFTY and BANKNIFTY for ABC bullish reversal patterns. Finds trades, executes them via Zerodha Kite, monitors SL/targets with trailing.

**Key Globals:**
- `INDEX_REGISTRY` — NIFTY (token=256265, lot=65, step=50) & BANKNIFTY (token=260105, lot=30, step=100)
- `TIMEFRAME_ENTRY` — defaults "15minute" (was "3minute" before config)
- `TIMEFRAME_ANCHOR` — "60minute" (used for anchor formation detection)
- `TIMEFRAME_FALLBACK` — "3minute" (fallback if 15min data fails)
- `STRIKE_RANGE` — configured via `program_config.json` (default 2)
- `ACTIVE_POSITIONS` — in-memory dict keyed by symbol (NIFTY/BANKNIFTY)
- `BACKTEST_DATE` — set when `--date=` flag is passed; None for live mode

**Flow:**
1. `main()` → `load_program_config()` → `load_kite_session()` → `fetch_instruments()`
2. If `--backtest-range=START,END` → `run_multi_day_backtest()` (no real trades)
3. If `--date=YYYY-MM-DD` → single-day backtest via `execute_scan_cycle()` + `execute_best_trade()`
4. If `_backtest=true` + no CLI flag → ERROR and exit
5. If live → `background_loop()` (scan → execute → monitor, infinite)

**`execute_scan_cycle(kite)` — Core Scanner:**
- Fetches historical data for NIFTY & BANKNIFTY (15min TF, lookback_days from config)
- Determines side: NIFTY → CE (calls), BANKNIFTY → PE (puts)
- Resolves all strikes in range (±STRIKE_RANGE from ATM): `resolve_option_strikes()`
- For each strike, fetches option price history from Kite
- Runs `scan_abc_reversal(df_entry, df_anchor)` on each strike's candles
- Stages found trades to `trade_db.stage_cycle_trade()` (temp JSON)
- Skips already-executed patterns via `trade_db.is_pattern_executed()`
- Returns list of dicts with: `symbol, pattern, side, contract, entry_spot, current_sl, t1, t2, t3, rr, strike, timeframe`

**`scan_abc_reversal(df_entry, df_anchor)` — ABC Reversal Pattern:**
```
A ← anchor candle (any type — no longer requires bearish candle)
B ← close > A.high
C ← retest: low ≤ A.high + close > A.low  OR  low ≤ A.low + close > A.low + close < A.open
D ← close > A.high
```
- No candle between A-D can close below A.low (invalidation)
- Lookback: 1-30 candles from D
- Targets (T1/T2/T3): computed from `find_targets()` using anchor timeframe
- RR = (T1 - entry) / (entry - SL), must be ≥ 1.88
- Minimum risk: (entry - SL) ≥ entry × 0.002 (0.2%)
- Returns dict or None

**`execute_best_trade(kite, staged)`:**
- Picks staged trade with max profit potential (max of t3 or t1)
- Resolves option: `resolve_option_contract()` or `resolve_option_strikes()`
- Calculates position size: `calc_position_size()` (1% risk per trade)
- Places limit order in live mode (entry × 1.005)
- Logs to journal CSV
- Records executed pattern key: `symbol|pattern|side|strike`

**`monitor_risk(kite)`:**
- Runs every cycle for each active position
- Checks if SL hit → close + mark SL_HIT in DB
- Checks if T1 hit → move SL to breakeven (trailing_stage=1)
- Checks if T2 hit → move SL to T1 (trailing_stage=2)
- Checks if T3 hit → close + mark TARGET_HIT in DB

**`simulate_trade_outcome(kite, best, day)` — Backtest Simulation:**
- Fetches 5 days of 3min candles starting from `day`
- Walks forward on each candle
- Returns SL_HIT / T1_HIT / T2_HIT / T3_HIT / None
- Tolerance: `max(abs(entry-sl)*0.3, entry*0.01, 0.5)` (risk-based, not fixed %)
- Retries Kite API up to 3 times on "Too many requests"

**`run_multi_day_backtest(kite, start_date, end_date)`:**
- Iterates over all trading days between start and end
- Each day: `execute_scan_cycle()` → `simulate_trade_outcome()` → log to journal
- Logs BACKTEST_ENTRY and EXIT_SL/EXIT_T3 rows to journal CSV
- Tracks wins/losses/P&L by symbol
- Uses `BACKTEST_DATE` global to override date for historical data fetching
- Clears cycle trades each day

**Backtest Guard:**
- If config has `_backtest: true` but no `--date=` or `--backtest-range=` flag, engine exits with error

**Dedup Keys:**
- `symbol|pattern|side|strike` — prevents same contract from being re-traded on subsequent days/cycles

---

### 2. `bull_nifty50_scanner_executor.py` — Nifty 50 Scanner

**Purpose:** Scans 48 individual Nifty 50 stocks for ABC bullish reversal patterns. For each matching stock, resolves the nearest ATM CE option and executes.

**Key Differences from Index Engine:**
- Scans individual stocks (not index options)
- Side is always "CE" (buys call options on bullish reversal)
- Strike computed from underlying close price + strike_step per stock
- No multi-day backtest support
- Uses `STOCK_REGISTRY` with 48 symbols (each has token, lot_size, strike_step)
- Supported operations: live trading, anchor scan, single-day backtest (`--date=`)

**`execute_scan_cycle(kite)`:**
- Fetches 15min TF data for all 48 stocks in parallel (10 workers)
- Runs `scan_abc_reversal()` on each stock's underlying price
- Adds `Side="CE"` and `Strike` (computed from close/strike_step) to result
- Dedup key: `symbol|pattern|side|strike`
- Stages found trades

**`execute_best_trade(kite, staged)`:**
- Picks best by max profit (T3 or T1)
- Resolves option via `resolve_option(symbol, spot, step, opt_type, target_strike)`
- Places limit order in live mode
- Records executed pattern

**`resolve_option(symbol, spot, step, opt_type, target_strike=None)`:**
- Accepts optional target_strike (from scanner's pre-computed strike)
- Falls back to nearest ATM if not provided
- Uses NFO_INSTRUMENTS dump if available, else constructs symbol name

**`execute_anchor_scan(kite)`:**
- Runs 60min anchor scan separately (batch of 5)
- Checks 4 old anchor patterns: ABCD, LL Sweep, Baby, Harami
- Logs to journal as "ANCHOR_SCAN"

**Left Side Rule:** Removed from index and nifty50 engines. Kept only in daily export engine.

---

### 3. `bull_nifty50_daily_scanner_export.py` — Daily Export Scanner

**Purpose:** Scans Nifty 50 stocks on daily timeframe (lookback 500 days), finds ABC reversal patterns, exports results to Excel in `output/exports/`.

**Key Differences:**
- Only scans, never executes trades
- Uses `day` timeframe (fetch limit 2000 days)
- **Left side rule is KEPT** (unlike index and nifty50 engines)
- Outputs to Excel instead of journal CSV
- Runs one scan and exits (no continuous loop)

---

### 4. `trade_db.py` — Trade Persistence

**JSON files used:**
- `output/monitor/trades_db.json` — Full trade database with CRUD
  - Structure: `{"next_id": N, "trades": [{id, engine, symbol, status, created_at, ...}]}`
  - Status: ACTIVE / SL_HIT / TARGET_HIT / etc.
  - Thread-safe with retry + temp file + atomic replace
- `output/monitor/cycle_trades.json` — Per-cycle temp storage
  - Structure: `{"engine_name": [trade_dict, ...]}`
- `output/monitor/executed_patterns.json` — Dedup registry
  - Structure: `{"engine_name": {"key": info_dict, ...}}`

**Known Issue — Single-day backtest (`--date=` mode):**
- `execute_best_trade()` calls `trade_db.create_trade()` which writes to `trades_db.json` with status "ACTIVE"
- Single-day backtest then returns WITHOUT calling `monitor_risk()` to simulate outcome or update trade status
- This leaves stale "ACTIVE" trades in the DB permanently
- The dashboard reads `trade_db.get_active_trades()` which returns ALL active trades, including stale backtest ones
- **Fix needed:** Single-day backtest should either skip `create_trade()` or close the trade after simulation

---

### 5. `app.py` — Flask Dashboard (Trading Control Center)

**Port:** 5050

**Programs Managed:**
| ID | Name | File |
|----|------|------|
| index | Index Trade Engine (Nifty & BankNifty) | `bull_index_trade_engine.py` |
| nifty50 | Nifty 50 Stock Scanner + Executor | `bull_nifty50_scanner_executor.py` |
| daily | Nifty 50 Daily Scanner (Export) | `bull_nifty50_daily_scanner_export.py` |

**Dashboard Sections:**
1. Status cards with start/stop buttons per program
2. Active Positions table — reads from `trade_db.get_active_trades()`
3. Backtest tab (`renderBacktest()`) — reads journal CSV
4. Trade journal tab — raw CSV display
5. Log viewer per program
6. Scan matches display
7. Token management (generate, check, exchange)
8. Backtest toggle switch

**`renderBacktest()` — Backtest Dashboard:**
- Reads `d.journal` from status API
- Groups by Symbol column from journal CSV
- Each group: entries (BACKTEST/BUY/ENTRY actions), SL hits (EXIT_SL), target hits (EXIT_T3), win rate, total/avg P&L, avg RR
- Expects: `BACKTEST_ENTRY` / `EXIT_SL` / `EXIT_T3` action names
- P&L from `P&L %` column (e.g., "-6.54%")

**API Endpoints:**
- `/api/status` — Positions, journal, logs, scans, stats, LTP, config
- `/api/config` — Read/write program_config.json
- `/api/start/<prog>` — Start a program as subprocess
- `/api/stop/<prog>` — Stop a program
- `/api/backtest/mode` — Get/set backtest mode
- `/api/token/*` — Token management endpoints
- `/api/export` — Monthly trade export to Excel

---

### 6. `program_config.json` — Configuration

```json
{
  "api_key": "...",
  "api_secret": "...",
  "daily": {
    "timeframe": "day",
    "lookback_days": 500
  },
  "_backtest": false,
  "index": {
    "timeframe": "15minute",
    "lookback_days": 100,
    "scan_interval": 15,
    "risk_percent": 1,
    "capital": 100000,
    "strike_range": 2
  },
  "nifty50": {
    "timeframe": "15minute",
    "lookback_days": 200,
    "scan_interval": 30,
    "risk_percent": 10,
    "capital": 100000
  }
}
```

**Global configs** (top level):
- `api_key`, `api_secret` — Zerodha Kite API credentials
- `_backtest` — Boolean, toggles live vs backtest for ALL engines
- `strike_range` — Controls ATM ± range for index engine strike selection

**Per-engine configs** override defaults:
- `timeframe` — Entry timeframe (e.g., "15minute")
- `lookback_days` — Historical data lookback
- `scan_interval` — Seconds between scans
- `risk_percent` — Max risk per trade as % of capital
- `capital` — Initial capital for position sizing

---

## NSE Weekly Expiry Change

- Effective **August 2025**: All derivative contracts expire on **Tuesday**
- NIFTY: Weekly Tuesday expiry
- BANKNIFTY: Fortnightly Tuesday expiry
- All code uses `get_weekly_expiry()` to determine target expiry date

---

## Scanner Details

### ABC Reversal Pattern (unified — replaces harami/ABCD/baby/LL sweep)

A bullish reversal structure with 4 candles A→B→C→D:

```
A ← Anchor (any candle type — no restriction on being bearish)
   Can be any structure: bullish engulfing, low 2, baby, harami, etc.
   Used for SL (A.low) and target benchmark (A.high)
B ← Close > A.high (confirms breakout)
C ← Retest (two valid cases):
   Case 1: low ≤ A.high AND close > A.low
   Case 2: low ≤ A.low AND close > A.low AND close < A.open
D ← Close > A.high (entry candle)
```

Conditions:
- ALL candles between A-D must have close > A.low (invalidation if any close below)
- At least one candle between A-D must have close > A.high (must have B-point)
- RR = (T1 - entry) / (entry - A.low) ≥ 1.88
- risk = entry - A.low ≥ entry × 0.002 (minimum 0.2% risk)
- No limit on candle count between A-D

---

## Simulated Backtest Details

### For Index Engine (`--backtest-range=START,END`):

Each trading day:
1. `execute_scan_cycle()` — runs scanner on historical data for that day using `BACKTEST_DATE` override
2. Picks best staged trade by max profit (T3 or T1)
3. Records executed pattern with dedup key: `symbol|pattern|side|strike`
4. Logs `BACKTEST_ENTRY` row to journal CSV
5. `simulate_trade_outcome()` — fetches 3min forward data, walks candle by candle:
   - Hits SL → returns `SL_HIT`
   - Hits T1/T2/T3 → returns `T1_HIT`/`T2_HIT`/`T3_HIT`
   - No exit within lookahead → returns `None`
6. Logs `EXIT_SL` or `EXIT_T3` row to journal CSV with P&L %
7. Computes P&L as %: `(exit_price - entry) / entry * 100`

### For Nifty50 (`--date=YYYY-MM-DD`):
- Single-day backtest only
- Creates DB trade record (known bug: leaves stale ACTIVE trades)
- No simulation of outcome

---

## Dashboard Backtest Display

The dashboard's `renderBacktest()` reads from journal CSV:

- **Symbol column** → used for grouping (shows contract name like "NIFTY2671424100PE")
- **Action column** → `BACKTEST_ENTRY` / `EXIT_SL` / `EXIT_T3`
- **P&L % column** → summed per symbol for total/avg P&L
- **RR column** → averaged per symbol
- Stats: Entries, SL Hits, Target Hits, Win Rate, Total P&L, Avg P&L, Avg RR

Win rate = targetHits / (slHits + targetHits) × 100

---

## Known Issues & TODOs

### 1. Single-day backtest leaves stale ACTIVE trades in DB
- **File:** `bull_index_trade_engine.py` line 976-985
- **Problem:** `--date=` mode calls `execute_best_trade()` which writes to `trades_db.json` with status "ACTIVE", then returns without simulating outcome or updating status
- **Effect:** Dashboard shows fake active positions
- **Fix:** Either skip `create_trade()` during backtest, or call `simulate_trade_outcome()` + `update_trade()` after execution
- **For nifty50 scanner** (lines 454-519): Same issue — `execute_best_trade()` called from `--date=` mode creates DB trades without closing them

### 2. Nifty50 scanner has no multi-day backtest
- Only `--date=YYYY-MM-DD` single-day
- No `--backtest-range=START,END` support
- The key `symbol|pattern|side|strike` is set up for it but the loop logic doesn't exist

### 3. ACTIVE_POSITIONS dict keyed by symbol (collision risk)
- In both index and nifty50 engines, `ACTIVE_POSITIONS` is `dict[symbol]`
- If multiple trades exist for same symbol (e.g., BANKNIFTY with different strikes), only last one survives
- Consider changing to `dict[trade_id]` or allowing list per symbol

### 4. ~~Kite position recovery uses wrong API field~~ ✅ FIXED
- ~~`p["net_quantity"]` doesn't exist in Kite API response~~ → Changed all `net_quantity` to `quantity` (correct Kite API field) across `app.py`, `bull_index_trade_engine.py`, and `bull_nifty50_scanner_executor.py`
- Kite positions now appear in Active Positions on the dashboard

### 5. Dashboard: Active Positions reads stale backtest trades
- `load_positions()` → `trade_db.get_active_trades()` returns ALL ACTIVE trades including stale backtest orphans
- Needs filtering by creation date or checking Kite for open positions

### 6. Backtest toggle stops index engine but not others
- Backtest toggle in dashboard only stops/restarts index engine via `/api/stop/index`
- Nifty50 and daily programs are not affected

---

## Key CLI Flags

```
# Index Engine
python bull_index_trade_engine.py                          # Live mode (requires _backtest=false)
python bull_index_trade_engine.py --date=2026-07-10        # Single-day backtest
python bull_index_trade_engine.py --backtest-range=2026-06-15,2026-07-10  # Multi-day backtest

# Nifty50 Scanner
python bull_nifty50_scanner_executor.py                    # Live mode
python bull_nifty50_scanner_executor.py --date=2026-07-10  # Single-day backtest
python bull_nifty50_scanner_executor.py --anchor-only      # Anchor scan only

# Daily Export
python bull_nifty50_daily_scanner_export.py                # Single scan + export to Excel

# Dashboard
python app.py                                               # Flask server on port 5050
```

---

## Output Files Reference

| File | Records | Read By |
|------|---------|---------|
| `output/monitor/trades_db.json` | All trades (CRUD) | Dashboard `load_positions()`, `get_all_trades()` |
| `output/monitor/trade_journal.csv` | Tab-separated trade log | Dashboard `load_journal()`, `renderBacktest()` |
| `output/monitor/executed_patterns.json` | Pattern dedup keys | `trade_db.is_pattern_executed()` |
| `output/monitor/cycle_trades.json` | Current cycle staged trades | `trade_db.get_cycle_trades()` |
| `output/logs/bull_index_trade_engine.log` | Index engine logs | Dashboard log viewer |
| `output/logs/bull_nifty50_scanner.log` | Nifty50 engine logs | Dashboard log viewer |
| `output/logs/bull_daily_scanner.log` | Daily engine logs | Dashboard log viewer |
| `output/exports/*.xlsx` | Monthly Excel exports | Manual download |

---

## Journal CSV Columns (tab-separated)

```
Timestamp | Symbol | Pattern | Timeframe | Action | Status | Entry | SL | Target | RR | Details | P&L %
```

**Action values for backtest:**
- `BACKTEST_ENTRY` — Trade entry
- `EXIT_SL` — Stop loss hit (loss)
- `EXIT_T3` — Target hit (win)

**Action values for live:**
- `BUY` / `BUY_CE` / `BUY_PE` — Trade placed
- `DRY_CE` / `DRY_PE` — Paper trade (backtest mode)
- `EXIT_SL` — SL hit
- `EXIT_T3` — T3 hit
- `TRAIL_BE` — SL moved to breakeven
- `TRAIL_T1` — SL moved to T1
- `ANCHOR_SCAN` — Anchor formation detected
- `KITE_RECOVERED` — Position recovered from Kite on restart

**P&L % format:** `"-6.54%"` for losses, `"-"` for entries (no P&L yet)
