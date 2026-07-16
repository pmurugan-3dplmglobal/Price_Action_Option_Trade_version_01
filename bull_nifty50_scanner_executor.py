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
TIMEFRAME_ANCHOR = "30minute"
BACKTEST_DATE = None

ACTIVE_POSITIONS = {}
position_lock = threading.Lock()
NFO_INSTRUMENTS = pd.DataFrame()
instruments_lock = threading.Lock()
ANCHOR_SCAN_REQUEST_FILE = os.path.join("output", "monitor", "anchor_scan_request.txt")
ANCHOR_SCAN_STOP_FILE = os.path.join("output", "monitor", "anchor_scan_stop.txt")
LIVE_EXECUTION_FLAG = os.path.join("input", "nifty50_live.flag")
SCAN_DISPLAY_FILE = os.path.join("output", "monitor", "scan_display_data.json")
SL_TARGET_OVERRIDES_FILE = os.path.join("output", "monitor", "sl_target_overrides.json")

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

def resolve_option_strikes(symbol, spot_price, step_size, option_type, n_range):
    with instruments_lock:
        if NFO_INSTRUMENTS.empty:
            return []
    atm = int(round(spot_price / step_size) * step_size)
    out = []
    seen = set()
    for offset in range(-n_range, n_range + 1):
        strike = atm + offset * step_size
        if strike in seen:
            continue
        seen.add(strike)
        try:
            df = NFO_INSTRUMENTS[
                (NFO_INSTRUMENTS['name'] == symbol.strip().upper()) &
                (NFO_INSTRUMENTS['instrument_type'] == option_type.upper()) &
                (NFO_INSTRUMENTS['strike'] == float(strike))
            ].copy()
            if df.empty:
                continue
            df = df.sort_values(by='expiry')
            c = df.iloc[0]
            out.append({"strike": strike, "token": int(c['instrument_token']), "tradingsymbol": c['tradingsymbol']})
        except Exception as e:
            logging.error(f"Strike resolution error for {symbol} {option_type} @ {strike}: {e}")
            continue
    return out

def fetch_option_data(kite, token, from_date, to_date, primary_tf, fallback_tf, min_candles=5):
    df = pd.DataFrame(kite.historical_data(token, from_date, to_date, primary_tf))
    if len(df) >= min_candles:
        return df
    df = pd.DataFrame(kite.historical_data(token, from_date, to_date, fallback_tf))
    if len(df) >= min_candles:
        logging.info(f"Fallback to {fallback_tf} for token {token} (only {len(df)} candles on {primary_tf})")
    return df

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

def _derive_sl_targets_for_symbol(kite, symbol, entry_price):
    """Run ABC reversal + anchor scanners on a single symbol to derive SL/T1/T2/T3.
    Returns {SL, T1, T2, T3, pattern} or None."""
    try:
        config = STOCK_REGISTRY.get(symbol)
        if not config:
            return None
        ref_now = dt.now()
        max_days = 200
        from_d = (ref_now - timedelta(days=min(LOOKBACK_DAYS, max_days))).strftime("%Y-%m-%d")
        to_d = ref_now.strftime("%Y-%m-%d")
        spot_quote = kite.ltp([config["token"]])
        current_spot = float(list(spot_quote.values())[0]["last_price"])
        step = config["strike_step"]
        atm = int(round(current_spot / step) * step)
        ce_opts = resolve_option_strikes(symbol, current_spot, step, "CE", 0)
        pe_opts = resolve_option_strikes(symbol, current_spot, step, "PE", 0)
        ce_map = {c["strike"]: c for c in ce_opts}
        pe_map = {p["strike"]: p for p in pe_opts}
        for strike in sorted(set(ce_map) & set(pe_map)):
            ce, pe = ce_map[strike], pe_map[strike]
            for side, opt in [("CE", ce), ("PE", pe)]:
                df_e = pd.DataFrame(kite.historical_data(opt["token"], from_d, to_d, TIMEFRAME_ENTRY))
                df_a = pd.DataFrame(kite.historical_data(opt["token"], from_d, to_d, TIMEFRAME_ANCHOR))
                if len(df_e) < 5 or len(df_a) < 5:
                    continue
                result = scan_abc_reversal(df_e, df_a)
                if result:
                    return {"SL": result["SL"], "T1": result["T1"], "T2": result["T2"], "T3": result["T3"], "pattern": result["Pattern"], "side": side, "strike": strike}
                anchor_scanners = [find_anchor_bullish_engulfing, find_anchor_ll_sweep, find_anchor_hammer_baby, find_anchor_bullish_harami]
                for scanner in anchor_scanners:
                    res = scanner(df_a)
                    if res:
                        t1, t2, t3 = find_profit_targets(df_a, entry_price)
                        if t1:
                            return {"SL": res["SL"], "T1": t1, "T2": t2, "T3": t3, "pattern": res["Pattern"], "side": side, "strike": strike}
        return None
    except Exception as e:
        logging.warning(f"SL/Target derivation failed for {symbol}: {e}")
        return None

