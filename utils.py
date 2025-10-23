import requests
import pandas as pd
import time

# ======================================
# 🔧 CẤU HÌNH CHÍNH
# ======================================
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

TRADES_PATH = "/trades"  # thường là ?symbol_name=BTCVNDC

# ======================================
# 🧩 HÀM GỌI API AN TOÀN
# ======================================
def safe_get(url, params=None, timeout=10, max_retries=3, pause=1.0):
    """Gọi API an toàn, tự retry nếu lỗi."""
    for attempt in range(max_retries):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            print(f"[Lỗi] {e} (thử lại {attempt+1}/{max_retries})")
            time.sleep(pause * (attempt + 1))
    return None


# ======================================
# 🪙 LẤY DANH SÁCH CẶP GIAO DỊCH VNDC
# ======================================
def get_onus_pairs(limit=200):
    """Lấy danh sách cặp giao dịch ONUS, chỉ lọc coin VNDC (BTCVNDC, ETHVNDC, SOLVNDC,...)"""
    pairs = []
    for base in BASE_URLS:
        for path in PAIRS_PATHS:
            url = base.rstrip("/") + path
            r = safe_get(url)
            if not r:
                continue
            try:
                data = r.json()
            except Exception:
                continue

            # Dạng list
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        sym = item.get("symbol") or item.get("url_symbol") or item.get("name")
                        if sym:
                            pairs.append(str(sym).upper())

            # Dạng dict có key data
            elif isinstance(data, dict) and "data" in data:
                for item in data["data"]:
                    sym = item.get("symbol") or item.get("url_symbol") or item.get("name")
                    if sym:
                        pairs.append(str(sym).upper())

    # Chuẩn hóa: bỏ ký tự lạ, lọc VNDC
    normalized = [p.replace("-", "").replace("_", "").replace("/", "").upper() for p in pairs]
    vndc_pairs = [p for p in normalized if p.endswith("VNDC")]

    # Nếu API không trả gì → fallback danh sách phổ biến
    if not vndc_pairs:
        print("⚠️ Không lấy được từ API, dùng danh sách VNDC mặc định.")
        vndc_pairs = [
            "BTCVNDC", "ETHVNDC", "BNBVNDC", "SOLVNDC", "ADAVNDC",
            "DOGEVNDC", "XRPVNDC", "TRXVNDC", "ETCVNDC", "DOTVNDC",
            "NEARVNDC", "MATICVNDC", "AVAXVNDC", "SHIBVNDC", "LINKVNDC"
        ]

    # Bỏ trùng + giới hạn
    vndc_pairs = list(dict.fromkeys(vndc_pairs))
    return vndc_pairs[:limit]


# ======================================
# 📊 LẤY DỮ LIỆU TRADES TỪ ONUS
# ======================================
def fetch_trades(symbol, limit=1000):
    """Lấy danh sách giao dịch gần nhất từ ONUS."""
    for base in BASE_URLS:
        url = base.rstrip("/") + TRADES_PATH
        params = {"symbol_name": symbol}
        r = safe_get(url, params=params)
        if not r:
            continue
        try:
            data = r.json()
        except Exception:
            continue

        # Tìm dữ liệu giao dịch
        raw = data.get("data", data)
        if not isinstance(raw, list) or len(raw) == 0:
            continue

        df = pd.DataFrame(raw)
        # Xác định cột thời gian, giá, khối lượng
        ts_col = next((c for c in df.columns if "time" in c or "timestamp" in c), None)
        price_col = next((c for c in df.columns if "price" in c), None)
        amt_col = next((c for c in df.columns if c in ["amount", "volume", "qty", "quantity"]), None)

        if not ts_col or not price_col:
            continue

        try:
            df["ts"] = pd.to_datetime(df[ts_col], unit="s", errors="coerce")
        except Exception:
            df["ts"] = pd.to_datetime(df[ts_col], errors="coerce")

        df["price"] = pd.to_numeric(df[price_col], errors="coerce")
        df["amount"] = pd.to_numeric(df[amt_col], errors="coerce") if amt_col else 0
        df = df.dropna(subset=["ts", "price"])
        if df.empty:
            continue

        df = df[["ts", "price", "amount"]].sort_values("ts")
        return df

    raise RuntimeError(f"Không lấy được dữ liệu trades cho {symbol}")


# ======================================
# 🧱 DỰNG OHLC TỪ TRADES
# ======================================
def build_ohlc_from_trades(trades_df, interval_minutes=15):
    """Tổng hợp nến (OHLC) từ trade feed."""
    if trades_df.empty:
        return pd.DataFrame()

    df = trades_df.set_index("ts").sort_index()
    rule = f"{interval_minutes}T"

    ohlc = df["price"].resample(rule).ohlc()
    vol = df["amount"].resample(rule).sum().rename("volume")
    merged = pd.concat([ohlc, vol], axis=1).dropna()
    merged = merged.astype(float)
    return merged


# ======================================
# 🔥 HÀM CHÍNH: LẤY NẾN OHLC TỪ ONUS
# ======================================
def fetch_ohlc_onus(symbol, interval_minutes=15, limit=200):
    """
    Lấy dữ liệu nến từ ONUS. 
    Nếu không có endpoint nến, sẽ tự build từ trades.
    """
    try:
        trades = fetch_trades(symbol)
        if trades is None or trades.empty:
            raise ValueError("Không có trade data.")
        ohlc = build_ohlc_from_trades(trades, interval_minutes)
        return ohlc.tail(limit)
    except Exception as e:
        print(f"[Cảnh báo] Không build được OHLC cho {symbol}: {e}")
        return pd.DataFrame()
