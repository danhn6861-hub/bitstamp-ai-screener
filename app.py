import streamlit as st
import pandas as pd
import requests
import ta

st.set_page_config(page_title="AI Coin Radar", layout="wide")
st.title("🚀 Bitstamp AI Coin Radar – Auto Update Every 5 Minutes")

@st.cache_data(ttl=300)
def get_pairs():
    url = "https://www.bitstamp.net/api/v2/trading-pairs-info/"
    r = requests.get(url).json()
    return [x['url_symbol'] for x in r if 'usd' in x['url_symbol']]

def get_data(pair):
    url = f"https://www.bitstamp.net/api/v2/ohlc/{pair}/?step=900&limit=200"
    data = requests.get(url).json()['data']['ohlc']
    df = pd.DataFrame(data).astype(float)
    return df

def analyze(df):
    df['ema20'] = df['close'].ewm(span=20).mean()
    df['ema50'] = df['close'].ewm(span=50).mean()
    df['ema200'] = df['close'].ewm(span=200).mean()
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], 14).rsi()
    macd = ta.trend.MACD(df['close'])
    df['macd'] = macd.macd()
    df['signal'] = macd.macd_signal()
    df['adx'] = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], 14).adx()
    df['volmean'] = df['volume'].rolling(10).mean()
    df['volsurge'] = df['volume'] / df['volmean']
    last = df.iloc[-1]
    score = 0
    if last['ema20'] > last['ema50'] > last['ema200']: score += 2
    if last['rsi'] > 55: score += 1
    if last['adx'] > 25: score += 1
    if last['macd'] > last['signal']: score += 2
    if last['volsurge'] > 1.5: score += 2
    trend = "LONG ✅" if score >=7 else "SHORT 🔻" if score <=3 else "NEUTRAL"
    return {
        "Price": round(last['close'],2),
        "RSI": round(last['rsi'],1),
        "ADX": round(last['adx'],1),
        "Vol Surge": round(last['volsurge'],2),
        "Score": score,
        "Signal": trend
    }

pairs = get_pairs()
results = []
for p in pairs[:50]:  # quét 50 coin đầu tiên để tránh chậm
    try:
        df = get_data(p)
        info = analyze(df)
        info["Coin"] = p.upper()
        results.append(info)
    except Exception:
        pass

df = pd.DataFrame(results).set_index("Coin")
longs = df[df['Signal'].str.contains("LONG")].sort_values("Score", ascending=False).head(10)
shorts = df[df['Signal'].str.contains("SHORT")].sort_values("Score").head(10)

col1, col2 = st.columns(2)
with col1:
    st.subheader("🔥 Top 10 Coin Tăng Mạnh")
    st.dataframe(longs)
with col2:
    st.subheader("💀 Top 10 Coin Giảm Mạnh")
    st.dataframe(shorts)
