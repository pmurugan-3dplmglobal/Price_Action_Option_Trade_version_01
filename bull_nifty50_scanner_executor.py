import os
import json
import logging
import time
import threading
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime as dt, timedelta, time as datetime_time
import pandas as pd
import numpy as np

from kiteconnect import KiteConnect
import trade_db

LIVE_MARKET_DEPLOYMENT = False
LOOKBACK_DAYS = 30
INITIAL_CAPITAL = 100000.0
MAX_RISK_PERCENT = 1.0
TOKEN_FILE = "input/kite_access_token.txt"
STATE_FILE = "output/monitor/stock_positions_state.json"
SCAN_INTERVAL_SECONDS = 300
STRIKE_RANGE = 0

TIMEFRAME_ENTRY = "15minute"
TIMEFRAME_ANCHOR = "60minute"
BACKTEST_DATE = None

ACTIVE_POSITIONS = {}
position_lock = threading.Lock()
NFO_INSTRUMENTS = pd.DataFrame()
instruments_lock = threading.Lock()
ANCHOR_SCAN_REQUEST_FILE = os.path.join("output", "monitor", "anchor_scan_request.txt")
ANCHOR_SCAN_STOP_FILE = os.path.join("output", "monitor", "anchor_scan_stop.txt")

journal_lock = threading.Lock()
JOURNAL_FILE = "output/monitor/trade_journal.csv"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("output/logs/bull_nifty50_scanner.log", mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

STOCK_REGISTRY = {
    "ADANIENT": {"token": 112129, "lot_size": 250, "strike_step": 50},
    "ADANIPORTS": {"token": 3861249, "lot_size": 400, "strike_step": 20},
    "APOLLOHOSP": {"token": 415745, "lot_size": 125, "strike_step": 100},
    "ASIANPAINT": {"token": 60417, "lot_size": 200, "strike_step": 20},
    "AXISBANK": {"token": 1510401, "lot_size": 625, "strike_step": 10},
    "BAJAJ-AUTO": {"token": 4267777, "lot_size": 125, "strike_step": 100},
    "BAJAJFINSV": {"token": 4268545, "lot_size": 500, "strike_step": 20},
    "BAJFINANCE": {"token": 81153, "lot_size": 125, "strike_step": 100},
    "BEL": {"token": 54017, "lot_size": 1000, "strike_step": 5},
    "BHARTIARTL": {"token": 2714625, "lot_size": 950, "strike_step": 20},
    "CIPLA": {"token": 177665, "lot_size": 650, "strike_step": 20},
    "COALINDIA": {"token": 5215745, "lot_size": 1250, "strike_step": 10},
    "DRREDDY": {"token": 225537, "lot_size": 125, "strike_step": 100},
    "EICHERMOT": {"token": 232961, "lot_size": 175, "strike_step": 50},
    "GRASIM": {"token": 315393, "lot_size": 400, "strike_step": 20},
    "HCLTECH": {"token": 1837313, "lot_size": 700, "strike_step": 20},
    "HDFCBANK": {"token": 341249, "lot_size": 550, "strike_step": 10},
    "HDFCLIFE": {"token": 119553, "lot_size": 1100, "strike_step": 10},
    "HEROMOTOCO": {"token": 345089, "lot_size": 300, "strike_step": 50},
    "HINDALCO": {"token": 348417, "lot_size": 1400, "strike_step": 10},
    "HINDUNILVR": {"token": 3404801, "lot_size": 300, "strike_step": 20},
    "ICICIBANK": {"token": 1270529, "lot_size": 700, "strike_step": 10},
    "INDIGO": {"token": 2865921, "lot_size": 300, "strike_step": 50},
    "INFY": {"token": 408065, "lot_size": 400, "strike_step": 20},
    "ITC": {"token": 424961, "lot_size": 1600, "strike_step": 5},
    "JIOFIN": {"token": 21806081, "lot_size": 2000, "strike_step": 5},
    "JSWSTEEL": {"token": 3001857, "lot_size": 675, "strike_step": 10},
    "KOTAKBANK": {"token": 492033, "lot_size": 400, "strike_step": 20},
    "LT": {"token": 2939649, "lot_size": 300, "strike_step": 50},
    "M&M": {"token": 519937, "lot_size": 350, "strike_step": 20},
    "MARUTI": {"token": 2800641, "lot_size": 50, "strike_step": 100},
    "NESTLEIND": {"token": 4543233, "lot_size": 400, "strike_step": 20},
    "NTPC": {"token": 2977281, "lot_size": 3000, "strike_step": 5},
    "ONGC": {"token": 633601, "lot_size": 3850, "strike_step": 5},
    "POWERGRID": {"token": 3834113, "lot_size": 3600, "strike_step": 5},
    "RELIANCE": {"token": 738561, "lot_size": 250, "strike_step": 20},
    "SBILIFE": {"token": 5633, "lot_size": 750, "strike_step": 20},
    "SBIN": {"token": 7795201, "lot_size": 1500, "strike_step": 10},
    "SHRIRAMFIN": {"token": 3184129, "lot_size": 300, "strike_step": 20},
    "SUNPHARMA": {"token": 857857, "lot_size": 700, "strike_step": 20},
    "TATACONSUM": {"token": 3465729, "lot_size": 550, "strike_step": 20},
    "TATASTEEL": {"token": 897537, "lot_size": 5500, "strike_step": 2},
    "TCS": {"token": 2953217, "lot_size": 175, "strike_step": 50},
    "TECHM": {"token": 3418369, "lot_size": 600, "strike_step": 20},
    "TITAN": {"token": 895745, "lot_size": 375, "strike_step": 50},
    "TRENT": {"token": 5064961, "lot_size": 150, "strike_step": 100},
    "ULTRACEMCO": {"token": 2952193, "lot_size": 100, "strike_step": 100},
    "WIPRO": {"token": 969473, "lot_size": 1500, "strike_step": 5}
}

SUPER_STOCKS = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY",
    "ITC", "SBIN", "BHARTIARTL", "LT", "WIPRO"
]

def save_state():
    with position_lock:
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(ACTIVE_POSITIONS, f, indent=4)
        except Exception as e:
            logging.error(f"State save failed: {e}")

def load_state():
    global ACTIVE_POSITIONS
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                ACTIVE_POSITIONS = json.load(f)
            logging.info(f"Recovered {len(ACTIVE_POSITIONS)} positions")
        except Exception:
            ACTIVE_POSITIONS = {}

