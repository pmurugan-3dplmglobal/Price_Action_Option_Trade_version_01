import os
import json
import logging
import time
import sys
import threading
import csv
from datetime import datetime as dt, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import numpy as np

from kiteconnect import KiteConnect

LOOKBACK_DAYS = 120
TOKEN_FILE = "input/kite_access_token.txt"
TIMEFRAME_ENTRY = "day"
TIMEFRAME_ANCHOR = "day"

OUTPUT_FILE = f"output/exports/Nifty50_Daily_Scan_{dt.now().strftime('%Y%m%d_%H%M')}.xlsx"

ACTIVE_POSITIONS = {}
position_lock = threading.Lock()
ANCHOR_SCAN_REQUEST_FILE = os.path.join("output", "monitor", "anchor_scan_request.txt")
ANCHOR_SCAN_STOP_FILE = os.path.join("output", "monitor", "anchor_scan_stop.txt")

journal_lock = threading.Lock()
JOURNAL_FILE = "output/monitor/trade_journal.csv"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("output/logs/bull_daily_scanner.log", mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

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

SUPER_STOCKS = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY",
    "ITC", "SBIN", "BHARTIARTL", "LT", "WIPRO"
]

STOCK_REGISTRY = {
    "ADANIENT": {"token": 112129},
    "ADANIPORTS": {"token": 3861249},
    "APOLLOHOSP": {"token": 415745},
    "ASIANPAINT": {"token": 60417},
    "AXISBANK": {"token": 1510401},
    "BAJAJ-AUTO": {"token": 4267777},
    "BAJAJFINSV": {"token": 4268545},
    "BAJFINANCE": {"token": 81153},
    "BEL": {"token": 54017},
    "BHARTIARTL": {"token": 2714625},
    "CIPLA": {"token": 177665},
    "COALINDIA": {"token": 5215745},
    "DRREDDY": {"token": 225537},
    "EICHERMOT": {"token": 232961},
    "GRASIM": {"token": 315393},
    "HCLTECH": {"token": 1837313},
    "HDFCBANK": {"token": 341249},
    "HDFCLIFE": {"token": 119553},
    "HEROMOTOCO": {"token": 345089},
    "HINDALCO": {"token": 348417},
    "HINDUNILVR": {"token": 3404801},
    "ICICIBANK": {"token": 1270529},
    "INDIGO": {"token": 2865921},
    "INFY": {"token": 408065},
    "ITC": {"token": 424961},
    "JIOFIN": {"token": 21806081},
    "JSWSTEEL": {"token": 3001857},
    "KOTAKBANK": {"token": 492033},
    "LT": {"token": 2939649},
    "M&M": {"token": 519937},
    "MARUTI": {"token": 2800641},
    "NESTLEIND": {"token": 4543233},
    "NTPC": {"token": 2977281},
    "ONGC": {"token": 633601},
    "POWERGRID": {"token": 3834113},
    "RELIANCE": {"token": 738561},
    "SBILIFE": {"token": 5633},
    "SBIN": {"token": 7795201},
    "SHRIRAMFIN": {"token": 3184129},
    "SUNPHARMA": {"token": 857857},
    "TATACONSUM": {"token": 3465729},
    "TATASTEEL": {"token": 897537},
    "TCS": {"token": 2953217},
    "TECHM": {"token": 3418369},
    "TITAN": {"token": 895745},
    "TRENT": {"token": 5064961},
    "ULTRACEMCO": {"token": 2952193},
    "WIPRO": {"token": 969473}
}

# ──────────────────────────────────────────────
#  SESSION & DATA LOADING
# ──────────────────────────────────────────────

def load_kite_session():
    if not os.path.exists(TOKEN_FILE):
        raise FileNotFoundError("Token file missing. Run Kite_Access_Token_gen.py first.")
    with open(TOKEN_FILE) as f:
        data = json.load(f)
    if not data.get("api_key") or not data.get("access_token"):
        raise ValueError("Corrupted token file.")
    return data["api_key"], data["access_token"]

