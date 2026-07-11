import os
import json
import logging
import time
import threading
import sys
import csv
from datetime import datetime as dt, timedelta, time as datetime_time
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import numpy as np

from kiteconnect import KiteConnect
import trade_db

LIVE_MARKET_DEPLOYMENT = False
LOOKBACK_DAYS = 30
INITIAL_CAPITAL = 100000.0
MAX_RISK_PERCENT = 1.0
TOKEN_FILE = "input/kite_access_token.txt"
SCAN_INTERVAL_SECONDS = 15

TIMEFRAME_ENTRY = "3minute"
TIMEFRAME_ANCHOR = "15minute"
TIMEFRAME_FALLBACK = "3minute"
STRIKE_RANGE = 3
BACKTEST_DATE = None

ACTIVE_POSITIONS = {}
position_lock = threading.Lock()
instrument_dump = None
ANCHOR_SCAN_REQUEST_FILE = os.path.join("output", "monitor", "anchor_scan_request.txt")
ANCHOR_SCAN_STOP_FILE = os.path.join("output", "monitor", "anchor_scan_stop.txt")

journal_lock = threading.Lock()
JOURNAL_FILE = "output/monitor/trade_journal.csv"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("output/logs/bull_index_trade_engine.log", mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

INDEX_REGISTRY = {
    "NIFTY": {"token": 256265, "lot_size": 65, "strike_step": 50, "tradingsymbol": "NIFTY 50"},
    "BANKNIFTY": {"token": 260105, "lot_size": 30, "strike_step": 100, "tradingsymbol": "NIFTY BANK"}
}

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
                writer = csv.writer(f, delimiter="\t")
                if not file_exists:
                    writer.writerow(headers)
                writer.writerow(row)
        except Exception as e:
            logging.error(f"Journal write failed: {e}")

def load_kite_session():
    if not os.path.exists(TOKEN_FILE):
        raise FileNotFoundError("Token file missing. Run Kite_Access_Token_gen.py first.")
    with open(TOKEN_FILE) as f:
        data = json.load(f)
    if not data.get("api_key") or not data.get("access_token"):
        raise ValueError("Corrupted token file.")
    return data["api_key"], data["access_token"]

def is_market_hours():
    now = dt.now()
    if now.weekday() in [5, 6]:
        return False
    t = now.time()
    return datetime_time(9, 15) <= t <= datetime_time(15, 30)

def fetch_option_data(kite, token, from_date, to_date, primary_tf, fallback_tf, min_candles=5):
    df = pd.DataFrame(kite.historical_data(token, from_date, to_date, primary_tf))
    if len(df) >= min_candles:
        return df
    df = pd.DataFrame(kite.historical_data(token, from_date, to_date, fallback_tf))
    if len(df) >= min_candles:
        logging.info(f"Fallback to {fallback_tf} for token {token} (only {len(df)} candles on {primary_tf})")
    return df

def fetch_instruments(kite):
    global instrument_dump
    try:
        logging.info("Syncing NFO instruments...")
        instruments = kite.instruments("NFO")
        instrument_dump = pd.DataFrame(instruments)
        logging.info(f"Synced {len(instrument_dump)} NFO contracts.")
    except Exception as e:
        logging.error(f"Instrument sync failed: {e}")
        raise

def get_weekly_expiry(target_weekday=1):
    now = dt.now()
    days_ahead = (target_weekday - now.weekday()) % 7
    if days_ahead == 0 and now.hour >= 15:
        days_ahead = 7
    return (now + timedelta(days=days_ahead)).date()

def resolve_option_contract(base_symbol, spot_price, step_size, option_type):
    global instrument_dump
    if instrument_dump is None or instrument_dump.empty:
        return None
    strike = int(round(spot_price / step_size) * step_size)
    target_expiry = get_weekly_expiry()
    try:
        df = instrument_dump[
            (instrument_dump['name'] == base_symbol) &
            (instrument_dump['instrument_type'] == option_type) &
            (instrument_dump['strike'] == strike)
        ].copy()
        if df.empty:
            return None
        df['expiry'] = pd.to_datetime(df['expiry']).dt.date
        weekly = df[df['expiry'] == target_expiry].sort_values(by='expiry')
        if not weekly.empty:
            c = weekly.iloc[0]
            return {"token": int(c['instrument_token']), "tradingsymbol": c['tradingsymbol']}
        df = df[df['expiry'] >= dt.now().date()].sort_values(by='expiry')
        if df.empty:
            return None
        c = df.iloc[0]
        return {"token": int(c['instrument_token']), "tradingsymbol": c['tradingsymbol']}
    except Exception as e:
        logging.error(f"Contract resolution error: {e}")
        return None

def resolve_option_strikes(base_symbol, spot_price, step_size, option_type, n_range=0):
    """Return ATM strike plus n_range strikes ITM/OTM (weekly expiry)."""
    global instrument_dump
    if instrument_dump is None or instrument_dump.empty:
        return []
    atm = int(round(spot_price / step_size) * step_size)
    target_expiry = get_weekly_expiry()
    out = []
    seen = set()
    for offset in range(-n_range, n_range + 1):
        strike = atm + offset * step_size
        if strike in seen:
            continue
        seen.add(strike)
        try:
            df = instrument_dump[
                (instrument_dump['name'] == base_symbol) &
                (instrument_dump['instrument_type'] == option_type) &
                (instrument_dump['strike'] == strike)
            ].copy()
            if df.empty:
                continue
            df['expiry'] = pd.to_datetime(df['expiry']).dt.date
            weekly = df[df['expiry'] == target_expiry].sort_values(by='expiry')
            if not weekly.empty:
                c = weekly.iloc[0]
                out.append({"strike": strike, "token": int(c['instrument_token']), "tradingsymbol": c['tradingsymbol']})
                continue
            df = df[df['expiry'] >= dt.now().date()].sort_values(by='expiry')
            if df.empty:
                continue
            c = df.iloc[0]
            out.append({"strike": strike, "token": int(c['instrument_token']), "tradingsymbol": c['tradingsymbol']})
        except Exception as e:
            logging.error(f"Strike resolution error: {e}")
            continue
    return out

# ──────────────────────────────────────────────
#  UTILITY FUNCTIONS
# ──────────────────────────────────────────────

def check_left_side_rule(df, anchor_low, setup_count, skip_adjacent=2):
    """Verify no candle before the pattern closes below anchor's low."""
    left = df.iloc[:-(setup_count + skip_adjacent)] if len(df) > setup_count + skip_adjacent else pd.DataFrame()
    if not left.empty:
        if anchor_low > float(left['close'].min()):
            return False
    return True

def find_profit_targets(df_hist, entry_close):
    """Find T1 (nearest support), T2 (recent high), T3 (breakout high) targets above entry."""
    hist = df_hist.copy()
    t1 = t2 = t3 = None
    for i in range(len(hist) - 3, 2, -1):
        w = hist.iloc[i-2:i+3]
        if len(w) == 5 and hist.iloc[i]['low'] == w['low'].min():
            support = float(hist.iloc[i]['low'])
            sub = hist.iloc[i+1:]
            if not sub.empty and (sub['close'] < support).any():
                if support > entry_close:
                    t1 = support
                break
    if len(hist) > 0:
        ll_idx = hist['low'].idxmin()
        pre = hist.loc[:ll_idx]
        if len(pre) > 0:
            pt2 = float(pre['high'].max())
            if pt2 > entry_close:
                t2 = pt2
    swing_t3 = None
    for i in range(len(hist) - 3, 2, -1):
        w = hist.iloc[i-2:i+3]
        if len(w) == 5 and hist.iloc[i]['high'] == w['high'].max():
            p = float(hist.iloc[i]['high'])
            if p > entry_close:
                swing_t3 = p
                break
    for i in range(len(hist) - 1, 2, -1):
        if hist.iloc[i]['close'] < hist.iloc[i]['open'] and (hist.iloc[i]['open'] - hist.iloc[i]['close']) > (hist.iloc[i-1]['high'] - hist.iloc[i-1]['low']):
            p = float(hist.iloc[i]['high'])
            if p > entry_close:
                t3 = p
                break
    if t2 is not None and swing_t3 is not None and swing_t3 > t2:
        if t3 is None or swing_t3 > t3:
            t3 = swing_t3
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
#  ABC REVERSAL SCANNER
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

def calculate_position_size(spot_price, stop_loss):
    risk_per_unit = abs(spot_price - stop_loss)
    if risk_per_unit <= 0:
        return 0
    max_risk_amount = INITIAL_CAPITAL * (MAX_RISK_PERCENT / 100.0)
    units = int(max_risk_amount / risk_per_unit)
    return max(units, 1)

# ──────────────────────────────────────────────
#  SCAN CYCLE — RUNS EVERY N SECONDS
# ──────────────────────────────────────────────

def run_scan_cycle(kite):
    target_date = BACKTEST_DATE
    if target_date is None:
        if not is_market_hours() and LIVE_MARKET_DEPLOYMENT:
            return []
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
    temp_stored_trades = []
    for symbol, config in INDEX_REGISTRY.items():
        with position_lock:
            if symbol in ACTIVE_POSITIONS:
                continue
        try:
            spot_quote = kite.ltp([config["token"]])
            current_spot = float(list(spot_quote.values())[0]["last_price"])
        except Exception:
            try:
                df_spot = pd.DataFrame(kite.historical_data(config["token"], from_entry, to_entry, TIMEFRAME_ENTRY))
                if df_spot.empty:
                    continue
                current_spot = float(df_spot.iloc[-1]['close'])
            except Exception as e:
                logging.warning(f"Spot data failed for {symbol}: {e}")
                continue
        ce_list = resolve_option_strikes(symbol, current_spot, config['strike_step'], "CE", STRIKE_RANGE)
        pe_list = resolve_option_strikes(symbol, current_spot, config['strike_step'], "PE", STRIKE_RANGE)
        ce_map = {c["strike"]: c for c in ce_list}
        pe_map = {p["strike"]: p for p in pe_list}
        for strike in sorted(set(ce_map) & set(pe_map)):
            ce = ce_map[strike]
            pe = pe_map[strike]
            dfs = {}
            try:
                with ThreadPoolExecutor(max_workers=4) as pool:
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
                    dfs[(tag_key, kind_key)] = fetch_option_data(kite, tok, from_d, to_d, TIMEFRAME_ENTRY if kind_key == "entry" else TIMEFRAME_ANCHOR, TIMEFRAME_FALLBACK)
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
                    if trade_db.is_pattern_executed("index", key):
                        logging.info(f"CE MATCH already executed (skip): {ce['tradingsymbol']} | {result_ce['Pattern']}")
                        matched = True
                        break
                    pos_size = calculate_position_size(current_spot, result_ce["SL"])
                    rr_str = f"RR: {result_ce['RR']}" if result_ce.get('RR') else ""
                    logging.info(f"CYCLE MATCH staged: {ce['tradingsymbol']} | {result_ce['Pattern']} | CE | Strike {strike} | Size: {pos_size} | Entry: {result_ce['Close']:.2f} | SL: {result_ce['SL']:.2f} | T1: {result_ce['T1']} | T2: {result_ce['T2']} | T3: {result_ce['T3']} | RR: {result_ce.get('RR', '')}")
                    trade_data = {
                        "symbol": symbol,
                        "contract": ce['tradingsymbol'],
                        "option_token": ce['token'],
                        "index_token": config["token"],
                        "strike": strike,
                        "entry_spot": result_ce["Close"],
                        "current_sl": result_ce["SL"],
                        "t1": result_ce["T1"],
                        "t2": result_ce["T2"],
                        "t3": result_ce["T3"],
                        "rr": result_ce.get("RR"),
                        "trailing_stage": 0,
                        "lot_size": config["lot_size"],
                        "position_size": pos_size,
                        "pattern": result_ce["Pattern"],
                        "timeframe": TIMEFRAME_ENTRY,
                        "side": "CE"
                    }
                    trade_db.stage_cycle_trade("index", trade_data)
                    temp_stored_trades.append(trade_data)
                    log_to_journal(ce['tradingsymbol'], result_ce['Pattern'], TIMEFRAME_ENTRY,
                                   "SCAN_MATCH", "STAGED",
                                   f"Side=CE Strike={strike} RR={result_ce.get('RR','')}",
                                   entry=result_ce['Close'], sl=result_ce['SL'],
                                   target=result_ce.get('T3',''), rr=result_ce.get('RR',''))
                    matched = True
                    break
                result_pe = scanner(df_pe_e, df_pe_a)
                if result_pe:
                    key = f"{symbol}|{result_pe['Pattern']}|PE|{strike}"
                    if trade_db.is_pattern_executed("index", key):
                        logging.info(f"PE MATCH already executed (skip): {pe['tradingsymbol']} | {result_pe['Pattern']}")
                        matched = True
                        break
                    pos_size = calculate_position_size(current_spot, result_pe["SL"])
                    logging.info(f"CYCLE MATCH staged: {pe['tradingsymbol']} | {result_pe['Pattern']} | PE | Strike {strike} | Size: {pos_size} | Entry: {result_pe['Close']:.2f} | SL: {result_pe['SL']:.2f} | T1: {result_pe['T1']} | T2: {result_pe['T2']} | T3: {result_pe['T3']} | RR: {result_pe.get('RR', '')}")
                    trade_data = {
                        "symbol": symbol,
                        "contract": pe['tradingsymbol'],
                        "option_token": pe['token'],
                        "index_token": config["token"],
                        "strike": strike,
                        "entry_spot": result_pe["Close"],
                        "current_sl": result_pe["SL"],
                        "t1": result_pe["T1"],
                        "t2": result_pe["T2"],
                        "t3": result_pe["T3"],
                        "rr": result_pe.get("RR"),
                        "trailing_stage": 0,
                        "lot_size": config["lot_size"],
                        "position_size": pos_size,
                        "pattern": result_pe["Pattern"],
                        "timeframe": TIMEFRAME_ENTRY,
                        "side": "PE"
                    }
                    trade_db.stage_cycle_trade("index", trade_data)
                    temp_stored_trades.append(trade_data)
                    log_to_journal(pe['tradingsymbol'], result_pe['Pattern'], TIMEFRAME_ENTRY,
                                   "SCAN_MATCH", "STAGED",
                                   f"Side=PE Strike={strike} RR={result_pe.get('RR','')}",
                                   entry=result_pe['Close'], sl=result_pe['SL'],
                                   target=result_pe.get('T3',''), rr=result_pe.get('RR',''))
                    matched = True
                    break
            # Anchor-formation logging (analysis only, no execution) — one log per setup formed
            for name, scanner in anchor_scanners:
                res_ce = scanner(df_ce_a) if not df_ce_a.empty else None
                if res_ce:
                    logging.info(f"ANCHOR FORMED: {ce['tradingsymbol']} | {res_ce['Pattern']} | Close: {res_ce['Close']:.2f} | SL: {res_ce['SL']:.2f}")
                    continue
                res_pe = scanner(df_pe_a) if not df_pe_a.empty else None
                if res_pe:
                    logging.info(f"ANCHOR FORMED: {pe['tradingsymbol']} | {res_pe['Pattern']} | Close: {res_pe['Close']:.2f} | SL: {res_pe['SL']:.2f}")
    return temp_stored_trades

# ──────────────────────────────────────────────
#  ANCHOR SCAN — RUNS ON DEMAND VIA DASHBOARD
# ──────────────────────────────────────────────

def run_anchor_scan(kite):
    if not is_market_hours() and LIVE_MARKET_DEPLOYMENT:
        return
    limits = {"minute": 60, "3minute": 100, "5minute": 100, "10minute": 100, "15minute": 200, "30minute": 200, "60minute": 400, "day": 2000}
    max_days = limits.get(TIMEFRAME_ANCHOR, 180)
    from_date = (dt.now() - timedelta(days=min(LOOKBACK_DAYS, max_days))).strftime("%Y-%m-%d")
    to_date = dt.now().strftime("%Y-%m-%d")
    scanners = [
        ("Setup_1", find_anchor_bullish_engulfing),
        ("Setup_2", find_anchor_ll_sweep),
        ("Setup_3", find_anchor_hammer_baby),
        ("Setup_4", find_anchor_bullish_harami),
    ]
    for symbol, config in INDEX_REGISTRY.items():
        if os.path.exists(ANCHOR_SCAN_STOP_FILE):
            logging.info("Anchor scan stopped by user")
            os.remove(ANCHOR_SCAN_STOP_FILE)
            return
        with position_lock:
            if symbol in ACTIVE_POSITIONS:
                continue
        try:
            spot_quote = kite.ltp([config["token"]])
            current_spot = float(list(spot_quote.values())[0]["last_price"])
        except Exception:
            try:
                df_spot = pd.DataFrame(kite.historical_data(config["token"], from_date, to_date, TIMEFRAME_ANCHOR))
                if df_spot.empty:
                    continue
                current_spot = float(df_spot.iloc[-1]['close'])
            except Exception as e:
                logging.warning(f"Anchor spot data failed for {symbol}: {e}")
                continue
        ce = resolve_option_contract(symbol, current_spot, config['strike_step'], "CE")
        pe = resolve_option_contract(symbol, current_spot, config['strike_step'], "PE")
        if not ce or not pe:
            logging.warning(f"Anchor: Could not resolve contracts for {symbol}")
            continue
        dfs = {}
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                tasks = {
                    pool.submit(kite.historical_data, ce["token"], from_date, to_date, TIMEFRAME_ANCHOR): "ce",
                    pool.submit(kite.historical_data, pe["token"], from_date, to_date, TIMEFRAME_ANCHOR): "pe",
                }
                for f in as_completed(tasks):
                    key = tasks[f]
                    try:
                        dfs[key] = pd.DataFrame(f.result())
                    except Exception as e:
                        logging.warning(f"Anchor {key} failed for {symbol}: {e}")
                        dfs[key] = pd.DataFrame()
        except Exception as e:
            logging.warning(f"Anchor contract data failed for {symbol}: {e}")
            continue
        df_ce, df_pe = dfs.get("ce", pd.DataFrame()), dfs.get("pe", pd.DataFrame())
        if df_ce.empty or df_pe.empty:
            continue
        for name, scanner in scanners:
            result_ce = scanner(df_ce)
            if result_ce:
                logging.info(f"ANCHOR CE MATCH: {ce['tradingsymbol']} | {result_ce['Pattern']} | Close: {result_ce['Close']}")
                log_to_journal(symbol, result_ce["Pattern"], TIMEFRAME_ANCHOR,
                               "ANCHOR_CE", "SCANNED", "A formation from anchor scan",
                               entry=result_ce["Close"], sl=result_ce["SL"], target="")
                break
            result_pe = scanner(df_pe)
            if result_pe:
                logging.info(f"ANCHOR PE MATCH: {pe['tradingsymbol']} | {result_pe['Pattern']} | Close: {result_pe['Close']}")
                log_to_journal(symbol, result_pe["Pattern"], TIMEFRAME_ANCHOR,
                               "ANCHOR_PE", "SCANNED", "A formation from anchor scan",
                               entry=result_pe["Close"], sl=result_pe["SL"], target="")
                break

# ──────────────────────────────────────────────
#  POSITION MANAGEMENT
# ──────────────────────────────────────────────

def close_position(kite, pos):
    if not LIVE_MARKET_DEPLOYMENT:
        logging.info(f"[BACKTEST EXIT] Closed {pos['contract']}")
        return
    try:
        kite.place_order(
            tradingsymbol=pos["contract"], exchange=kite.EXCHANGE_NFO,
            transaction_type=kite.TRANSACTION_TYPE_SELL, quantity=pos["lot_size"] * pos["position_size"],
            order_type=kite.ORDER_TYPE_MARKET, product=kite.PRODUCT_MIS
        )
    except Exception as e:
        logging.error(f"Exit failed for {pos['contract']}: {e}")

def execute_index_entry(kite, pos):
    if not LIVE_MARKET_DEPLOYMENT:
        logging.info(f"[BACKTEST ENTRY] {pos['contract']} ({pos['side']})")
        return True
    try:
        kite.place_order(
            tradingsymbol=pos["contract"], exchange=kite.EXCHANGE_NFO,
            transaction_type=kite.TRANSACTION_TYPE_BUY, quantity=pos["lot_size"] * pos["position_size"],
            order_type=kite.ORDER_TYPE_MARKET, product=kite.PRODUCT_MIS
        )
        return True
    except Exception as e:
        logging.error(f"Entry failed for {pos['contract']}: {e}")
        return False

def simulate_trade_outcome(kite, best, target_date):
    try:
        token = best["option_token"]
        entry = best["entry_spot"]
        sl_val = best["current_sl"]
        t1 = best.get("t1")
        t2 = best.get("t2")
        t3 = best.get("t3")
        expiry_limit = target_date + timedelta(days=14)
        tf = best.get("timeframe", "15minute") or "15minute"
        logging.info(f"[SIM] Simulating {best['contract']} entry={entry} sl={sl_val} t1={t1} t2={t2} t3={t3} tf={tf}")
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

# ──────────────────────────────────────────────
#  EXECUTION FUNCTIONS
# ──────────────────────────────────────────────

def execute_highest_rr_trade(kite, staged):
    """After a scan cycle, if >2 trades were staged, execute the one with max profit."""
    if not staged:
        return
    best = max(staged, key=lambda t: (t.get("t3") or t.get("t1") or 0) - t.get("entry_spot", 0))
    key = f"{best['symbol']}|{best['pattern']}|{best['side']}|{best.get('strike', '')}"
    if trade_db.is_pattern_executed("index", key):
        logging.info(f"Best cycle trade {key} already executed; skipping")
        return
    pos = best.copy()
    pos["trade_id"] = trade_db.create_trade("index", best["symbol"], {k: v for k, v in pos.items() if k != "trade_id"})
    ACTIVE_POSITIONS[best["symbol"]] = pos
    ok = execute_index_entry(kite, pos)
    if ok:
        trade_db.record_executed_pattern("index", key, {"contract": best["contract"], "entry": best["entry_spot"]})
        profit = round((best.get("t3") or best.get("t1") or 0) - best["entry_spot"], 2)
        rr_best = best.get("rr", "")
        if LIVE_MARKET_DEPLOYMENT:
            log_to_journal(best["symbol"], best["pattern"], best["timeframe"],
                           "BUY_" + best["side"], "SUCCESS", f"Contract: {best['contract']}, Qty: {best['position_size']}",
                           entry=best["entry_spot"], sl=best["current_sl"], target=best.get("t1", ""), rr=rr_best)
        else:
            log_to_journal(best["symbol"], best["pattern"], best["timeframe"],
                           "DRY_" + best["side"], "SUCCESS", f"Contract: {best['contract']}, Size: {best['position_size']}",
                           entry=best["entry_spot"], sl=best["current_sl"], target=best.get("t1", ""), rr=rr_best)
            sim_result, sim_detail = simulate_trade_outcome(kite, best, BACKTEST_DATE)
            if sim_result:
                log_to_journal(best["symbol"], best["pattern"], best["timeframe"],
                               sim_result, "COMPLETED", sim_detail,
                               entry=best["entry_spot"], sl=best["current_sl"], target=best.get("t1", ""), rr=rr_best)
                logging.info(f"[BACKTEST] Trade outcome: {sim_result} | {sim_detail}")
        logging.info(f"EXECUTED best cycle trade: {best['symbol']} {best['side']} | {best['pattern']} | max-profit={profit}")
    else:
        ACTIVE_POSITIONS.pop(best["symbol"], None)
        if pos.get("trade_id"):
            trade_db.update_trade(pos["trade_id"], {"status": "FAILED", "updated_at": dt.now().strftime("%Y-%m-%d %H:%M:%S")})

def monitor_active_positions(kite):
    from_date = (dt.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    to_date = dt.now().strftime("%Y-%m-%d")
    to_clear = []
    with position_lock:
        for symbol, pos in ACTIVE_POSITIONS.items():
            try:
                df = pd.DataFrame(kite.historical_data(pos["option_token"], from_date, to_date, TIMEFRAME_ENTRY))
                if df.empty:
                    continue
                last = df.iloc[-1]
                close_price = float(last['close'])
                high_price = float(last['high'])
                tid = pos.get("trade_id")
                if close_price < pos["current_sl"]:
                    logging.warning(f"SL HIT: {pos['contract']} at {close_price}")
                    close_position(kite, pos)
                    pnl = ((close_price - pos["entry_spot"]) / pos["entry_spot"]) * 100
                    log_to_journal(symbol, pos["pattern"], TIMEFRAME_ENTRY,
                                   "EXIT_SL", "CLOSED", f"SL: {close_price}", pnl,
                                   entry=pos["entry_spot"], sl=pos["current_sl"], target=pos.get("t1",""))
                    if tid: trade_db.update_trade(tid, {"status": "SL_HIT", "exit_time": dt.now().strftime("%Y-%m-%d %H:%M:%S"), "pnl_percent": round(pnl, 2)})
                    to_clear.append(symbol)
                    continue
                if pos["trailing_stage"] == 0 and pos["t1"] is not None and high_price >= pos["t1"]:
                    pos["current_sl"] = pos["entry_spot"]
                    pos["trailing_stage"] = 1
                    logging.info(f"TRAIL-1: {pos['contract']} SL to BE ({pos['current_sl']:.2f})")
                    log_to_journal(symbol, pos["pattern"], TIMEFRAME_ENTRY,
                                   "TRAIL_BE", "MUTATED", f"SL={pos['current_sl']:.2f}",
                                   entry=pos["entry_spot"], sl=pos["current_sl"], target=pos.get("t1",""))
                    if tid: trade_db.update_trade(tid, {"trailing_stage": 1, "current_sl": pos["current_sl"]})
                elif pos["trailing_stage"] == 1 and pos["t2"] is not None and high_price >= pos["t2"]:
                    pos["current_sl"] = pos["t1"]
                    pos["trailing_stage"] = 2
                    logging.info(f"TRAIL-2: {pos['contract']} SL to T1 ({pos['current_sl']:.2f})")
                    log_to_journal(symbol, pos["pattern"], TIMEFRAME_ENTRY,
                                   "TRAIL_T1", "MUTATED", f"SL={pos['current_sl']:.2f}",
                                   entry=pos["entry_spot"], sl=pos["current_sl"], target=pos.get("t2",""))
                    if tid: trade_db.update_trade(tid, {"trailing_stage": 2, "current_sl": pos["current_sl"]})
                if pos["t3"] is not None and high_price >= pos["t3"]:
                    logging.info(f"T3 HIT: {pos['contract']} at {pos['t3']}")
                    close_position(kite, pos)
                    pnl = ((pos["t3"] - pos["entry_spot"]) / pos["entry_spot"]) * 100
                    log_to_journal(symbol, pos["pattern"], TIMEFRAME_ENTRY,
                                   "EXIT_T3", "CLOSED", f"T3={pos['t3']}", pnl,
                                   entry=pos["entry_spot"], sl=pos["current_sl"], target=pos["t3"])
                    if tid: trade_db.update_trade(tid, {"status": "TARGET_HIT", "exit_time": dt.now().strftime("%Y-%m-%d %H:%M:%S"), "pnl_percent": round(pnl, 2)})
                    to_clear.append(symbol)
            except Exception as e:
                logging.error(f"Risk monitor error for {symbol}: {e}")
        for sym in to_clear:
            ACTIVE_POSITIONS.pop(sym, None)

# ──────────────────────────────────────────────
#  MAIN LOOP — SCAN CYCLE + RISK MONITOR
# ──────────────────────────────────────────────

def main_scan_loop(kite):
    active = trade_db.get_active_trades("index")
    for t in active:
        if t["symbol"] in INDEX_REGISTRY:
            with position_lock:
                ACTIVE_POSITIONS[t["symbol"]] = {k: v for k, v in t.items() if k not in ("id", "engine", "symbol", "status", "created_at", "updated_at")}
                ACTIVE_POSITIONS[t["symbol"]]["trade_id"] = t["id"]
                ACTIVE_POSITIONS[t["symbol"]]["entry_spot"] = ACTIVE_POSITIONS[t["symbol"]].get("entry_spot") or t.get("entry_spot")
            logging.info(f"Recovered position: {t['symbol']} | {t.get('contract','')}")
    try:
        kite_positions = kite.positions()
        for p in kite_positions.get("day", []) + kite_positions.get("net", []):
            if p["exchange"] != "NFO" or int(p["net_quantity"]) == 0:
                continue
            symbol = next((s for s in INDEX_REGISTRY if s in p["tradingsymbol"]), None)
            if not symbol or symbol in ACTIVE_POSITIONS:
                continue
            nq = abs(int(p["net_quantity"]))
            lots = nq // INDEX_REGISTRY[symbol]["lot_size"]
            if lots == 0:
                continue
            side = "CE" if "CE" in p["tradingsymbol"] else "PE"
            pos = {
                "contract": p["tradingsymbol"], "option_token": int(p["instrument_token"]),
                "entry_spot": float(p["net_price"]), "current_sl": 0,
                "t1": 0, "t2": 0, "t3": 0, "trailing_stage": 0,
                "lot_size": INDEX_REGISTRY[symbol]["lot_size"], "position_size": lots,
                "pattern": "KITE_RECOVERED", "side": side,
                "timeframe": TIMEFRAME_ENTRY
            }
            pos["trade_id"] = trade_db.create_trade("index", symbol, {k: v for k, v in pos.items() if k != "trade_id"})
            ACTIVE_POSITIONS[symbol] = pos
            logging.info(f"Recovered from Kite: {symbol} {p['tradingsymbol']} qty={nq}")
    except Exception as e:
        logging.warning(f"Kite position recovery failed: {e}")
    cycle = 0
    while True:
        try:
            cycle += 1
            if cycle == 1 or cycle % 4 == 1:
                with position_lock:
                    active = len(ACTIVE_POSITIONS)
                    symbols = list(ACTIVE_POSITIONS.keys())
                logging.info(f"[BEAT] Cycle {cycle} | Active: {active} {symbols if active else ''}")
            temp_stored_trades = run_scan_cycle(kite)

            if temp_stored_trades and len(temp_stored_trades) > 2:
                execute_highest_rr_trade(kite, temp_stored_trades)
            elif temp_stored_trades:
                logging.info(f"[CYCLE] {len(temp_stored_trades)} trade(s) staged this cycle; need >2 to execute. No execution this cycle.")

            trade_db.clear_cycle_trades("index")

            monitor_active_positions(kite)
            time.sleep(max(0, SCAN_INTERVAL_SECONDS))
        except Exception as e:
            logging.error(f"Background error: {e}")
            time.sleep(5)

def load_program_config():
    try:
        cfg_path = os.path.join(os.path.dirname(__file__), "input", "program_config.json")
        if os.path.exists(cfg_path):
            with open(cfg_path) as f:
                full = json.load(f)
            cfg = full.get("index", {})
            if "timeframe_entry" in cfg:
                globals().update({"TIMEFRAME_ENTRY": cfg["timeframe_entry"]})
            elif "timeframe" in cfg:
                globals().update({"TIMEFRAME_ENTRY": cfg["timeframe"]})
            if "timeframe_anchor" in cfg:
                globals().update({"TIMEFRAME_ANCHOR": cfg["timeframe_anchor"]})
            elif "timeframe" in cfg:
                globals().update({"TIMEFRAME_ANCHOR": cfg["timeframe"]})
            if "strike_range" in cfg:
                globals().update({"STRIKE_RANGE": int(cfg["strike_range"])})
            if "lookback_days" in cfg: globals().update({"LOOKBACK_DAYS": int(cfg["lookback_days"])})
            if "scan_interval" in cfg: globals().update({"SCAN_INTERVAL_SECONDS": int(cfg["scan_interval"])})
            if "risk_percent" in cfg: globals().update({"MAX_RISK_PERCENT": float(cfg["risk_percent"])})
            if "capital" in cfg: globals().update({"INITIAL_CAPITAL": float(cfg["capital"])})
            if "_backtest" in full: globals().update({"LIVE_MARKET_DEPLOYMENT": not full["_backtest"]})
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
                best = max(staged, key=lambda t: (t.get("t3") or t.get("t1") or 0) - t.get("entry_spot", 0))
                sym = best["symbol"]
                if sym not in results["by_symbol"]:
                    results["by_symbol"][sym] = {"trades": 0, "wins": 0, "losses": 0, "no_exits": 0}
                results["by_symbol"][sym]["trades"] += 1
                key = f"{best['symbol']}|{best['pattern']}|{best['side']}|{best.get('strike', '')}"
                if not trade_db.is_pattern_executed("index", key):
                    trade_db.record_executed_pattern("index", key, {"contract": best["contract"], "entry": best["entry_spot"]})
                contract_display = best.get('contract', sym)
                log_to_journal(contract_display, best['pattern'], best.get('timeframe', TIMEFRAME_ENTRY),
                               "BACKTEST_ENTRY", "ENTRY",
                               details=f"Symbol={sym} Strike={best.get('strike','')}",
                               entry=best['entry_spot'], sl=best['current_sl'],
                               target=best.get('t3') or best.get('t1') or "",
                               rr=best.get('rr'))
                sim_result, _ = simulate_trade_outcome(kite, best, day)
                exit_action = ""
                pnl = 0.0
                if sim_result == "SL_HIT":
                    exit_action = "EXIT_SL"
                    pnl = round(((best['current_sl'] - best['entry_spot']) / best['entry_spot']) * 100, 2)
                    results["losses"] += 1
                    results["by_symbol"][sym]["losses"] += 1
                elif sim_result == "T1_HIT":
                    exit_action = "EXIT_T3"
                    pnl = round(((best.get('t1', best['entry_spot']) - best['entry_spot']) / best['entry_spot']) * 100, 2)
                    results["wins"] += 1
                    results["by_symbol"][sym]["wins"] += 1
                elif sim_result == "T2_HIT":
                    exit_action = "EXIT_T3"
                    pnl = round(((best.get('t2', best['entry_spot']) - best['entry_spot']) / best['entry_spot']) * 100, 2)
                    results["wins"] += 1
                    results["by_symbol"][sym]["wins"] += 1
                elif sim_result == "T3_HIT":
                    exit_action = "EXIT_T3"
                    pnl = round(((best.get('t3', best['entry_spot']) - best['entry_spot']) / best['entry_spot']) * 100, 2)
                    results["wins"] += 1
                    results["by_symbol"][sym]["wins"] += 1
                else:
                    exit_action = "EXIT_UNKNOWN"
                    results["no_exits"] += 1
                    results["by_symbol"][sym]["no_exits"] += 1
                if exit_action:
                    log_to_journal(contract_display, best['pattern'], best.get('timeframe', TIMEFRAME_ENTRY),
                                   exit_action, sim_result or "NO_EXIT",
                                   details=f"Symbol={sym} Strike={best.get('strike','')}",
                                   entry=best['entry_spot'], sl=best['current_sl'],
                                   target=best.get('t3') or best.get('t1') or "",
                                   rr=best.get('rr'), pnl_pct=pnl)
                logging.info(f"  Trade: {best['contract']} | {best['pattern']} | outcome={sim_result or 'unknown'} | P&L={pnl:.2f}%")
            trade_db.clear_cycle_trades("index")
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
        logging.info("Starting Index Trade Engine...")
    try:
        api_key, access_token = load_kite_session()
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        fetch_instruments(kite)
    except Exception as e:
        logging.error(f"Init failed: {e}")
        return
    if anchor_only:
        run_anchor_scan(kite)
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
        trade_db.clear_cycle_trades("index")
        return
    if not LIVE_MARKET_DEPLOYMENT:
        logging.error("Config has _backtest=true but no --date= or --backtest-range= flag. "
                      "Use --date=YYYY-MM-DD or --backtest-range=START,END to run backtest. Exiting.")
        return
    logging.info(f"Scanner: {TIMEFRAME_ENTRY} | Anchor: {TIMEFRAME_ANCHOR} | Capital: {INITIAL_CAPITAL} | Risk: {MAX_RISK_PERCENT}%")
    worker = threading.Thread(target=main_scan_loop, args=(kite,), daemon=True)
    worker.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Engine stopped by user.")

if __name__ == "__main__":
    main()