def log_to_journal(symbol, pattern, timeframe, action, status, details="", pnl_pct=0.0, entry="", sl="", target="", rr=""):
    file_exists = os.path.exists(JOURNAL_FILE)
    headers = ["Timestamp", "Symbol", "Pattern", "Timeframe", "Action", "Status", "Entry", "SL", "Target", "RR", "Details", "P&L %"]
    row = [
        dt.now().strftime("%Y-%m-%d %H:%M:%S"),
        symbol, pattern, timeframe, action, status,
        f"{entry:.2f}" if isinstance(entry, (int, float)) and entry else str(entry) if entry else "",
        f"{sl:.2f}" if isinstance(sl, (int, float)) and sl else str(sl) if sl else "",
        f"{target:.2f}" if isinstance(target, (int, float)) and target else str(target) if target else "",
        f"{rr:.2f}" if isinstance(rr, (int, float)) and rr else str(rr) if rr else "",
        details,
        f"{pnl_pct:.2f}%" if pnl_pct != 0.0 else "-"
    ]
    with journal_lock:
        try:
            with open(JOURNAL_FILE, mode="a", newline="", encoding="utf-8") as f:
                w = csv.writer(f, delimiter="\t")
                if not file_exists:
                    w.writerow(headers)
                w.writerow(row)
        except Exception as e:
            logging.error(f"Journal error: {e}")

def load_kite_session():
    if not os.path.exists(TOKEN_FILE):
        raise FileNotFoundError("Token file missing. Run Kite_Access_Token_gen.py first.")
    with open(TOKEN_FILE) as f:
        data = json.load(f)
    if not data.get("api_key") or not data.get("access_token"):
        raise ValueError("Corrupted token file.")
    return data["api_key"], data["access_token"]

def sync_instruments(kite):
    global NFO_INSTRUMENTS
    try:
        instruments = kite.instruments("NSE")
        df = pd.DataFrame(instruments)
        if not df.empty:
            df['tradingsymbol'] = df['tradingsymbol'].str.strip()
            df['segment'] = df['segment'].str.strip()
            synced = 0
            for sym in STOCK_REGISTRY:
                m = df[(df['tradingsymbol'] == sym) & (df['segment'] == 'NSE')]
                if not m.empty:
                    STOCK_REGISTRY[sym]["token"] = int(m.iloc[0]['instrument_token'])
                    synced += 1
            logging.info(f"Synced tokens for {synced} stocks")
        nfo = kite.instruments("NFO")
        with instruments_lock:
            NFO_INSTRUMENTS = pd.DataFrame(nfo)
            if not NFO_INSTRUMENTS.empty:
                NFO_INSTRUMENTS['name'] = NFO_INSTRUMENTS['name'].str.strip().str.upper()
                NFO_INSTRUMENTS['instrument_type'] = NFO_INSTRUMENTS['instrument_type'].str.strip().str.upper()
                logging.info(f"Synced {len(NFO_INSTRUMENTS)} NFO contracts")
    except Exception as e:
        logging.error(f"Instrument sync failed: {e}")

def is_market_hours():
    now = dt.now()
    if now.weekday() in [5, 6]:
        return False
    t = now.time()
    return datetime_time(9, 15) <= t <= datetime_time(15, 30)

# ──────────────────────────────────────────────
#  UTILITY FUNCTIONS
# ──────────────────────────────────────────────

def check_left_side(df, anchor_low, pattern_candle_count, skip_adjacent=2):
    """Verify no candle before the pattern closes below anchor's low."""
    left = df.iloc[:-(pattern_candle_count + skip_adjacent)] if len(df) > pattern_candle_count + skip_adjacent else pd.DataFrame()
    if not left.empty and anchor_low > float(left['close'].min()):
        return False
    return True

def find_profit_targets(df_hist, entry_close):
    """Find T1 (nearest support), T2 (recent high), T3 (breakout high) targets above entry."""
    hist = df_hist.copy()
    t1 = t2 = t3 = None
    for i in range(len(hist) - 3, 2, -1):
        w = hist.iloc[i-2:i+3]
        if len(w) == 5 and hist.iloc[i]['low'] == w['low'].min():
            s = float(hist.iloc[i]['low'])
            sub = hist.iloc[i+1:]
            if not sub.empty and (sub['close'] < s).any() and s > entry_close:
                t1 = s
                break
    if len(hist) > 0:
        ll = hist['low'].idxmin()
        pre = hist.loc[:ll]
        if len(pre) > 0:
            p = float(pre['high'].max())
            if p > entry_close:
                t2 = p
    swing = None
    for i in range(len(hist) - 3, 2, -1):
        w = hist.iloc[i-2:i+3]
        if len(w) == 5 and hist.iloc[i]['high'] == w['high'].max():
            p = float(hist.iloc[i]['high'])
            if p > entry_close:
                swing = p
                break
    for i in range(len(hist) - 1, 2, -1):
        if hist.iloc[i]['close'] < hist.iloc[i]['open'] and (hist.iloc[i]['open'] - hist.iloc[i]['close']) > (hist.iloc[i-1]['high'] - hist.iloc[i-1]['low']):
            p = float(hist.iloc[i]['high'])
            if p > entry_close:
                t3 = p
                break
    if t2 is not None and swing is not None and swing > t2:
        if t3 is None or swing > t3:
            t3 = swing
    if t1 is None or t1 <= entry_close:
        return None, None, None
    if t2 is not None and t2 <= t1:
        t2 = None
    if t3 is not None:
        if t2 is None and t3 <= t1:
            t3 = None
        elif t2 is not None and t3 <= t2:
            t3 = None
    return t1, t2, t3

# ──────────────────────────────────────────────
#  ANCHOR (A-FORMATION) DETECTION — 4 PATTERNS
# ──────────────────────────────────────────────

def find_anchor_bullish_engulfing(df):
    """A = bullish engulfing candle. Bearish candle-1, then bullish candle that wraps its body+wick."""
    if len(df) < 5:
        return None
    bearish_candle, bull_anchor = df.iloc[-4], df.iloc[-3]
    if not (float(bearish_candle['close']) < float(bearish_candle['open'])):
        return None
    if not (float(bull_anchor['close']) > float(bull_anchor['open'])):
        return None
    if not (float(bull_anchor['open']) <= float(bearish_candle['close']) and float(bull_anchor['close']) > float(bearish_candle['high'])):
        return None
    a_low = float(bull_anchor['low'])
    anchor_close = float(bull_anchor['close'])
    return {"Pattern": "BULL_A_ABCD_Engulf", "Close": anchor_close, "SL": a_low + 2, "Signal": "A_Formation"}