def reconcile_positions(kite):
    """Cross-reference ACTIVE_POSITIONS against Kite open positions.
    - Remove stale entries not in Kite and not in DB as ACTIVE
    - Derive SL/Targets for positions that have none
    - Mark carry_forward flag"""
    today = dt.now().strftime("%Y-%m-%d")
    kite_symbols = set()
    try:
        kite_pos = kite.positions()
        for plist in [kite_pos.get("day", []), kite_pos.get("net", [])]:
            for p in plist:
                sym = next((s for s in STOCK_REGISTRY if s in p.get("tradingsymbol", "")), None)
                if sym and abs(int(p.get("quantity", 0))) > 0:
                    kite_symbols.add(sym)
    except Exception as e:
        logging.warning(f"Kite position fetch for reconciliation failed: {e}")
    db_active = {t["symbol"] for t in trade_db.get_active_trades("nifty50") if t.get("symbol") in STOCK_REGISTRY}
    with position_lock:
        stale = [s for s in ACTIVE_POSITIONS if s not in kite_symbols and s not in db_active]
        for s in stale:
            pos = ACTIVE_POSITIONS[s]
            tid = pos.get("trade_id")
            logging.info(f"[RECONCILE] Removing stale position: {s}")
            if tid:
                trade_db.remove_trades([tid])
            ACTIVE_POSITIONS.pop(s, None)
        for s, pos in list(ACTIVE_POSITIONS.items()):
            now_str = dt.now().isoformat()
            if "entry_time" not in pos:
                pos["entry_time"] = now_str
            entry_date = pos["entry_time"][:10] if isinstance(pos["entry_time"], str) else today
            pos["carry_forward"] = entry_date < today
            if (pos.get("current_sl") or 0) == 0 or (pos.get("t1") or 0) == 0:
                db_found = False
                contract = pos.get("contract", "")
                if contract:
                    all_trades = trade_db.get_all_trades("nifty50")
                    for t in all_trades:
                        if t.get("contract") == contract and t.get("current_sl") and t.get("t1"):
                            pos["current_sl"] = t["current_sl"]
                            pos["t1"] = t["t1"]
                            pos["t2"] = t.get("t2")
                            pos["t3"] = t.get("t3")
                            pos["pattern"] = t.get("pattern", pos.get("pattern", "DB_RECOVERED"))
                            db_found = True
                            logging.info(f"[RECONCILE] Restored SL/Targets for {s} from DB: SL={pos['current_sl']} T1={pos['t1']}")
                            tid = pos.get("trade_id")
                            if tid:
                                trade_db.update_trade(tid, {"current_sl": pos["current_sl"], "t1": pos["t1"], "t2": pos["t2"], "t3": pos["t3"]})
                            break
                if not db_found:
                    config = STOCK_REGISTRY.get(s)
                    if config:
                        result = _derive_sl_targets_for_symbol(kite, s, pos.get("entry_spot", 0))
                        if result:
                            pos["current_sl"] = result["SL"]
                            pos["t1"] = result["T1"]
                            pos["t2"] = result["T2"]
                            pos["t3"] = result["T3"]
                            pos["pattern"] = result.get("pattern", pos.get("pattern", "DERIVED"))
                            pos["side"] = result.get("side", pos.get("side", "CE"))
                            pos["strike"] = result.get("strike", pos.get("strike", 0))
                            tid = pos.get("trade_id")
                            if tid:
                                trade_db.update_trade(tid, {"current_sl": result["SL"], "t1": result["T1"], "t2": result["T2"], "t3": result["T3"], "pattern": pos["pattern"]})
                            logging.info(f"[RECONCILE] Derived SL/Targets for {s}: SL={result['SL']} T1={result['T1']} T2={result['T2']} T3={result['T3']}")
                        else:
                            logging.info(f"[RECONCILE] No pattern match for {s}, leaving as passive tracking")
        save_state()

# ──────────────────────────────────────────────
#  SCAN CYCLE — RUNS EVERY N SECONDS
# ──────────────────────────────────────────────

