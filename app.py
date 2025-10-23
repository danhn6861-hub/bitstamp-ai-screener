import streamlit as st
import pandas as pd
import requests
import ta  # thư viện tính RSI, EMA, ADX

st.set_page_config(page_title="AI Coin Screener", layout="wide")
st.title("🚀 Bitstamp AI Coin Screener (Realtime M15)")
st.write("Tự động quét tín hiệu Long/Short theo EMA – RSI – ADX – Supertrend")

PAIRS = ["btcusd", "ethusd", "solusd", "xrpusd", "adausd", "avaxusd"]

@st.cache_data(ttl=300)
def fetch_data(pair):
    url = f"https://www.bitstamp.net/api/v2/ohlc/{pair}/?step=900&limit=200"
    r = requests.get(url)
    df = pd.DataFrame(r.json()['data']['ohlc'])
    df = df.astype(float)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    return df

def analyze(df):
    df['ema20'] = df['close'].ewm(span=20).mean()
    df['ema50'] = df['close'].ewm(span=50).mean()
    df['ema200'] = df['close'].ewm(span=200).mean()
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    df['adx'] = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14).adx()
    latest = df.iloc[-1]
    signal = "Chờ"  # mặc định
    if latest['ema20'] > latest['ema50'] > latest['ema200'] and latest['rsi'] > 55 and latest['adx'] > 25:
        signal = "LONG ✅"
    elif latest['ema20'] < latest['ema50'] < latest['ema200'] and latest['rsi'] < 45 and latest['adx'] > 25:
        signal = "SHORT 🔻"
    return {
        "Giá": latest['close'],
        "RSI": round(latest['rsi'], 2),
        "ADX": round(latest['adx'], 2),
        "EMA20>50>200": latest['ema20'] > latest['ema50'] > latest['ema200'],
        "Tín hiệu": signal
    }

data = []
for p in PAIRS:
    df = fetch_data(p)
    info = analyze(df)
    info["Coin"] = p.upper()
    data.append(info)

table = pd.DataFrame(data).set_index("Coin")
st.dataframe(table, use_container_width=True)
st.success("✅ Dữ liệu lấy từ Bitstamp API – không cần API key – cập nhật mỗi 15 phút")
