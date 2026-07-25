import os
import json
import logging
import csv
import time
import threading
from datetime import datetime as dt, timedelta, time as datetime_time
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import numpy as np

# ──────────────────────────────────────────────
#  CONSTANTS & REGISTRIES
# ──────────────────────────────────────────────

TOKEN_FILE = "input/kite_access_token.txt"
JOURNAL_FILE = "output/monitor/trade_journal.csv"

LOOKBACK_LIMITS = {
    "minute": 60,
    "3minute": 100,
    "5minute": 100,
    "10minute": 100,
    "15minute": 200,
    "30minute": 200,
    "60minute": 400,
    "day": 2000
}

def get_next_candle_start_time(candle_date, timeframe_str):
    try:
        dt_val = pd.to_datetime(candle_date)
        tf_s = str(timeframe_str).lower()
        if "60min" in tf_s or tf_s == "60minute" or "1hour" in tf_s: tf_minutes = 60
        elif "30min" in tf_s or tf_s == "30minute": tf_minutes = 30
        elif "15min" in tf_s or tf_s == "15minute": tf_minutes = 15
        elif "10min" in tf_s or tf_s == "10minute": tf_minutes = 10
        elif "5min" in tf_s or tf_s == "5minute": tf_minutes = 5
        elif "3min" in tf_s or tf_s == "3minute": tf_minutes = 3
        elif "day" in tf_s: tf_minutes = 1440
        else: tf_minutes = 15
        next_dt = dt_val + pd.Timedelta(minutes=tf_minutes)
        return str(next_dt)
    except Exception:
        return str(candle_date)

INDEX_REGISTRY = {
    "NIFTY": {"token": 256265, "lot_size": 65, "strike_step": 50, "tradingsymbol": "NIFTY 50"},
    "BANKNIFTY": {"token": 260105, "lot_size": 30, "strike_step": 100, "tradingsymbol": "NIFTY BANK"}
}

SUPER_STOCKS = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY",
    "ITC", "SBIN", "BHARTIARTL", "LT", "WIPRO"
]

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
    "ETERNAL": {"token": 1304833, "lot_size": 2425, "strike_step": 5},
    "GRASIM": {"token": 315393, "lot_size": 400, "strike_step": 20},
    "HCLTECH": {"token": 1837313, "lot_size": 700, "strike_step": 20},
    "HDFCBANK": {"token": 341249, "lot_size": 550, "strike_step": 10},
    "HDFCLIFE": {"token": 119553, "lot_size": 1100, "strike_step": 10},
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
    "MAXHEALTH": {"token": 5728513, "lot_size": 525, "strike_step": 10},
    "NESTLEIND": {"token": 4543233, "lot_size": 500, "strike_step": 20},
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
    "TMPV": {"token": 884737, "lot_size": 1600, "strike_step": 10},
    "TCS": {"token": 2953217, "lot_size": 175, "strike_step": 50},
    "TECHM": {"token": 3418369, "lot_size": 600, "strike_step": 20},
    "TITAN": {"token": 895745, "lot_size": 375, "strike_step": 50},
    "TRENT": {"token": 5064961, "lot_size": 150, "strike_step": 100},
    "ULTRACEMCO": {"token": 2952193, "lot_size": 100, "strike_step": 100},
    "VEDL": {"token": 0, "lot_size": 1000, "strike_step": 5},
    "WIPRO": {"token": 969473, "lot_size": 1500, "strike_step": 5}
}

def sync_stock_tokens(kite):
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
    except Exception as e:
        logging.error(f"Stock token sync failed: {e}")

# ──────────────────────────────────────────────
#  SESSION & UTILITIES
# ──────────────────────────────────────────────

