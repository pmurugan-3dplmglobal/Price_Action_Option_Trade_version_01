# Master System Documentation & Deployment Guide — Price Action Strategy (Prod Code v01)

---

## 1. Executive Summary & Overview

The **Price Action Strategy (Prod Code v01)** is a multi-engine, automated intraday trading and scanning system built for Zerodha Kite Connect. It executes price-action strategies—specifically the **Unified ABC Bullish Reversal Pattern**—across NIFTY & BankNifty index options as well as Nifty 50 constituent stock options.

The system features:
- **Index Options Trade Engine**: Continuously scans ATM Call & Put options for NIFTY and BankNifty.
- **Nifty 50 Stock Option Scanner & Executor**: Parallel-scans 48 constituent stocks and displays the stocks once pattern formed (optional: executes ATM Call/Put options on top-ranked setups).
- **Daily Analytical Scanner**: Analyzes daily timeframe charts for long-term setups and exports structured reports to Excel (CSV format ).
- **Trading Control Center (Web Dashboard)**: A Flask web application (port 5050) providing real-time process control, token management, position tracking, log viewing, and backtest analytics.
- **Persistent Database & Logging Layer**: Thread-safe JSON database and tab-separated CSV journal logging.

---

## 2. System Architecture & Component Mapping

### 2.1 System Architecture Diagram

```
                     Browser (http://localhost:5050)
                                    │
                               ┌────┴────┐
                               │ app.py  │ (Flask Control Center / Port 5050)
                               └────┬────┘
                                    │ (Subprocess Management)
          ┌─────────────────────────┼─────────────────────────┐
          ▼                         ▼                         ▼
bull_index_trade_engine.py  bull_nifty50_scanner_executor.py  bull_nifty50_daily_scanner_export.py
 (NIFTY / BANKNIFTY Options)     (Nifty 50 Stock Options)      (Daily Scan + Excel Export)
          │                         │                         │
          └─────────────────────────┼─────────────────────────┘
                                    ▼
                         input/ & output/ Files
                     (Token, Config, Journal, DB)
```

### 2.2 Directory & File Layout

```
Prod_code_01/
├── app.py                                # Flask dashboard (Trading Control Center)
├── trading_core.py                       # Shared strategy core (pattern scanners, registries, utilities)
├── bull_index_trade_engine.py            # Index engine — NIFTY & BANKNIFTY options
├── bull_nifty50_scanner_executor.py      # Nifty 50 stock scanner + executor
├── bull_nifty50_daily_scanner_export.py  # Nifty 50 daily scanner (Excel export)
├── trade_db.py                           # JSON-based trade persistence & cycle staging
├── Kite_Access_Token_gen.py              # Zerodha Kite OAuth token generator utility
├── launcher.py                           # Subprocess launcher helper
├── test_anchor_scan.py                   # Standalone anchor scan test script
├── requirements.txt                      # Python dependencies
├── .gitignore                            # Git ignore rules
├── kill_all.bat                          # Kill all running engine processes (Windows)
├── input/
│   ├── program_config.json               # Global + per-engine configuration
│   ├── kite_access_token.txt             # Saved daily Kite API credentials & session token
│   ├── nifty50_live.flag                 # Flag file to enable live Nifty 50 execution
│   └── index_live.flag                   # Flag file to enable live Index execution
├── output/
│   ├── logs/                             # Log files per engine
│   │   ├── index_trade_engine.log
│   │   ├── nifty50_scanner.log
│   │   ├── daily_scanner.log
│   │   ├── dashboard_out.log             # Dashboard subprocess stdout
│   │   ├── dashboard_err.log             # Dashboard subprocess stderr
│   │   └── token_generation.log          # Token generator script log
│   ├── monitor/                          # Runtime state & DB files
│   │   ├── trades_db.json                # Persistent trade database
│   │   ├── trade_journal.csv             # Tab-separated trade journal (dashboard source)
│   │   ├── executed_patterns.json        # Deduplication registry (pattern keys)
│   │   ├── cycle_trades.json             # Staged cycle trade storage
│   │   ├── stock_positions_state.json    # Nifty 50 active position recovery state
│   │   ├── scan_display_data.json        # Nifty 50 scan display data for dashboard
│   │   ├── scan_display_index.json       # Index scan display data for dashboard
│   │   ├── export_state.json             # Tracks last auto-export month
│   │   ├── sl_target_overrides.json      # In-flight SL/T1 overrides from dashboard
│   │   ├── anchor_scan_request.txt       # Request file for cross-engine anchor scan
│   │   └── anchor_scan_stop.txt          # Stop signal for anchor scan subprocess
│   └── exports/                          # Monthly Excel export reports & daily scans
└── Read_Me_Notes/
    └── DOCUMENTATION.md                  # MASTER DOCUMENTATION FILE (THIS FILE)
```

