# utils.py
import requests
import pandas as pd
import time
from datetime import datetime
from typing import List, Optional
import math

# ---- CONFIG: nếu ONUS thay đổi, chỉ sửa BASE_URL ở đây ----
# Theo docs public ONUS spot docs: base endpoint dùng trong ví dụ là spot-markets.goonus.io
BASE_URLS = [
    "https://spot-markets.goonus.io",      # primary (thường thấy trong docs)
    "https://api.goonus.io",               # fallback candidates
    "https://spot.goonus.io"
]

# Endpoints we will try (constructed on BASE_URL)
PAIRS_PATHS = [
    "/trading-pairs-info/",   # common endpoint (Bitstamp-like)
    "/symbols",               # possible alternative
    "/public/symbols"
]

TRADES_PATH = "/trades"      # expects ?symbol_name=BTC_USDT
# Some onus docs show e.g. /trades?symbol_name=BTC_USDT

# Helper: try GET with retries
def safe_get(url, params=None, headers=None, timeout=10, max_retries=3, pause=1.0):
    for attempt in range(1, max_retries+1):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            if attempt == max_retries:
                raise
            time.sleep(pause * attempt)
    raise RuntimeError("safe_get unreachable")

# Get list of trading pairs from ONUS - try multiple endpoints and URL bases
def get_onus_pairs(limit=200) -> List[str]:
    pairs = []
    for base in BASE_URLS:
        for ppath in PAIRS_PATHS:
            url = base.rstrip("/") + ppath
            try:
                r = safe_get(url)
                data = r.json()
                # try multiple possible structures
                # 1) list of dicts with 'url_symbol' or 'symbol' or 'name'
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            if "url_symbol" in item:
                                pairs.append(item["url_symbol"])
                            elif "symbol" in item:
                                pairs.append(item["symbol"])
                            elif "name" in item:
                                pairs.append(item["name"])
                            elif "pair" in item:
                                pairs.append(item["pair"])
                elif isinstance(data, dict):
                    # some endpoints wrap results
                    if "data" in data and isinstance(data["data"], list):
                        for item in data["data"]:
                            if isinstance(item, dict):
                                if "url_symbol" in item:
                                    pairs.append(item["url_symbol"])
                                elif "symbol" in item:
                                    pairs.append(item["symbol"])
                # dedupe & return if found
                if pairs:
                    # normalize to uppercase and common style (e.g. BTC_USDT)
                    normalized = []
                    for p in pairs:
                        s = str(p).upper().replace("-", "_").replace("/", "_")
                        normalized.append(s)
                    normalized = list(dict.fromkeys(normalized))
                    return normalized[:limit]
            except Exception:
                continue
    # If nothing found, return empty list
    return []

# Fetch recent trades for a symbol
def fetch_trades(symbol: str, base_url=None, limit=1000):
    # symbol should be like BTC_USDT or BTC-USDT depending on API; try both
    if base_url is None:
        base_candidates = BASE_URLS
    else:
        base_candidates = [base_url]
    for base in base_candidates:
        for sep in ["_", "-", "/"]:
            sym = symbol.replace("_", sep).replace("-", sep).replace("/", sep)
            url = base.rstrip("/") + TRADES_PATH
            params = {"symbol_name": sym}
            try:
                r = safe_get(url, params=params)
                data = r.json()
                # Expecting list of trades or dict with data key
                if isinstance(data, dict) and "data" in data:
                    raw = data["data"]
                else:
                    raw = data
                # raw should be list of trade dicts with timestamp & price & amount
                df = pd.DataFrame(raw)
                # normalize potential fields
                if 'timestamp' in df.columns:
                    df['ts'] = pd.to_datetime(df['timestamp'], unit='s', origin='unix', errors='coerce')
                elif 'time' in df.columns:
                    # some endpoints return ISO time string
                    try:
                        df['ts'] = pd.to_datetime(df['time'])
                    except:
                        df['ts'] = None
                elif 'created_at' in df.columns:
                    df['ts'] = pd.to_datetime(df['created_at'])
                else:
                    # try to create ts from 'date' or 'trade_time'
                    df['ts'] = pd.to_datetime(df.iloc[:,0], errors='coerce')
                # price and amount column candidates
                price_cols = [c for c in df.columns if c.lower() in ("price","price_str","p")]
                amount_cols = [c for c in df.columns if c.lower() in ("amount","qty","quantity","volume")]
                if price_cols:
                    df['price'] = pd.to_numeric(df[price_cols[0]], errors='coerce')
                else:
                    df['price'] = pd.to_numeric(df.get('price', None), errors='coerce')
                if amount_cols:
                    df['amount'] = pd.to_numeric(df[amount_cols[0]], errors='coerce')
                else:
                    df['amount'] = pd.to_numeric(df.get('amount', None), errors='coerce')
                # drop rows without timestamp or price
                df = df.dropna(subset=['ts','price'])
                df = df.sort_values('ts')
                return df[['ts','price','amount']]
            except Exception:
                continue
    raise RuntimeError(f"Không lấy được trade feed cho {symbol} từ ONUS")

