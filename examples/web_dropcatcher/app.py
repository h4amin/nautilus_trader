import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import random

st.set_page_config(page_title="BTC DropCatcher Sim", layout="wide")
st.title("BTC DropCatcher – Live Paper Trading Sim (Sandbox)")
st.sidebar.header("Controls")
balance = st.sidebar.number_input("Virtual USD balance", value=100000, step=10000)
leverage = st.sidebar.slider("Leverage", 1, 125, 10)

if st.sidebar.button("Start / Restart Simulation"):
    st.session_state.balance = balance
    st.session_state.trades = []
    st.session_state.price_history = [108000 + random.uniform(-500,500)]
    st.success("Simulation started with $100K virtual!")

# Fake live data (replace with real Nautilus feed later)
if 'price_history' not in st.session_state:
    st.session_state.price_history = [108000]
    st.session_state.balance = 100000
    st.session_state.trades = []

current_price = st.session_state.price_history[-1] * (1 + random.uniform(-0.003, 0.003))
st.session_state.price_history.append(current_price)

# Simple fake ML signal
return_5m = (current_price / st.session_state.price_history[-30]) - 1 if len(st.session_state.price_history)>30 else 0
imbalance = random.uniform(-0.9, 0.3)
prob_drop = 0.5 + 0.4 * (return_5m < -0.015) * (imbalance < -0.65)
prob_drop = max(0.5, min(0.95, prob_drop + random.uniform(-0.05,0.05)))

col1, col2, col3 = st.columns(3)
col1.metric("BTC Price", f"${current_price:,.0f}")
col2.metric("5m Return", f"{return_5m:.2%}")
col3.metric("ML Drop Probability (20min)", f"{prob_drop:.1%}", 
            delta=f"{prob_drop-0.75:+.1%}" if prob_drop>0.75 else None)

# Fire signal
if prob_drop > 0.75 and random.random() > 0.7:  # ~30% of high-prob signals trigger
    size = (st.session_state.balance * 0.05 * leverage) / current_price
    st.session_state.trades.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "side": "SHORT",
        "price": current_price,
        "size": size,
        "prob": prob_drop
    })
    st.success(f"SHORT executed! Size {size:.4f} BTC @ ${current_price:,.0f}")

# Charts
df = pd.DataFrame({
    "Time": range(len(st.session_state.price_history)),
    "Price": st.session_state.price_history
})
fig = go.Figure()
fig.add_trace(go.Scatter(y=df.Price, mode='lines', name='BTC Price'))
fig.update_layout(height=400, title="Live BTC Price (simulated feed)")
st.plotly_chart(fig, use_container_width=True)

if st.session_state.trades:
    trades_df = pd.DataFrame(st.session_state.trades)
    st.subheader("Recent Signals")
    st.dataframe(trades_df.style.format({"price": "${:,.0f}", "prob": "{:.1%}"}))

st.sidebar.info("This runs 100% in the cloud after deploy · Zero real money · Nautilus sandbox ready")