### 2.3 File Map & Component Responsibilities

| File | Primary Responsibility |
|---|---|
| `trading_core.py` | Shared Strategy Core. Contains common pattern finding (`scan_abc_reversal`, 4 anchor detectors), `STOCK_REGISTRY`, `SUPER_STOCKS`, `INDEX_REGISTRY`, `find_profit_targets`, session loading, market hours check, and journal writer. |
| `app.py` | Web Dashboard & Process Manager. Serves REST API, handles login URL generation & request token exchange, controls subprocess start/stop, displays live positions, journal logs, and backtest results. |
| `bull_index_trade_engine.py` | Scans NIFTY and BankNifty index options on 15m/60m timeframes for ABC Reversals, stages trades, places market orders (MIS), and manages trailing SL. Supports multi-day forward backtesting. |
| `bull_nifty50_scanner_executor.py` | Parallel-scans 48 Nifty 50 stocks, ranks setups by R:R, places NRML limit orders for ATM Call options on top setups, and manages trailing SL via a 60-second daemon thread. |
| `bull_nifty50_daily_scanner_export.py` | Analytical daily-timeframe scanner (lookback up to 2000 days). Generates summary tables and exports results to Excel (`output/exports/`). |
| `trade_db.py` | Thread-safe JSON storage manager for `trades_db.json`, cycle staging (`cycle_trades.json`), and pattern deduplication (`executed_patterns.json`). |
| `Kite_Access_Token_gen.py` | Interactive CLI tool to perform Zerodha Kite login, obtain request token, exchange it for access token, and save to `input/kite_access_token.txt`. |
| `launcher.py` | Script to launch index engine, stock scanner, and dashboard concurrently in background processes. |

---

## 3. Configuration & Data Flow

### 3.1 `input/program_config.json` Schema

```json
{
  "api_key": "your_kite_api_key",
  "api_secret": "your_kite_api_secret",
  "_backtest": false,
  "daily": {
    "timeframe": "day",
    "lookback_days": 500
  },
  "index": {
    "timeframe": "3minute",
    "lookback_days": 100,
    "scan_interval": 15,
    "risk_percent": 1.0,
    "capital": 100000,
    "strike_range": 1
  },
  "nifty50": {
    "timeframe": "30minute",
    "lookback_days": 200,
    "scan_interval": 30,
    "risk_percent": 10.0,
    "capital": 100000
  }
}
```

* **Global Settings**: `api_key`, `api_secret`, and `_backtest` (toggles dry/paper run vs real Kite API order placement across all engines).
* **Per-Engine Settings**: `timeframe`, `lookback_days`, `scan_interval` (seconds), `risk_percent`, and `capital`. Index engine additionally supports `strike_range` (ATM ± number of strikes evaluated).

### 3.2 Historical Data Lookback Limits (Kite API Caps)

Engines automatically cap requested lookback days according to Zerodha Kite API constraints:

