# Common Equity Universe & Liquidity Shield Manager
import logging
import pandas as pd

# ──────────────────────────────────────────────
#  PREDEFINED NSE INDICES CONSTITUENTS
# ──────────────────────────────────────────────

NIFTY50_SYMBOLS = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJAJFINSV", "BAJFINANCE", "BEL", "BHARTIARTL",
    "BPCL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY",
    "EICHERMOT", "ETERNAL", "GRASIM", "HCLTECH", "HDFCBANK",
    "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK",
    "INDUSINDBK", "INFY", "ITC", "JWSSTEEL", "KOTAKBANK",
    "LT", "LTIM", "M&M", "MARUTI", "NESTLEIND",
    "NTPC", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE",
    "SBIN", "SHRIRAMFIN", "SUNPHARMA", "TATACONSUM", "TATAMOTORS",
    "TATASTEEL", "TCS", "TECHM", "TITAN", "ULTRACEMCO", "WIPRO"
]

NIFTY_NEXT100_SYMBOLS = [
    "ABB", "ACC", "ADANIENSOL", "ADANIGREEN", "ADANIPOWER",
    "ATGL", "AMBUJACEM", "BANKBARODA", "BERGEPAINT", "BOSCHLTD",
    "CANBK", "CHOLAFIN", "COLPAL", "DLF", "DMART",
    "GAIL", "GODREJCP", "HAL", "HAVELLES", "ICICIGI",
    "ICICIPRULI", "IOC", "IRCTC", "IRFC", "JINDALSTEL",
    "JIOFIN", "LODHA", "MAXHEALTH", "NAUKRI", "NHPC",
    "NMDC", "OBEROIRLTY", "OIL", "PAYTM", "PFC",
    "PIDILITIND", "PNB", "RECLTD", "RVNL", "SIEMENS",
    "SRF", "TATAELXSI", "TATAPOWER", "TORNTPOWER", "TRENT",
    "TVSMOTOR", "UNITDSPR", "VBL", "VEDL", "ZYDUSLIFE"
]

NIFTY_MIDCAP100_SYMBOLS = [
    "AARTIIND", "ABCAPITAL", "ABFRL", "ALKEM", "APLAPOLLO",
    "ASTRAL", "AUROPHARMA", "BALKRISIND", "BANDHANBNK", "BHARATFORG",
    "BSOFT", "CGPOWER", "COFORGE", "CONCOR", "CUMMINSIND",
    "DALBHARAT", "DIXON", "ESCORTS", "FEDERALBNK", "FORTIS",
    "GLENMARK", "GMRINFRA", "GODREJPROP", "GUJGASLTD", "IDFCFIRSTB",
    "INDIANB", "INDHOTEL", "INDUSTOWER", "IPCALAB", "JISLJALEQS",
    "JUBLFOOD", "KEI", "KPITTECH", "LICHSGFIN", "LUPIN",
    "M&MFIN", "MFSL", "MPHASIS", "MRF", "MUTHOOTFIN",
    "NATIONALUM", "NAVINFLUOR", "OBEROIRLTY", "OFSS", "PAGEIND",
    "PERSISTENT", "PETRONET", "POLYCAB", "POONAWALLA", "PRESTIGE",
    "SAIL", "SCHAEFFLER", "SOLARINDS", "SONACOMS", "SUNDARMFIN",
    "SUPREMEIND", "SYNGENE", "TATACHEM", "TATACOMM", "TIINDIA",
    "TORNTPHARM", "VOLTAS", "WHIRLPOOL", "YESBANK", "ZEEL"
]

NIFTY_SMALLCAP250_SYMBOLS = [
    "ANGELONE", "APARINDS", "BECTORFOOD", "BATAINDIA", "BLUESTARCO",
    "CAMPUS", "CDSL", "CEATLTD", "CENTURYPLY", "CERA",
    "CESC", "CHAMBLFERT", "CIEINDIA", "CROMPTON", "CYIENT",
    "DATAPATTNS", "DEEPAKNTR", "DELHIVERY", "DEVYANI", "ECLERX",
    "EQUITASBNK", "EXIDEIND", "FINPIPE", "FIRSTSOURCE", "FIVESTAR",
    "GLS", "GNFC", "GODFRYPHLP", "GRANULES", "HAPPSTMNDS",
    "HFCL", "HOMEFIRST", "HONASA", "IDBI", "IIFL",
    "IEX", "INDRAMEDCO", "INTELLECT", "JBCHEPHARM", "JKCEMENT",
    "KAYNES", "KEC", "KALYANKJIL", "KARURVYSYA", "LALPATHLAB",
    "LATENTVIEW", "LEMONTREE", "LXCHEM", "MAPMYINDIA", "MASTEK",
    "METROPOLIS", "MINDACORP", "MSUMI", "NATCOPHARM", "NIPPONLIFE",
    "PRAJIND", "RADICO", "RAIRAIL", "ROUTE", "RITES",
    "SAPPDIR", "SONATSOFTW", "SUVENPHAR", "TANLA", "TATAINVEST",
    "UCOBANK", "UTIAMC", "VIPIND", "ZENSARTECH"
]

INDICES_REGISTRY_MAP = {
    "NIFTY50": NIFTY50_SYMBOLS,
    "NIFTY_NEXT_100": NIFTY_NEXT100_SYMBOLS,
    "NIFTY_MIDCAP_100": NIFTY_MIDCAP100_SYMBOLS,
    "NIFTY_SMALLCAP_250": NIFTY_SMALLCAP250_SYMBOLS
}

# ──────────────────────────────────────────────
#  LIQUIDITY & TURNOVER SHIELD
# ──────────────────────────────────────────────

def is_liquid_cash_stock(df, min_volume=500000, min_turnover_cr=10.0):
    """
    Evaluates whether a cash stock meets minimum daily volume and turnover shields
    to prevent illiquid slippage or low-cap trap setups.
    """
    if df is None or df.empty or len(df) < 5:
        return False
    try:
        avg_vol = float(df['volume'].tail(20).mean()) if 'volume' in df.columns else 0
        avg_close = float(df['close'].tail(20).mean()) if 'close' in df.columns else 0
        turnover_cr = (avg_vol * avg_close) / 10_000_000.0
        
        if avg_vol < min_volume and turnover_cr < min_turnover_cr:
            return False
        return True
    except Exception as e:
        logging.warning(f"Liquidity check exception: {e}")
        return True