def find_anchor_ll_sweep(df):
    """A = Low 2 (second lower low). Sweep candle dips below Low 1, bounce candle recovers."""
    if len(df) < 30:
        return None
    lookback_range = df.iloc[-29:-4]
    low_1 = float(lookback_range['low'].min())
    sweep_candle, bounce_candle, confirm_candle_1, confirm_candle_2 = df.iloc[-4], df.iloc[-3], df.iloc[-2], df.iloc[-1]
    if not (float(sweep_candle['close']) < float(sweep_candle['open'])):
        return None
    sweep_low = float(sweep_candle['low'])
    v1 = (sweep_low < low_1) and (float(sweep_candle['close']) > low_1)
    v2 = (float(sweep_candle['close']) < low_1) and (float(bounce_candle['close']) > low_1)
    if not (v1 or v2):
        return None
    if not (float(bounce_candle['close']) > float(sweep_candle['high'])):
        return None
    if float(confirm_candle_1['close']) < sweep_low or float(confirm_candle_2['close']) < sweep_low:
        return None
    anchor_close = float(bounce_candle['close'])
    return {"Pattern": "BULL_A_LL_Sweep", "Close": anchor_close, "SL": sweep_low + 2, "Signal": "Low2_Formation"}

def find_anchor_hammer_baby(df):
    """A = baby/hammer candle completely inside bearish mother's body, with long lower wick."""
    if len(df) < 5:
        return None
    mother_candle, baby_candle, post_baby_1, post_baby_2, post_baby_3 = df.iloc[-5], df.iloc[-4], df.iloc[-3], df.iloc[-2], df.iloc[-1]
    if not (float(mother_candle['close']) < float(mother_candle['open'])):
        return None
    if not (float(baby_candle['close']) > float(baby_candle['open'])):
        return None
    if not (float(baby_candle['high']) <= float(mother_candle['open']) and float(baby_candle['low']) >= float(mother_candle['close'])):
        return None
    body = float(baby_candle['close']) - float(baby_candle['open'])
    lower_wick = float(baby_candle['open']) - float(baby_candle['low'])
    if lower_wick <= body:
        return None
    if float(post_baby_2['close']) < float(baby_candle['low']) or float(post_baby_3['close']) < float(baby_candle['low']):
        return None
    anchor_close = float(baby_candle['close'])
    return {"Pattern": "BULL_A_Baby_Candle", "Close": anchor_close, "SL": float(baby_candle['low']) + 2, "Signal": "Baby_Formation"}

def find_anchor_bullish_harami(df):
    """A = bullish inside bar (cin) fully inside bearish mother body."""
    if len(df) < 5:
        return None
    bearish_mother, bullish_inside, post_harami_1, post_harami_2, post_harami_3 = df.iloc[-5], df.iloc[-4], df.iloc[-3], df.iloc[-2], df.iloc[-1]
    if not (float(bearish_mother['close']) < float(bearish_mother['open']) and float(bullish_inside['close']) > float(bullish_inside['open'])):
        return None
    if not (float(bullish_inside['high']) <= float(bearish_mother['open']) and float(bullish_inside['low']) >= float(bearish_mother['close'])):
        return None
    inside_low = float(bullish_inside['low'])
    if float(post_harami_2['close']) < inside_low or float(post_harami_3['close']) < inside_low:
        return None
    anchor_close = float(bullish_inside['close'])
    return {"Pattern": "BULL_A_Harami", "Close": anchor_close, "SL": inside_low + 2, "Signal": "Harami_Formation"}

# ──────────────────────────────────────────────
#  ABC REVERSAL SCANNER & POSITION SIZING
# ──────────────────────────────────────────────

def scan_abc_reversal(df_entry, df_anchor):
    if len(df_entry) < 5 or len(df_anchor) < 5:
        return None
    d_idx = len(df_entry) - 1
    d = df_entry.iloc[d_idx]
    max_lookback = min(len(df_entry) - 1, 30)
    for lookback in range(1, max_lookback + 1):
        a_idx = d_idx - lookback
        a = df_entry.iloc[a_idx]
        benchmark = float(a['high'])
        invalidation = float(a['low'])
        if not (float(d['close']) > benchmark):
            continue
        between = df_entry.iloc[a_idx + 1 : d_idx]
        if not between.empty and float(between['close'].min()) < invalidation:
            continue
        if between.empty or float(between['close'].max()) <= benchmark:
            continue
        retest_ok = False
        for j in range(len(between)):
            c_row = between.iloc[j]
            if float(c_row['low']) <= benchmark and float(c_row['close']) > invalidation:
                retest_ok = True
                break
            if float(c_row['low']) <= invalidation and float(c_row['close']) > invalidation and float(c_row['close']) < float(a['open']):
                retest_ok = True
                break
        if not retest_ok:
            continue
        close_price = float(d['close'])
        t1, t2, t3 = find_profit_targets(df_anchor, close_price)
        if t1 is None:
            continue
        risk = close_price - invalidation
        if risk <= 0 or risk < close_price * 0.002 or ((t1 - close_price) / risk) < 1.88:
            continue
        rr = (t1 - close_price) / risk if risk > 0 else 0
        return {"Pattern": "BULL_ABC_Reversal", "SL": invalidation, "T1": t1, "T2": t2, "T3": t3, "Close": close_price, "RR": round(rr, 2)}
    return None

def calculate_position_size(price, sl):
    risk_unit = abs(price - sl)
    if risk_unit <= 0:
        return 0
    max_risk = INITIAL_CAPITAL * (MAX_RISK_PERCENT / 100.0)
    return max(int(max_risk / risk_unit), 1)

# ──────────────────────────────────────────────
#  OPTION CONTRACT RESOLUTION
# ──────────────────────────────────────────────

def resolve_option_contract(symbol, spot, step, opt_type, target_strike=None):
    with instruments_lock:
        if NFO_INSTRUMENTS.empty:
            s = target_strike or int(round(spot / step) * step)
            return f"{symbol}{dt.now().strftime('%y%b').upper()}{s}{opt_type}"
        try:
            m = NFO_INSTRUMENTS[
                (NFO_INSTRUMENTS['name'] == symbol.strip().upper()) &
                (NFO_INSTRUMENTS['instrument_type'] == opt_type.upper())
            ].copy()
            if m.empty:
                return None
            m['strike'] = m['strike'].astype(float)
            target = target_strike or round(spot / step) * step
            sub = m[m['strike'] == float(target)]
            if sub.empty:
                idx = (m['strike'] - spot).abs().idxmin()
                sel = m.loc[idx]
            else:
                sub = sub.sort_values(by='expiry')
                sel = sub.iloc[0]
            return str(sel['tradingsymbol'])
        except Exception as e:
            logging.error(f"Option resolve error for {symbol}: {e}")
            s = target_strike or int(round(spot / step) * step)
            return f"{symbol}{dt.now().strftime('%y%b').upper()}{s}{opt_type}"