def _process_stock(kite, symbol, config, from_entry, to_entry, from_anchor, to_anchor, entry_scanners, anchor_scanners):
    """Process a single stock: resolve option strikes, fetch option data, run scanners."""
    try:
        spot_quote = kite.ltp([config["token"]])
        current_spot = float(list(spot_quote.values())[0]["last_price"])
    except Exception:
        try:
            df_spot = pd.DataFrame(kite.historical_data(config["token"], from_entry, to_entry, TIMEFRAME_ENTRY))
            if df_spot.empty:
                return []
            current_spot = float(df_spot.iloc[-1]['close'])
        except Exception as e:
            logging.warning(f"Spot data failed for {symbol}: {e}")
            return []

    ce_list = resolve_option_strikes(symbol, current_spot, config['strike_step'], "CE", STRIKE_RANGE)
    pe_list = resolve_option_strikes(symbol, current_spot, config['strike_step'], "PE", STRIKE_RANGE)
    ce_map = {c["strike"]: c for c in ce_list}
    pe_map = {p["strike"]: p for p in pe_list}

    trades = []
    for strike in sorted(set(ce_map) & set(pe_map)):
        ce = ce_map[strike]
        pe = pe_map[strike]

        dfs = {}
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                tasks = {
                    pool.submit(kite.historical_data, ce["token"], from_entry, to_entry, TIMEFRAME_ENTRY): ("ce", "entry"),
                    pool.submit(kite.historical_data, pe["token"], from_entry, to_entry, TIMEFRAME_ENTRY): ("pe", "entry"),
                    pool.submit(kite.historical_data, ce["token"], from_anchor, to_anchor, TIMEFRAME_ANCHOR): ("ce", "anchor"),
                    pool.submit(kite.historical_data, pe["token"], from_anchor, to_anchor, TIMEFRAME_ANCHOR): ("pe", "anchor"),
                }
                for f in as_completed(tasks):
                    tag, kind = tasks[f]
                    try:
                        dfs[(tag, kind)] = pd.DataFrame(f.result())
                    except Exception as e:
                        logging.warning(f"{tag} {kind} failed for {symbol} {strike}: {e}")
                        dfs[(tag, kind)] = pd.DataFrame()
        except Exception as e:
            logging.warning(f"Contract data failed for {symbol} {strike}: {e}")
            continue

        for tag_key, kind_key, from_d, to_d in [
            ("ce", "entry", from_entry, to_entry),
            ("pe", "entry", from_entry, to_entry),
            ("ce", "anchor", from_anchor, to_anchor),
            ("pe", "anchor", from_anchor, to_anchor),
        ]:
            df = dfs.get((tag_key, kind_key), pd.DataFrame())
            if len(df) < 5:
                tok = ce["token"] if tag_key == "ce" else pe["token"]
                dfs[(tag_key, kind_key)] = fetch_option_data(kite, tok, from_d, to_d,
                    TIMEFRAME_ENTRY if kind_key == "entry" else TIMEFRAME_ANCHOR,
                    TIMEFRAME_ENTRY if kind_key == "entry" else TIMEFRAME_ANCHOR)

        df_ce_e = dfs.get(("ce", "entry"), pd.DataFrame())
        df_pe_e = dfs.get(("pe", "entry"), pd.DataFrame())
        df_ce_a = dfs.get(("ce", "anchor"), pd.DataFrame())
        df_pe_a = dfs.get(("pe", "anchor"), pd.DataFrame())
        if df_ce_e.empty or df_pe_e.empty:
            continue

        matched = False
        for name, scanner in entry_scanners:
            if matched:
                break

            result_ce = scanner(df_ce_e, df_ce_a)
            if result_ce:
                key = f"{symbol}|{result_ce['Pattern']}|CE|{strike}"
                if trade_db.is_pattern_executed("nifty50", key):
                    logging.info(f"CE MATCH already executed (skip): {ce['tradingsymbol']} | {result_ce['Pattern']}")
                    matched = True
                    break
                pos_size = calculate_position_size(current_spot, result_ce["SL"])
                logging.info(f"CYCLE MATCH staged: {ce['tradingsymbol']} | {result_ce['Pattern']} | CE | Strike {strike} | Size: {pos_size} | Entry: {result_ce['Close']:.2f} | SL: {result_ce['SL']:.2f} | T1: {result_ce['T1']} | T2: {result_ce['T2']} | T3: {result_ce['T3']} | RR: {result_ce.get('RR', '')}")
                trade_data = {
                    "symbol": symbol, "contract": ce['tradingsymbol'], "option_token": ce['token'],
                    "index_token": config["token"], "strike": strike, "entry_spot": result_ce["Close"],
                    "current_sl": result_ce["SL"], "t1": result_ce["T1"], "t2": result_ce["T2"],
                    "t3": result_ce["T3"], "rr": result_ce.get("RR"), "trailing_stage": 0,
                    "lot_size": config["lot_size"], "position_size": pos_size,
                    "pattern": result_ce["Pattern"], "timeframe": TIMEFRAME_ENTRY, "side": "CE",
                    "strike_step": config["strike_step"]
                }
                trade_db.stage_cycle_trade("nifty50", trade_data)
                trades.append(trade_data)
                log_to_journal(ce['tradingsymbol'], result_ce['Pattern'], TIMEFRAME_ENTRY,
                               "SCAN_MATCH", "STAGED", f"Side=CE Strike={strike} RR={result_ce.get('RR','')}",
                               entry=result_ce['Close'], sl=result_ce['SL'], target=result_ce.get('T3',''), rr=result_ce.get('RR',''))
                matched = True
                break

            result_pe = scanner(df_pe_e, df_pe_a)
            if result_pe:
                key = f"{symbol}|{result_pe['Pattern']}|PE|{strike}"
                if trade_db.is_pattern_executed("nifty50", key):
                    logging.info(f"PE MATCH already executed (skip): {pe['tradingsymbol']} | {result_pe['Pattern']}")
                    matched = True
                    break
                pos_size = calculate_position_size(current_spot, result_pe["SL"])
                logging.info(f"CYCLE MATCH staged: {pe['tradingsymbol']} | {result_pe['Pattern']} | PE | Strike {strike} | Size: {pos_size} | Entry: {result_pe['Close']:.2f} | SL: {result_pe['SL']:.2f} | T1: {result_pe['T1']} | T2: {result_pe['T2']} | T3: {result_pe['T3']} | RR: {result_pe.get('RR', '')}")
                trade_data = {
                    "symbol": symbol, "contract": pe['tradingsymbol'], "option_token": pe['token'],
                    "index_token": config["token"], "strike": strike, "entry_spot": result_pe["Close"],
                    "current_sl": result_pe["SL"], "t1": result_pe["T1"], "t2": result_pe["T2"],
                    "t3": result_pe["T3"], "rr": result_pe.get("RR"), "trailing_stage": 0,
                    "lot_size": config["lot_size"], "position_size": pos_size,
                    "pattern": result_pe["Pattern"], "timeframe": TIMEFRAME_ENTRY, "side": "PE",
                    "strike_step": config["strike_step"]
                }
                trade_db.stage_cycle_trade("nifty50", trade_data)
                trades.append(trade_data)
                log_to_journal(pe['tradingsymbol'], result_pe['Pattern'], TIMEFRAME_ENTRY,
                               "SCAN_MATCH", "STAGED", f"Side=PE Strike={strike} RR={result_pe.get('RR','')}",
                               entry=result_pe['Close'], sl=result_pe['SL'], target=result_pe.get('T3',''), rr=result_pe.get('RR',''))
                matched = True
                break

        for name, scanner in anchor_scanners:
            res_ce = scanner(df_ce_a) if not df_ce_a.empty else None
            if res_ce:
                logging.info(f"ANCHOR FORMED: {ce['tradingsymbol']} | {res_ce['Pattern']} | Close: {res_ce['Close']:.2f} | SL: {res_ce['SL']:.2f}")
                continue
            res_pe = scanner(df_pe_a) if not df_pe_a.empty else None
            if res_pe:
                logging.info(f"ANCHOR FORMED: {pe['tradingsymbol']} | {res_pe['Pattern']} | Close: {res_pe['Close']:.2f} | SL: {res_pe['SL']:.2f}")

    return trades


