import requests
import pandas as pd
import time
from datetime import datetime

# Danh sách endpoint có thể dùng — ONUS có nhiều cụm khác nhau
BASE_URLS = [
    "https://spot-markets.goonus.io",
    "https://api.goonus.io",
    "https://spot.goonus.io"
]

PAIRS_PATHS = [
    "/trading-pairs-info/",
    "/symbols",
    "/public/symbols"
]

TRADES_PATH = "/trades"  # thường dùng ?symbol_name=BTCVNDC

def safe_get(url, params=None, timeout=10, max_retries=3, pause=1.0):
    """Gọi API an toàn, retry nếu lỗi."""
    for attempt in range(max_retries):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception:
            time.sleep(pause * (attempt + 1))
    raise RuntimeError(f"Lỗi khi truy cập {url}")

def get_onus_pairs(limit=200):
    """Lấy danh sách cặp giao dịch ONUS và lọc chỉ cặp VNDC."""
    pairs = []
    for base in BASE_URLS:
        for path in PAIRS_PATHS:
            url = base.rstrip("/") + path
            try:
                r = safe_get(url)
                data = r.json()
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            sym = item.get("symbol") or item.get("url_symbol") or item.get("name")
                            if sym:
                                pairs.append(str(sym).upper())
                elif isinstance(data, dict) and "data" in data:
                    for item in data["data"]:
                        sym = item.get("symbol") or item.get("url_symbol") or item.get("name")
                        if sym:
                            pairs.append(str(sym).upper())
                if pairs:
                    normalized = [p.replace("-", "").replace("_", "").replace("/", "").upper() for p in pairs]
                    vndc_pairs = [p for p in normalized if p.endswith("VNDC")]
                    return list(dict.fromkeys(vndc_pairs))[:limit]
            except Exception:
                continue
    return []

def fetch_trades(symbol, limit=1000):
    """Lấy danh sách giao dịch gần nhất từ ONUS."""
    for base in BASE_URLS:
        url = base.rstrip("/") + TRADES_PATH
        for sep in ["", "_", "-"]:
            sym = symbol.replace("_", sep).replace("-", sep)
            params = {"symbol_name": sym}
            try:
                r = safe_get(url, params=params)
                data = r.json()
                raw = data["data"] if isinstance(data, dict) and "data" in data else data
                df = pd.DataFrame(raw)
                if df.empty:
                    continue
                # Chuẩn hoá cột
                ts_col = next((c for c in df.columns if "time" in c or "timestamp" in c), None)
                price_col = next((c for c in df.columns if "price" in c), None)
                amt_col = next((c for c in df.columns if c in ["amount", "volume", "qty", "quantity"]), None)
                if ts_col and price_col:
                    df["ts"] = pd.to_datetime(df[ts_col], unit="s", errors="coerce")
                    df["price"] = pd.to_numeric(df[price_col], errors="coerce")
                    if amt_col:
                        df["amount"] = pd.to_numeric(df[amt_col], errors="coerce")
                    else:
                        df["amount"] = 0
                    df = df.dropna(subset=["ts", "price"])
                    return df[["ts", "price", "amount"]]
            except Exception:
                continue
    raise RuntimeError(f"Không lấy được dữ liệu trades cho {symbol}")

def build_ohlc_from_trades(trades_df, interval_minutes=15):
    """Tự tổng hợp OHLC từ trade feed."""
    if trades_df.empty:
        return pd.DataFrame()
    df = trades_df.set_index("ts").sort_index()
    rule = f"{interval_minutes}T"
    ohlc = df["price"].resample(rule).ohlc()
    vol = df["amount"].resample(rule).sum().rename("volume")
    return pd.concat([ohlc, vol], axis=1).dropna()

def fetch_ohlc_onus(symbol, interval_minutes=15, limit=200):
    """Thử lấy nến trực tiếp, nếu không có thì build từ trades."""
    trades = fetch_trades(symbol)
    ohlc = build_ohlc_from_trades(trades, interval_minutes)
    return ohlc.tail(limit)
