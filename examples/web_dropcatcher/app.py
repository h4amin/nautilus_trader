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
    leverage = st.slider("Leverage", 1, 50, 5)
    risk_pct = st.slider(
        "Margin % per trade (of equity)",
        0.5, 5.0, 1.0, 0.1,
        help="Fraction of account used as margin per trade; actual PnL scales with leverage."
    )
    fee_rate = st.number_input("Fee per side (%)", 0.01, 0.5, 0.05, 0.01)
    atr_mult_sl = st.slider("ATR Stop Loss Multiplier", 1.0, 8.0, 2.0, 0.1)
    atr_mult_tp = st.slider("ATR Take Profit Multiplier", 1.0, 10.0, 3.0, 0.1)

st.title("Nautilus Pro Reversal — Deterministic Backtest")

# ---------------------------
# Load BTC CSV
# ---------------------------
csv_file = "btc_5min.csv"
if not os.path.exists(csv_file):
    st.error(f"{csv_file} not found! Place it next to app.py.")
    st.stop()

df = pd.read_csv(csv_file)
if 'close' not in df.columns:
    st.error("CSV must contain a 'close' column.")
    st.stop()

# ---------------------------
# ATR Calculation
# ---------------------------
high = df['high'] if 'high' in df.columns else df['close']
low = df['low'] if 'low' in df.columns else df['close']
close = df['close']

df['tr'] = np.maximum(
    high - low,
    np.maximum(abs(high - close.shift()), abs(low - close.shift()))
)
df['atr'] = df['tr'].rolling(30).mean().ffill()

prices = df['close'].tolist()
atr = df['atr'].tolist()
st.success(f"Loaded {len(prices):,} candles.")

# ---------------------------
# Z-Score Reversal Signal
# ---------------------------
window = 60
roll_mean = df['close'].rolling(window).mean().ffill()
roll_std = df['close'].rolling(window).std().replace(0, 1).ffill()
df['zscore'] = (df['close'] - roll_mean) / roll_std

# ---------------------------
# BACKTEST
# ---------------------------
if st.button("RUN BACKTEST", type="primary", use_container_width=True):
    initial_balance = 100_000.0
    balance = initial_balance
    equity = [balance]
    wins = 0
    trades = 0
    fee = fee_rate / 100.0
    max_lookahead = 300

    trades_list = []
    i = window
    n = len(df)

    while i < n - 2:
        z = df['zscore'].iloc[i]
        atr_val = atr[i]

        if np.isnan(z) or np.isnan(atr_val) or abs(z) < 2.0:
            i += 1
            continue

        direction = "short" if z > 2.0 else "long"
        margin = min(balance * (risk_pct / 100.0), balance * 0.05)
        if margin <= 0:
            break

        entry_index = i
        entry_price = prices[i + 1]
        notional = margin * leverage
        size = notional / entry_price

        if direction == "long":
            sl_price = entry_price - atr_mult_sl * atr_val
            tp_price = entry_price + atr_mult_tp * atr_val
        else:
            sl_price = entry_price + atr_mult_sl * atr_val
            tp_price = entry_price - atr_mult_tp * atr_val

        exit_price = None
        exit_index = None
        end_index = min(i + max_lookahead, n - 1)

        for j in range(i + 2, end_index + 1):
            p = prices[j]
            if direction == "long":
                if p <= sl_price:
                    exit_price = sl_price
                    exit_index = j
                    break
                if p >= tp_price:
                    exit_price = tp_price
                    exit_index = j
                    break
            else:
                if p >= sl_price:
                    exit_price = sl_price
                    exit_index = j
                    break
                if p <= tp_price:
                    exit_price = tp_price
                    exit_index = j
                    break

        if exit_price is None:
            exit_price = prices[end_index]
            exit_index = end_index

        if direction == "long":
            raw_pnl = (exit_price - entry_price) * size
        else:
            raw_pnl = (entry_price - exit_price) * size

        entry_fee = entry_price * abs(size) * fee
        exit_fee = exit_price * abs(size) * fee
        pnl = raw_pnl - (entry_fee + exit_fee)

        balance += pnl
        balance = max(balance, 0.0)
        trades += 1
        if pnl > 0:
            wins += 1

        equity.append(balance)
        trades_list.append({
            "entry_index": entry_index,
            "exit_index": exit_index,
            "direction": direction,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": pnl
        })

        i = exit_index + 1

    # ---------------------------
    # Results
    # ---------------------------
    final_balance = balance
    total_return = (final_balance / initial_balance - 1) * 100.0
    win_rate = (wins / trades * 100.0) if trades > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Final Equity", f"${final_balance:,.2f}")
    c2.metric("Total Trades", trades)
    c3.metric("Win Rate", f"{win_rate:.1f}%")
    c4.metric("Total Return", f"{total_return:.1f}%")

    fig = go.Figure()
    fig.add_trace(go.Scatter(y=equity, mode='lines', line=dict(color="#00ff9d", width=3)))
    fig.update_layout(title="Equity Curve", template="plotly_dark", height=550)
    st.plotly_chart(fig, use_container_width=True)

    if trades_list:
        trades_df = pd.DataFrame(trades_list)
        avg_win = trades_df[trades_df["pnl"] > 0]["pnl"].mean() if (trades_df["pnl"] > 0).any() else 0
        avg_loss = trades_df[trades_df["pnl"] < 0]["pnl"].mean() if (trades_df["pnl"] < 0).any() else 0
        max_dd = (trades_df["pnl"].cumsum().cummax() - trades_df["pnl"].cumsum()).max()

        col5, col6, col7 = st.columns(3)
        col5.metric("Avg Win", f"${avg_win:,.2f}")
        col6.metric("Avg Loss", f"${avg_loss:,.2f}")
        col7.metric("Max Drawdown", f"${max_dd:,.2f}")

else:
    st.info("Place your `btc_5min.csv` next to `app.py` and click RUN BACKTEST.")
