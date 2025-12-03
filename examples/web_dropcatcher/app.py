import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os

st.set_page_config(page_title="Nautilus Pro • Real Imbalance Engine", layout="wide")
st.markdown("<h1 style='text-align:center; color:#00ff9d;'>NAUTILUS PRO • REAL IMBALANCE 2024</h1>", unsafe_allow_html=True)

# --------------------- SIDEBAR ---------------------
with st.sidebar:
    st.header("Real Imbalance Engine")
    leverage = st.slider("Leverage", 1, 20, 7)
    risk_pct = st.slider("Risk % of equity", 0.5, 5.0, 2.0, 0.1)
    fee_rate = st.number_input("Fee per side (%)", 0.00, 0.20, 0.05, 0.01)
    sl_atr = st.slider("Stop Loss × ATR", 0.8, 3.0, 1.4, 0.1)
    tp_atr = st.slider("Take Profit × ATR", 2.0, 8.0, 4.5, 0.1)

# --------------------- LOAD DATA ---------------------
csv_file = "btc_5min.csv"
if not os.path.exists(csv_file):
    st.error(f"Put btc_5min.csv next to app.py")
    st.stop()

df = pd.read_csv(csv_file)
required = ['open', 'high', 'low', 'close', 'volume']
if not all(col in df.columns for col in required):
    st.error("CSV needs: open, high, low, close, volume")
    st.stop()

# --------------------- REAL IMBALANCE ENGINE ---------------------
# Cumulative Volume Delta (tick rule)
df['buy_vol']  = np.where(df['close'] >= df['open'], df['volume'], 0)
df['sell_vol'] = np.where(df['close'] <  df['open'], df['volume'], 0)
df['cvd'] = (df['buy_vol'] - df['sell_vol']).cumsum()
df['cvd_slope'] = df['cvd'].diff(24)  # last ~2 hours

# Volume Profile High-Volume Node (last 500 bars)
lookback = 500
df['hv_node'] = df['close'].rolling(lookback).quantile(0.9)

# Momentum fade
df['mom_30m'] = df['close'].pct_change(6)   # 30 min momentum
df['rsi'] = 100 - (100 / (1 + 
          df['close'].diff().clip(lower=0).rolling(14).mean() /
          abs(df['close'].diff()).rolling(14).mean()))

# ATR
high = df['high']; low = df['low']; close = df['close']
tr = np.maximum(high-low, np.maximum(abs(high-close.shift()), abs(low-close.shift())))
df['atr'] = tr.rolling(30).mean().ffill()

# FINAL CONFIDENCE (the real 2024 sauce)
cvd_factor     = np.clip(df['cvd_slope'] / 2e7, -0.4, 0.4)          # aggressive buying/selling
near_hvn       = 1 - np.clip(abs(df['close'] - df['hv_node']) / df['atr'] / 3, 0, 1)  # near high-volume node
momentum_fade  = -np.clip(df['mom_30m'].rolling(6).sum(), -0.03, 0.03) / 0.03 * 0.25

df['confidence'] = 0.50 + cvd_factor * 0.8 + near_hvn * 0.4 + momentum_fade
df['confidence'] = df['confidence'].clip(0.0, 0.99)

# --------------------- BACKTEST ---------------------
if st.button("RUN REAL IMBALANCE BACKTEST", type="primary", use_container_width=True):
    balance = 100_000.0
    equity = [balance]
    trades = 0
    wins = 0
    fee = fee_rate / 100

    i = 1000  # warm-up
    while i < len(df) - 50:
        conf = df['confidence'].iloc[i]
        price = df['close'].iloc[i]
        atr_val = df['atr'].iloc[i]

        if conf > 0.80:   # LONG signal (extreme selling exhaustion)
            direction = 1
        elif conf < 0.20: # SHORT signal (extreme buying exhaustion)
            direction = -1
        else:
            i += 1
            continue

        # Entry next bar
        entry_price = df['close'].iloc[i+1]
        size = (balance * (risk_pct/100) * leverage) / entry_price

        sl = entry_price - direction * sl_atr * atr_val
        tp = entry_price + direction * tp_atr * atr_val

        # Simulate exit
        exit_price = None
        for j in range(i+2, len(df)):
            p = df['close'].iloc[j]
            if direction == 1:
                if p <= sl: exit_price = sl; break
                if p >= tp: exit_price = tp; break
            else:
                if p >= sl: exit_price = sl; break
                if p <= tp: exit_price = tp; break
        if exit_price is None:
            exit_price = df['close'].iloc[-1]

        pnl = direction * (exit_price - entry_price) * size
        pnl -= 2 * fee * abs(size) * entry_price  # fees
        balance += pnl
        balance = max(balance, 0)
        equity.append(balance)
        trades += 1
        if pnl > 0: wins += 1

        i = j if exit_price is not None else len(df)

    # --------------------- RESULTS ---------------------
    ret = (balance / 100000 - 1) * 100
    wr = wins/trades*100 if trades>0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Final Equity", f"${balance:,.0f}")
    c2.metric("Total Trades", trades)
    c3.metric("Win Rate", f"{wr:.1f}%")
    c4.metric("Return", f"{ret:+.1f}%")

    fig = go.Figure()
    fig.add_trace(go.Scatter(y=equity, line=dict(color="#00ff9d", width=3)))
    fig.update_layout(template="plotly_dark", height=600, title="Real Imbalance Equity Curve")
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Click the button → watch real imbalance magic happen.")
