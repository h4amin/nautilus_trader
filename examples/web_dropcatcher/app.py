# app.py — Nautilus Pro Reversal • Local CSV Backtest with Fees
import streamlit as st
import numpy as np
import pandas as pd
import os
import plotly.graph_objects as go

st.set_page_config(page_title="Nautilus Pro Reversal • Elite", layout="wide")

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
    st.header("Nautilus Pro Reversal • Elite")
    leverage = st.slider("Leverage", 20, 125, 75)
    risk_pct = st.slider("Risk %", 1.0, 6.0, 3.0, 0.1)
    fee_rate = st.number_input("Fee per side (%)", 0.01, 0.5, 0.05, 0.01)  # default 0.05%

st.title("Nautilus Pro Reversal — Backtest with Local BTC CSV & Fees")

# ---------------------------
# Load CSV
# ---------------------------
csv_file = "btc_5min.csv"
if not os.path.exists(csv_file):
    st.error(f"{csv_file} not found! Please place it in the same folder as app.py.")
    st.stop()

df = pd.read_csv(csv_file)
prices = df['close'].tolist()
st.success(f"Loaded {len(prices)} BTC 5-min candles from {csv_file}")

# ---------------------------
# Run Backtest
# ---------------------------
if st.button("RUN NAUTILUS REVERSAL BACKTEST", type="primary", use_container_width=True):
    balance = 100_000.0
    equity_curve = [balance]
    wins = 0
    total_trades = 0
    fee = fee_rate / 100

    for i in range(100, len(prices) - 60):
        imbalance = np.random.uniform(-0.9, 0.9)
        ret_5m = (prices[i] / prices[i-60] - 1) if prices[i-60] != 0 else 0
        confidence = max(
            np.clip(0.53 + 0.65*max(0, imbalance-0.20) - 0.12*max(0, ret_5m), 0.4, 0.99),
            np.clip(0.53 + 0.65*max(0, -imbalance-0.20) + 0.12*max(0, ret_5m), 0.4, 0.99)
        )

        if confidence > 0.88:
            recent_return = prices[i] / prices[i-60] - 1
            direction = "short" if recent_return > 0 else "long"
            size = balance * (risk_pct / 100) * leverage
            size = min(size, balance * 0.05)  # max 5% account per trade
            entry_index = i + 1
            if entry_index >= len(prices) - 10:
                continue
            # Add slippage
            entry_price = prices[entry_index] * (1 + np.random.uniform(-0.0005, 0.0005))
            max_hold = 50
            exit_index = entry_index + 1
            while exit_index < len(prices) and exit_index < entry_index + max_hold:
                # Reversal exit condition: confidence drops
                imbalance_f = np.random.uniform(-0.9, 0.9)
                ret_f = (prices[exit_index] / prices[exit_index-60] - 1) if prices[exit_index-60] != 0 else 0
                conf_f = max(
                    np.clip(0.53 + 0.65*max(0, imbalance_f-0.20) - 0.12*max(0, ret_f), 0.4, 0.99),
                    np.clip(0.53 + 0.65*max(0, -imbalance_f-0.20) + 0.12*max(0, ret_f), 0.4, 0.99)
                )
                if conf_f < 0.5:
                    break
                exit_index += 1

            exit_price = prices[min(exit_index, len(prices)-1)]
            if direction == "long":
                pnl = ((exit_price - entry_price) / entry_price) * leverage * size
            else:
                pnl = ((entry_price - exit_price) / entry_price) * leverage * size
            # Subtract fees
            pnl -= (entry_price * size * fee) + (exit_price * size * fee)
            balance += pnl
            balance = max(balance, 1.0)
            wins += 1 if pnl > 0 else 0
            total_trades += 1
            equity_curve.append(balance)

    final_balance = balance
    total_return = (final_balance / 100_000 - 1) * 100
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Final Equity", f"${final_balance:,.0f}")
    col2.metric("Total Trades", f"{total_trades:,}")
    col3.metric("Win Rate", f"{win_rate:.1f}%")
    col4.metric("2024 Return", f"{total_return:+.1f}%")

    fig = go.Figure()
    fig.add_trace(go.Scatter(y=equity_curve, line=dict(color="#00ff9d", width=3)))
    fig.update_layout(title="Nautilus Pro Reversal Equity Curve • BTC 5-min (with Fees)", template="plotly_dark", height=550)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Click the button above to run the reversal backtest using BTC 5-min data.")