# Build OHLC dataframe from trades (resample to given interval seconds)
def build_ohlc_from_trades(trades_df: pd.DataFrame, interval_minutes: int = 15):
    if trades_df.empty:
        return pd.DataFrame()
    df = trades_df.copy().set_index('ts')
    df = df.sort_index()
    rule = f"{interval_minutes}T"
    ohlc = df['price'].resample(rule).ohlc()
    vol = df['amount'].resample(rule).sum().rename('volume')
    df_ohlc = pd.concat([ohlc, vol], axis=1).dropna()
    df_ohlc.columns = ['open','high','low','close','volume']
    # ensure floats
    df_ohlc = df_ohlc.astype(float)
    return df_ohlc

# Try to fetch OHLC directly from ONUS if endpoint exists; otherwise fallback to trades
def fetch_ohlc_onus(symbol: str, interval_minutes: int = 15, limit=200, base_url=None):
    # Some ONUS deployments might have an OHLC endpoint like /kline or /candles - try common patterns
    candidates = []
    if base_url is None:
        bases = BASE_URLS
    else:
        bases = [base_url]
    # common endpoints to try
    paths = [
        f"/kline/{symbol}?period={interval_minutes}m&limit={limit}",
        f"/candles?symbol={symbol}&interval={interval_minutes}m&limit={limit}",
        f"/klines?symbol={symbol}&interval={interval_minutes}m&limit={limit}"
    ]
    for base in bases:
        for p in paths:
            url = base.rstrip("/") + p
            try:
                r = safe_get(url)
                data = r.json()
                # Try to parse common formats (list of lists, dict with data, etc.)
                if isinstance(data, dict) and 'data' in data:
                    arr = data['data']
                else:
                    arr = data
                # If arr is list of lists like [ [ts, open, high, low, close, volume], ... ]
                if isinstance(arr, list) and len(arr) and isinstance(arr[0], list):
                    df = pd.DataFrame(arr, columns=['ts','open','high','low','close','volume'] + [f'c{i}' for i in range(len(arr[0])-6)])
                    df['ts'] = pd.to_datetime(df['ts'], unit='s', origin='unix', errors='coerce')
                    df = df.set_index('ts')
                    df = df[['open','high','low','close','volume']].astype(float)
                    return df
                # if arr is list of dicts with keys
                if isinstance(arr, list) and len(arr) and isinstance(arr[0], dict):
                    df = pd.DataFrame(arr)
                    # try to standardize timestamp key names
                    if 'timestamp' in df.columns:
                        df['ts'] = pd.to_datetime(df['timestamp'], unit='s', errors='coerce')
                    elif 'open_time' in df.columns:
                        df['ts'] = pd.to_datetime(df['open_time'], unit='ms', errors='coerce')
                    else:
                        # fallback
                        df['ts'] = pd.to_datetime(df.iloc[:,0], errors='coerce')
                    for col in ['open','high','low','close','volume']:
                        if col not in df.columns:
                            # try alternative names
                            for alt in ['o','h','l','c','v','amount','volume']:
                                if alt in df.columns:
                                    df[col] = df[alt]
                                    break
                    df = df.set_index('ts')[[ 'open','high','low','close','volume']].astype(float)
                    return df
            except Exception:
                continue
    # fallback: build from trades
    trades = fetch_trades(symbol)
    ohlc = build_ohlc_from_trades(trades, interval_minutes=interval_minutes)
    # keep only last 'limit' rows
    if len(ohlc) > limit:
        return ohlc.tail(limit)
    return ohlc