| Timeframe Interval | Max Allowed Lookback Days |
|---|---|
| `minute` | 60 days |
| `3minute` | 100 days |
| `5minute` | 100 days |
| `10minute` | 100 days |
| `15minute` | 200 days |
| `30minute` | 200 days |
| `60minute` | 400 days |
| `day` | 2000 days |

### 3.3 Token Generation & OAuth Flow

```
1. Run Kite_Access_Token_gen.py  OR  Use Dashboard Token Modal (/api/token/url)
2. Log in to Zerodha in browser -> Authorized redirect URL containing request_token
3. Paste redirect URL into script/dashboard modal (/api/token/exchange)
4. kite.generate_session(request_token, api_secret) obtains access_token
5. Token saved to input/kite_access_token.txt:
   {
     "api_key": "...",
     "access_token": "...",
     "generated_at": "YYYY-MM-DD HH:MM:SS"
   }
6. Engines check token on startup; tokens expire daily before market open.
```

### 3.4 Data Flow Diagrams

#### Configuration Propagation
```
Dashboard UI (Save Config) ──► POST /api/config/<prog_id>
                                       │
                                       ▼
                            input/program_config.json
                                       │
                                       ▼ (Subprocess Start)
                              Engine load_program_config()
```

#### Trade Execution & Journaling Flow
```
Engine Entry/Exit Trigger
         │
         ├──► trade_db.py ──► output/monitor/trades_db.json & executed_patterns.json
         │
         ├──► Journal Writer ──► output/monitor/trade_journal.csv (Tab-delimited)
                                        │
                                        ▼ (Polled every 5s)
                               Dashboard UI (Active Positions, Journal, Backtest View)
```

---

## 4. Detailed Engine Specifications

### 4.1 Index Trade Engine (`bull_index_trade_engine.py`)

* **Instruments**: Weekly Option contracts for NIFTY (lot size 65, step 50) and BANKNIFTY (lot size 30, step 100).
* **Timeframes**: Entry timeframe `3minute`, Anchor timeframe `15minute` (fallback `3minute`).
* **Expiry Rules**: Calculates target weekly expiry using `get_weekly_expiry()`. Aligned with NSE derivatives Tuesday expiry rules (effective August 2025).
* **Strike Selection**: Evaluates ATM $\pm$ `strike_range` (e.g., range 1 = ATM-1 to ATM+1 strikes).
* **Cycle Batching & Staging**:
  1. Fetches historical candles for all strikes in range.
  2. Runs `scan_abc_reversal()` on option candle data.
  3. Stages setups to `output/monitor/cycle_trades.json` via `trade_db.stage_cycle_trade()`.
  4. Deduplicates against `output/monitor/executed_patterns.json` using pattern key `symbol|pattern|side|strike`.
  5. If staged trades exist, calls `execute_best_trade()` to select and execute the setup with maximum profit potential ($T3 - \text{entry}$).
* **Execution**: Market orders (MIS) in live mode; logs `DRY_CE` / `DRY_PE` in backtest mode.
* **Risk & Trailing SL**: Evaluates option prices continuously:
  * Close $< \text{SL} \rightarrow$ `EXIT_SL`
  * Stage 0: SL at initial pattern low.
  * Stage 1 ($T1$ hit): Move SL to breakeven (`TRAIL_BE`).
  * Stage 2 ($T2$ hit): Move SL to $T1$ (`TRAIL_T1`).
  * Stage 3 ($T3$ hit): Exit full position (`EXIT_T3`).
* **Backtest Engine**:
  * Multi-day backtest (`--backtest-range=START,END`): Iterates through each trading day in range, runs scanner, simulates trade outcomes candle-by-candle with 3m forward lookahead data, and outputs stats to journal.

### 4.2 Nifty 50 Stock Scanner & Executor (`bull_nifty50_scanner_executor.py`)

