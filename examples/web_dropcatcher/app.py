# app.py — Nautilus Pro • Realistic Backtest with OKX 5-min candles
import streamlit as st
import numpy as np
import pandas as pd
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

st.title("Nautilus Pro — Backtest with OKX BTC 5-min Candles")

# ---------------------------
# Fetch BTC 5-min candles from OKX
# ---------------------------
@st.cache_data(show_spinner=False)
def fetch_okx_5min(symbol="BTC-USDT", total_candles=105000, limit_per_request=5000):
    url = "https://www.okx.com/api/v5/market/history-candles"
    all_candles = []
    before = None
    progress = st.progress(0)

    total_requests = int(total_candles / limit_per_request) + 1
    request_count = 0

    while len(all_candles) < total_candles:
        params = {"instId": symbol, "bar": "5m", "limit": limit_per_request}
        if before:
            params["before"] = before

        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if "data" not in data or not data["data"]:
            st.warning("No more data returned by OKX.")
            break

        candles = data["data"]
        all_candles.extend(candles)
        before = candles[-1][0]

        request_count += 1
        progress.progress(min(request_count/total_requests, 1.0))
        time.sleep(0.12)  # rate limit

    all_candles.reverse()
    closes = [float(c[4]) for c in all_candles if float(c[4]) > 0]
    return closes[-105000:]  # last ~1 year

# ---------------------------
# Run backtest
# ---------------------------
if st.button("RUN NAUTILUS BACKTEST", type="primary", use_container_width=True):
    with st.spinner("Fetching BTC 5-min candles from OKX..."):
        prices = fetch_okx_5min()
    
    st.success(f"Fetched {len(prices)} candles.")

    balance = 100000.0
    equity_curve = [balance]
    wins = 0
    total_trades = 0

    for i in range(100, len(prices) - 60):
        imbalance = np.random.uniform(-0.9, 0.9)
        ret_5m = (prices[i] / prices[i-60] - 1) if prices[i-60] != 0 else 0

        confidence = max(
            np.clip(0.53 + 0.65*max(0, imbalance-0.20) - 0.12*max(0, ret_5m), 0.4, 0.99),
            np.clip(0.53 + 0.65*max(0, -imbalance-0.20) + 0.12*max(0, ret_5m), 0.4, 0.99)
        )

        if confidence > 0.88:
            size = balance * (risk_pct / 100) * leverage
            size = min(size, balance * 0.05)

            entry_index = i + 1
            if entry_index >= len(prices) - 10:
                continue
            entry_price = prices[entry_index] * (1 + np.random.uniform(-0.0005, 0.0005))  # slippage

            max_hold = 50
            exit_index = entry_index + 1
            while exit_index < len(prices) and exit_index < entry_index + max_hold:
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
            pnl = ((exit_price - entry_price) / entry_price) * leverage * size
            balance += pnl
            balance = max(balance, 1.0)

            wins += 1 if pnl > 0 else 0
            total_trades += 1
            equity_curve.append(balance)

    final_balance = balance
    total_return = (final_balance / 100000 - 1) * 100
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Final Equity", f"${final_balance:,.0f}")
    col2.metric("Total Trades", f"{total_trades:,}")
    col3.metric("Win Rate", f"{win_rate:.1f}%")
    col4.metric("2024 Return", f"{total_return:+.1f}%")

    fig = go.Figure()
    fig.add_trace(go.Scatter(y=equity_curve, line=dict(color="#00ff9d", width=3)))
    fig.update_layout(title="Nautilus Pro Equity Curve • OKX 5-min", template="plotly_dark", height=550)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Click the button above to fetch BTC data and run the backtest.")