# ──────────────────────────────────────────────
#  EXECUTION FUNCTIONS
# ──────────────────────────────────────────────

def close_position(kite, pos):
    if not LIVE_MARKET_DEPLOYMENT:
        logging.info(f"[BACKTEST EXIT] {pos['contract']}")
        return
    try:
        q = kite.quote(f"{kite.EXCHANGE_NFO}:{pos['contract']}")
        ltp = q[f"{kite.EXCHANGE_NFO}:{pos['contract']}"]["last_price"]
        bid = q[f"{kite.EXCHANGE_NFO}:{pos['contract']}"]["depth"]["buy"][0]["price"]
        price = round((bid if bid > 0 else ltp) * 0.995, 1)
        kite.place_order(
            variety=kite.VARIETY_REGULAR, tradingsymbol=pos["contract"],
            exchange=kite.EXCHANGE_NFO, transaction_type=kite.TRANSACTION_TYPE_SELL,
            quantity=pos["lot_size"] * pos.get("position_size", 1), order_type=kite.ORDER_TYPE_LIMIT,
            price=price, product=kite.PRODUCT_NRML
        )
    except Exception as e:
        logging.error(f"Exit failed for {pos['contract']}: {e}")

def find_best_setup_by_rr(setups):
    """Pick the trade setup with the highest risk-reward ratio."""
    if not setups:
        return None
    ranked = sorted(setups, key=lambda x: x["RR"], reverse=True)
    best = ranked[0]
    logging.info(f"\n=== BEST TRADE ===")
    logging.info(f"{best['Symbol']} | {best['Pattern']}")
    logging.info(f"Entry: {best['Close']:.2f} | SL: {best['SL']:.2f}")
    logging.info(f"T1: {best['T1']:.2f} | T2: {best['T2']:.2f} | T3: {best['T3']:.2f}")
    logging.info(f"R:R = {best['RR']:.2f}")
    logging.info(f"==================\n")
    return best

# ──────────────────────────────────────────────
#  SCAN CYCLE — RUNS EVERY N SECONDS
# ──────────────────────────────────────────────

def run_scan_cycle(kite):
    target_date = BACKTEST_DATE
    if target_date is None:
        ref_now = dt.now()
    else:
        ref_now = target_date
    limits = {"minute": 60, "3minute": 100, "5minute": 100, "10minute": 100, "15minute": 200, "30minute": 200, "60minute": 400, "day": 2000}
    max_days = limits.get(TIMEFRAME_ENTRY, 180)
    from_date = (ref_now - timedelta(days=min(LOOKBACK_DAYS, max_days))).strftime("%Y-%m-%d")
    to_date = ref_now.strftime("%Y-%m-%d")
    entry_scanners = [
        ("S1_ABC", scan_abc_reversal),
    ]
    all_setups = []
    staged = []
    staged_keys = set()
    scan_order = SUPER_STOCKS + [s for s in STOCK_REGISTRY if s not in SUPER_STOCKS]
    with ThreadPoolExecutor(max_workers=10) as pool:
        fetch_tasks = {}
        for symbol in scan_order:
            config = STOCK_REGISTRY[symbol]
            with position_lock:
                if symbol in ACTIVE_POSITIONS:
                    continue
            fetch_tasks[pool.submit(lambda cfg=config: pd.DataFrame(
                kite.historical_data(cfg["token"], from_date, to_date, TIMEFRAME_ENTRY)
            ))] = symbol
        for f in as_completed(fetch_tasks):
            symbol = fetch_tasks[f]
            config = STOCK_REGISTRY[symbol]
            try:
                df = f.result()
            except Exception as e:
                logging.warning(f"Data failed for {symbol}: {e}")
                continue
            if df.empty:
                continue
            for name, scanner in entry_scanners:
                result = scanner(df, df)
                if result:
                    result["Symbol"] = symbol
                    result["Config"] = config
                    result["Side"] = "CE"
                    step = config.get("strike_step", 50)
                    result["Strike"] = int(round(result["Close"] / step) * step)
                    key = f"{symbol}|{result['Pattern']}|{result['Side']}|{result['Strike']}"
                    if trade_db.is_pattern_executed("nifty50", key):
                        logging.info(f"MATCH already executed (skip): {symbol} | {result['Pattern']} | {result['Side']} @ {result['Strike']}")
                    elif key in staged_keys:
                        logging.info(f"MATCH already staged this cycle (skip): {symbol} | {result['Pattern']} | {result['Side']} @ {result['Strike']}")
                    else:
                        all_setups.append(result)
                        staged.append(result)
                        staged_keys.add(key)
                        trade_db.stage_cycle_trade("nifty50", result)
                        logging.info(f"CYCLE MATCH staged: {symbol} | {result['Pattern']} | {result['Side']} @ {result['Strike']} | RR={result['RR']:.2f} | Entry: {result['Close']:.2f} | T3: {result['T3']}")
                        log_to_journal(symbol, result['Pattern'], TIMEFRAME_ENTRY,
                                       "SCAN_MATCH", "STAGED",
                                       f"Side={result['Side']} Strike={result['Strike']} RR={result['RR']:.2f}",
                                       entry=result['Close'], sl=result['SL'], target=result.get('T3',''),
                                       rr=result['RR'])
                    break
    if not staged:
        logging.info("No new trades meet criteria this cycle.")
    return staged