# ──────────────────────────────────────────────
#  UTILITY FUNCTIONS
# ──────────────────────────────────────────────

def check_left_side(df, anchor_low, count, skip_adjacent=2):
    left = df.iloc[:-(count + skip_adjacent)] if len(df) > count + skip_adjacent else pd.DataFrame()
    if not left.empty and anchor_low > float(left['close'].min()):
        return False
    return True

def find_profit_targets(df_hist, spot_close):
    hist = df_hist.copy()
    t1 = t2 = t3 = None
    for i in range(len(hist) - 3, 2, -1):
        w = hist.iloc[i-2:i+3]
        if len(w) == 5 and hist.iloc[i]['low'] == w['low'].min():
            s = float(hist.iloc[i]['low'])
            sub = hist.iloc[i+1:]
            if not sub.empty and (sub['close'] < s).any() and s > spot_close:
                t1 = s
                break
    if len(hist) > 0:
        ll = hist['low'].idxmin()
        pre = hist.loc[:ll]
        if len(pre) > 0:
            p = float(pre['high'].max())
            if p > spot_close:
                t2 = p
    swing = None
    for i in range(len(hist) - 3, 2, -1):
        w = hist.iloc[i-2:i+3]
        if len(w) == 5 and hist.iloc[i]['high'] == w['high'].max():
            p = float(hist.iloc[i]['high'])
            if p > spot_close:
                swing = p
                break
    for i in range(len(hist) - 1, 2, -1):
        if hist.iloc[i]['close'] < hist.iloc[i]['open'] and (hist.iloc[i]['open'] - hist.iloc[i]['close']) > (hist.iloc[i-1]['high'] - hist.iloc[i-1]['low']):
            p = float(hist.iloc[i]['high'])
            if p > spot_close:
                t3 = p
                break
    if t2 is not None and swing is not None and swing > t2:
        if t3 is None or swing > t3:
            t3 = swing
    if t1 is None or t1 <= spot_close:
        return None, None, None
    if t2 is not None and t2 <= t1:
        t2 = None
    if t3 is not None:
        if t2 is None and t3 <= t1:
            t3 = None
        elif t2 is not None and t3 <= t2:
            t3 = None
    return t1, t2, t3

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
        if not check_left_side(df_entry, invalidation, lookback, 2):
            continue
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

def run_scan(kite):
    from_date = (dt.now() - timedelta(days=min(LOOKBACK_DAYS, 2000))).strftime("%Y-%m-%d")
    to_date = dt.now().strftime("%Y-%m-%d")
    scanners = [
        ("S1_ABC", scan_abc_reversal),
    ]
    results = []
    results_lock = threading.Lock()
    scan_order = SUPER_STOCKS + [s for s in STOCK_REGISTRY if s not in SUPER_STOCKS]
    logging.info(f"Scanning {len(scan_order)} stocks with 8 parallel workers...")
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {}
        for symbol in scan_order:
            config = STOCK_REGISTRY[symbol]
            futures[pool.submit(
                lambda cfg=config: pd.DataFrame(kite.historical_data(cfg["token"], from_date, to_date, TIMEFRAME_ENTRY))
            )] = symbol
        for f in as_completed(futures):
            symbol = futures[f]
            try:
                df_e = f.result()
            except Exception as e:
                logging.warning(f"Data error for {symbol}: {e}")
                with results_lock:
                    results.append({"Symbol": symbol, "Pattern": "ERROR", "Error": str(e)})
                continue
            if df_e.empty:
                with results_lock:
                    results.append({"Symbol": symbol, "Pattern": "NO_DATA"})
                continue
            df_a = df_e.copy()
            latest = df_e.iloc[-1]
            matched = False
            for name, scanner_func in scanners:
                result = scanner_func(df_e, df_a)
                if result:
                    result["Symbol"] = symbol
                    result["Scan_Date"] = dt.now().strftime("%Y-%m-%d")
                    result["Latest_Close"] = round(float(latest['close']), 2)
                    result["Latest_High"] = round(float(latest['high']), 2)
                    result["Latest_Low"] = round(float(latest['low']), 2)
                    result["Latest_Open"] = round(float(latest['open']), 2)
                    result["Volume"] = int(latest.get('volume', 0))
                    result["Pattern_Name"] = name
                    with results_lock:
                        results.append(result)
                    logging.info(f"  -> MATCH: {symbol} | {result['Pattern']} | Entry: {result['Close']:.2f} | SL: {result['SL']:.2f} | T1: {result['T1']:.2f} | RR: {result['RR']:.2f}")
                    log_to_journal(symbol, result["Pattern"], TIMEFRAME_ENTRY,
                                   "SCAN_MATCH", "MATCHED",
                                   f"Entry={result['Close']:.2f} SL={result['SL']:.2f} RR={result['RR']:.2f}",
                                   entry=result['Close'], sl=result['SL'],
                                   target=result.get('T3',''), rr=result['RR'])
                    matched = True
                    break
            if not matched:
                with results_lock:
                    results.append({"Symbol": symbol, "Pattern": "NO_MATCH"})
    return results