def run_scan_cycle(kite):
    target_date = BACKTEST_DATE
    if target_date is None:
        ref_now = dt.now()
    else:
        ref_now = target_date
    limits = {"minute": 60, "3minute": 100, "5minute": 100, "10minute": 100, "15minute": 200, "30minute": 200, "60minute": 400, "day": 2000}
    max_days_entry = limits.get(TIMEFRAME_ENTRY, 180)
    max_days_anchor = limits.get(TIMEFRAME_ANCHOR, 180)
    from_entry = (ref_now - timedelta(days=min(LOOKBACK_DAYS, max_days_entry))).strftime("%Y-%m-%d")
    to_entry = ref_now.strftime("%Y-%m-%d")
    from_anchor = (ref_now - timedelta(days=min(LOOKBACK_DAYS, max_days_anchor))).strftime("%Y-%m-%d")
    to_anchor = ref_now.strftime("%Y-%m-%d")

    entry_scanners = [
        ("Setup_1", scan_abc_reversal),
    ]
    anchor_scanners = [
        ("A1", find_anchor_bullish_engulfing),
        ("A2", find_anchor_ll_sweep),
        ("A3", find_anchor_hammer_baby),
        ("A4", find_anchor_bullish_harami),
    ]

    scan_order = SUPER_STOCKS + [s for s in STOCK_REGISTRY if s not in SUPER_STOCKS]
    temp_stored_trades = []

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {}
        for symbol in scan_order:
            config = STOCK_REGISTRY[symbol]
            with position_lock:
                if symbol in ACTIVE_POSITIONS:
                    continue
            futures[pool.submit(_process_stock, kite, symbol, config,
                from_entry, to_entry, from_anchor, to_anchor,
                entry_scanners, anchor_scanners)] = symbol

        for f in as_completed(futures):
            symbol = futures[f]
            try:
                result = f.result()
                if result:
                    temp_stored_trades.extend(result)
            except Exception as e:
                logging.error(f"Error processing {symbol}: {e}")

    if not temp_stored_trades:
        logging.info("No new trades meet criteria this cycle.")
    return temp_stored_trades

def _avg_target_rank(trade):
    targets = [t for t in [trade.get("t1"), trade.get("t2"), trade.get("t3")] if t]
    if not targets:
        return 0
    avg_target = sum(targets) / len(targets)
    risk = trade.get("entry_spot", 0) - trade.get("current_sl", 0)
    if risk <= 0:
        return 0
    return (avg_target - trade["entry_spot"]) / risk