def execute_highest_rr_trade(kite, staged):
    """After a scan cycle, if >2 trades were staged, execute the one with max profit."""
    if not staged:
        return
    best = max(staged, key=lambda s: (s.get("T3") or s.get("T1") or 0) - s.get("Close", 0))
    sym = best["Symbol"]
    side = best.get("Side", "CE")
    strike = best.get("Strike", "")
    key = f"{sym}|{best['Pattern']}|{side}|{strike}"
    if trade_db.is_pattern_executed("nifty50", key):
        logging.info(f"Best cycle trade {key} already executed; skipping")
        return
    cfg = best["Config"]
    cp = best["Close"]
    pos_size = calculate_position_size(cp, best["SL"])
    if strike:
        target_strike = strike
    else:
        target_strike = int(round(cp / cfg['strike_step']) * cfg['strike_step'])
    opt_type = "CE" if side == "CE" else "PE"
    contract = resolve_option_contract(sym, cp, cfg['strike_step'], opt_type, target_strike)
    if not contract:
        logging.error(f"Could not resolve option for {sym}")
        return
    pos = {
        "contract": contract, "entry_spot": cp, "current_sl": best["SL"],
        "t1": best["T1"], "t2": best["T2"], "t3": best["T3"],
        "trailing_stage": 0, "lot_size": cfg["lot_size"], "position_size": pos_size,
        "pattern": best["Pattern"], "timeframe": TIMEFRAME_ENTRY,
        "side": opt_type, "strike": target_strike
    }
    pos["trade_id"] = trade_db.create_trade("nifty50", sym, {k: v for k, v in pos.items() if k != "trade_id"})
    ACTIVE_POSITIONS[sym] = pos
    save_state()
    if LIVE_MARKET_DEPLOYMENT:
        try:
            q = kite.quote(f"{kite.EXCHANGE_NFO}:{contract}")
            ltp = q[f"{kite.EXCHANGE_NFO}:{contract}"]["last_price"]
            ask = q[f"{kite.EXCHANGE_NFO}:{contract}"]["depth"]["sell"][0]["price"]
            price = round((ask if ask > 0 else ltp) * 1.005, 1)
            qty = cfg["lot_size"] * pos_size
            oid = kite.place_order(
                variety=kite.VARIETY_REGULAR, tradingsymbol=contract,
                exchange=kite.EXCHANGE_NFO, transaction_type=kite.TRANSACTION_TYPE_BUY,
                quantity=qty, order_type=kite.ORDER_TYPE_LIMIT, price=price,
                product=kite.PRODUCT_NRML
            )
            rr_best = round((best["T1"] - best["Close"]) / (best["Close"] - best["SL"]), 2) if best["Close"] != best["SL"] else 0
            log_to_journal(sym, best["Pattern"], TIMEFRAME_ENTRY, "BUY", "SUCCESS",
                           f"Order: {oid}, Qty: {qty}, {opt_type}@{target_strike}", entry=best["Close"], sl=best["SL"], target=best["T1"], rr=rr_best)
        except Exception as e:
            log_to_journal(sym, best["Pattern"], TIMEFRAME_ENTRY, "BUY", "FAILED", str(e),
                           entry=best["Close"], sl=best["SL"], target=best["T1"])
            with position_lock:
                ACTIVE_POSITIONS.pop(sym, None)
            save_state()
            return
    else:
        log_to_journal(sym, best["Pattern"], TIMEFRAME_ENTRY, "BACKTEST_BEST", "SUCCESS",
                       f"Contract: {contract}, Size: {pos_size}, {opt_type}@{target_strike}", entry=best["Close"], sl=best["SL"], target=best["T1"])
    trade_db.record_executed_pattern("nifty50", key, {"contract": contract, "entry": cp})
    logging.info(f"EXECUTED best cycle trade: {sym} | {best['Pattern']} | max-profit={round((best['T3'] or best['T1'] or 0) - cp, 2)}")

# ──────────────────────────────────────────────
#  ANCHOR SCAN — RUNS ON DEMAND VIA DASHBOARD
# ──────────────────────────────────────────────

def run_anchor_scan(kite):
    limits = {"minute": 60, "3minute": 100, "5minute": 100, "10minute": 100, "15minute": 200, "30minute": 200, "60minute": 400, "day": 2000}
    max_days = limits.get(TIMEFRAME_ANCHOR, 180)
    from_date = (dt.now() - timedelta(days=min(LOOKBACK_DAYS, max_days))).strftime("%Y-%m-%d")
    to_date = dt.now().strftime("%Y-%m-%d")
    scanners = [
        ("S1", find_anchor_bullish_engulfing),
        ("S2", find_anchor_ll_sweep),
        ("S3", find_anchor_hammer_baby),
        ("S4", find_anchor_bullish_harami),
    ]
    scan_order = SUPER_STOCKS + [s for s in STOCK_REGISTRY if s not in SUPER_STOCKS]
    batch_size = 5
    for i in range(0, len(scan_order), batch_size):
        if os.path.exists(ANCHOR_SCAN_STOP_FILE):
            logging.info("Anchor scan stopped by user")
            os.remove(ANCHOR_SCAN_STOP_FILE)
            return
        batch = scan_order[i:i+batch_size]
        with ThreadPoolExecutor(max_workers=batch_size) as pool:
            tasks = {}
            for symbol in batch:
                config = STOCK_REGISTRY[symbol]
                with position_lock:
                    if symbol in ACTIVE_POSITIONS:
                        continue
                tasks[pool.submit(lambda cfg=config: pd.DataFrame(
                    kite.historical_data(cfg["token"], from_date, to_date, TIMEFRAME_ANCHOR)
                ))] = symbol
            for f in as_completed(tasks):
                symbol = tasks[f]
                try:
                    df = f.result()
                except Exception as e:
                    logging.warning(f"Anchor data failed for {symbol}: {e}")
                    continue
                if df.empty:
                    continue
            for name, scanner_func in scanners:
                result = scanner_func(df)
                if result:
                    logging.info(f"ANCHOR MATCH: {symbol} | {result['Pattern']} | Close: {result['Close']}")
                    log_to_journal(symbol, result["Pattern"], TIMEFRAME_ANCHOR,
                                   "ANCHOR_SCAN", "SCANNED", "A formation from anchor scan",
                                    entry=result["Close"], sl=result["SL"], target="")
                    break
        time.sleep(1)
    logging.info("Anchor scan complete")

# ──────────────────────────────────────────────
#  POSITION MONITORING — SL, TRAILING, TARGETS
# ──────────────────────────────────────────────

