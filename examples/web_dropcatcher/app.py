# Nautilus Pro Reversal — Local CSV Backtest (Deterministic)
# Rewritten to remove randomness and use a realistic ATR stop/take-profit and risk model.
# Place this file next to your `btc_5min.csv` and run with `streamlit run app.py`.

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
    st.header("Nautilus Pro Reversal • Elite — Deterministic")
    leverage = st.slider("Leverage", 1, 125, 10)
    risk_pct = st.slider("Risk % (per trade)", 0.1, 5.0, 1.0, 0.1)
    fee_rate = st.number_input("Fee per side (%)", 0.01, 0.5, 0.05, 0.01)
    atr_period = st.number_input("ATR period (bars)", 5, 100, 14, 1)
    atr_mult = st.number_input("ATR stop multiplier", 0.5, 10.0, 3.0, 0.1)
    tp_atr_mult = st.number_input("TP (take profit) ATR multiple", 0.5, 10.0, 3.0, 0.1)
    lookback = st.number_input("Signal lookback (bars)", 10, 500, 60, 1)
    zscore_thresh = st.number_input("Reversion z-score threshold", 0.5, 5.0, 2.0, 0.1)

st.title("Nautilus Pro Reversal — Backtest with Local BTC CSV & Deterministic Risk")

# ---------------------------
# Load CSV
# ---------------------------
csv_file = "btc_5min.csv"
if not os.path.exists(csv_file):
    st.error(f"{csv_file} not found! Please place it in the same folder as app.py.")
    st.stop()

# Read CSV, expect columns: timestamp, open, high, low, close, volume (at minimum)
raw = pd.read_csv(csv_file)
if 'close' not in raw.columns or 'high' not in raw.columns or 'low' not in raw.columns or 'open' not in raw.columns:
    st.error("CSV must contain 'open','high','low','close' columns.")
    st.stop()

# Ensure datetime if possible
if 'timestamp' in raw.columns:
    try:
        raw['timestamp'] = pd.to_datetime(raw['timestamp'])
        raw = raw.set_index('timestamp')
    except Exception:
        pass

df = raw.copy().reset_index(drop=True)
prices = df['close'].values
st.success(f"Loaded {len(prices)} BTC 5-min candles from {csv_file}")

# ---------------------------
# Helper indicators
# ---------------------------

def atr(df, n=14):
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=1).mean()

# Compute SMA and z-score over lookback window to detect overextension
window = int(lookback)
df['sma'] = df['close'].rolling(window=window, min_periods=1).mean()
df['dev'] = (df['close'] - df['sma'])
df['std'] = df['dev'].rolling(window=window, min_periods=1).std().replace(0, np.nan).fillna(0)
df['zscore'] = df['dev'] / (df['std'] + 1e-12)

df['atr'] = atr(df, int(atr_period))

# ---------------------------
# Backtest parameters
# ---------------------------
INITIAL_BALANCE = 100_000.0
MIN_BALANCE = 0.0  # allow full drawdown for realism (don't force $1 floor)