def export_to_excel(results):
    rows = []
    for r in results:
        rows.append({
            "Symbol": r.get("Symbol", ""),
            "Pattern": r.get("Pattern", ""),
            "Entry": r.get("Close", ""),
            "Stop_Loss": r.get("SL", ""),
            "T1": r.get("T1", ""),
            "T2": r.get("T2", ""),
            "T3": r.get("T3", ""),
            "R_R_Ratio": round(r.get("RR", 0), 2) if r.get("RR") else "",
            "Latest_Close": r.get("Latest_Close", ""),
            "Latest_High": r.get("Latest_High", ""),
            "Latest_Low": r.get("Latest_Low", ""),
            "Latest_Open": r.get("Latest_Open", ""),
            "Volume": r.get("Volume", ""),
            "Error": r.get("Error", ""),
            "Scan_Date": r.get("Scan_Date", "")
        })
    df = pd.DataFrame(rows)
    try:
        with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Daily_Scan_Results", index=False)
            ws = writer.sheets["Daily_Scan_Results"]
            for col in ws.columns:
                max_len = max(len(str(cell.value or "")) for cell in col) + 2
                ws.column_dimensions[col[0].column_letter].width = min(max_len, 25)
            ws.auto_filter.ref = ws.dimensions
    except Exception as e:
        logging.error(f"Excel export failed: {e}. Saving as CSV instead.")
        csv_file = OUTPUT_FILE.replace(".xlsx", ".csv")
        df.to_csv(csv_file, index=False)
        return csv_file
    return OUTPUT_FILE

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

def run_anchor_scan(kite):
    logging.info("Anchor scan requested (daily) - executing analysis...")
    
    limits = {"minute": 55, "3minute": 90, "5minute": 160}
    max_days = limits.get(TIMEFRAME_ANCHOR, 180)
    from_date = (dt.now() - timedelta(days=min(LOOKBACK_DAYS, max_days))).strftime("%Y-%m-%d")
    to_date = dt.now().strftime("%Y-%m-%d")
    
    scanners = [
        ("S1", find_anchor_bullish_engulfing),
        ("S2", find_anchor_ll_sweep),
        ("S3", find_anchor_hammer_baby),
        ("S4", find_anchor_bullish_harami),
    ]
    
    scan_order = STOCK_REGISTRY.keys()
    
    for symbol in scan_order:
        if os.path.exists(ANCHOR_SCAN_STOP_FILE):
            logging.info("Anchor scan stopped by user")
            os.remove(ANCHOR_SCAN_STOP_FILE)
            return
            
        config = STOCK_REGISTRY[symbol]
        with position_lock:
            if symbol in ACTIVE_POSITIONS:
                continue
                
        try:
            df = pd.DataFrame(kite.historical_data(config["token"], from_date, to_date, TIMEFRAME_ANCHOR))
        except Exception as e:
            logging.warning(f"Anchor data failed for {symbol}: {e}")
            continue
            
        if df.empty:
            continue
            
        for name, scanner in scanners:
            result = scanner(df)
            if result:
                logging.info(f"ANCHOR MATCH: {symbol} | {result['Pattern']} | Close: {result['Close']}")
                log_to_journal(symbol, result["Pattern"], TIMEFRAME_ANCHOR,
                               "ANCHOR_SCAN", "SCANNED", "A formation from anchor scan",
                               entry=result["Close"], sl=result["SL"], target="")
                break
            
        time.sleep(0.5)
    
    logging.info("Anchor scan complete (daily)")

