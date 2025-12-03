# app.py — Nautilus Pro Reversal (Corrected, Safe, Deterministic)
# -----------------------------------------------
# This version fixes:
# • Position sizing
# • Leverage handling
# • Fees
# • Reversal signal (z-score)
# • ATR stop-loss & take-profit
# • No negative equity
# • No double-counting leverage
# -----------------------------------------------

import streamlit as st
import numpy as np
import pandas as pd
import os
import plotly.graph_objects as go

st.set_page_config(page_title="Nautilus Pro Reversal • Fixed", layout="wide")

st.markdown("""
<style>
    #MainMenu, header, footer, .stDeployButton {visibility: hidden;}
    section[data-testid="stSidebar"] {background: #0a0e17;}
    .stPlotlyChart {background: #000 !important;}
</style>
""", unsafe_allow_html=True)

# ---------------------------
# Sidebar
# ---------------------------
with st.sidebar:
    st.header("Nautilus Pro Reversal • Fixed")
    leverage = st.slider("Leverage", 1, 50, 10)
    risk_pct = st.slider("Risk % per trade", 0.5, 5.0, 2.0, 0.1)
    fee_rate = st.number_input("Fee per side (%)", 0.01, 0.5, 0.05, 0.01)
    atr_mult_sl = st.slider("ATR Stop Loss Multiplier", 1.0, 8.0, 3.0, 0.1)
    atr_mult_tp = st.slider("ATR Take Profit Multiplier", 1.0, 10.0, 5.0, 0.1)

st.title("Nautilus Pro Reversal — Deterministic Backtest")

# ---------------------------
# Load BTC CSV
# ---------------------------
csv_file = "btc_5min.csv"
if not os.path.exists(csv_file):
    st.error(f"{csv_file} not found! Place it next to app.py.")
    st.stop()

df = pd.read_csv(csv_file)
if 'close' not in df:
    st.error("CSV must contain a 'close' column.")
    st.stop()

# Compute ATR for stops
high = df['high'] if 'high' in df else df['close']
low = df['low'] if 'low' in df else df['close']
close = df['close']

df['tr'] = np.maximum(high - low, np.maximum(abs(high - close.shift()), abs(low - close.shift())))
df['atr'] = df['tr'].rolling(30).mean().fillna(method='bfill')

prices = df['close'].tolist()
atr = df['atr'].tolist()
st.success(f"Loaded {len(prices)} candles.")

# ---------------------------
# REVSERSAL SIGNAL — Z-Score
# ---------------------------
# Reversal trigger = |Z| > 2.0
window = 60
roll_mean = df['close'].rolling(window).mean().fillna(method='bfill')
roll_std = df['close'].rolling(window).std().replace(0, 1).fillna(method='bfill')

df['zscore'] = (df['close'] - roll_mean) / roll_std

# ---------------------------
# BACKTEST
# ---------------------------
if st.button("RUN BACKTEST", type="primary", use_container_width=True):
    balance = 100_000.0
    equity = [balance]

    wins = 0
    trades = 0
    fee = fee_rate / 100

    for i in range(window, len(df) - 2):
        z = df['zscore'].iloc[i]
        atr_val = atr[i]
        price = prices[i]

        # --- ENTRY CONDITION ---
        if abs(z) < 2.0:
            continue

        direction = "short" if z > 2 else "long"

        # --- POSITION SIZE (Never > 5%) ---
        notional = balance * (risk_pct / 100)
        notional = min(notional, balance * 0.05)

        if notional <= 0:
            continue

        size = notional / price  # coin size

        # --- ENTRY PRICE ---
        entry_price = prices[i+1]

        # --- SL & TP ---
        sl_price = entry_price - atr_mult_sl * atr_val if direction == "long" else entry_price + atr_mult_sl * atr_val
        tp_price = entry_price + atr_mult_tp * atr_val if direction == "long" else entry_price - atr_mult_tp * atr_val

        # --- SIMULATE UNTIL STOP OR TP ---
        exit_price = None

        for j in range(i+2, min(i+300, len(prices))):
            p = prices[j]

            if direction == "long":
                if p <= sl_price:
                    exit_price = sl_price
                    break
                if p >= tp_price:
                    exit_price = tp_price
                    break
            else:  # short
                if p >= sl_price:
                    exit_price = sl_price
                    break
                if p <= tp_price:
                    exit_price = tp_price
                    break

        if exit_price is None:
            exit_price = prices[j]

        # --- PNL CALC (Correct, ONE leverage application) ---
        if direction == "long":
            raw_pnl = (exit_price - entry_price) * size
        else:
            raw_pnl = (entry_price - exit_price) * size

        pnl = raw_pnl * leverage

        # --- FEES ---
        fee_cost = (entry_price * size * fee) + (exit_price * size * fee)
        pnl -= fee_cost

        # --- UPDATE BALANCE ---
        balance += pnl
        balance = max(balance, 0)  # never negative

        trades += 1
        if pnl > 0:
            wins += 1

        equity.append(balance)

    # ---------------------------
    # METRICS
    # ---------------------------
    final_balance = balance
    total_return = (final_balance / 100_000 - 1) * 100
    win_rate = (wins / trades * 100) if trades > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Final Equity", f"${final_balance:,.2f}")
    c2.metric("Total Trades", trades)
    c3.metric("Win Rate", f"{win_rate:.1f}%")
    c4.metric("Total Return", f"{total_return:.1f}%")

    fig = go.Figure()
    fig.add_trace(go.Scatter(y=equity, mode='lines'))
    fig.update_layout(title="Equity Curve", template="plotly_dark", height=550)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Click RUN BACKTEST to simulate deterministic reversals.")