def load_kite_session(token_file=TOKEN_FILE):
    if not os.path.exists(token_file):
        raise FileNotFoundError(f"Token file missing at {token_file}. Run Kite_Access_Token_gen.py first.")
    with open(token_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not data.get("api_key") or not data.get("access_token"):
        raise ValueError("Corrupted token file.")
    return data["api_key"], data["access_token"]

def log_to_journal(symbol, pattern, timeframe, action, status, details="", pnl_pct=0.0, entry="", sl="", target="", rr="", journal_file=JOURNAL_FILE, lock=None, event_time=None):
    file_exists = os.path.exists(journal_file)
    headers = ["Timestamp", "Symbol", "Pattern", "Timeframe", "Action", "Status", "Entry", "SL", "Target", "RR", "Details", "P&L %"]
    if event_time is not None:
        raw = str(event_time).replace('T', ' ')
        if '+' in raw:
            raw = raw.split('+')[0]
        ts_str = raw
    else:
        ts_str = dt.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [
        ts_str,
        symbol, pattern, timeframe, action, status,
        f"{entry:.2f}" if isinstance(entry, (int, float)) and entry else str(entry) if entry else "",
        f"{sl:.2f}" if isinstance(sl, (int, float)) and sl else str(sl) if sl else "",
        f"{target:.2f}" if isinstance(target, (int, float)) and target else str(target) if target else "",
        f"{rr:.2f}" if isinstance(rr, (int, float)) and rr else str(rr) if rr else "",
        details,
        f"{pnl_pct:.2f}%" if pnl_pct != 0.0 else "-"
    ]
    def _write():
        try:
            with open(journal_file, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter="\t")
                if not file_exists:
                    writer.writerow(headers)
                writer.writerow(row)
        except Exception as e:
            logging.error(f"Journal write failed: {e}")

    if lock:
        with lock:
            _write()
    else:
        _write()

def is_market_hours():
    now = dt.now()
    if now.weekday() in [5, 6]:
        return False
    t = now.time()
    return datetime_time(9, 15) <= t <= datetime_time(15, 30)

def get_weekly_expiry(target_weekday=1):
    now = dt.now()
    days_ahead = (target_weekday - now.weekday()) % 7
    if days_ahead == 0 and now.hour >= 15:
        days_ahead = 7
    return (now + timedelta(days=days_ahead)).date()

def cap_lookback_days(timeframe, requested_days):
    limit = LOOKBACK_LIMITS.get(timeframe, 200)
    return min(requested_days, limit)

def check_left_side_rule(df, anchor_low, setup_count=0, skip_adjacent=0, lookback_candles=100):
    """Verify no candle in the preceding lookback_candles has a CLOSE below anchor's low (tails/wicks permitted)."""
    if df is None or df.empty:
        return True
    end_idx = len(df) - (setup_count + skip_adjacent) if (setup_count + skip_adjacent) > 0 else len(df)
    start_idx = max(0, end_idx - lookback_candles)
    left = df.iloc[start_idx:end_idx] if end_idx > start_idx else pd.DataFrame()
    if not left.empty and anchor_low > float(left['close'].min()):
        return False
    return True

# Alias for backward compatibility
check_left_side = check_left_side_rule

def find_profit_targets(df_hist, entry_close, stop_loss=None):
    """
    Timeframe & Asset class adaptive profit target finder.
    Handles Intraday Options (1m, 3m, 5m, 15m, 30m, 60m) AND Daily/Weekly/Monthly Stock & Index charts.
    - Daily/Weekly/Monthly TFs: Scans up to 730 days (2 years) to extract major 52-week & multi-month swing highs.
    - Intraday Option TFs: Scans active 30 days window to ignore ancient decaying option contract highs.
    """
    if df_hist is None or len(df_hist) < 3:
        return None, None, None

    hist = df_hist.copy()

    # 1. Identify datetime column
    time_col = None
    for col in ['datetime', 'date', 'timestamp', 'time', 'date_time']:
        if col in hist.columns:
            time_col = col
            break

    is_higher_tf = False
    if time_col is not None:
        try:
            hist[time_col] = pd.to_datetime(hist[time_col])
            hist = hist.sort_values(time_col).reset_index(drop=True)
            time_diffs = hist[time_col].diff().dropna()
            if not time_diffs.empty:
                median_diff = time_diffs.median()
                # If candle spacing is >= 20 hours, it is a Daily, Weekly, or Monthly chart
                if median_diff >= pd.Timedelta(hours=20):
                    is_higher_tf = True
        except Exception:
            pass

    # 2. Adaptive lookback window based on Timeframe & Asset Type
    if time_col is not None:
        try:
            max_dt = hist[time_col].max()
            if is_higher_tf:
                # Daily / Weekly / Monthly charts: Look back up to 730 days (2 years) to capture major 52-week swing highs
                min_dt = max_dt - pd.Timedelta(days=730)
            else:
                # Intraday (1m, 3m, 5m, 15m, 60m): Look back 30 calendar days (~20 trading sessions)
                min_dt = max_dt - pd.Timedelta(days=30)
            
            sub_hist = hist[hist[time_col] >= min_dt]
            if len(sub_hist) >= 5:
                hist = sub_hist
        except Exception:
            pass

    # 3. Find lowest low in active dataset
    ll_idx = hist['low'].idxmin()

    # 4. Calculate ATR for dynamic capping & fallback target spacing
    high_low_diff = (hist['high'] - hist['low']).abs()
    atr = float(high_low_diff.tail(20).mean()) if len(hist) >= 5 else (entry_close * 0.02)
    if pd.isna(atr) or atr <= 0:
        atr = entry_close * 0.02

    # 5. Dynamic target cap & minimum start relative to entry price & asset type
    risk = (entry_close - stop_loss) if (stop_loss and stop_loss < entry_close) else max(atr * 1.5, entry_close * 0.03)

    if entry_close < 300:  # Option contract premium
        max_target_cap = max(entry_close * 3.5, entry_close + 15 * atr)
        min_target_start = max(entry_close * 1.20, entry_close + 1.5 * risk)
        step_tol = 0.04
    elif is_higher_tf:     # Daily/Weekly/Monthly Stock or Index (allows major 52-week peaks)
        max_target_cap = max(entry_close * 2.0, entry_close + 20 * atr)
        min_target_start = max(entry_close * 1.03, entry_close + 1.5 * risk)
        step_tol = 0.03
    else:                  # Intraday Spot Stock / Index
        max_target_cap = max(entry_close * 1.25, entry_close + 10 * atr)
        min_target_start = max(entry_close * 1.02, entry_close + 1.5 * risk)
        step_tol = 0.02

    # 6. Extract Non-Negated 5-bar structural swing high resistance pivots above min_target_start
    non_negated_targets = []
    n = len(hist)
    for i in range(n - 2, 1, -1):
        w = hist.iloc[max(0, i-2):min(n, i+3)]
        if len(w) >= 3 and hist.iloc[i]['high'] == w['high'].max():
            h_val = float(hist.iloc[i]['high'])
            if min_target_start <= h_val <= max_target_cap:
                # NEGATION THEORY RULE: Discard if price action after bar i closed above h_val prior to entry (Breached / Negated)
                subsequent_bars = hist.iloc[i+1:]
                if not subsequent_bars.empty:
                    max_subsequent_close = float(subsequent_bars['close'].max())
                    if max_subsequent_close > h_val * 1.005:
                        continue  # Negated target level -> Discarded
                non_negated_targets.append(h_val)

    if not non_negated_targets:
        for i in range(n - 1, 0, -1):
            h_val = float(hist.iloc[i]['high'])
            if min_target_start <= h_val <= max_target_cap:
                subsequent_bars = hist.iloc[i+1:]
                if not subsequent_bars.empty:
                    if float(subsequent_bars['close'].max()) > h_val * 1.005:
                        continue
                non_negated_targets.append(h_val)

    # Sort non-negated target levels ascending by price
    sorted_levels = sorted(list(set(non_negated_targets)))

    # Cluster non-negated levels within step_tol distance
    clustered = []
    for p in sorted_levels:
        if not clustered or (p - clustered[-1]) / clustered[-1] > step_tol:
            clustered.append(round(p, 2))

    t1 = clustered[0] if len(clustered) >= 1 else None
    t2 = clustered[1] if len(clustered) >= 2 else None
    t3 = clustered[2] if len(clustered) >= 3 else None

    # 7. Dynamic Risk-based fallbacks if non-negated pivot targets are missing
    if t1 is None:
        t1 = round(entry_close + max(1.5 * risk, entry_close * 0.20), 2)
    if t2 is None:
        t2 = round(max(t1 + 1.5 * risk, t1 * 1.15), 2)
    if t3 is None:
        t3 = round(max(t2 + 2.0 * risk, t2 * 1.15), 2)

    # Ordering & minimum separation check
    if t2 <= t1 * (1 + step_tol):
        t2 = round(t1 * (1 + step_tol * 2), 2)
    if t3 <= t2 * (1 + step_tol):
        t3 = round(t2 * (1 + step_tol * 2), 2)

    return t1, t2, t3

def calculate_position_size(spot_price, stop_loss, capital=100000.0, risk_percent=1.0):
    risk_per_unit = abs(spot_price - stop_loss)
    if risk_per_unit <= 0:
        return 0
    max_risk_amount = capital * (risk_percent / 100.0)
    units = int(max_risk_amount / risk_per_unit)
    return max(units, 1)

# ──────────────────────────────────────────────
#  ANCHOR (A-FORMATION) DETECTION — 5 PATTERNS
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
    sl_val = round(a_low - max(0.50, a_low * 0.02), 2)
    return {"Pattern": "BULL_A_ABCD_Engulf", "Close": anchor_close, "SL": sl_val, "Signal": "A_Formation"}

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
    sl_val = round(sweep_low - max(0.50, sweep_low * 0.02), 2)
    return {"Pattern": "BULL_A_LL_Sweep", "Close": anchor_close, "SL": sl_val, "Signal": "Low2_Formation"}

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
    b_low = float(baby_candle['low'])
    sl_val = round(b_low - max(0.50, b_low * 0.02), 2)
    return {"Pattern": "BULL_A_Baby_Candle", "Close": anchor_close, "SL": sl_val, "Signal": "Baby_Formation"}

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
    sl_val = round(inside_low - max(0.50, inside_low * 0.02), 2)
    return {"Pattern": "BULL_A_Harami", "Close": anchor_close, "SL": sl_val, "Signal": "Harami_Formation"}

def find_anchor_two_higher_highs(df):
    """Setup 3: A1 & A2 are two successive higher high candles with bullish engulfing structure."""
    if len(df) < 5:
        return None
    a1, a2 = df.iloc[-4], df.iloc[-3]
    if not (float(a1['close']) > float(a1['open']) and float(a2['close']) > float(a2['open'])):
        return None
    if not (float(a2['high']) > float(a1['high']) and float(a2['low']) > float(a1['low'])):
        return None
    a_low = min(float(a1['low']), float(a2['low']))
    anchor_close = float(a2['close'])
    sl_val = round(a_low - max(0.50, a_low * 0.02), 2)
    return {"Pattern": "BULL_A_Two_Higher_Highs", "Close": anchor_close, "SL": sl_val, "Signal": "HigherHigh_Engulf"}

# ──────────────────────────────────────────────
#  ANCHOR BCD BREAKOUT SCANNER (A -> B -> C -> D)
# ──────────────────────────────────────────────

def scan_anchor_bcd_breakout(df_entry, df_anchor):
    """
    Two-phase A-first scanner:
      Phase 1: Find anchor candle A (using 5 anchor detectors + base fallback).
      Phase 2: From A, scan forward sequentially: B (breakout > A.high) ->
               C (red retest) -> D (confirmation close > A.high).
      Returns first complete A -> B -> C -> D pattern, or None.
    """
    anchor_funcs = [
        find_anchor_bullish_engulfing,
        find_anchor_ll_sweep,
        find_anchor_hammer_baby,
        find_anchor_bullish_harami,
        find_anchor_two_higher_highs
    ]

    # ── Phase 1: Find anchor A candles ──
    anchors = []
    for a_idx in range(4, len(df_entry) - 3):
        a = df_entry.iloc[a_idx]
        sub_df = df_entry.iloc[: min(len(df_entry), a_idx + 3)]
        sub_df_direct = df_entry.iloc[: a_idx + 1]

        anchor_match = None
        for fn in anchor_funcs:
            res = fn(sub_df) or fn(sub_df_direct)
            if res:
                anchor_match = res
                break

        benchmark = float(a['high'])
        invalidation = anchor_match["SL"] if anchor_match else round(float(a['low']) - max(0.50, float(a['low']) * 0.02), 2)
        anchor_name = anchor_match["Pattern"] if anchor_match else "BULL_A_Base"

        # Left-Side Rule: no close below A.low in preceding 100 candles
        a_low = float(a['low'])
        left_df = df_entry.iloc[max(0, a_idx - 100) : a_idx]
        if not left_df.empty and float(left_df['close'].min()) < a_low:
            continue

        # Pre-compute targets for NoPA filter
        t1, t2, t3 = find_profit_targets(df_anchor, benchmark, stop_loss=invalidation)

        # NoPA: discard if SL/T1/T2 already closed past post-A (closing basis)
        if t1 is not None:
            after_a = df_entry.iloc[a_idx + 1 :]
            if not after_a.empty:
                if float(after_a['close'].min()) <= invalidation:
                    continue
                if float(after_a['close'].max()) >= t1:
                    continue
                if t2 is not None and float(after_a['close'].max()) >= t2:
                    continue

        anchors.append({
            "idx": a_idx, "a": a, "benchmark": benchmark,
            "invalidation": invalidation, "anchor_name": anchor_name, "a_low": a_low,
            "t1": t1, "t2": t2, "t3": t3
        })

    # ── Phase 2: For each anchor, scan forward B -> C -> D ──
    for cand in anchors:
        a_idx = cand["idx"]
        a = cand["a"]
        benchmark = cand["benchmark"]
        invalidation = cand["invalidation"]
        anchor_name = cand["anchor_name"]

        remaining = df_entry.iloc[a_idx + 1:]
        if len(remaining) < 3:
            continue

        # Point B: FIRST candle after A closing above benchmark
        b_idx = None
        for j in range(len(remaining)):
            if float(remaining.iloc[j]['close']) > benchmark:
                b_idx = a_idx + 1 + j
                break
        if b_idx is None:
            continue

        # Point C: FIRST candle AFTER B with red retest (dips to/close to benchmark, above SL)
        c_slice = df_entry.iloc[b_idx + 1:]
        c_idx = None
        for j in range(len(c_slice)):
            c_row = c_slice.iloc[j]
            c_low = float(c_row['low'])
            c_close = float(c_row['close'])
            c_open = float(c_row['open'])
            is_red = c_close < c_open
            if (c_low <= benchmark and c_close > invalidation and is_red) or \
               (c_low <= invalidation and c_close > invalidation and c_close < float(a['open']) and is_red):
                c_idx = b_idx + 1 + j
                break
        if c_idx is None:
            continue

        # Point D: FIRST candle AFTER C closing above benchmark
        d_slice = df_entry.iloc[c_idx + 1:]
        d_idx = None
        for j in range(len(d_slice)):
            if float(d_slice.iloc[j]['close']) > benchmark:
                d_idx = c_idx + 1 + j
                break
        if d_idx is None:
            continue

        d = df_entry.iloc[d_idx]

        # Invalidation: no candle between A-D closes below SL
        between = df_entry.iloc[a_idx + 1 : d_idx]
        if not between.empty and float(between['close'].min()) < invalidation:
            continue

        close_price = float(d['close'])
        sl_val = invalidation
        t1, t2, t3 = find_profit_targets(df_anchor, close_price, stop_loss=sl_val)
        if t1 is None:
            continue

        risk = close_price - sl_val
        if risk <= 0 or risk < close_price * 0.002 or ((t1 - close_price) / risk) < 1.88:
            continue

        rr = (t1 - close_price) / risk if risk > 0 else 0
        short_names = {
            "BULL_A_ABCD_Engulf": "BE_ABCD",
            "BULL_A_LL_Sweep": "LL_ABCD",
            "BULL_A_Baby_Candle": "HAMMER_ABCD",
            "BULL_A_Harami": "HARAMI_ABCD",
            "BULL_A_Two_Higher_Highs": "HH_ABCD",
            "BULL_A_Base": "BASE_ABCD"
        }
        pattern_label = short_names.get(anchor_name, "BE_ABCD")
        d_time_str = str(d.get("date", ""))
        a_time_str = str(a.get("date", ""))

        return {
            "Pattern": pattern_label,
            "SL": sl_val,
            "T1": t1,
            "T2": t2,
            "T3": t3,
            "Close": close_price,
            "RR": round(rr, 2),
            "CandleTime": d_time_str,
            "CandleATime": a_time_str
        }

    return None

# Alias for backward compatibility across engines and scripts
def _record_completed_scan_trade(contract_name, pattern_label, entry, sl, target, rr, action_str, status_str, pnl_pct, entry_time, exit_time):
    try:
        import trade_db, csv
        journal_db_path = os.path.join("output", "monitor", "journal_trades_db.json")
        csv_path = os.path.join("output", "monitor", "trade_journal.csv")
        
        entry_row = {
            "Timestamp": exit_time or entry_time,
            "Symbol": contract_name,
            "Pattern": pattern_label,
            "Action": action_str,
            "Status": status_str,
            "Entry": round(entry, 2),
            "SL": round(sl, 2),
            "Target": round(target, 2),
            "RR": round(rr, 2),
            "P&L %": f"{pnl_pct:+.2f}%",
            "entry_time": entry_time,
            "exit_time": exit_time
        }
        
        existing = trade_db._read_json(journal_db_path, {"journal_entries": []})
        entries = existing.get("journal_entries", [])
        if any(e.get("Symbol") == contract_name and e.get("Timestamp") == entry_row["Timestamp"] for e in entries):
            return
            
        entries.append(entry_row)
        trade_db._write_json(journal_db_path, {"updated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "journal_entries": entries})
        
        write_header = not os.path.exists(csv_path)
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Timestamp", "Symbol", "Pattern", "Action", "Status", "Entry", "SL", "Target", "RR", "P&L %"])
            if write_header:
                writer.writeheader()
            writer.writerow({
                "Timestamp": entry_row["Timestamp"],
                "Symbol": entry_row["Symbol"],
                "Pattern": entry_row["Pattern"],
                "Action": entry_row["Action"],
                "Status": entry_row["Status"],
                "Entry": entry_row["Entry"],
                "SL": entry_row["SL"],
                "Target": entry_row["Target"],
                "RR": entry_row["RR"],
                "P&L %": entry_row["P&L %"]
            })
    except Exception as e:
        logging.warning(f"Journal record error: {e}")


# ──────────────────────────────────────────────
#  SHARED ENGINE UTILITIES (identical between engines)
# ──────────────────────────────────────────────

def fetch_option_data(kite, token, from_date, to_date, primary_tf, fallback_tf, min_candles=5):
    df = pd.DataFrame(kite.historical_data(token, from_date, to_date, primary_tf))
    if len(df) >= min_candles:
        return df
    df = pd.DataFrame(kite.historical_data(token, from_date, to_date, fallback_tf))
    if len(df) >= min_candles:
        logging.info(f"Fallback to {fallback_tf} for token {token} (only {len(df)} candles on {primary_tf})")
    return df

def trading_days_between(start, end):
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days

def calc_rr(entry, sl, t1, t2):
    if entry is None or sl is None or t1 is None:
        return 0
    risk = entry - sl
    if risk <= 0:
        return 0
    targets = [t1]
    if t2 is not None:
        targets.append(t2)
    return sum((t - entry) / risk for t in targets) / len(targets)

def live_execution_enabled(flag_path):
    return os.path.exists(flag_path)

# ──────────────────────────────────────────────
#  SHARED POSITION MANAGEMENT
# ──────────────────────────────────────────────

NFO_CACHE_FILE = os.path.join("output", "monitor", "nfo_instruments_cache.csv")

def get_option_lot_size(contract):
    """Look up actual lot size from NFO instruments cache, not from registry."""
    try:
        if not os.path.exists(NFO_CACHE_FILE):
            return None
        df = pd.read_csv(NFO_CACHE_FILE)
        row = df[df['tradingsymbol'] == contract]
        if not row.empty:
            return int(row.iloc[0]['lot_size'])
    except Exception as e:
        logging.warning(f"Lot size lookup failed for {contract}: {e}")
    return None

def close_stock_position(kite, pos, live_market, product=None):
    if not live_market:
        logging.info(f"[BACKTEST EXIT] Closed stock {pos.get('contract','')}")
        return
    contract = pos.get("contract") or pos.get("symbol")
    if not contract:
        logging.error("close_stock_position failed: missing contract/symbol name")
        return
    target_product = product
    try:
        if kite:
            net_positions = kite.positions().get("net", [])
            for p in net_positions:
                if p.get("tradingsymbol") == contract and abs(int(p.get("quantity", 0))) > 0:
                    prod = p.get("product")
                    if prod:
                        target_product = prod
                        break
    except Exception as e:
        logging.warning(f"Could not fetch Kite stock position product for {contract}: {e}")
    if not target_product:
        target_product = pos.get("product") or kite.PRODUCT_CNC
    try:
        q = kite.quote(f"{kite.EXCHANGE_NSE}:{contract}")
        ltp = q[f"{kite.EXCHANGE_NSE}:{contract}"]["last_price"]
        bid = q[f"{kite.EXCHANGE_NSE}:{contract}"]["depth"]["buy"][0]["price"]
        price = round((bid if bid > 0 else ltp) * 0.995, 1)
        qty = pos.get("position_size", pos.get("quantity", 1))
        try:
            kite.place_order(
                variety=kite.VARIETY_REGULAR, tradingsymbol=contract,
                exchange=kite.EXCHANGE_NSE, transaction_type=kite.TRANSACTION_TYPE_SELL,
                quantity=qty, order_type=kite.ORDER_TYPE_LIMIT,
                price=price, product=target_product
            )
            logging.info(f"Closed stock {contract} with product {target_product}")
        except Exception as primary_err:
            logging.warning(f"Primary stock exit with {target_product} failed for {contract}: {primary_err}. Retrying with fallback...")
            alt_product = kite.PRODUCT_MIS if target_product == kite.PRODUCT_CNC else kite.PRODUCT_CNC
            kite.place_order(
                variety=kite.VARIETY_REGULAR, tradingsymbol=contract,
                exchange=kite.EXCHANGE_NSE, transaction_type=kite.TRANSACTION_TYPE_SELL,
                quantity=qty, order_type=kite.ORDER_TYPE_LIMIT,
                price=price, product=alt_product
            )
            logging.info(f"Fallback stock exit SUCCESS for {contract} with product {alt_product}")
    except Exception as e:
        logging.error(f"Stock exit failed for {contract}: {e}")

def close_position(kite, pos, live_market, product=None):
    if not live_market:
        logging.info(f"[BACKTEST EXIT] Closed {pos.get('contract','')}")
        return
    contract = pos.get("contract") or pos.get("symbol")
    if not contract:
        logging.error("close_position failed: missing contract name")
        return
    target_product = product
    try:
        if kite:
            net_positions = kite.positions().get("net", [])
            for p in net_positions:
                if p.get("tradingsymbol") == contract and abs(int(p.get("quantity", 0))) > 0:
                    prod = p.get("product")
                    if prod:
                        target_product = prod
                        break
    except Exception as e:
        logging.warning(f"Could not fetch Kite position product for {contract}: {e}")
    if not target_product:
        target_product = pos.get("product") or kite.PRODUCT_NRML
    try:
        q = kite.quote(f"{kite.EXCHANGE_NFO}:{contract}")
        ltp = q[f"{kite.EXCHANGE_NFO}:{contract}"]["last_price"]
        bid = q[f"{kite.EXCHANGE_NFO}:{contract}"]["depth"]["buy"][0]["price"]
        price = round((bid if bid > 0 else ltp) * 0.995, 1)
        position_size = pos.get("position_size", 1)
        lot_size = get_option_lot_size(contract)
        if not lot_size:
            lot_size = pos.get("lot_size", 1)
        qty = lot_size * position_size
        try:
            kite.place_order(
                variety=kite.VARIETY_REGULAR, tradingsymbol=contract,
                exchange=kite.EXCHANGE_NFO, transaction_type=kite.TRANSACTION_TYPE_SELL,
                quantity=qty, order_type=kite.ORDER_TYPE_LIMIT,
                price=price, product=target_product
            )
            logging.info(f"Closed {contract} with product {target_product}")
        except Exception as primary_err:
            logging.warning(f"Primary exit with {target_product} failed for {contract}: {primary_err}. Retrying with alternative product...")
            alt_product = kite.PRODUCT_MIS if target_product == kite.PRODUCT_NRML else kite.PRODUCT_NRML
            kite.place_order(
                variety=kite.VARIETY_REGULAR, tradingsymbol=contract,
                exchange=kite.EXCHANGE_NFO, transaction_type=kite.TRANSACTION_TYPE_SELL,
                quantity=qty, order_type=kite.ORDER_TYPE_LIMIT,
                price=price, product=alt_product
            )
            logging.info(f"Fallback exit SUCCESS for {contract} with product {alt_product}")
    except Exception as e:
        logging.error(f"Exit failed for {contract}: {e}")

def load_program_config_for_engine(cfg_section, extra_fields=None):
    """Load engine config from program_config.json. Returns dict of applied overrides."""
    applied = {}
    try:
        cfg_path = os.path.join(os.path.dirname(__file__), "input", "program_config.json")
        if os.path.exists(cfg_path):
            with open(cfg_path) as f:
                full = json.load(f)
            if "_backtest" in full:
                applied["LIVE_MARKET_DEPLOYMENT"] = not full["_backtest"]
            cfg = full.get(cfg_section, {})
            for src_key, dst_key in [
                ("timeframe_entry", "TIMEFRAME_ENTRY"),
                ("timeframe_anchor", "TIMEFRAME_ANCHOR"),
                ("lookback_days", "LOOKBACK_DAYS"),
                ("scan_interval", "SCAN_INTERVAL_SECONDS"),
                ("risk_percent", "MAX_RISK_PERCENT"),
                ("capital", "INITIAL_CAPITAL"),
            ]:
                if src_key in cfg:
                    applied[dst_key] = cfg[src_key]
            if extra_fields:
                for src_key, dst_key in extra_fields:
                    if src_key in cfg:
                        applied[dst_key] = cfg[src_key]
                    elif src_key in full:
                        applied[dst_key] = full[src_key]
    except Exception as e:
        logging.warning(f"Config load ({cfg_section}): {e}")
    return applied

def sync_kite_positions(kite, registry, positions_dict, lock, engine, timeframe_entry, timeframe_anchor):
    try:
        kite_pos = kite.positions()
        for plist in [kite_pos.get("day", []), kite_pos.get("net", [])]:
            for p in plist:
                sym = next((s for s in registry if s in p.get("tradingsymbol", "")), None)
                if not sym:
                    continue
                nq = abs(int(p.get("quantity", 0)))
                if nq == 0:
                    continue
                contract = p["tradingsymbol"]
                entry = float(p.get("net_price") or p.get("buy_price") or p.get("average_price") or 0)
                lot_size = registry[sym]["lot_size"]
                is_stock = p.get("exchange", "") == "NSE"
                with lock:
                    if sym in positions_dict:
                        if not positions_dict[sym].get("option_token"):
                            positions_dict[sym]["option_token"] = int(p.get("instrument_token", 0))
                        scan_sl = lookup_scan_sl_target(contract, sym, engine, kite, entry, timeframe_entry, timeframe_anchor)
                        if scan_sl:
                            for k, v in scan_sl.items():
                                positions_dict[sym][k] = v
                            tid = positions_dict[sym].get("trade_id")
                            if tid:
                                import trade_db
                                trade_db.update_trade(tid, scan_sl)
                        continue
                    positions_dict[sym] = {
                        "contract": contract, "option_token": int(p.get("instrument_token", 0)),
                        "entry_spot": entry,
                        "current_sl": 0, "t1": 0, "t2": 0, "t3": 0,
                        "trailing_stage": 0, "lot_size": lot_size if not is_stock else 1,
                        "position_size": nq // lot_size if not is_stock else nq,
                        "pattern": "MANUAL_ENTRY",
                        "timeframe": timeframe_entry, "side": "CE",
                        "entry_time": dt.now().isoformat(),
                        "position_type": "stock" if is_stock else "option"
                    }
                import trade_db
                tid = trade_db.create_trade(engine, sym, {"contract": contract, "entry_spot": entry, "current_sl": 0, "t1": 0, "t2": 0, "t3": 0, "lot_size": lot_size, "pattern": "MANUAL_ENTRY", "entry_time": dt.now().isoformat()})
                with lock:
                    positions_dict[sym]["trade_id"] = tid
                logging.info(f"[KITE_SYNC] New manual position: {contract} entry={entry}")
                scan_sl = lookup_scan_sl_target(contract, sym, engine, kite, entry, timeframe_entry, timeframe_anchor)
                if scan_sl:
                    with lock:
                        for k, v in scan_sl.items():
                            positions_dict[sym][k] = v
                    trade_db.update_trade(tid, scan_sl)
                    logging.info(f"[KITE_SYNC] Applied scan SL/Target for {contract}: SL={scan_sl.get('current_sl')} T1={scan_sl.get('t1')} T2={scan_sl.get('t2')} T3={scan_sl.get('t3')}")
    except Exception as e:
        logging.warning(f"Kite position sync failed: {e}")

def derive_sl_targets_for_contract(kite, contract, entry_price, timeframe_entry="15minute", timeframe_anchor="15minute"):
    """Derive SL and Targets for a specific contract using Negation Theory on historical candles."""
    try:
        ref_now = dt.now()
        from_d = (ref_now - timedelta(days=5)).strftime("%Y-%m-%d")
        to_d = ref_now.strftime("%Y-%m-%d")
        exch = "NFO" if ("CE" in contract or "PE" in contract or "NIFTY" in contract or "BANK" in contract) else "NSE"
        quote_key = f"{exch}:{contract}"
        q = kite.quote([quote_key])
        token = q.get(quote_key, {}).get("instrument_token")
        if not token:
            return None
        df_e = pd.DataFrame(kite.historical_data(token, from_d, to_d, timeframe_entry))
        df_a = pd.DataFrame(kite.historical_data(token, from_d, to_d, timeframe_anchor))
        if len(df_a) < 5:
            return None
        res = scan_anchor_bcd_breakout(df_e, df_a)
        if res:
            return {"current_sl": res["SL"], "t1": res["T1"], "t2": res["T2"], "t3": res["T3"], "pattern": res["Pattern"]}
        anchor_low = float(df_a.iloc[-10:]['low'].min())
        curr_price = float(df_a.iloc[-1]['close']) if len(df_a) else 0
        ep = entry_price if (entry_price and entry_price > 0) else curr_price
        sl_val = round(anchor_low - max(0.50, anchor_low * 0.02), 2)
        if ep > 0 and sl_val >= ep:
            sl_val = round(ep * 0.95, 2)
        t1, t2, t3 = find_profit_targets(df_a, ep, stop_loss=sl_val)
        if t1 is None:
            t1 = round(ep * 1.05, 2) if ep > 0 else None
            t2 = round(ep * 1.10, 2) if ep > 0 else None
            t3 = round(ep * 1.20, 2) if ep > 0 else None
        return {"current_sl": sl_val, "t1": t1, "t2": t2, "t3": t3, "pattern": "NEGATION_DERIVED"}
    except Exception as e:
        logging.warning(f"Derive contract SL/Target failed for {contract}: {e}")
        return None

def lookup_scan_sl_target(contract, symbol, engine, kite=None, entry_price=0, timeframe_entry="15minute", timeframe_anchor="15minute", entry_date=None, is_stock=False):
    """
    Search trade_db and scan display files using:
    - Options: contract name as primary key (e.g. NIFTY26JUL23850CE)
    - Stocks: symbol + entry_date as primary key (e.g. RELIANCE_2026-07-23)
    If not found, fall back to Negation Theory derivation on contract/stock historical candles.
    """
    if not entry_date:
        entry_date = dt.now().strftime("%Y-%m-%d")
        
    stock_key = f"{symbol}_{entry_date}".replace(" ", "").upper()
    clean_c = stock_key if is_stock else str(contract or symbol).replace(" ", "").upper()
    
    try:
        import trade_db
        all_trades = trade_db.get_all_trades(engine)
        for t in all_trades:
            t_is_stock = t.get("position_type") == "stock"
            t_date = (t.get("created_at") or t.get("entry_time") or "")[:10]
            tc = f"{t.get('symbol')}_{t_date}".replace(" ", "").upper() if t_is_stock else str(t.get("contract") or t.get("symbol") or "").replace(" ", "").upper()
            if tc and (tc == clean_c or clean_c in tc or tc in clean_c):
                sl = t.get("current_sl")
                t1 = t.get("t1")
                if sl and t1:
                    return {"current_sl": sl, "t1": t1, "t2": t.get("t2"), "t3": t.get("t3"), "pattern": t.get("pattern", "DB_SYNC")}
    except Exception:
        pass

    paths = {"index": "output/monitor/scan_display_index.json", "nifty50": "output/monitor/scan_display_data.json"}
    path = paths.get(engine)
    if path and os.path.exists(path):
        try:
            with open(path) as f:
                data = json.load(f)
            for section in ("staged_trades", "carry_forward", "active_live"):
                for trade in data.get(section, []):
                    t_date = (trade.get("entry_time") or "")[:10]
                    tc = f"{trade.get('symbol')}_{t_date}".replace(" ", "").upper() if is_stock else str(trade.get("contract") or trade.get("symbol") or "").replace(" ", "").upper()
                    if tc and (tc == clean_c or clean_c in tc or tc in clean_c):
                        sl = trade.get("current_sl")
                        t1 = trade.get("t1")
                        if sl and t1:
                            return {"current_sl": sl, "t1": t1, "t2": trade.get("t2"), "t3": trade.get("t3"), "pattern": trade.get("pattern", "SCAN_SYNC")}
        except Exception:
            pass

    if kite and (contract or symbol) and entry_price > 0:
        return derive_sl_targets_for_contract(kite, contract or symbol, entry_price, timeframe_entry, timeframe_anchor)

    return None

def write_scan_display_data(staged, active, display_file, engine_name=None):
    try:
        now_str = dt.now().strftime("%Y-%m-%d %H:%M:%S")
        today = dt.now().strftime("%Y-%m-%d")
        import trade_db
        db_trades = trade_db.get_all_trades(engine_name) if engine_name else []
        db_map = {}
        for dbt in db_trades:
            c = str(dbt.get("contract") or dbt.get("symbol") or "").replace(" ", "").upper()
            if c: db_map[c] = dbt

        def build_trade(t, result, entry_time, exit_time):
            contract = t.get("contract") or t.get("symbol") or ""
            c_clean = str(contract).replace(" ", "").upper()
            db_record = db_map.get(c_clean)
            entry = db_record.get("entry_spot") if (db_record and db_record.get("entry_spot") is not None) else t.get("entry_spot")
            sl = db_record.get("current_sl") if (db_record and db_record.get("current_sl")) else t.get("current_sl")
            t1 = db_record.get("t1") if (db_record and db_record.get("t1")) else t.get("t1")
            t2 = db_record.get("t2") if (db_record and db_record.get("t2")) else t.get("t2")
            t3 = db_record.get("t3") if (db_record and db_record.get("t3")) else t.get("t3")
            pattern = db_record.get("pattern") if (db_record and db_record.get("pattern")) else t.get("pattern", "")
            rr = calc_rr(entry, sl, t1, t2) if entry is not None else 0
            return {
                "symbol": t.get("symbol", ""),
                "contract": contract,
                "side": t.get("side", ""),
                "entry_spot": entry,
                "current_sl": sl,
                "t1": t1,
                "t2": t2,
                "t3": t3,
                "pattern": pattern,
                "entry_time": entry_time,
                "exit_time": exit_time,
                "result": result,
                "carry_forward": False,
                "rr": round(rr, 2),
                "candle_a_time": t.get("candle_a_time", "")
            }
        new_staged = [build_trade(t, t.get("pattern", "BE_ABCD"), t.get("entry_time", now_str), None) for t in (staged or [])]
        carry_fwd = []
        active_live = []
        active_keys = set()
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
            c = str(p.get("contract") or s or "").replace(" ", "").upper()
            if c: active_keys.add(c)

        def _trade_key(t):
            return str(t.get("contract") or t.get("symbol") or "").replace(" ", "").upper()

        new_keys = {_trade_key(t) for t in new_staged if _trade_key(t)}

        preserved = []
        try:
            if os.path.exists(display_file):
                with open(display_file) as f:
                    existing_data = json.load(f)
                for t in existing_data.get("staged_trades", []):
                    k = _trade_key(t)
                    if k and k not in new_keys and k not in active_keys:
                        preserved.append(t)
        except Exception:
            pass

        staged_list = preserved + new_staged

        data = {
            "date": today,
            "timestamp": now_str,
            "staged_trades": staged_list,
            "carry_forward": carry_fwd,
            "active_live": active_live
        }
        if engine_name:
            data["engine"] = engine_name
        os.makedirs(os.path.dirname(display_file), exist_ok=True)
        with open(display_file, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logging.error(f"Display data write failed: {e}")

def derive_sl_targets_for_symbol(kite, symbol, entry_price, registry, timeframe_entry, timeframe_anchor, lookback_days, resolve_fn):
    """Run ABC reversal + anchor scanners on a single symbol to derive SL/T1/T2/T3."""
    try:
        config = registry.get(symbol)
        if not config:
            return None
        ref_now = dt.now()
        limits = {"minute": 60, "3minute": 100, "5minute": 100, "10minute": 100, "15minute": 200, "30minute": 200, "60minute": 400, "day": 2000}
        max_days = limits.get(timeframe_entry, 200)
        from_d = (ref_now - timedelta(days=min(lookback_days, max_days))).strftime("%Y-%m-%d")
        to_d = ref_now.strftime("%Y-%m-%d")
        spot_quote = kite.ltp([config["token"]])
        current_spot = float(list(spot_quote.values())[0]["last_price"])
        step = config["strike_step"]
        ce_opts = resolve_fn(symbol, current_spot, step, "CE", 0)
        pe_opts = resolve_fn(symbol, current_spot, step, "PE", 0)
        ce_map = {c["strike"]: c for c in ce_opts}
        pe_map = {p["strike"]: p for p in pe_opts}
        for strike in sorted(set(ce_map) & set(pe_map)):
            ce, pe = ce_map[strike], pe_map[strike]
            for side, opt in [("CE", ce), ("PE", pe)]:
                df_e = pd.DataFrame(kite.historical_data(opt["token"], from_d, to_d, timeframe_entry))
                df_a = pd.DataFrame(kite.historical_data(opt["token"], from_d, to_d, timeframe_anchor))
                if len(df_e) < 5 or len(df_a) < 5:
                    continue
                result = scan_anchor_bcd_breakout(df_e, df_a)
                if result:
                    return {"SL": result["SL"], "T1": result["T1"], "T2": result["T2"], "T3": result["T3"], "pattern": result["Pattern"], "side": side, "strike": strike}
                anchor_scanners = [find_anchor_bullish_engulfing, find_anchor_ll_sweep, find_anchor_hammer_baby, find_anchor_bullish_harami, find_anchor_two_higher_highs]
                for scanner in anchor_scanners:
                    res = scanner(df_a)
                    if res:
                        t1, t2, t3 = find_profit_targets(df_a, entry_price, stop_loss=res.get("SL"))
                        if t1:
                            return {"SL": res["SL"], "T1": t1, "T2": t2, "T3": t3, "pattern": res["Pattern"], "side": side, "strike": strike}
        return None
    except Exception as e:
        logging.warning(f"SL/Target derivation failed for {symbol}: {e}")
        return None

def reconcile_positions(kite, registry, positions_dict, lock, engine, timeframe_entry, timeframe_anchor, lookback_days, resolve_fn, save_state_fn=None):
    """Cross-reference ACTIVE_POSITIONS against Kite open positions and DB."""
    today = dt.now().strftime("%Y-%m-%d")
    kite_symbols = set()
    try:
        kite_pos = kite.positions()
        for plist in [kite_pos.get("day", []), kite_pos.get("net", [])]:
            for p in plist:
                sym = next((s for s in registry if s in p.get("tradingsymbol", "")), None)
                if sym and abs(int(p.get("quantity", 0))) > 0:
                    kite_symbols.add(sym)
    except Exception as e:
        logging.warning(f"Kite position fetch for reconciliation failed: {e}")
    import trade_db
    db_active = {t["symbol"] for t in trade_db.get_active_trades(engine) if t.get("symbol") in registry}
    with lock:
        stale_zero = [s for s, p in list(positions_dict.items())
                      if p.get("pattern") == "KITE_RECOVERED"
                      and p.get("position_type") != "stock"
                      and (p.get("entry_spot") or 0) == 0
                      and (p.get("current_sl") or 0) == 0]
        for s in stale_zero:
            logging.info(f"[RECONCILE] Removing stale KITE_RECOVERED ghost: {s}")
            tid = positions_dict[s].get("trade_id")
            if tid:
                try: trade_db.remove_trades([tid])
                except Exception: pass
            positions_dict.pop(s, None)
        if stale_zero:
            logging.info(f"[RECONCILE] Purged {len(stale_zero)} ghost positions")
        stale = [s for s in positions_dict if s not in registry] + \
                [s for s in positions_dict if s in registry and s not in kite_symbols and s not in db_active]
        for s in stale:
            pos = positions_dict[s]
            tid = pos.get("trade_id")
            logging.info(f"[RECONCILE] Removing stale position: {s}")
            if tid:
                trade_db.remove_trades([tid])
            positions_dict.pop(s, None)
        for s, pos in list(positions_dict.items()):
            now_str = dt.now().isoformat()
            if "entry_time" not in pos:
                pos["entry_time"] = now_str
            entry_date = pos["entry_time"][:10] if isinstance(pos["entry_time"], str) else today
            pos["carry_forward"] = entry_date < today
            if (pos.get("current_sl") or 0) == 0 or (pos.get("t1") or 0) == 0:
                db_found = False
                contract = pos.get("contract", "")
                if contract:
                    all_trades = trade_db.get_all_trades(engine)
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
                    config = registry.get(s)
                    if config:
                        result = derive_sl_targets_for_symbol(kite, s, pos.get("entry_spot", 0), registry, timeframe_entry, timeframe_anchor, lookback_days, resolve_fn)
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
    SL_TARGET_OVERRIDES_FILE = os.path.join("output", "monitor", "sl_target_overrides.json")
    if os.path.exists(SL_TARGET_OVERRIDES_FILE):
        try:
            with open(SL_TARGET_OVERRIDES_FILE) as f:
                eng_overrides = json.load(f).get(engine, {})
            for sym, vals in eng_overrides.items():
                if sym in positions_dict:
                    for k in ("current_sl", "t1", "t2", "t3"):
                        if k in vals:
                            positions_dict[sym][k] = vals[k]
                    tid = positions_dict[sym].get("trade_id")
                    if tid:
                        trade_db.update_trade(tid, {k: positions_dict[sym][k] for k in ("current_sl", "t1", "t2", "t3") if k in positions_dict[sym]})
                    logging.info(f"[RECONCILE] Re-applied override for {sym}: SL={positions_dict[sym].get('current_sl')} T1={positions_dict[sym].get('t1')}")
        except Exception as e:
            logging.warning(f"Override re-apply failed: {e}")
    if save_state_fn:
        save_state_fn()

def scan_symbol(kite, symbol, config, from_entry, to_entry, from_anchor, to_anchor,
                entry_scanners, anchor_scanners, resolve_fn, engine_name,
                timeframe_entry, timeframe_anchor, timeframe_fallback,
                active_positions, position_lock, trade_db, strike_range,
                log_fn):
    trades = []
    try:
        spot_quote = kite.ltp([config["token"]])
        current_spot = float(list(spot_quote.values())[0]["last_price"])
    except Exception:
        try:
            df_spot = pd.DataFrame(kite.historical_data(config["token"], from_entry, to_entry, timeframe_entry))
            if df_spot.empty:
                return []
            current_spot = float(df_spot.iloc[-1]['close'])
        except Exception as e:
            logging.warning(f"Spot data failed for {symbol}: {e}")
            return []
    ce_list = resolve_fn(symbol, current_spot, config['strike_step'], "CE", strike_range)
    pe_list = resolve_fn(symbol, current_spot, config['strike_step'], "PE", strike_range)
    ce_map = {c["strike"]: c for c in ce_list}
    pe_map = {p["strike"]: p for p in pe_list}
    for strike in sorted(set(ce_map) & set(pe_map)):
        ce = ce_map[strike]
        pe = pe_map[strike]
        same_tf = timeframe_entry == timeframe_anchor and from_entry == from_anchor and to_entry == to_anchor
        dfs = {}
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                tasks = {
                    pool.submit(kite.historical_data, ce["token"], from_entry, to_entry, timeframe_entry): ("ce", "entry"),
                    pool.submit(kite.historical_data, pe["token"], from_entry, to_entry, timeframe_entry): ("pe", "entry"),
                }
                if not same_tf:
                    tasks[pool.submit(kite.historical_data, ce["token"], from_anchor, to_anchor, timeframe_anchor)] = ("ce", "anchor")
                    tasks[pool.submit(kite.historical_data, pe["token"], from_anchor, to_anchor, timeframe_anchor)] = ("pe", "anchor")
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
        if same_tf:
            dfs[("ce", "anchor")] = dfs.get(("ce", "entry"), pd.DataFrame())
            dfs[("pe", "anchor")] = dfs.get(("pe", "entry"), pd.DataFrame())
        for tag_key, kind_key, from_d, to_d in [
            ("ce", "entry", from_entry, to_entry),
            ("pe", "entry", from_entry, to_entry),
            ("ce", "anchor", from_anchor, to_anchor),
            ("pe", "anchor", from_anchor, to_anchor),
        ]:
            if same_tf and kind_key == "anchor":
                continue
            df = dfs.get((tag_key, kind_key), pd.DataFrame())
            if len(df) < 5:
                tok = ce["token"] if tag_key == "ce" else pe["token"]
                tf = timeframe_entry if kind_key == "entry" else timeframe_anchor
                dfs[(tag_key, kind_key)] = fetch_option_data(kite, tok, from_d, to_d, tf, timeframe_fallback)
        if same_tf:
            dfs[("ce", "anchor")] = dfs.get(("ce", "entry"), pd.DataFrame())
            dfs[("pe", "anchor")] = dfs.get(("pe", "entry"), pd.DataFrame())
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
                candle_time = str(result_ce.get("CandleTime") or df_ce_e.iloc[-1]['date'])
                if result_ce["Close"] < 300 and result_ce["T1"] > result_ce["Close"] * 5:
                    log_fn(ce['tradingsymbol'], result_ce["Pattern"], timeframe_entry,
                           "SCAN_MATCH", "NO_TARGETS", "Stale ITM regime targets",
                           entry=result_ce["Close"], sl=result_ce["SL"],
                           target=0, rr=0, event_time=candle_time)
                    matched = True
                    break
                key = f"{symbol}|{result_ce['Pattern']}|CE|{strike}"
                if trade_db.is_pattern_executed(engine_name, key):
                    logging.info(f"CE MATCH already executed (skip): {ce['tradingsymbol']} | {result_ce['Pattern']}")
                    matched = True
                    break
                pos_size = calculate_position_size(current_spot, result_ce["SL"])
                rr_str = f"RR: {result_ce['RR']}" if result_ce.get('RR') else ""
                candle_a_time = str(result_ce.get("CandleATime", ""))
                logging.info(f"CYCLE MATCH staged: {ce['tradingsymbol']} | {result_ce['Pattern']} | CE | Strike {strike} | Size: {pos_size} | Entry: {result_ce['Close']:.2f} | SL: {result_ce['SL']:.2f} | T1: {result_ce['T1']} | T2: {result_ce['T2']} | T3: {result_ce['T3']} | RR: {result_ce.get('RR', '')} | A:{candle_a_time} D:{candle_time}")
                trade_data = {
                    "symbol": symbol, "contract": ce['tradingsymbol'], "option_token": ce['token'],
                    "index_token": config["token"], "strike": strike, "entry_spot": result_ce["Close"],
                    "current_sl": result_ce["SL"], "t1": result_ce["T1"], "t2": result_ce["T2"],
                    "t3": result_ce["T3"], "rr": result_ce.get("RR"), "trailing_stage": 0,
                    "lot_size": config["lot_size"], "position_size": pos_size,
                    "pattern": result_ce["Pattern"], "timeframe": timeframe_entry, "side": "CE",
                    "strike_step": config["strike_step"], "entry_time": candle_time,
                    "candle_a_time": candle_a_time
                }
                trade_db.stage_cycle_trade(engine_name, trade_data)
                trades.append(trade_data)
                log_fn(ce['tradingsymbol'], result_ce['Pattern'], timeframe_entry,
                       "SCAN_MATCH", "STAGED", f"Side=CE Strike={strike} RR={result_ce.get('RR','')}",
                       entry=result_ce['Close'], sl=result_ce['SL'],
                       target=result_ce.get('T3',''), rr=result_ce.get('RR',''),
                       event_time=candle_time)
                matched = True
                break
            result_pe = scanner(df_pe_e, df_pe_a)
            if result_pe:
                candle_time = str(result_pe.get("CandleTime") or df_pe_e.iloc[-1]['date'])
                if result_pe["Close"] < 300 and result_pe["T1"] > result_pe["Close"] * 5:
                    log_fn(pe['tradingsymbol'], result_pe["Pattern"], timeframe_entry,
                           "SCAN_MATCH", "NO_TARGETS", "Stale ITM regime targets",
                           entry=result_pe["Close"], sl=result_pe["SL"],
                           target=0, rr=0, event_time=candle_time)
                    matched = True
                    break
                key = f"{symbol}|{result_pe['Pattern']}|PE|{strike}"
                if trade_db.is_pattern_executed(engine_name, key):
                    logging.info(f"PE MATCH already executed (skip): {pe['tradingsymbol']} | {result_pe['Pattern']}")
                    matched = True
                    break
                pos_size = calculate_position_size(current_spot, result_pe["SL"])
                candle_a_time = str(result_pe.get("CandleATime", ""))
                logging.info(f"CYCLE MATCH staged: {pe['tradingsymbol']} | {result_pe['Pattern']} | PE | Strike {strike} | Size: {pos_size} | Entry: {result_pe['Close']:.2f} | SL: {result_pe['SL']:.2f} | T1: {result_pe['T1']} | T2: {result_pe['T2']} | T3: {result_pe['T3']} | RR: {result_pe.get('RR', '')} | A:{candle_a_time} D:{candle_time}")
                trade_data = {
                    "symbol": symbol, "contract": pe['tradingsymbol'], "option_token": pe['token'],
                    "index_token": config["token"], "strike": strike, "entry_spot": result_pe["Close"],
                    "current_sl": result_pe["SL"], "t1": result_pe["T1"], "t2": result_pe["T2"],
                    "t3": result_pe["T3"], "rr": result_pe.get("RR"), "trailing_stage": 0,
                    "lot_size": config["lot_size"], "position_size": pos_size,
                    "pattern": result_pe["Pattern"], "timeframe": timeframe_entry, "side": "PE",
                    "strike_step": config["strike_step"], "entry_time": candle_time,
                    "candle_a_time": candle_a_time
                }
                trade_db.stage_cycle_trade(engine_name, trade_data)
                trades.append(trade_data)
                log_fn(pe['tradingsymbol'], result_pe['Pattern'], timeframe_entry,
                       "SCAN_MATCH", "STAGED", f"Side=PE Strike={strike} RR={result_pe.get('RR','')}",
                       entry=result_pe['Close'], sl=result_pe['SL'],
                       target=result_pe.get('T3',''), rr=result_pe.get('RR',''),
                       event_time=candle_time)
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


def monitor_active_positions(kite, registry, positions_dict, lock, product_type, engine_name,
                              timeframe_entry, trade_db, log_fn, save_state_fn=None,
                              live=True):
    from_date = (dt.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    to_date = dt.now().strftime("%Y-%m-%d")
    to_clear = []
    with lock:
        for sym, pos in positions_dict.items():
            try:
                token = pos.get("option_token") or registry.get(sym, {}).get("token")
                if not token:
                    continue
                df = pd.DataFrame(kite.historical_data(token, from_date, to_date, timeframe_entry))
                if df.empty:
                    continue
                last = df.iloc[-1]
                cp = float(last['close'])
                hp = float(last['high'])
                tid = pos.get("trade_id")
                is_stock = pos.get("position_type") == "stock"
                sl_hit = cp <= pos.get("current_sl", 0)
                if sl_hit:
                    logging.warning(f"SL: {sym} at {cp}")
                    if is_stock:
                        close_stock_position(kite, pos, live, product_type)
                    else:
                        close_position(kite, pos, live, product_type)
                    entry_s = pos.get("entry_spot", 0)
                    pnl = ((cp - entry_s) / entry_s * 100) if entry_s else 0
                    log_fn(sym, pos.get("pattern", ""), timeframe_entry, "EXIT_SL", "CLOSED",
                           f"SL hit: {cp}", pnl,
                           entry=entry_s, sl=pos.get("current_sl", 0), target=pos.get("t1", ""),
                           event_time=last.get('date'))
                    if tid:
                        trade_db.update_trade(tid, {"status": "SL_HIT", "exit_time": dt.now().strftime("%Y-%m-%d %H:%M:%S"), "pnl_percent": round(pnl, 2)})
                    to_clear.append(sym)
                    continue
                if pos.get("trailing_stage", 0) == 0 and pos.get("t1") and hp >= pos["t1"]:
                    pos["current_sl"] = pos.get("entry_spot", 0)
                    pos["trailing_stage"] = 1
                    logging.info(f"TRAIL-1 {sym}: SL=BE ({pos['current_sl']:.2f})")
                    log_fn(sym, pos.get("pattern", ""), timeframe_entry, "TRAIL_BE", "MUTATED",
                           f"SL={pos['current_sl']:.2f}",
                           entry=pos.get("entry_spot", 0), sl=pos["current_sl"], target=pos.get("t1", ""),
                           event_time=last.get('date'))
                    if tid:
                        trade_db.update_trade(tid, {"trailing_stage": 1, "current_sl": pos["current_sl"]})
                elif pos.get("trailing_stage", 0) == 1 and pos.get("t2") and hp >= pos["t2"]:
                    pos["current_sl"] = pos.get("t1", 0)
                    pos["trailing_stage"] = 2
                    logging.info(f"TRAIL-2 {sym}: SL=T1 ({pos['current_sl']:.2f})")
                    log_fn(sym, pos.get("pattern", ""), timeframe_entry, "TRAIL_T1", "MUTATED",
                           f"SL={pos['current_sl']:.2f}",
                           entry=pos.get("entry_spot", 0), sl=pos["current_sl"], target=pos.get("t2", ""),
                           event_time=last.get('date'))
                    if tid:
                        trade_db.update_trade(tid, {"trailing_stage": 2, "current_sl": pos["current_sl"]})
                if pos.get("t3") and hp >= pos["t3"]:
                    logging.info(f"T3: {sym} at {pos['t3']}")
                    if pos.get("position_type") == "stock":
                        close_stock_position(kite, pos, live, product_type)
                    else:
                        close_position(kite, pos, live, product_type)
                    entry_s = pos.get("entry_spot", 0)
                    pnl = ((pos["t3"] - entry_s) / entry_s * 100) if entry_s else 0
                    log_fn(sym, pos.get("pattern", ""), timeframe_entry, "EXIT_T3", "CLOSED",
                           f"T3={pos['t3']}", pnl,
                           entry=entry_s, sl=pos.get("current_sl", ""), target=pos["t3"],
                           event_time=last.get('date'))
                    if tid:
                        trade_db.update_trade(tid, {"status": "TARGET_HIT", "exit_time": dt.now().strftime("%Y-%m-%d %H:%M:%S"), "pnl_percent": round(pnl, 2)})
                    to_clear.append(sym)
            except Exception as e:
                logging.error(f"Risk error {sym}: {e}")
        for s in to_clear:
            positions_dict.pop(s, None)
    if to_clear and save_state_fn:
        save_state_fn()


def simulate_trade_outcome(kite, trade, target_date, resolve_token_fn=None):
    try:
        sym = trade["symbol"]
        cp = trade["entry_spot"]
        side = trade.get("side", "CE")
        strike = trade.get("strike")
        strike_step = trade.get("strike_step", 50)
        token = trade.get("option_token")
        if not token and resolve_token_fn:
            target_strike = strike or int(round(cp / strike_step) * strike_step)
            opt_type = "CE" if side == "CE" else "PE"
            contract = resolve_token_fn(sym, cp, strike_step, opt_type, target_strike)
            if not contract:
                return {"result": None, "detail": "option_resolve_failed", "entry_time": None, "exit_time": None, "pnl_pct": None}
            token = contract
        if not token:
            return {"result": None, "detail": "no_token", "entry_time": None, "exit_time": None, "pnl_pct": None}
        entry = cp
        sl_val = trade["current_sl"]
        t1 = trade.get("t1")
        t2 = trade.get("t2")
        t3 = trade.get("t3")
        expiry_limit = target_date + timedelta(days=14)
        tf = trade.get("timeframe", "15minute") or "15minute"
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
                return {"result": "SL_HIT", "detail": f"SL_HIT at {exit_time}", "entry_time": str(entry_time), "exit_time": str(exit_time), "pnl_pct": round(pnl, 2)}
            if t1 and high >= t1:
                exit_t = candle['date']
                if t3 and high >= t3:
                    pnl = (t3 - entry) / entry * 100
                    return {"result": "T3_HIT", "detail": f"T3_HIT at {exit_t}", "entry_time": str(entry_time), "exit_time": str(exit_t), "pnl_pct": round(pnl, 2)}
                if t2 and high >= t2:
                    pnl = (t2 - entry) / entry * 100
                    return {"result": "T2_HIT", "detail": f"T2_HIT at {exit_t}", "entry_time": str(entry_time), "exit_time": str(exit_t), "pnl_pct": round(pnl, 2)}
                pnl = (t1 - entry) / entry * 100
                return {"result": "T1_HIT", "detail": f"T1_HIT at {exit_t}", "entry_time": str(entry_time), "exit_time": str(exit_t), "pnl_pct": round(pnl, 2)}
        return {"result": "NO_EXIT", "detail": "No SL or target hit before expiry", "entry_time": str(entry_time), "exit_time": None, "pnl_pct": None}
    except Exception as e:
        logging.error(f"[SIM] Exception: {e}")
        return {"result": None, "detail": str(e), "entry_time": None, "exit_time": None, "pnl_pct": None}


def resolve_option_strikes(nfo_instruments, base_symbol, spot_price, step_size, option_type, n_range=0):
    """Return ATM strike plus n_range strikes ITM/OTM. nfo_instruments can be None for derived calls."""
    if nfo_instruments is None:
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
            df = nfo_instruments[
                (nfo_instruments['name'] == base_symbol.strip().upper()) &
                (nfo_instruments['instrument_type'] == option_type.upper()) &
                (nfo_instruments['strike'] == float(strike))
            ].copy()
            if df.empty:
                continue
            df = df.sort_values(by='expiry')
            c = df.iloc[0]
            out.append({"strike": strike, "token": int(c['instrument_token']), "tradingsymbol": c['tradingsymbol']})
        except Exception as e:
            logging.error(f"Strike resolution error for {base_symbol} {option_type} @ {strike}: {e}")
            continue
    return out

