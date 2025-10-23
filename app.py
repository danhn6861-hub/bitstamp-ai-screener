import streamlit as st
import pandas as pd
import time
from utils import get_onus_pairs, fetch_ohlc_onus
from indicators import add_indicators

st.set_page_config(layout="wide", page_title="ONUS VNDC AI Screener")
st.title("🇻🇳 ONUS VNDC AI Screener – Quét tín hiệu mạnh nhất (M15)")
st.caption("Chỉ quét các cặp coin VNDC trên sàn ONUS. Không cần API key.")

# ===== Tham số người dùng =====
LONG_THRESHOLD = 6
SHORT_THRESHOLD = 3
INTERVAL_MIN = 15
SCAN_LIMIT = st.sidebar.slider("🔎 Số lượng coin VNDC quét", 10, 300, 100)
refresh_pairs = st.sidebar.button("🧩 Làm mới danh sách coin (VNDC)")
refresh_signals = st.sidebar.button("🔁 Cập nhật tín hiệu mới nhất")

# ===== Cache danh sách cặp =====
@st.cache_data(ttl=600)
def load_pairs(limit):
    return get_onus_pairs(limit)

if refresh_pairs or "pairs" not in st.session_state:
    pairs = load_pairs(SCAN_LIMIT)
    # Nếu API không có kết quả, dùng danh sách cặp VNDC cố định
    if not pairs:
        pairs = [
            "BTCVNDC","ETHVNDC","BNBVNDC","SOLVNDC","DOGEVNDC",
            "ADAVNDC","ETCVNDC","DOTVNDC","SHIBVNDC","AVAXVNDC",
            "LINKVNDC","XRPVNDC","TRXVNDC","NEARVNDC","MATICVNDC"
        ]
        st.warning("Không lấy được danh sách từ API, đang dùng danh sách VNDC mặc định.")
    st.session_state["pairs"] = pairs

pairs = st.session_state["pairs"]
st.success(f"✅ Đang theo dõi {len(pairs)} cặp VNDC từ ONUS.")

# ===== Quét dữ liệu =====
if refresh_signals or "results" not in st.session_state:
    st.info("🧠 Đang quét dữ liệu ONUS... (khoảng 1–2 phút)")
    results = []
    progress = st.progress(0)
    for i, p in enumerate(pairs):
        try:
            df = fetch_ohlc_onus(p, interval_minutes=INTERVAL_MIN)
            if df.empty:
                continue
            df = add_indicators(df)
            last = df.iloc[-1]
            score = 0
            if last["ema20"] > last["ema50"] > last["ema200"]: score += 2
            if last["rsi"] > 55: score += 1
            if last["adx"] > 25: score += 1
            if last["macd"] > last["macd_signal"]: score += 2
            if last["volsurge"] > 1.3: score += 2
            signal = "NEUTRAL"
            if score >= LONG_THRESHOLD:
                signal = "LONG ✅"
            elif score <= SHORT_THRESHOLD:
                signal = "SHORT 🔻"
            results.append({
                "Coin": p,
                "Giá (VNDC)": round(last["close"], 2),
                "RSI": round(last["rsi"], 1),
                "ADX": round(last["adx"], 1),
                "Vol Surge": round(last["volsurge"], 2),
                "Score": score,
                "Tín hiệu": signal
            })
        except Exception as e:
            print("Lỗi:", p, e)
        progress.progress((i+1)/len(pairs))
        time.sleep(0.05)
    df_result = pd.DataFrame(results).set_index("Coin")
    st.session_state["results"] = df_result
else:
    df_result = st.session_state["results"]

# ===== Hiển thị kết quả =====
if not df_result.empty:
    longs = df_result[df_result["Tín hiệu"].str.contains("LONG")].sort_values("Score", ascending=False).head(10)
    shorts = df_result[df_result["Tín hiệu"].str.contains("SHORT")].sort_values("Score", ascending=True).head(10)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🔥 Top 10 Coin Tăng Mạnh (VNDC)")
        st.dataframe(longs, use_container_width=True)
    with col2:
        st.subheader("💀 Top 10 Coin Giảm Mạnh (VNDC)")
        st.dataframe(shorts, use_container_width=True)
else:
    st.warning("⚠️ Không có dữ liệu hợp lệ. Hãy ấn '🔁 Cập nhật tín hiệu mới nhất'.")