* **Instruments**: All 50 Nifty 50 constituent stocks with individual tokens, lot sizes, and strike steps defined in `STOCK_REGISTRY`.
* **Stock Ordering**: Scans all 50 stocks equally in standard alphabetical order (`sorted(STOCK_REGISTRY.keys())`) without priority bias.
* **Parallel Processing**: Uses a `ThreadPoolExecutor` with 2 worker threads per stock for fast candle retrieval (entry + anchor timeframes fetched concurrently), and 10 stocks processed in parallel across 10 main threads.
* **Side**: Scans both Call (`CE`) and Put (`PE`) ATM option contracts for each stock for bullish reversal setups; executes on the matched side.
* **Execution Details**:
  * Product: `NRML` (delivery/options product).
  * Entry: `LIMIT` order at ask price $+ 0.5\%$ slippage buffer.
  * Exit: `LIMIT` order at bid price $- 0.5\%$ slippage buffer.
* **State Persistence & Risk Daemon**:
  * Saves active positions to `output/monitor/stock_positions_state.json`.
  * Dedicated daemon thread checks underlying stock spot price every 60 seconds against SL/Targets. Restores active state on script restart.

### 4.3 Daily Scanner Export (`bull_nifty50_daily_scanner_export.py`)

* **Purpose**: Purely analytical scanner running on `day` timeframe (lookback up to 2000 days).
* **Left-Side Rule**: Retains left-side swing validation rule (verifies higher-low swing structure on daily timeframe).
* **Output**: Formats results table in log and exports detailed spreadsheet to `output/exports/scans_YYYYMMDD_HHMMSS.xlsx`. Supports `--anchor-only` scanning mode.

### 4.4 Trade DB & Staging Layer (`trade_db.py`)

Provides thread-safe JSON read/write operations using temporary file replacement:
* **`trades_db.json`**: Primary database storing trade records (`id`, `engine`, `symbol`, `status`, `entry`, `sl`, `t1`, `t2`, `t3`, `pnl`, `created_at`).
* **`cycle_trades.json`**: Staging area for setups discovered during the current scan cycle before executing the best setup.
* **`executed_patterns.json`**: Key-value registry (`symbol|pattern|side|strike`) ensuring identical patterns are not re-traded.

### 4.5 Web Dashboard & Control Center (`app.py`)

Flask application running on port `5050`.

#### REST API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Renders main HTML dashboard interface |
| `/api/status` | GET | Returns JSON with live positions, journal rows, program statuses, logs, token health, and backtest stats |
| `/api/token/check` | GET | Verifies if `input/kite_access_token.txt` is present and valid for today |
| `/api/token/url` | GET | Returns the Zerodha Kite login authorization URL |
| `/api/token/exchange` | POST | Receives `request_token`, generates `access_token`, and updates token file |
| `/api/config/<prog_id>` | POST | Updates configuration in `input/program_config.json` |
| `/api/programs/<prog_id>/start` | POST | Launches the specified program as a background subprocess |
| `/api/programs/<prog_id>/stop` | POST | Stops the program subprocess (using `taskkill` on Windows / `SIGTERM` on Linux) |
| `/api/backtest/mode` | GET/POST | Toggles global `_backtest` flag in config |
| `/api/logs/clear` | POST | Truncates log files in `output/logs/` |
| `/api/export/monthly` | POST | Exports completed trades for current month to Excel archive (`trade_archive.xlsx`) |
| `/api/trades` | GET | Returns raw trade records from DB. Supports `?engine=` and `?active=true` query params |
| `/api/live-execution/nifty50` | GET/POST | Toggles live execution flag for Nifty 50 engine (`input/nifty50_live.flag`) |
| `/api/live-execution/index` | GET/POST | Toggles live execution flag for Index engine (`input/index_live.flag`) |
| `/api/anchor/scan` | POST | Triggers an anchor scan subprocess (`--anchor-only`) for the specified engine |
| `/api/anchor/stop` | POST | Signals the anchor scan subprocess to stop via `anchor_scan_stop.txt` |
| `/api/anchor/status` | GET | Returns current anchor scan running state and engine info |
| `/api/update-position` | POST | Overrides SL/T1 for an active position (writes to `sl_target_overrides.json`) |

