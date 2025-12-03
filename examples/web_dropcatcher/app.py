# app.py — Nautilus Pro • Realistic PnL with Dynamic Exits
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

st.title("Nautilus Pro — Full-Year Backtest with Dynamic Exits")

# ---------------------------
# Fetch BTC 5-min prices from OKX
# ---------------------------
def get_okx_full_year_5m():
    st.info("Fetching 1 year of BTC-USDT 5-min candles from OKX...")
    url = "https://www.okx.com/api/v5/market/history-candles"
    inst = "BTC-USDT"
    bar = "5m"
    limit = 5000
    all_candles = []
    next_before = None

    while len(all_candles) < 110000:  # ~1 year
        params = {"instId": inst, "bar": bar, "limit": limit}
        if next_before:
            params["before"] = next_before

        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if "data" not in data or not data["data"]:
            break

        candles = data["data"]
        all_candles.extend(candles)
        next_before = candles[-1][0]
        time.sleep(0.12)  # rate limit

    all_candles.reverse()
    closes = [float(c[4]) for c in all_candles if float(c[4]) > 0]  # remove zeros
    return closes

# ---------------------------
# Run backtest
# ---------------------------
if st.button("RUN NAUTILUS BACKTEST", type="primary", use_container_width=True):

    prices = get_okx_full_year_5m()
    prices = prices[-105000:]  # last ~1 year

    balance = 100000.0
    equity_curve = [balance]
    wins = 0
    total_trades = 0

    for i in range(100, len(prices) - 60):
        # Confidence engine
        imbalance = np.random.uniform(-0.9, 0.9)
        ret_5m = (prices[i] / prices[i-60] - 1) if prices[i-60] != 0 else 0

        confidence = max(
            np.clip(0.53 + 0.65*max(0, imbalance-0.20) - 0.12*max(0, ret_5m), 0.4, 0.99),
            np.clip(0.53 + 0.65*max(0, -imbalance-0.20) + 0.12*max(0, ret_5m), 0.4, 0.99)
        )

        if confidence > 0.88:
            # Position size capped at 5% of account
            size = balance * (risk_pct / 100) * leverage
            size = min(size, balance * 0.05)

            # Execution delay: 1 bar
            entry_index = i + 1
            if entry_index >= len(prices) - 10:
                continue
            entry_price = prices[entry_index]

            # Skip zero prices
            if entry_price <= 0:
                continue

            # Slippage ±0.05%
            slippage = np.random.uniform(-0.0005, 0.0005)
            entry_price *= (1 + slippage)

            # --- Dynamic Exit ---
            max_hold = 50  # max 50 bars (~4 hours)
            exit_index = entry_index + 1
            while exit_index < len(prices) and exit_index < entry_index + max_hold:
                # Recalculate confidence at each future bar
                imbalance_f = np.random.uniform(-0.9, 0.9)
                ret_f = (prices[exit_index] / prices[exit_index-60] - 1) if prices[exit_index-60] != 0 else 0
                conf_f = max(
                    np.clip(0.53 + 0.65*max(0, imbalance_f-0.20) - 0.12*max(0, ret_f), 0.4, 0.99),
                    np.clip(0.53 + 0.65*max(0, -imbalance_f-0.20) + 0.12*max(0, ret_f), 0.4, 0.99)
                )
                if conf_f < 0.5:  # exit threshold
                    break
                exit_index += 1

            # Ensure exit index is valid
            if exit_index >= len(prices):
                exit_index = len(prices) - 1
            exit_price = prices[exit_index]

            if exit_price <= 0:
                continue

            # Realistic PnL calculation
            pnl = ((exit_price - entry_price) / entry_price) * leverage * size
            balance += pnl
            balance = max(balance, 1.0)

            # Win/loss stats
            wins += 1 if pnl > 0 else 0
            total_trades += 1
            equity_curve.append(balance)

    # Metrics
    final_balance = balance
    total_return = (final_balance / 100000 - 1) * 100
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Final Equity", f"${final_balance:,.0f}")
    col2.metric("Total Trades", f"{total_trades:,}")
    col3.metric("Win Rate", f"{win_rate:.1f}%")
    col4.metric("2024 Return", f"{total_return:+.1f}%")

    # Equity curve
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=equity_curve, line=dict(color="#00ff9d", width=3)))
    fig.update_layout(title="Nautilus Pro Equity Curve • 1 Year (Dynamic Exits)", template="plotly_dark", height=550)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Click the button above to run the full-year Nautilus backtest with dynamic exits.")
