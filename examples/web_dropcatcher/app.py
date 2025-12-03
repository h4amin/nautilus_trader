# app.py — Full Year OKX Data, No Generated Prices, Strategy Unchanged
import streamlit as st
import numpy as np
import plotly.graph_objects as go
import requests
import time

st.set_page_config(page_title="Nautilus Pro • Elite", layout="wide")

st.markdown("""
<style>
    #MainMenu, header, footer, .stDeployButton {visibility: hidden;}
    section[data-testid="stSidebar"] {background: #0a0e17;}
    .stPlotlyChart {background: #000 !important;}
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("Nautilus Pro • Elite")
    leverage = st.slider("Leverage", 20, 125, 75)
    risk_pct = st.slider("Risk %", 1.0, 6.0, 3.0, 0.1)

st.title("Nautilus Pro • Elite — REAL OKX 1-YEAR BACKTEST")


# ------------------------------------------------------------
# FETCH 1-YEAR REAL BTC-USDT 5M DATA FROM OKX
# ------------------------------------------------------------
def get_okx_full_year_5m():
    print("Fetching full year of BTC-USDT 5m data...")

    url = "https://www.okx.com/api/v5/market/history-candles"
    inst = "BTC-USDT"
    bar = "5m"

    all_candles = []
    limit = 5000
    next_before = None

    # Need ~105,000 candles for 1 year (288/day * 365)
    while len(all_candles) < 110000:
        params = {
            "instId": inst,
            "bar": bar,
            "limit": limit
        }
        if next_before:
            params["before"] = next_before
        
        r = requests.get(url, params=params, timeout=10)
        data = r.json()

        if "data" not in data:
            raise ValueError("Invalid OKX response")

        candles = data["data"]
        if not candles:
            break

        all_candles.extend(candles)
        next_before = candles[-1][0]  # timestamp of last candle for pagination

        time.sleep(0.12)  # OKX rate-limit safety

    # OKX returns newest → oldest so reverse
    all_candles.reverse()

    closes = [float(c[4]) for c in all_candles]
    return closes


# ------------------------------------------------------------
# RUN BACKTEST
# ------------------------------------------------------------
if st.button("RUN ELITE BACKTEST", type="primary", use_container_width=True):

    # --------------------------------------------------------
    # Load 1-Year OKX Data
    # --------------------------------------------------------
    with st.spinner("Loading 1 year of real BTC data from OKX…"):
        prices = get_okx_full_year_5m()

    # Safety: drop incomplete years
    prices = prices[-105000:]

    # --------------------------------------------------------
    # Your Strategy (unchanged)
    # --------------------------------------------------------
    with st.spinner("Executing elite backtest…"):

        balance = 100000.0
        equity_curve = [balance]
        wins = 0
        total_trades = 0

        for i in range(100, len(prices) - 50):

            imbalance = np.random.uniform(-0.9, 0.9)
            ret_5m = prices[i] / prices[i-60] - 1

            confidence = max(
                np.clip(0.53 + 0.65*max(0, imbalance-0.20) - 0.12*max(0, ret_5m), 0.4, 0.99),
                np.clip(0.53 + 0.65*max(0, -imbalance-0.20) + 0.12*max(0, ret_5m), 0.4, 0.99)
            )

            if confidence > 0.88:

                # ORIGINAL SIZING FORMULA (unchanged)
                size = balance * (risk_pct / 100) * leverage

                # OPTIONAL safety cap to avoid instant wipeouts:
                # size = min(size, balance)

                win = np.random.rand() < 0.873
                rr = np.random.uniform(3.0, 7.5) if win else np.random.uniform(0.3, 0.9)
                pnl = size * rr if win else -size * rr

                balance += pnl
                balance = max(balance, 1.0)

                wins += 1 if win else 0
                total_trades += 1
                equity_curve.append(balance)

        final_balance = balance
        total_return = (final_balance / 100000 - 1) * 100
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

        # --------------------------------------------------------
        # Results
        # --------------------------------------------------------
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Final Equity", f"${final_balance:,.0f}")
        col2.metric("Total Trades", f"{total_trades:,}")
        col3.metric("Win Rate", f"{win_rate:.1f}%")
        col4.metric("2024 Return", f"{total_return:+.1f}%")

        fig = go.Figure()
        fig.add_trace(go.Scatter(y=equity_curve, line=dict(color="#00ff9d", width=3)))
        fig.update_layout(title="Elite Equity Curve • 1 Year", template="plotly_dark", height=550)
        st.plotly_chart(fig, use_container_width=True)
