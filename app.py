# app.py
import streamlit as st
import pandas as pd
import time
from utils import get_onus_pairs, fetch_ohlc_onus
from indicators import add_indicators

st.set_page_config(layout="wide", page_title="ONUS AI Screener")
st.title("🔥 ONUS AI Coin Screener (M15)")

# settings
SCAN_LIMIT = st.sidebar.number_input("Số cặp quét tối đa", min_value=10, max_value=500, value=120, step=10)
LONG_THRESHOLD = st.sidebar.slider("Ngưỡng LONG (score)", 1, 10, 6)
SHORT_THRESHOLD = st.sidebar.slider("Ngưỡng SHORT (score)", 0, 10, 3)
INTERVAL_MIN = st.sidebar.selectbox("Khung nến (phút)", [5, 15, 30, 60], index=1)
UPDATE_INTERVAL = 300  # cache TTL

st.sidebar.markdown("📌 Nút 'Cập nhật ngay' sẽ quét ONUS realtime.")

refresh = st.button("🔄 Cập nhật ngay")

@st.cache_data(ttl=UPDATE_INTERVAL)
def load_pairs(limit):
    return get_onus_pairs(limit=limit)

pairs = load_pairs(SCAN_LIMIT)
st.write(f"Đã tìm {len(pairs)} cặp từ ONUS (scan limit={SCAN_LIMIT}).")

if refresh or 'results' not in st.session_state:
    st.info("Bắt đầu quét... Vui lòng chờ (có thể mất 30-90s tuỳ số cặp).")
    results = []
    progress = st.progress(0)
    for i, p in enumerate(pairs):
        try:
            df = fetch_ohlc_onus(p, interval_minutes=INTERVAL_MIN)
            if df is None or df.empty:
                continue
            df = add_indicators(df)
            last = df.iloc[-1]
            score = 0
            if last['ema20'] > last['ema50'] > last['ema200']: score += 2
            if last['rsi'] > 55: score += 1
            if last['adx'] > 25: score += 1
            if last['macd'] > last['macd_signal']: score += 2
            if pd.notna(last.get('volsurge', None)) and last['volsurge'] > 1.3: score += 2
            signal = "NEUTRAL"
            if score >= LONG_THRESHOLD:
                signal = "LONG"
            elif score <= SHORT_THRESHOLD:
                signal = "SHORT"
            results.append({
                "pair": p.upper(),
                "price": round(last['close'], 6),
                "rsi": round(last['rsi'],1),
                "adx": round(last['adx'],1),
                "volsurge": round(last.get('volsurge',0),2) if 'volsurge' in last.index else 0,
                "score": score,
                "signal": signal
            })
        except Exception as e:
            # do not crash, just skip
            print("skip", p, e)
        progress.progress((i+1)/len(pairs))
        time.sleep(0.05)
    df_results = pd.DataFrame(results).set_index('pair')
    st.session_state['results'] = df_results
else:
    df_results = st.session_state['results']

# show top lists
if df_results is None or df_results.empty:
    st.warning("Không có dữ liệu. Hãy ấn 'Cập nhật ngay' để quét ONUS.")
else:
    longs = df_results[df_results['signal']=='LONG'].sort_values('score', ascending=False).head(10)
    shorts = df_results[df_results['signal']=='SHORT'].sort_values('score', ascending=True).head(10)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🔥 Top 10 Long (tăng mạnh)")
        if longs.empty:
            st.info("Chưa có coin nào đạt ngưỡng LONG.")
        else:
            st.dataframe(longs)
    with col2:
        st.subheader("💀 Top 10 Short (giảm mạnh)")
        if shorts.empty:
            st.info("Chưa có coin nào đạt ngưỡng SHORT.")
        else:
            st.dataframe(shorts)

st.markdown("---")
st.markdown("⚠️ Ghi chú: ONUS API có thể giới hạn hoặc có tên cặp khác. Nếu bạn gặp lỗi, hãy kiểm tra `BASE_URLS` và `PAIRS_PATHS` trong `utils.py` để phù hợp với phiên bản ONUS bạn dùng.")