def monitor_active_positions(kite):
    from_date = (dt.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    to_date = dt.now().strftime("%Y-%m-%d")
    to_clear = []
    with position_lock:
        for sym, pos in ACTIVE_POSITIONS.items():
            try:
                df = pd.DataFrame(kite.historical_data(
                    STOCK_REGISTRY[sym]["token"], from_date, to_date, TIMEFRAME_ENTRY))
                if df.empty:
                    continue
                last = df.iloc[-1]
                cp = float(last['close'])
                hp = float(last['high'])
                tid = pos.get("trade_id")
                if cp <= pos["current_sl"]:
                    logging.warning(f"SL: {sym} at {cp}")
                    close_position(kite, pos)
                    pnl = ((cp - pos["entry_spot"]) / pos["entry_spot"]) * 100
                    log_to_journal(sym, pos["pattern"], TIMEFRAME_ENTRY, "EXIT_SL", "CLOSED",
                                   f"SL hit: {cp}", pnl,
                                   entry=pos["entry_spot"], sl=pos["current_sl"], target=pos.get("t1",""))
                    if tid: trade_db.update_trade(tid, {"status": "SL_HIT", "exit_time": dt.now().strftime("%Y-%m-%d %H:%M:%S"), "pnl_percent": round(pnl, 2)})
                    to_clear.append(sym)
                    continue
                mutated = False
                if pos["trailing_stage"] == 0 and pos["t1"] and hp >= pos["t1"]:
                    pos["current_sl"] = pos["entry_spot"]
                    pos["trailing_stage"] = 1
                    mutated = True
                    logging.info(f"TRAIL-1 {sym}: SL=BE ({pos['current_sl']:.2f})")
                    log_to_journal(sym, pos["pattern"], TIMEFRAME_ENTRY, "TRAIL_BE", "MUTATED",
                                   f"SL={pos['current_sl']:.2f}",
                                   entry=pos["entry_spot"], sl=pos["current_sl"], target=pos.get("t1",""))
                    if tid: trade_db.update_trade(tid, {"trailing_stage": 1, "current_sl": pos["current_sl"]})
                elif pos["trailing_stage"] == 1 and pos["t2"] and hp >= pos["t2"]:
                    pos["current_sl"] = pos["t1"]
                    pos["trailing_stage"] = 2
                    mutated = True
                    logging.info(f"TRAIL-2 {sym}: SL=T1 ({pos['current_sl']:.2f})")
                    log_to_journal(sym, pos["pattern"], TIMEFRAME_ENTRY, "TRAIL_T1", "MUTATED",
                                   f"SL={pos['current_sl']:.2f}",
                                   entry=pos["entry_spot"], sl=pos["current_sl"], target=pos.get("t2",""))
                    if tid: trade_db.update_trade(tid, {"trailing_stage": 2, "current_sl": pos["current_sl"]})
                if pos["t3"] and hp >= pos["t3"]:
                    logging.info(f"T3: {sym} at {pos['t3']}")
                    close_position(kite, pos)
                    pnl = ((pos["t3"] - pos["entry_spot"]) / pos["entry_spot"]) * 100
                    log_to_journal(sym, pos["pattern"], TIMEFRAME_ENTRY, "EXIT_T3", "CLOSED",
                                   f"T3={pos['t3']}", pnl,
                                   entry=pos["entry_spot"], sl=pos.get("current_sl",""), target=pos["t3"])
                    if tid: trade_db.update_trade(tid, {"status": "TARGET_HIT", "exit_time": dt.now().strftime("%Y-%m-%d %H:%M:%S"), "pnl_percent": round(pnl, 2)})
                    to_clear.append(sym)
            except Exception as e:
                logging.error(f"Risk error {sym}: {e}")
        for s in to_clear:
            ACTIVE_POSITIONS.pop(s, None)
    if to_clear:
        save_state()

def position_monitor_loop(kite):
    """Background thread that checks stop-loss, trailing, and targets every 60s."""
    while True:
        try:
            monitor_active_positions(kite)
        except Exception as e:
            logging.error(f"Position monitor error: {e}")
        time.sleep(60)

# ──────────────────────────────────────────────
#  MAIN LOOP — SCAN CYCLE + ANCHOR POLL
# ──────────────────────────────────────────────

def main_scan_loop(kite):
    while True:
        try:
            if not is_market_hours() and LIVE_MARKET_DEPLOYMENT:
                time.sleep(600)
                continue
            logging.info("[BEAT] Starting Nifty 50 scan cycle...")
            if os.path.exists(ANCHOR_SCAN_REQUEST_FILE):
                try:
                    with open(ANCHOR_SCAN_REQUEST_FILE) as f:
                        engine = f.read().strip()
                    os.remove(ANCHOR_SCAN_REQUEST_FILE)
                    if engine != "nifty50":
                        logging.info(f"Anchor scan flag not for nifty50, skipping (got {engine})")
                    else:
                        logging.info(f"Anchor scan requested via flag file (engine: {engine})")
                        run_anchor_scan(kite)
                except Exception:
                    pass
            start = time.time()
            staged = run_scan_cycle(kite)
            if staged and len(staged) > 2:
                execute_highest_rr_trade(kite, staged)
            elif staged:
                logging.info(f"[CYCLE] {len(staged)} trade(s) staged; need >2 to execute. No execution this cycle.")
            trade_db.clear_cycle_trades("nifty50")
            elapsed = time.time() - start
            sleep = max(0, SCAN_INTERVAL_SECONDS - elapsed)
            logging.info(f"[BEAT] Cycle done in {elapsed:.2f}s. Sleep {sleep:.0f}s")
            time.sleep(sleep)
        except Exception as e:
            logging.error(f"Main loop error: {e}")
            time.sleep(10)

def load_program_config():
    try:
        cfg_path = os.path.join(os.path.dirname(__file__), "input", "program_config.json")
        if os.path.exists(cfg_path):
            with open(cfg_path) as f:
                full = json.load(f)
            cfg = full.get("nifty50", {})
            if "timeframe" in cfg:
                globals().update({"TIMEFRAME_ENTRY": cfg["timeframe"], "TIMEFRAME_ANCHOR": cfg["timeframe"]})
            if "lookback_days" in cfg: globals().update({"LOOKBACK_DAYS": int(cfg["lookback_days"])})
            if "scan_interval" in cfg: globals().update({"SCAN_INTERVAL_SECONDS": int(cfg["scan_interval"])})
            if "risk_percent" in cfg: globals().update({"MAX_RISK_PERCENT": float(cfg["risk_percent"])})
            if "capital" in cfg: globals().update({"INITIAL_CAPITAL": float(cfg["capital"])})
            if "_backtest" in full: globals().update({"LIVE_MARKET_DEPLOYMENT": not full["_backtest"]})
            if "strike_range" in full: globals().update({"STRIKE_RANGE": int(full["strike_range"])})
    except Exception as e:
        logging.warning(f"Config load: {e}")

def trading_days_between(start, end):
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days

def _resolve_option_token(contract_symbol):
    with instruments_lock:
        if NFO_INSTRUMENTS.empty:
            return None
        m = NFO_INSTRUMENTS[NFO_INSTRUMENTS['tradingsymbol'] == contract_symbol]
        if m.empty:
            return None
        return int(m.iloc[0]['instrument_token'])

def simulate_trade_outcome(kite, best, target_date):
    try:
        sym = best["Symbol"]
        cfg = best["Config"]
        cp = best["Close"]
        side = best.get("Side", "CE")
        target_strike = best.get("Strike")
        if not target_strike:
            target_strike = int(round(cp / cfg['strike_step']) * cfg['strike_step'])
        opt_type = "CE" if side == "CE" else "PE"
        contract = resolve_option_contract(sym, cp, cfg['strike_step'], opt_type, target_strike)
        if not contract:
            return None, "option_resolve_failed"
        token = _resolve_option_token(contract)
        if not token:
            return None, "option_token_not_found"
        entry = cp
        sl_val = best["SL"]
        t1 = best.get("T1")
        t2 = best.get("T2")
        t3 = best.get("T3")
        logging.info(f"[SIM] Simulating {contract} entry={entry} sl={sl_val} t1={t1} t2={t2} t3={t3}")
        expiry_limit = target_date + timedelta(days=14)
        tf = "3minute"
        from_str = target_date.strftime("%Y-%m-%d")
        to_str = expiry_limit.strftime("%Y-%m-%d")
        for attempt in range(3):
            try:
                df = pd.DataFrame(kite.historical_data(token, from_str, to_str, tf))
                break
            except Exception as e:
                if "Too many requests" in str(e) and attempt < 2:
                    time.sleep(5)
                    continue
                raise
        if df.empty:
            logging.info(f"[SIM] No data for token {token} from {from_str} to {to_str}")
            return None, "no_data"
        logging.info(f"[SIM] Fetched {len(df)} {tf} candles for token {token}")
        entry_idx = None
        tolerance = max(abs(entry - sl_val) * 0.3, entry * 0.01, 0.5)
        for i in range(len(df)):
            cclose = float(df.iloc[i]['close'])
            if abs(cclose - entry) < tolerance:
                entry_idx = i
                break
        if entry_idx is None:
            logging.info(f"[SIM] Entry candle not found for price {entry}")
            return None, "entry_candle_not_found"
        if entry_idx >= len(df) - 1:
            logging.info(f"[SIM] No subsequent candles after entry at index {entry_idx} of {len(df)}")
            return None, "no_subsequent_candles"
        logging.info(f"[SIM] Entry at index {entry_idx} ({df.iloc[entry_idx]['date']}), scanning {len(df) - entry_idx - 1} candles forward")
        for i in range(entry_idx + 1, len(df)):
            candle = df.iloc[i]
            low = float(candle['low'])
            high = float(candle['high'])
            if low <= sl_val:
                res = f"SL_HIT at {candle['date']}"
                logging.info(f"[SIM] {res}")
                return "SL_HIT", res
            if t1 and high >= t1:
                if t3 and high >= t3:
                    res = f"T3_HIT at {candle['date']}"
                    logging.info(f"[SIM] {res}")
                    return "T3_HIT", res
                if t2 and high >= t2:
                    res = f"T2_HIT at {candle['date']}"
                    logging.info(f"[SIM] {res}")
                    return "T2_HIT", res
                if high >= t1:
                    res = f"T1_HIT at {candle['date']}"
                    logging.info(f"[SIM] {res}")
                    return "T1_HIT", res
        logging.info(f"[SIM] No SL or target hit")
        return "NO_EXIT", "No SL or target hit before expiry"
    except Exception as e:
        logging.error(f"[SIM] Exception: {e}")
        return None, str(e)

def run_multi_day_backtest(kite, start_date, end_date):
    global BACKTEST_DATE, LIVE_MARKET_DEPLOYMENT
    LIVE_MARKET_DEPLOYMENT = False
    days = trading_days_between(start_date, end_date)
    logging.info(f"Multi-day backtest: {len(days)} trading days from {start_date} to {end_date}")
    results = {"total_days": len(days), "days_with_trades": 0, "total_trades": 0, "wins": 0, "losses": 0, "no_exits": 0, "by_symbol": {}}
    for idx, day in enumerate(days):
        BACKTEST_DATE = day
        logging.info(f"[{idx+1}/{len(days)}] Backtesting {day}...")
        try:
            staged = run_scan_cycle(kite)
            if staged and len(staged) >= 1:
                results["days_with_trades"] += 1
                results["total_trades"] += 1
                best = max(staged, key=lambda s: (s.get("T3") or s.get("T1") or 0) - s.get("Close", 0))
                sym = best["Symbol"]
                if sym not in results["by_symbol"]:
                    results["by_symbol"][sym] = {"trades": 0, "wins": 0, "losses": 0, "no_exits": 0}
                results["by_symbol"][sym]["trades"] += 1
                key = f"{sym}|{best['Pattern']}|{best.get('Side', 'CE')}|{best.get('Strike', '')}"
                if not trade_db.is_pattern_executed("nifty50", key):
                    trade_db.record_executed_pattern("nifty50", key, {"entry": best["Close"]})
                contract_display = resolve_option_contract(sym, best["Close"], best["Config"]["strike_step"], "CE", best.get("Strike"))
                if not contract_display:
                    contract_display = sym
                log_to_journal(contract_display, best['Pattern'], TIMEFRAME_ENTRY,
                               "BACKTEST_ENTRY", "ENTRY",
                               details=f"Symbol={sym} Strike={best.get('Strike','')}",
                               entry=best['Close'], sl=best['SL'],
                               target=best.get('T3') or best.get('T1') or "",
                               rr=best.get('RR'))
                sim_result, _ = simulate_trade_outcome(kite, best, day)
                exit_action = ""
                pnl = 0.0
                if sim_result == "SL_HIT":
                    exit_action = "EXIT_SL"
                    pnl = round(((best['SL'] - best['Close']) / best['Close']) * 100, 2)
                    results["losses"] += 1
                    results["by_symbol"][sym]["losses"] += 1
                elif sim_result == "T1_HIT":
                    exit_action = "EXIT_T3"
                    pnl = round(((best.get('T1', best['Close']) - best['Close']) / best['Close']) * 100, 2)
                    results["wins"] += 1
                    results["by_symbol"][sym]["wins"] += 1
                elif sim_result == "T2_HIT":
                    exit_action = "EXIT_T3"
                    pnl = round(((best.get('T2', best['Close']) - best['Close']) / best['Close']) * 100, 2)
                    results["wins"] += 1
                    results["by_symbol"][sym]["wins"] += 1
                elif sim_result == "T3_HIT":
                    exit_action = "EXIT_T3"
                    pnl = round(((best.get('T3', best['Close']) - best['Close']) / best['Close']) * 100, 2)
                    results["wins"] += 1
                    results["by_symbol"][sym]["wins"] += 1
                else:
                    exit_action = "EXIT_UNKNOWN"
                    results["no_exits"] += 1
                    results["by_symbol"][sym]["no_exits"] += 1
                if exit_action:
                    log_to_journal(contract_display, best['Pattern'], TIMEFRAME_ENTRY,
                                   exit_action, sim_result or "NO_EXIT",
                                   details=f"Symbol={sym} Strike={best.get('Strike','')}",
                                   entry=best['Close'], sl=best['SL'],
                                   target=best.get('T3') or best.get('T1') or "",
                                   rr=best.get('RR'), pnl_pct=pnl)
                logging.info(f"  Trade: {contract_display} | {best['Pattern']} | outcome={sim_result or 'unknown'} | P&L={pnl:.2f}%")
            trade_db.clear_cycle_trades("nifty50")
            time.sleep(3)
        except Exception as e:
            logging.error(f"  Error on {day}: {e}")
            time.sleep(3)
    wr = results["wins"] / (results["wins"] + results["losses"]) * 100 if (results["wins"] + results["losses"]) > 0 else 0
    logging.info(f"\n{'='*60}")
    logging.info(f"BACKTEST RESULTS: {start_date} to {end_date}")
    logging.info(f"{'='*60}")
    logging.info(f"Trading days scanned: {results['total_days']}")
    logging.info(f"Days with trades:     {results['days_with_trades']}")
    logging.info(f"Total trades found:   {results['total_trades']}")
    logging.info(f"Wins:                 {results['wins']}")
    logging.info(f"Losses:               {results['losses']}")
    logging.info(f"No exit:              {results['no_exits']}")
    logging.info(f"Win rate:             {wr:.1f}%")
    for sym, s in sorted(results["by_symbol"].items()):
        swr = s["wins"] / (s["wins"] + s["losses"]) * 100 if (s["wins"] + s["losses"]) > 0 else 0
        logging.info(f"  {sym}: {s['trades']} trades, {s['wins']}W/{s['losses']}L, {swr:.1f}% WR")
    logging.info(f"{'='*60}")
    return results

def main():
    global BACKTEST_DATE, LIVE_MARKET_DEPLOYMENT
    load_program_config()
    anchor_only = "--anchor-only" in sys.argv
    date_arg = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--date=")), None)
    range_arg = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--backtest-range=")), None)
    if date_arg:
        try:
            BACKTEST_DATE = dt.strptime(date_arg, "%Y-%m-%d").date()
        except Exception:
            BACKTEST_DATE = None
            logging.warning(f"Invalid --date value: {date_arg}")
    if not anchor_only and BACKTEST_DATE is None and range_arg is None:
        logging.info("Starting Nifty 50 Stock Scanner + Executor")
    try:
        ak, at = load_kite_session()
        kite = KiteConnect(api_key=ak)
        kite.set_access_token(at)
        load_state()
        active = trade_db.get_active_trades("nifty50")
        for t in active:
            if t["symbol"] not in STOCK_REGISTRY: continue
            pos = {k: v for k, v in t.items() if k not in ("id", "engine", "symbol", "status", "created_at", "updated_at")}
            pos["trade_id"] = t["id"]
            with position_lock:
                ACTIVE_POSITIONS[t["symbol"]] = pos
            logging.info(f"Recovered position: {t['symbol']}")
        try:
            kite_positions = kite.positions()
            for p in kite_positions.get("day", []) + kite_positions.get("net", []):
                if p["exchange"] not in ("NFO", "NSE") or int(p.get("net_quantity", 0)) == 0:
                    continue
                symbol = next((s for s in STOCK_REGISTRY if s in p["tradingsymbol"]), None)
                if not symbol or symbol in ACTIVE_POSITIONS:
                    continue
                if p["exchange"] == "NFO":
                    nq = abs(int(p.get("net_quantity", 0)))
                    lots = nq // STOCK_REGISTRY[symbol]["lot_size"]
                    if lots == 0: continue
                    pos = {
                        "contract": p["tradingsymbol"], "entry_spot": float(p.get("net_price", 0)),
                        "current_sl": 0, "t1": 0, "t2": 0, "t3": 0,
                        "trailing_stage": 0, "lot_size": STOCK_REGISTRY[symbol]["lot_size"],
                        "position_size": lots, "pattern": "KITE_RECOVERED",
                        "timeframe": TIMEFRAME_ENTRY
                    }
                    pos["trade_id"] = trade_db.create_trade("nifty50", symbol, {k: v for k, v in pos.items() if k != "trade_id"})
                    ACTIVE_POSITIONS[symbol] = pos
                    logging.info(f"Recovered from Kite: {symbol} {p['tradingsymbol']} qty={nq}")
        except Exception as e:
            logging.warning(f"Kite position recovery failed: {e}")
        sync_instruments(kite)
        if anchor_only:
            run_anchor_scan(kite)
            return
    except Exception as e:
        logging.error(f"Init: {e}")
        return
    if range_arg:
        LIVE_MARKET_DEPLOYMENT = False
        parts = range_arg.split(",")
        start = dt.strptime(parts[0].strip(), "%Y-%m-%d").date()
        end = dt.strptime(parts[1].strip(), "%Y-%m-%d").date()
        run_multi_day_backtest(kite, start, end)
        return
    if BACKTEST_DATE is not None:
        LIVE_MARKET_DEPLOYMENT = False
        logging.info(f"Backtest run for date {BACKTEST_DATE} (dry, no real orders)...")
        staged = run_scan_cycle(kite)
        if staged and len(staged) > 2:
            execute_highest_rr_trade(kite, staged)
        else:
            logging.info(f"[BACKTEST] {len(staged) if staged else 0} trade(s) staged; need >2 to execute.")
        trade_db.clear_cycle_trades("nifty50")
        return
    if not LIVE_MARKET_DEPLOYMENT:
        logging.error("Config has _backtest=true but no --date= or --backtest-range= flag. "
                      "Use --date=YYYY-MM-DD or --backtest-range=START,END to run backtest. Exiting.")
        return
    logging.info(f"TF: {TIMEFRAME_ENTRY} | Interval: {SCAN_INTERVAL_SECONDS}s | Risk: {MAX_RISK_PERCENT}%")
    t1 = threading.Thread(target=position_monitor_loop, args=(kite,), daemon=True)
    t1.start()
    t2 = threading.Thread(target=main_scan_loop, args=(kite,), daemon=True)
    t2.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Engine stopped.")

if __name__ == "__main__":
    main()