# ---------------------------
# Run Backtest
# ---------------------------
if st.button("RUN DETERMINISTIC REVERSAL BACKTEST", type="primary", use_container_width=True):
    balance = INITIAL_BALANCE
    equity_curve = [balance]
    wins = 0
    total_trades = 0
    fee = fee_rate / 100.0

    positions = []  # store active trades for logging
    trade_log = []

    # iterate starting after we have enough lookback and ATR
    start = max(window, int(atr_period))

    for i in range(start, len(df) - 1):
        price = df.at[i, 'close']
        z = df.at[i, 'zscore']
        atr_val = df.at[i, 'atr'] if df.at[i, 'atr'] > 0 else np.nan

        # check existing positions and update exits (we use simple single-position model)
        # For simplicity, assume at most 1 position at a time
        if positions:
            pos = positions[0]
            current_price = df.at[i, 'close']
            # check stop loss
            if pos['side'] == 'long':
                if current_price <= pos['stop']:
                    exit_price = pos['stop']
                    reason = 'stop'
                elif current_price >= pos['tp']:
                    exit_price = pos['tp']
                    reason = 'tp'
                else:
                    exit_price = None
            else:
                if current_price >= pos['stop']:
                    exit_price = pos['stop']
                    reason = 'stop'
                elif current_price <= pos['tp']:
                    exit_price = pos['tp']
                    reason = 'tp'
                else:
                    exit_price = None

            if exit_price is not None:
                # close position
                size_usd = pos['size_usd']
                entry_price = pos['entry_price']
                side = pos['side']
                if side == 'long':
                    pnl = ((exit_price - entry_price) / entry_price) * size_usd * leverage
                else:
                    pnl = ((entry_price - exit_price) / entry_price) * size_usd * leverage

                # fees (on both sides) approximated as fee percent * notional
                pnl -= (entry_price * size_usd * fee) + (exit_price * size_usd * fee)

                balance += pnl
                trade_log.append({
                    'entry_index': pos['entry_index'],
                    'exit_index': i,
                    'side': side,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'size_usd': size_usd,
                    'reason': reason
                })
                wins += 1 if pnl > 0 else 0
                total_trades += 1
                positions.pop(0)
                equity_curve.append(balance)

        # If flat, check for reversal entry
        if not positions and not np.isnan(z) and not np.isnan(atr_val):
            # Reversal signal: zscore exceeds threshold in magnitude
            if abs(z) >= zscore_thresh:
                side = 'short' if z > 0 else 'long'

                # size calculation: risk per trade is risk_pct of account, compute size in USD such that
                # stop distance = atr_mult * ATR, so risk in USD = size_usd * (stop_distance / entry_price) * leverage
                entry_price = df.at[i + 1, 'close']  # enter at next bar's open/close
                stop_distance = atr_mult * atr_val

                if side == 'long':
                    stop_price = entry_price - stop_distance
                    tp_price = entry_price + tp_atr_mult * atr_val
                else:
                    stop_price = entry_price + stop_distance
                    tp_price = entry_price - tp_atr_mult * atr_val

                # If stop_price/TP invalid (e.g., negative), skip
                if stop_price <= 0 or tp_price <= 0:
                    continue

                # risk in fraction of entry price (per unit of position): stop_distance / entry_price
                risk_fraction = stop_distance / entry_price
                if risk_fraction <= 0:
                    continue

                # size_usd so that risk_pct of account is risked (considering leverage)
                target_risk_usd = balance * (risk_pct / 100.0)
                # risk on leveraged position = size_usd * risk_fraction * leverage
                size_usd = target_risk_usd / (risk_fraction * leverage)

                # cap position to 5% notional of account (safety)
                max_notional = balance * 0.05
                if size_usd > max_notional:
                    size_usd = max_notional

                # minimal size sanity check
                if size_usd <= 0:
                    continue

                # create position
                pos = {
                    'entry_index': i + 1,
                    'entry_price': entry_price,
                    'side': side,
                    'size_usd': size_usd,
                    'stop': stop_price,
                    'tp': tp_price
                }

                positions.append(pos)
                # we don't subtract notional from balance until exit (P&L realized)

    # If still position open at end, close at last price
    if positions:
        pos = positions[0]
        exit_price = df.at[len(df) - 1, 'close']
        entry_price = pos['entry_price']
        if pos['side'] == 'long':
            pnl = ((exit_price - entry_price) / entry_price) * pos['size_usd'] * leverage
        else:
            pnl = ((entry_price - exit_price) / entry_price) * pos['size_usd'] * leverage
        pnl -= (entry_price * pos['size_usd'] * fee) + (exit_price * pos['size_usd'] * fee)
        balance += pnl
        trade_log.append({
            'entry_index': pos['entry_index'],
            'exit_index': len(df) - 1,
            'side': pos['side'],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl': pnl,
            'size_usd': pos['size_usd'],
            'reason': 'eod'
        })
        wins += 1 if pnl > 0 else 0
        total_trades += 1
        equity_curve.append(balance)

    # Metrics
    final_balance = balance
    total_return = (final_balance / INITIAL_BALANCE - 1) * 100
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Final Equity", f"${final_balance:,.2f}")
    col2.metric("Total Trades", f"{total_trades:,}")
    col3.metric("Win Rate", f"{win_rate:.1f}%")
    col4.metric("Total Return", f"{total_return:+.1f}%")

    # Equity curve plot
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=equity_curve, line=dict(width=3)))
    fig.update_layout(title="Deterministic Reversal Equity Curve • BTC 5-min (with Fees)", template="plotly_dark", height=550)
    st.plotly_chart(fig, use_container_width=True)

    # Show trade table (last 200 trades)
    if trade_log:
        trades_df = pd.DataFrame(trade_log)
        st.subheader("Recent trades (last 200)")
        st.dataframe(trades_df.sort_values('exit_index', ascending=False).head(200))

else:
    st.info("Click the button above to run the deterministic reversal backtest using BTC 5-min data.")
