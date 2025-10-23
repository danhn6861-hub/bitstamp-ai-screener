# indicators.py
import pandas as pd
import ta

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    macd = ta.trend.MACD(df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['adx'] = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14).adx()
    df['volmean10'] = df['volume'].rolling(10).mean()
    df['volsurge'] = df['volume'] / df['volmean10']
    # simple supertrend
    def supertrend(df, period=10, multiplier=3.0):
        hl2 = (df['high'] + df['low']) / 2
        atr = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close'], window=period).average_true_range()
        final_upper = hl2 + multiplier * atr
        final_lower = hl2 - multiplier * atr
        trend = [True]
        for i in range(1, len(df)):
            if df['close'].iloc[i] > final_upper.iloc[i-1]:
                trend.append(True)
            elif df['close'].iloc[i] < final_lower.iloc[i-1]:
                trend.append(False)
            else:
                trend.append(trend[-1])
        df['supertrend'] = trend
        return df
    df = supertrend(df)
    return df