def execute_highest_rr_trade(kite, staged):
    """After a scan cycle, pick best by avg RR and execute (if live)."""
    if not staged:
        return
    best = max(staged, key=_avg_target_rank)
    sym = best["symbol"]
    side = best.get("side", "CE")
    strike = best.get("strike", "")
    key = f"{sym}|{best['pattern']}|{side}|{strike}"
    if trade_db.is_pattern_executed("nifty50", key):
        logging.info(f"Best cycle trade {key} already executed; skipping")
        return
    cp = best["entry_spot"]
    strike_step = best.get("strike_step", 50)
    pos_size = calculate_position_size(cp, best["current_sl"])
    target_strike = strike if strike else int(round(cp / strike_step) * strike_step)
    opt_type = "CE" if side == "CE" else "PE"
    contract = resolve_option_contract(sym, cp, strike_step, opt_type, target_strike)
    if not contract:
        logging.error(f"Could not resolve option for {sym}")
        return
    live_ok = LIVE_MARKET_DEPLOYMENT and _live_execution_enabled()
    if live_ok:
        pos = {
            "contract": contract, "entry_spot": cp, "current_sl": best["current_sl"],
            "t1": best["t1"], "t2": best["t2"], "t3": best["t3"],
            "trailing_stage": 0, "lot_size": best["lot_size"], "position_size": pos_size,
            "pattern": best["pattern"], "timeframe": TIMEFRAME_ENTRY,
            "side": opt_type, "strike": target_strike,
            "entry_time": dt.now().isoformat()
        }
        pos["trade_id"] = trade_db.create_trade("nifty50", sym, {k: v for k, v in pos.items() if k != "trade_id"})
        ACTIVE_POSITIONS[sym] = pos
        save_state()
    avg_rr = round(_avg_target_rank(best), 2)
    if live_ok:
        try:
            q = kite.quote(f"{kite.EXCHANGE_NFO}:{contract}")
            ltp = q[f"{kite.EXCHANGE_NFO}:{contract}"]["last_price"]
            ask = q[f"{kite.EXCHANGE_NFO}:{contract}"]["depth"]["sell"][0]["price"]
            price = round((ask if ask > 0 else ltp) * 1.005, 1)
            qty = best["lot_size"] * pos_size
            oid = kite.place_order(
                variety=kite.VARIETY_REGULAR, tradingsymbol=contract,
                exchange=kite.EXCHANGE_NFO, transaction_type=kite.TRANSACTION_TYPE_BUY,
                quantity=qty, order_type=kite.ORDER_TYPE_LIMIT, price=price,
                product=kite.PRODUCT_NRML
            )
            log_to_journal(sym, best["pattern"], TIMEFRAME_ENTRY, "BUY", "SUCCESS",
                           f"Order: {oid}, Qty: {qty}, {opt_type}@{target_strike}", entry=cp, sl=best["current_sl"], target=best["t1"], rr=avg_rr)
        except Exception as e:
            log_to_journal(sym, best["pattern"], TIMEFRAME_ENTRY, "BUY", "FAILED", str(e),
                           entry=cp, sl=best["current_sl"], target=best["t1"])
            with position_lock:
                ACTIVE_POSITIONS.pop(sym, None)
            save_state()
            return
    elif BACKTEST_DATE is not None:
        log_to_journal(sym, best["pattern"], TIMEFRAME_ENTRY, "BACKTEST_BEST", "SUCCESS",
                       f"Contract: {contract}, Size: {pos_size}, {opt_type}@{target_strike}", entry=cp, sl=best["current_sl"], target=best["t1"])
        sim = simulate_trade_outcome(kite, best, BACKTEST_DATE)
        if sim["result"]:
            log_to_journal(sym, best["pattern"], TIMEFRAME_ENTRY,
                           sim["result"], "COMPLETED", sim["detail"],
                           entry=cp, sl=best["current_sl"], target=best.get("t1",""), rr=avg_rr)
            logging.info(f"[BACKTEST] Trade outcome: {sim['result']} | {sim['detail']} | P&L: {sim['pnl_pct']}%")
    else:
        log_to_journal(sym, best["pattern"], TIMEFRAME_ENTRY, "SCAN_READY", "SUCCESS",
                       f"Contract: {contract}, Size: {pos_size}, {opt_type}@{target_strike} | Manual entry pending", entry=cp, sl=best["current_sl"], target=best["t1"])
        logging.info(f"SCAN_READY best trade: {sym} {contract} | Entry: {cp} | SL: {best['current_sl']} | T1: {best.get('t1','')}")
        targets = [t for t in [best.get("t1"), best.get("t2"), best.get("t3")] if t]
        avg_target = sum(targets) / len(targets) if targets else 0
        logging.info(f"SCAN_READY best cycle trade: {sym} | {best['pattern']} | avg-target={avg_target:.2f} | avg-RR={avg_rr}")
        return
    trade_db.record_executed_pattern("nifty50", key, {"contract": contract, "entry": cp})
    targets = [t for t in [best.get("t1"), best.get("t2"), best.get("t3")] if t]
    avg_target = sum(targets) / len(targets) if targets else 0
    logging.info(f"EXECUTED best cycle trade: {sym} | {best['pattern']} | avg-target={avg_target:.2f} | avg-RR={avg_rr}")

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
    batch_size = 2
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
#  DISPLAY DATA WRITER + KITE SYNC
# ──────────────────────────────────────────────

def _live_execution_enabled():
    return os.path.exists(LIVE_EXECUTION_FLAG)

def _calc_rr(entry, sl, t1, t2):
    if entry is None or sl is None or t1 is None:
        return 0
    risk = entry - sl
    if risk <= 0:
        return 0
    targets = [t1]
    if t2 is not None:
        targets.append(t2)
    return sum((t - entry) / risk for t in targets) / len(targets)

