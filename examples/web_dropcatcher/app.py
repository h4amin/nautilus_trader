import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import random

st.set_page_config(page_title="BTC DropCatcher", layout="wide")
st.title("BTC DropCatcher – Cloud Paper Trading Sim")

if st.sidebar.button("Start Simulation"):
    st.session_state.balance = 100000.0
    st.session_state.price_history = [108000]
    st.session_state.trades = []
    st.session_state.running = True

if st.session_state.get("running"):
    price = st.session_state.price_history[-1] * (1 + random.uniform(-0.004, 0.004))
    st.session_state.price_history.append(price)
    return_5m = (price / st.session_state.price_history[max(-30, -len(st.session_state.price_history))]) - 1
    imbalance = random.uniform(-0.9, 0.3)
    prob_drop = max(0.5, min(0.95, 0.5 + 0.4*(return_5m < -0.015)*(imbalance < -0.65)))

    if prob_drop > 0.75 and random.random() > 0.65:
        size = (st.session_state.balance * 0.05) / price
        pnl = size * random.uniform(400, 900)
        st.session_state.balance += pnl
        st.session_state.trades.append({"Time": datetime.now().strftime("%H:%M"), "SHORT": f"${price:,.0f}", "Prob": f"{prob_drop:.1%}", "P&L": f"+${pnl:,.0f}"})
        st.success("SHORT signal fired!")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("BTC Price", f"${price:,.0f}")
    c2.metric("5m Return", f"{return_5m:.2%}")
    c3.metric("Imbalance", f"{imbalance:.1%}")
    c4.metric("Drop Prob", f"{prob_drop:.1%}", delta=f"{(prob_drop-0.75)*100:+.0f}%" if prob_drop>0.75 else None)

    if len(st.session_state.price_history) > 1:
        fig = go.Figure(go.Scatter(y=st.session_state.price_history, mode="lines"))
        fig.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    if st.session_state.trades:
        st.write(pd.DataFrame(st.session_state.trades))
        st.metric("Virtual P&L", f"${st.session_state.balance-100000:+,.0f}")
