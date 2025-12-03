# app.py — REAL OKX PRICES + NO HARD-CODED WIN RATE

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

st.title("Nautilus Pro • Elite — 2024 Backtest (REAL OKX DATA)")


# ---------------------------------------------------------------------
# Fetch REAL OKX BTC-USDT 5-minute historical candles
# ---------------------------------------------------------------------
def get_okx_btc_history(limit=5000):
    url = "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=5m&limit=" + str(limit)
    r = requests.get(url, timeout=10)
    data = r.json()

    if "data" not in data:
        raise ValueError("Error pulling OKX API data")

    candles = data["data"]
    candles.reverse()  # oldest → newest
    closes = [float(c[4]) for c in candles]
    return closes


if st.button("RUN ELITE BACKTEST", type="primary", use_container_width=True):

    # -------------------------------------------------------
    # Load real prices
    # -------------------------------------------------------
    with st.spinner("Fetching real BTC prices from OKX…"):
        prices = get_okx_btc_history(limit=8000)


    # -------------------------------------------------------
    # Backtest (strategy unchanged, ONLY win logic replaced)
    # -------------------------------------------------------
    with st.spinner("Executing elite trades…"):

        balance = 100000.0
        equity_curve = [balance]
        wins = 0
        total_trades = 0

        for i in range(100, len(prices) - 50):

            # Your original random imbalance + confidence logic remains exactly:
            imbalance = np.random.uniform(-0.9, 0.9)
            ret_5m = prices[i] / prices[i-60] - 1

            confidence = max(
                np.clip(0.53 + 0.65*max(0, imbalance-0.20) - 0.12*max(0, ret_5m), 0.4, 0.99),
                np.clip(0.53 + 0.65*max(0, -imbalance-0.20) + 0.12*max(0, ret_5m), 0.4, 0.99)
            )

            # ------------------------------
            # ENTRY TRIGGER (unchanged)
            # ------------------------------
            if confidence > 0.88:

                # position sizing (unchanged)
                size = balance * (risk_pct / 100) * leverage

                # ---------------------------------------------------------------
                # FIXED: REMOVE HARD-CODED WIN RATE → USE REAL FUTURE PRICE MOVE
                # ---------------------------------------------------------------
                # Look 10 candles ahead (50 minutes) — same timing as high RR logic
                future_return = prices[i+10] / prices[i] - 1

                # Win if price goes up — LOSS if price goes down
                win = future_return > 0

                # Convert real price movement into an RR-like multiplier
                # Scaled so real returns map to your original RR range
                rr = abs(future_return * leverage * 20)

                # PnL based on real move, no randomness
                pnl = size * rr if win else -size * rr

                # Update balance
                balance += pnl
                balance = max(balance, 1.0)

                wins += 1 if win else 0
                total_trades += 1
                equity_curve.append(balance)

        # -------------------------------------------------------
        # Results
        # -------------------------------------------------------
        final_balance = balance
        total_return = (final_balance / 100000 - 1) * 100
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Final Equity", f"${final_balance:,.0f}")
        col2.metric("Total Trades", f"{total_trades:,}")
        col3.metric("Win Rate", f"{win_rate:.1f}%")
        col4.metric("2024 Return", f"{total_return:+.1f}%")

        fig = go.Figure()
        fig.add_trace(go.Scatter(y=equity_curve, line=dict(color="#00ff9d", width=3)))
        fig.update_layout(title="Elite Equity Curve (REAL OKX)", template="plotly_dark", height=550)
        st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Click the button above to run the backtest.")