def write_scan_display_data(staged, active):
    try:
        now_str = dt.now().strftime("%Y-%m-%d %H:%M:%S")
        today = dt.now().strftime("%Y-%m-%d")
        def build_trade(t, result, entry_time, exit_time):
            entry = t.get("entry_spot")
            sl = t.get("current_sl")
            t1 = t.get("t1")
            t2 = t.get("t2")
            rr = _calc_rr(entry, sl, t1, t2)
            return {
                "symbol": t.get("symbol", ""),
                "contract": t.get("contract", ""),
                "side": t.get("side", ""),
                "entry_spot": entry,
                "current_sl": sl,
                "t1": t1,
                "t2": t2,
                "t3": t.get("t3"),
                "pattern": t.get("pattern", ""),
                "entry_time": entry_time,
                "exit_time": exit_time,
                "result": result,
                "carry_forward": False,
                "rr": round(rr, 2)
            }
        staged_list = [build_trade(t, "SCAN_READY", now_str, None) for t in (staged or [])]
        carry_fwd = []
        active_live = []
        for s, p in active.items():
            t = p.copy()
            t["symbol"] = s
            et = p.get("entry_time", now_str)
            entry_date = et[:10] if isinstance(et, str) else today
            cf = entry_date < today
            entry_time_display = et if isinstance(et, str) else now_str
            trade = build_trade(t, "ACTIVE", entry_time_display, None)
            trade["carry_forward"] = cf
            if cf:
                carry_fwd.append(trade)
            else:
                active_live.append(trade)
        data = {
            "date": today,
            "timestamp": now_str,
            "staged_trades": staged_list,
            "carry_forward": carry_fwd,
            "active_live": active_live
        }
        os.makedirs(os.path.dirname(SCAN_DISPLAY_FILE), exist_ok=True)
        with open(SCAN_DISPLAY_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logging.error(f"Display data write failed: {e}")

def _sync_kite_positions(kite):
    try:
        kite_pos = kite.positions()
        for plist in [kite_pos.get("day", []), kite_pos.get("net", [])]:
            for p in plist:
                sym = next((s for s in STOCK_REGISTRY if s in p.get("tradingsymbol", "")), None)
                if not sym:
                    continue
                nq = abs(int(p.get("quantity", 0)))
                if nq == 0:
                    continue
                with position_lock:
                    if sym in ACTIVE_POSITIONS:
                        continue
                contract = p["tradingsymbol"]
                entry = float(p.get("net_price", 0))
                with position_lock:
                    ACTIVE_POSITIONS[sym] = {
                        "contract": contract, "entry_spot": entry,
                        "current_sl": 0, "t1": 0, "t2": 0, "t3": 0,
                        "trailing_stage": 0,
                        "lot_size": STOCK_REGISTRY[sym]["lot_size"],
                        "position_size": nq // STOCK_REGISTRY[sym]["lot_size"],
                        "pattern": "MANUAL_ENTRY",
                        "timeframe": TIMEFRAME_ENTRY, "side": "CE",
                        "entry_time": dt.now().isoformat()
                    }
                tid = trade_db.create_trade("nifty50", sym, {"contract": contract, "entry_spot": entry, "entry_time": dt.now().isoformat()})
                with position_lock:
                    ACTIVE_POSITIONS[sym]["trade_id"] = tid
                logging.info(f"[KITE_SYNC] New manual position: {contract} entry={entry}")
    except Exception as e:
        logging.warning(f"Kite position sync failed: {e}")

# ──────────────────────────────────────────────
#  MAIN LOOP — SCAN CYCLE + ANCHOR POLL
# ──────────────────────────────────────────────

def main_scan_loop(kite):
    _sync_counter = 0
    while True:
        try:
            if _live_execution_enabled() and not is_market_hours():
                time.sleep(600)
                continue
            _sync_counter += 1
            if _sync_counter % 5 == 0 and not BACKTEST_DATE:
                _sync_kite_positions(kite)
            if os.path.exists(SL_TARGET_OVERRIDES_FILE):
                try:
                    with open(SL_TARGET_OVERRIDES_FILE) as f:
                        overrides = json.load(f)
                    eng_overrides = overrides.get("nifty50", {})
                    if eng_overrides:
                        with position_lock:
                            for sym, vals in eng_overrides.items():
                                if sym not in ACTIVE_POSITIONS:
                                    continue
                                pos = ACTIVE_POSITIONS[sym]
                                changed = False
                                for key in ("current_sl", "t1"):
                                    if key in vals:
                                        pos[key] = vals[key]
                                        changed = True
                                if changed:
                                    tid = pos.get("trade_id")
                                    if tid:
                                        trade_db.update_trade(tid, {"current_sl": pos["current_sl"], "t1": pos["t1"]})
                                    logging.info(f"[OVERRIDE] Applied SL/T1 for {sym}: SL={pos['current_sl']} T1={pos['t1']}")
                            save_state()
                    os.remove(SL_TARGET_OVERRIDES_FILE)
                except Exception as e:
                    logging.warning(f"Override apply failed: {e}")
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
            if staged:
                execute_highest_rr_trade(kite, staged)
            else:
                logging.info("[CYCLE] No trades staged this cycle.")
            trade_db.clear_cycle_trades("nifty50")
            with position_lock:
                write_scan_display_data(staged or [], dict(ACTIVE_POSITIONS))
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
            if "timeframe_entry" in cfg:
                globals().update({"TIMEFRAME_ENTRY": cfg["timeframe_entry"]})
            elif "timeframe" in cfg:
                globals().update({"TIMEFRAME_ENTRY": cfg["timeframe"]})
            if "timeframe_anchor" in cfg:
                globals().update({"TIMEFRAME_ANCHOR": cfg["timeframe_anchor"]})
            elif "timeframe" in cfg:
                globals().update({"TIMEFRAME_ANCHOR": cfg["timeframe"]})
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

def simulate_trade_outcome(kite, trade, target_date):
    try:
        sym = trade["symbol"]
        cp = trade["entry_spot"]
        side = trade.get("side", "CE")
        target_strike = trade.get("strike")
        strike_step = trade.get("strike_step", 50)
        if not target_strike:
            target_strike = int(round(cp / strike_step) * strike_step)
        opt_type = "CE" if side == "CE" else "PE"
        contract = resolve_option_contract(sym, cp, strike_step, opt_type, target_strike)
        if not contract:
            return {"result": None, "detail": "option_resolve_failed", "entry_time": None, "exit_time": None, "pnl_pct": None}
        token = _resolve_option_token(contract)
        if not token:
            return {"result": None, "detail": "option_token_not_found", "entry_time": None, "exit_time": None, "pnl_pct": None}
        entry = cp
        sl_val = trade["current_sl"]
        t1 = trade.get("t1")
        t2 = trade.get("t2")
        t3 = trade.get("t3")
        expiry_limit = target_date + timedelta(days=14)
        tf = TIMEFRAME_ENTRY
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
            return {"result": None, "detail": "no_data", "entry_time": None, "exit_time": None, "pnl_pct": None}
        entry_idx = None
        best_diff = float('inf')
        for i in range(len(df)):
            cclose = float(df.iloc[i]['close'])
            diff = abs(cclose - entry)
            if diff < best_diff:
                best_diff = diff
                entry_idx = i
        if entry_idx is None:
            return {"result": None, "detail": "entry_candle_not_found", "entry_time": None, "exit_time": None, "pnl_pct": None}
        if entry_idx >= len(df) - 1:
            return {"result": None, "detail": "no_subsequent_candles", "entry_time": None, "exit_time": None, "pnl_pct": None}
        entry_time = df.iloc[entry_idx]['date']
        for i in range(entry_idx + 1, len(df)):
            candle = df.iloc[i]
            low = float(candle['low'])
            high = float(candle['high'])
            if low <= sl_val:
                exit_time = candle['date']
                pnl = (sl_val - entry) / entry * 100
                return {"result": "SL_HIT", "detail": f"SL_HIT at {exit_time}", "entry_time": entry_time, "exit_time": exit_time, "pnl_pct": round(pnl, 2)}
            if t1 and high >= t1:
                exit_t = candle['date']
                if t3 and high >= t3:
                    pnl = (t3 - entry) / entry * 100
                    return {"result": "T3_HIT", "detail": f"T3_HIT at {exit_t}", "entry_time": entry_time, "exit_time": exit_t, "pnl_pct": round(pnl, 2)}
                if t2 and high >= t2:
                    pnl = (t2 - entry) / entry * 100
                    return {"result": "T2_HIT", "detail": f"T2_HIT at {exit_t}", "entry_time": entry_time, "exit_time": exit_t, "pnl_pct": round(pnl, 2)}
                pnl = (t1 - entry) / entry * 100
                return {"result": "T1_HIT", "detail": f"T1_HIT at {exit_t}", "entry_time": entry_time, "exit_time": exit_t, "pnl_pct": round(pnl, 2)}
        return {"result": "NO_EXIT", "detail": "No SL or target hit before expiry", "entry_time": entry_time, "exit_time": None, "pnl_pct": None}
    except Exception as e:
        logging.error(f"[SIM] Exception: {e}")
        return {"result": None, "detail": str(e), "entry_time": None, "exit_time": None, "pnl_pct": None}

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
            if staged:
                results["days_with_trades"] += 1
                results["total_trades"] += 1
                best = max(staged, key=_avg_target_rank)
                sym = best["symbol"]
                if sym not in results["by_symbol"]:
                    results["by_symbol"][sym] = {"trades": 0, "wins": 0, "losses": 0, "no_exits": 0}
                results["by_symbol"][sym]["trades"] += 1
                key = f"{sym}|{best['pattern']}|{best.get('side', 'CE')}|{best.get('strike', '')}"
                if not trade_db.is_pattern_executed("nifty50", key):
                    trade_db.record_executed_pattern("nifty50", key, {"entry": best["entry_spot"]})
                strike_step = best.get("strike_step", 50)
                contract_display = resolve_option_contract(sym, best["entry_spot"], strike_step, best.get("side", "CE"), best.get("strike"))
                if not contract_display:
                    contract_display = sym
                log_to_journal(contract_display, best['pattern'], TIMEFRAME_ENTRY,
                               "BACKTEST_ENTRY", "ENTRY",
                               details=f"Symbol={sym} Strike={best.get('strike','')}",
                               entry=best['entry_spot'], sl=best['current_sl'],
                               target=best.get('t3') or best.get('t1') or "",
                               rr=best.get('rr'))
                sim = simulate_trade_outcome(kite, best, day)
                sim_result = sim["result"]
                exit_action = ""
                pnl = 0.0
                if sim_result == "SL_HIT":
                    exit_action = "EXIT_SL"
                    pnl = sim["pnl_pct"] or 0.0
                    results["losses"] += 1
                    results["by_symbol"][sym]["losses"] += 1
                elif sim_result in ("T1_HIT", "T2_HIT", "T3_HIT"):
                    exit_action = sim_result.replace("_HIT", "")
                    pnl = sim["pnl_pct"] or 0.0
                    results["wins"] += 1
                    results["by_symbol"][sym]["wins"] += 1
                else:
                    exit_action = "EXIT_UNKNOWN"
                    results["no_exits"] += 1
                    results["by_symbol"][sym]["no_exits"] += 1
                if exit_action:
                    log_to_journal(contract_display, best['pattern'], TIMEFRAME_ENTRY,
                                   exit_action, sim_result or "NO_EXIT",
                                   details=f"Symbol={sym} Strike={best.get('strike','')}",
                                   entry=best['entry_spot'], sl=best['current_sl'],
                                   target=best.get('t3') or best.get('t1') or "",
                                   rr=best.get('rr'), pnl_pct=pnl)
                logging.info(f"  Trade: {contract_display} | {best['pattern']} | outcome={sim_result or 'unknown'} | P&L={pnl:.2f}%")
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
            if "entry_time" not in pos:
                pos["entry_time"] = t.get("created_at") or dt.now().isoformat()
            with position_lock:
                ACTIVE_POSITIONS[t["symbol"]] = pos
            logging.info(f"Recovered position: {t['symbol']}")
        try:
            kite_positions = kite.positions()
            for p in kite_positions.get("day", []) + kite_positions.get("net", []):
                if p["exchange"] not in ("NFO", "NSE") or int(p.get("quantity", 0)) == 0:
                    continue
                symbol = next((s for s in STOCK_REGISTRY if s in p["tradingsymbol"]), None)
                if not symbol or symbol in ACTIVE_POSITIONS:
                    continue
                if p["exchange"] == "NFO":
                    nq = abs(int(p.get("quantity", 0)))
                    lots = nq // STOCK_REGISTRY[symbol]["lot_size"]
                    if lots == 0: continue
                    pos = {
                        "contract": p["tradingsymbol"], "entry_spot": float(p.get("net_price", 0)),
                        "current_sl": 0, "t1": 0, "t2": 0, "t3": 0,
                        "trailing_stage": 0, "lot_size": STOCK_REGISTRY[symbol]["lot_size"],
                        "position_size": lots, "pattern": "KITE_RECOVERED",
                        "timeframe": TIMEFRAME_ENTRY,
                        "entry_time": dt.now().isoformat()
                    }
                    pos["trade_id"] = trade_db.create_trade("nifty50", symbol, {k: v for k, v in pos.items() if k != "trade_id"})
                    ACTIVE_POSITIONS[symbol] = pos
                    logging.info(f"Recovered from Kite: {symbol} {p['tradingsymbol']} qty={nq}")
        except Exception as e:
            logging.warning(f"Kite position recovery failed: {e}")
        reconcile_positions(kite)
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
        if staged:
            best = max(staged, key=_avg_target_rank)
            execute_highest_rr_trade(kite, staged)
            with position_lock:
                write_scan_display_data(staged, dict(ACTIVE_POSITIONS))
            logging.info(f"\n{'='*100}")
            logging.info(f"{'TRADE LOG':^100}")
            logging.info(f"{'='*100}")
            hdr = f"{'#':<4} {'Symbol':<14} {'Contract':<24} {'Side':<4} {'Entry':>8} {'SL':>8} {'T1':>8} {'T2':>8} {'T3':>8} {'EntryTime':<24} {'ExitTime':<24} {'Result':<12} {'P&L%':>8}"
            logging.info(hdr)
            logging.info(f"{'-'*100}")
            for idx, t in enumerate(staged, 1):
                sim = simulate_trade_outcome(kite, t, BACKTEST_DATE)
                et = str(sim["entry_time"]) if sim["entry_time"] is not None else "-"
                ext = str(sim["exit_time"]) if sim["exit_time"] is not None else "-"
                r = sim["result"] or "FAIL"
                pnl = sim["pnl_pct"]
                pnl_s = f"{pnl:+.2f}%" if pnl is not None else "-"
                t1v = t.get("t1", "-")
                t2v = t.get("t2", "-")
                t3v = t.get("t3", "-")
                logging.info(f"{idx:<4} {t['symbol']:<14} {t.get('contract',''):<24} {t.get('side',''):<4} {t['entry_spot']:>8.2f} {t['current_sl']:>8.2f} {str(t1v):>8} {str(t2v):>8} {str(t3v):>8} {et:<24} {ext:<24} {r:<12} {pnl_s:>8}")
            logging.info(f"{'='*100}")
            logging.info(f"BEST TRADE: {best['symbol']} {best.get('contract','')} | avg-target RR={_avg_target_rank(best):.2f}")
        else:
            with position_lock:
                write_scan_display_data([], dict(ACTIVE_POSITIONS))
            logging.info("[BACKTEST] No trades staged for this date.")
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