---

## 5. Strategy Logic: Unified ABC Reversal Pattern

The strategy identifies bullish reversal setups formed by 4 key candles ($A \rightarrow B \rightarrow C \rightarrow D$):

```
Price
  ▲
  │           [B] Breakout (Close > A.high)
  │             ▲
  │    [A]      │        [D] Entry Candle (Close > A.high)
  │   Anchor    │   [C]   ▲
  │   Candle    │  Retest │
  │    ┌──┐     │   ┌──┐  │ ┌──┐
  │    │  │     └───┤  ├──┴─┤  │
  │    └──┘         └──┘    └──┘
  │    High          Low > A.low
  │    Low (SL)
  └───────────────────────────────────► Time
```

### 5.1 Pattern Rules
1. **Candle A (Anchor)**: Base candle establishing reference levels (`A.high` for breakout/targets, `A.low` for Stop Loss).
2. **Candle B (Breakout)**: Candle closing strictly above `A.high` (`Close > A.high`).
3. **Candle C (Retest)**: Retests anchor zone without invalidation. Valid in two cases:
   - *Case 1*: `Low <= A.high` AND `Close > A.low`
   - *Case 2*: `Low <= A.low` AND `Close > A.low` AND `Close < A.open`
4. **Candle D (Entry Candle)**: Final confirmation closing above anchor high (`Close > A.high`).
5. **Invalidation**: No candle between A and D can close below `A.low`. If any candle closes below `A.low`, the pattern is invalid.
6. **Lookback Window**: Pattern formation evaluated across 1 to 30 candles. If a prior pattern achieved SL or Target on closing basis within the lookback window, the pattern is invalidated.

### 5.2 Target & Risk-Reward Calculation
* **Stop Loss (SL)**: Set at `A.low`.
* **Risk (R)**: $\text{Entry} - \text{SL}$. Minimum risk required: $\text{Risk} \ge \text{Entry} \times 0.002$ ($0.2\%$).
* **Targets ($T1, T2, T3$)**: Derived from swing structural points on the anchor timeframe:
  * **T1**: First prior resistance / swing structural high above anchor.
  * **T2**: Major swing high prior to lowest low.
  * **T3**: High of swing point or bearish engulfing origin.
* **Risk-Reward Constraint**: Minimum $R:R = \frac{T1 - \text{Entry}}{\text{Entry} - \text{SL}} \ge 1.88$.

### 5.3 The Strategy Setups (Implemented in `trading_core.py`)

| Setup | Pattern Name | Anchor Candle (A) Description | Entry (D) & SL Rules | `trading_core.py` Function |
|---|---|---|---|---|
| **Setup 1** | **Bullish Engulfing ($A - B - C - D$)** | Bullish engulfing candle wrapping prior bearish body/wick. | **D**: Close > `A.high`<br>**SL**: Below `A.low` or `C.low`<br>**Targets**: Negation levels $T1, T2, T3$ | `find_anchor_bullish_engulfing()` & `scan_abc_reversal()` |
| **Setup 2** | **Lower Low (LL) Sweep Setup** | Sweep candle dips below `Low 1` (prior 25-candle swing low); Candle **B** recovers and closes above sweep high. | **D**: Close > `B.high`<br>**SL**: Below Sweep Candle Low<br>**Targets**: Structural peaks $T1, T2, T3$ | `find_anchor_ll_sweep()` |
| **Setup 3** | **Two Higher High + Bullish Engulfing** | Two successive higher-high candles ($A1$ and $A2$) with bullish engulfing structure. | **D**: Close > `A1`/`A2.high`<br>**SL**: Below `A1`/`A2.low`<br>**Targets**: Resistance peaks $T1, T2, T3$ | `find_anchor_two_higher_highs()` |
| **Setup 4** | **Baby Candle / Pinbar / Hammer** | Small baby candle, pinbar, or hammer inside a mother candle after a downtrend. | **D**: Close > `A.high`<br>**SL**: Below `A.low` or `C.low`<br>**Targets**: Resistance peaks $T1, T2, T3$ | `find_anchor_hammer_baby()` |
| **Setup 5** | **Bullish Harami (Inside Bar)** | Bullish inside bar completely enclosed within prior bearish mother candle body. | **D**: Close > `Inside.high`<br>**SL**: Below `Inside.low`<br>**Targets**: Resistance peaks $T1, T2, T3$ | `find_anchor_bullish_harami()` |

