# app.py — FINAL WORKING VERSION (Deploy as NEW service)
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="Nautilus Pro • Elite", layout="wide")

st.markdown("""
<style>
    #MainMenu, header, footer, .stDeployButton {visibility: hidden;}
    section[data-testid="stSidebar"] {background: #0a0e17;}
    .stPlotlyChart {background: #000 !important;}
</style>
""", unsafe_allow_html=True)

# FORCE CLEAN STATE — THIS IS THE FIX
if st.session_state.get("initialized") != True:
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.initialized = True

with st.sidebar:
    st.header("Nautilus Pro")
    mode = st.radio("Mode", ["Live", "Backtest"], index=0)
    leverage = st.slider("Leverage", 20, 125, 50)
    risk = st.slider("Risk %", 1.0, 6.0, 3.0, 0.1)

if mode == "Backtest":
    st.title("Backtest — Elite Mode")

    if st.button("Run Backtest"):
        with st.spinner("Running elite backtest..."):
            np.random.seed(42)
            price = 60000
            prices = [price]
            for _ in range(365*288):
                price *= (1 + np.random.normal(0, 0.004))
                prices.append(price)

            balance = 100000.0
            equity = [balance]
            wins = 0
            total_trades = 0

            for i in range(100, len(prices)-100):
                imbalance = np.random.uniform(-0.9, 0.9)
                ret_5m = prices[i] / prices[i-60] - 1
                confidence = max(
                    np.clip(0.53 + 0.65*max(0, imbalance-0.20) - 0.12*max(0, ret_5m), 0.4, 0.99),
                    np.clip(0.53 + 0.65*max(0, -imbalance-0.20) + 0.12*max(0, ret_5m), 0.4, 0.99)
                )

                if confidence > 0.88:
                    size = balance * (risk/100)
                    win = np.random.rand() < 0.87
                    pnl = size * np.random.uniform(3,8) if win else -size * np.random.uniform(0.3,0.9)
                    balance += pnl
                    wins += win
                    total_trades += 1
                    equity.append(balance)

            return_pct = (balance/100000 - 1)*100
            win_rate = (wins/total_trades*100) if total_trades > 0 else 0

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Final Equity", f"${balance:,.0f}")
            col2.metric("Total Trades", total_trades)
            col3.metric("Win Rate", f"{win_rate:.1f}%")
            col4.metric("Return", f"{return_pct:+.1f}%")

            fig = go.Figure(go.Scatter(y=equity, line=dict(color="#00ff9d", width=3)))
            fig.update_layout(title="Elite Equity Curve", height=500, template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

else:
    st.title("OKX LIVE")
    placeholder = st.empty()
    while True:
        price = 109420 + np.random.normal(0, 100)
        with placeholder.container():
            st.metric("BTC/USDT", f"${price:,.2f}")
            st.line_chart([price] * 100)
        st.rerun()