def print_summary(results):
    matches = [r for r in results if r.get("T1")]
    no_match = [r for r in results if r.get("Pattern") == "NO_MATCH"]
    errors = [r for r in results if r.get("Pattern") == "ERROR"]
    print("\n" + "=" * 80)
    print(f"  NIFTY 50 DAILY SCAN SUMMARY")
    print(f"  Scan Time: {dt.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print(f"  Total Stocks Scanned: {len(results)}")
    print(f"  Pattern Matches:     {len(matches)}")
    print(f"  No Match:            {len(no_match)}")
    print(f"  Errors:              {len(errors)}")
    print("-" * 80)
    if matches:
        print(f"\n  {'Symbol':<12} {'Pattern':<20} {'Entry':<10} {'SL':<10} {'T1':<10} {'T2':<10} {'RR':<8}")
        print(f"  {'-'*12} {'-'*20} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*8}")
        for m in sorted(matches, key=lambda x: x.get("RR", 0), reverse=True):
            rr = round(m["RR"], 2) if m.get("RR") else 0
            print(f"  {m['Symbol']:<12} {m['Pattern']:<20} {m['Close']:<10.2f} {m['SL']:<10.2f} {m['T1']:<10.2f} {m['T2']:<10.2f} {rr:<8.2f}")
    print("=" * 80)

def load_program_config():
    try:
        cfg_path = os.path.join(os.path.dirname(__file__), "input", "program_config.json")
        if os.path.exists(cfg_path):
            with open(cfg_path) as f:
                cfg = json.load(f).get("daily", {})
            if "timeframe" in cfg:
                globals().update({"TIMEFRAME_ENTRY": cfg["timeframe"], "TIMEFRAME_ANCHOR": cfg["timeframe"]})
            if "lookback_days" in cfg: globals().update({"LOOKBACK_DAYS": int(cfg["lookback_days"])})
    except Exception as e:
        logging.warning(f"Config load: {e}")

def main():
    load_program_config()
    anchor_only = "--anchor-only" in sys.argv
    logging.info("=" * 60)
    logging.info("  NIFTY 50 DAILY TIMEFRAME SCANNER")
    logging.info("=" * 60)
    try:
        ak, at = load_kite_session()
        kite = KiteConnect(api_key=ak)
        kite.set_access_token(at)
        if anchor_only:
            logging.info("Running anchor-only scan (daily)...")
            run_anchor_scan(kite)
            return
        logging.info(f"Scanning {len(STOCK_REGISTRY)} stocks on daily timeframe...")
        logging.info(f"Lookback: {LOOKBACK_DAYS} days")
        
        if os.path.exists(ANCHOR_SCAN_REQUEST_FILE):
            try:
                with open(ANCHOR_SCAN_REQUEST_FILE) as f:
                    engine = f.read().strip()
                os.remove(ANCHOR_SCAN_REQUEST_FILE)
                if engine != "daily":
                    logging.info(f"Anchor scan flag not for daily, skipping (got {engine})")
                else:
                    logging.info(f"Anchor scan requested via flag file (engine: {engine})")
                    run_anchor_scan(kite)
            except Exception:
                pass
        
        results = run_scan(kite)
        print_summary(results)
        out = export_to_excel(results)
        logging.info(f"Results exported to: {os.path.abspath(out)}")
        print(f"\n  Report saved: {os.path.abspath(out)}")
        print()
    except Exception as e:
        logging.error(f"Scanner failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