---

## 6. Backtest vs. Live Mode Matrix & Journal Reference

### 6.1 Operating Modes Comparison

| Feature | Backtest Mode (`_backtest: true`) | Live Mode (`_backtest: false`) |
|---|---|---|
| **Order Execution** | Simulated / Logged to journal | Real Kite Connect API orders placed |
| **`LIVE_MARKET_DEPLOYMENT`** | `False` | `True` |
| **Market Hours Check** | Bypassed | Enforced (9:15 AM - 3:30 PM IST) |
| **Index Trade Action** | Logs `DRY_CE` / `DRY_PE` | Places `BUY` MIS market order |
| **Nifty 50 Trade Action** | Logs `DRY_BEST` / `BACKTEST_ENTRY` | Places `BUY` NRML limit order |
| **Exit Execution** | Simulated SL / Target hits | Real sell limit/market order placed |

### 6.2 Trade Journal CSV Format

File path: `output/monitor/trade_journal.csv` (Tab-delimited format)

```
Timestamp    Symbol    Pattern    Timeframe    Action    Status    Entry    SL    Target    RR    Details    P&L %
```

#### Action Column Values
* `BUY` / `BUY_CE` / `BUY_PE`: Live trade entry order placed.
* `DRY_CE` / `DRY_PE` / `DRY_BEST`: Paper trade entry logged in backtest mode.
* `BACKTEST_ENTRY`: Historical backtest entry event.
* `BACKTEST_BEST`: Best trade selected during multi-day backtest cycle.
* `EXIT_SL`: Position closed due to Stop Loss hit.
* `EXIT_T3`: Position closed due to Target 3 hit.
* `TRAIL_BE`: Trailing Stop Loss moved to breakeven (T1 hit).
* `TRAIL_T1`: Trailing Stop Loss moved to T1 level (T2 hit).
* `ANCHOR_SCAN` / `ANCHOR_CE` / `ANCHOR_PE`: Anchor formation detected during scan.
* `KITE_RECOVERED`: Position state successfully recovered from Kite on restart.
* `SCAN_MATCH` / `SCAN_READY`: Pattern match staged or ready for manual entry.

---

## 7. Cloud Deployment Guide (24/7 Production Setup)

Deploying the trading bot to a cloud virtual machine ensures uninterrupted 24/7 operation, redundant power and network connectivity, and remote access via mobile/laptop.

### 7.1 Recommended Cloud Platform: Oracle Cloud Always Free

| Feature | Oracle Cloud Free Tier | AWS Free Tier | GCP Free Tier |
|---|---|---|---|
| **Compute / CPU** | **4 ARM Cores** (Ampere A1) | 1 vCPU | 0.2 vCPU |
| **RAM Memory** | **24 GB** | 1 GB | 0.6 GB |
| **Storage Disk** | **200 GB** | 30 GB | 30 GB |
| **Free Duration** | **Always Free (Never expires)** | 12 Months Only | Never expires (restricted) |
| **Static IP** | Included Free | Additional Cost | Additional Cost |
| **24/7 Execution** | ✅ Full Capacity | ❌ Limited after 1 yr | ⚠️ Severely limited |

---

### 7.2 Step-by-Step Installation & Setup

#### Step 1: Create Account & Provision VM Instance
1. Sign up at [Oracle Cloud Free Tier](https://cloud.oracle.com). Select region closest to India (e.g., **Mumbai**).
2. Navigate to **Compute** $\rightarrow$ **Instances** $\rightarrow$ **Create Instance**.
3. Configure instance properties:
   - **Name**: `trading-bot`
   - **Image**: Ubuntu 24.04 LTS (Canonical)
   - **Shape**: `VM.Standard.A1.Flex` (ARM) — Set **4 OCPUs** and **24 GB RAM**.
   - **Boot Volume**: 200 GB.
4. Add SSH Key:
   - On Windows PowerShell, generate an SSH key pair:
     ```powershell
     ssh-keygen -t rsa -b 4096 -f ~\.ssh\oracle_key
     ```
   - Upload/paste `oracle_key.pub` content during instance creation.
5. Click **Create** and copy the assigned **Public IP Address**.

#### Step 2: Connect and Prepare System Environment
Open PowerShell on your Windows PC and connect to the VM:
```powershell
ssh -i ~\.ssh\oracle_key ubuntu@<PUBLIC_IP>
```

Run system updates and install required runtime dependencies:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git screen htop
```

#### Step 3: Deployment & Code Setup
Upload project files from Windows PC to VM using SCP:
```powershell
scp -i ~\.ssh\oracle_key -r "G:\Poovendan\AI\Trading\Share\ReadyToDeploy\Prod_code_01\Price_Action_Strategy\*" ubuntu@<PUBLIC_IP>:~/trading/
```

Or clone via Git on the VM:
```bash
git clone <your-repository-url> ~/trading
```

Install Python package dependencies:
```bash
cd ~/trading
pip3 install -r requirements.txt
```

#### Step 4: Generate Zerodha Kite Access Token
Run the token generator utility inside your SSH session:
```bash
cd ~/trading
python3 Kite_Access_Token_gen.py
```
Copy the generated login URL into your local browser, log in to Zerodha, and paste the redirect URL back into the SSH prompt to create `input/kite_access_token.txt`.

#### Step 5: Run Services via GNU `screen`
Using `screen` allows trading engines to run persistently in the background after closing SSH:

```bash
# 1. Start Index Options Trade Engine
screen -S index_trade
cd ~/trading && python3 bull_index_trade_engine.py
# Press Ctrl+A, then D to detach

# 2. Start Stock Scanner & Executor
screen -S stock_scanner
cd ~/trading && python3 bull_nifty50_scanner_executor.py
# Press Ctrl+A, then D to detach

# 3. Start Web Control Center Dashboard
screen -S dashboard
cd ~/trading && python3 app.py
# Press Ctrl+A, then D to detach
```

#### Step 6: Access Dashboard Remotely

**Method A: Secure SSH Tunneling (Recommended)**
On your Windows PC PowerShell:
```powershell
ssh -i ~\.ssh\oracle_key -L 5050:localhost:5050 ubuntu@<PUBLIC_IP>
```
Open browser at: `http://localhost:5050`

**Method B: Direct Public Access**
On VM, allow port 5050 through firewall:
```bash
sudo ufw allow 5050/tcp
```
In Oracle Cloud Console $\rightarrow$ VCN $\rightarrow$ Security Lists $\rightarrow$ Add Ingress Rule for TCP Port `5050`. Access via `http://<PUBLIC_IP>:5050`.

---

### 7.3 Linux Maintenance & Monitoring Commands

| Operational Task | Linux Command |
|---|---|
| List running screen sessions | `screen -ls` |
| Reattach to dashboard session | `screen -r dashboard` |
| Detach active screen | Press `Ctrl+A` then `D` |
| Terminate screen session | `screen -XS index_trade quit` |
| Stream live index engine logs | `tail -f ~/trading/output/logs/index_trade_engine.log` |
| Stream live stock scanner logs | `tail -f ~/trading/output/logs/nifty50_scanner.log` |
| View trade journal entries | `cat ~/trading/output/monitor/trade_journal.csv` |
| Check system memory usage | `free -h` |
| Check disk space | `df -h` |

---

## 8. Command Line Interface (CLI) Quick Reference

```bash
# ---------------------------------------------------------
# 1. Trading Control Center Dashboard (Flask App)
# ---------------------------------------------------------
python app.py                                               # Start dashboard on port 5050

# ---------------------------------------------------------
# 2. Index Options Trade Engine
# ---------------------------------------------------------
python bull_index_trade_engine.py                          # Live mode (reads _backtest from config)
python bull_index_trade_engine.py --date=2026-07-10        # Single-day backtest execution
python bull_index_trade_engine.py --backtest-range=2026-06-15,2026-07-10 # Multi-day historical backtest
python bull_index_trade_engine.py --anchor-only            # Execute anchor scan (A-formation detection only)

# ---------------------------------------------------------
# 3. Nifty 50 Stock Scanner & Executor
# ---------------------------------------------------------
python bull_nifty50_scanner_executor.py                    # Live scanning and execution mode
python bull_nifty50_scanner_executor.py --date=2026-07-10  # Single-day backtest mode
python bull_nifty50_scanner_executor.py --backtest-range=2026-06-15,2026-07-10 # Multi-day historical backtest
python bull_nifty50_scanner_executor.py --anchor-only      # Execute anchor scan only

# ---------------------------------------------------------
# 4. Daily Scanner Export
# ---------------------------------------------------------
python bull_nifty50_daily_scanner_export.py                # Run daily scan & export Excel to output/exports/
python bull_nifty50_daily_scanner_export.py --anchor-only  # Run daily anchor scan & export Excel

# ---------------------------------------------------------
# 5. Utilities
# ---------------------------------------------------------
python Kite_Access_Token_gen.py                            # Interactive token generation
python launcher.py                                         # Launcher helper script
```

---

## 9. Recent Refactoring & System Changelog

1. **Decoupled API Credentials**: Removed hardcoded credentials from `app.py`. All engines read `api_key` and `api_secret` dynamically from `input/program_config.json`.
2. **Cycle Batching & Staging**: Refactored `bull_index_trade_engine.py` and `bull_nifty50_scanner_executor.py`. Setup results are staged to `output/monitor/cycle_trades.json` and deduplicated against `output/monitor/executed_patterns.json`. Best trade selected based on maximum profit target ($T3 - \text{entry}$).
3. **Kite API Lookback Corrections**: Aligned engine lookback maps with official Zerodha Kite API limits (`3minute: 100d`, `15minute: 200d`, `60minute: 400d`, `day: 2000d`).
4. **Anchor Subprocess Handling**: Fixed double-trigger issue in dashboard anchor scan API. `api_anchor_scan()` now exclusively delegates to `--anchor-only` subprocesses.
5. **Kite Position Field Fix**: Fixed position recovery field name across `app.py` and engines (`net_quantity` corrected to `quantity`).
6. **Multi-day Backtest for Nifty 50**: Extended `--backtest-range=START,END` flag support to `bull_nifty50_scanner_executor.py`, enabling historical multi-day backtesting identical to the Index Engine.

---

## 10. Known Issues & Future Technical Roadmap

1. **Single-day Backtest DB Cleanup**: Running `--date=YYYY-MM-DD` single-day backtests writes trade records with status `"ACTIVE"` into `trades_db.json` without updating status post-simulation. *Fix*: Update backtest routine to skip `create_trade()` or automatically close simulation records.
2. **`ACTIVE_POSITIONS` Dictionary Keying**: `ACTIVE_POSITIONS` is keyed by symbol string (e.g. `BANKNIFTY`). Keying by unique trade ID will support multiple concurrent option positions per symbol.
3. **Dashboard Backtest Scope**: The dashboard backtest toggle currently targets the Index Engine subprocess; can be expanded to toggle all engines simultaneously.
