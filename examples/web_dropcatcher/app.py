Python is complaining because you copied the Markdown code fences (` ```python` and ```), which are not valid Python.

Below is the updated `app.py` **without** any backticks. You can copy-paste it directly over your existing `app.py`:

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
    if 'close' not in df:
        st.error("CSV must contain a 'close' column.")
        st.stop()

    # ---------------------------
    # ATR Calculation
    # ---------------------------
    high = df['high'] if 'high' in df else df['close']
    low = df['low'] if 'low' in df else df['close']
    close = df['close']

    df['tr'] = np.maximum(
        high - low,
        np.maximum(abs(high - close.shift()), abs(low - close.shift()))
    )
    df['atr'] = df['tr'].rolling(30).mean().fillna(method='bfill')

    prices = df['close'].tolist()
    atr = df['atr'].tolist()
    st.success(f"Loaded {len(prices)} candles.")

    # ---------------------------
    # REVERSAL SIGNAL — Z-Score
    # ---------------------------
    window = 60
    roll_mean = df['close'].rolling(window).mean().fillna(method='bfill')
    roll_std = df['close'].rolling(window).std().replace(0, 1).fillna(method='bfill')

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
        max_lookahead = 300  # max bars to hold a trade

        trades_list = []  # store per-trade details

        i = window
        n = len(df)

        while i < n - 2:
            z = df['zscore'].iloc[i]
            atr_val = atr[i]

            # Skip if no signal or invalid ATR/zscore
            if np.isnan(z) or np.isnan(atr_val):
                i += 1
                continue

            if abs(z) < 2.0:
                i += 1
                continue

            # Direction: mean reversion
            direction = "short" if z > 2.0 else "long"

            # --- POSITION SIZING ---
            # Treat risk_pct as margin % of equity
            margin = balance * (risk_pct / 100.0)
            margin = min(margin, balance * 0.05)  # cap margin at 5% of balance

            if margin <= 0:
                # No more usable capital
                break

            # Save entry index before we start moving i
            entry_index = i

            # Use next candle's price as entry (no intra-bar lookahead)
            entry_price = prices[i + 1]

            # Levered notional and size
            notional = margin * leverage          # trade size in quote currency
            size = notional / entry_price         # coin size

            # --- SL & TP based on ATR ---
            if direction == "long":
                sl_price = entry_price - atr_mult_sl * atr_val
                tp_price = entry_price + atr_mult_tp * atr_val
            else:  # short
                sl_price = entry_price + atr_mult_sl * atr_val
                tp_price = entry_price - atr_mult_tp * atr_val

            # --- SIMULATE TRADE UNTIL STOP OR TP OR TIMEOUT ---
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
                else:  # short
                    if p >= sl_price:
                        exit_price = sl_price
                        exit_index = j
                        break
                    if p <= tp_price:
                        exit_price = tp_price
                        exit_index = j
                        break

            # If neither SL nor TP hit within max_lookahead, exit at last price
            if exit_price is None:
                exit_price = prices[end_index]
                exit_index = end_index

            # --- PNL CALC (no extra leverage multiplier) ---
            if direction == "long":
                raw_pnl = (exit_price - entry_price) * size
            else:
                raw_pnl = (entry_price - exit_price) * size

            # --- FEES on levered notional ---
            entry_fee = entry_price * abs(size) * fee
            exit_fee = exit_price * abs(size) * fee
            fee_cost = entry_fee + exit_fee

            pnl = raw_pnl - fee_cost

            # --- UPDATE BALANCE & STATS ---
            balance += pnl
            balance = max(balance, 0.0)  # never negative

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
                "margin": margin,
                "notional": notional,
                "size": size,
                "pnl": pnl,
                "fee_cost": fee_cost,
            })

            # Move to first bar after this trade exits (no overlapping trades)
            i = exit_index + 1

        # ---------------------------
        # METRICS
        # ---------------------------
        final_balance = balance
        total_return = (final_balance / initial_balance - 1) * 100.0
        win_rate = (wins / trades * 100.0) if trades > 0 else 0.0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Final Equity", f"${final_balance:,.2f}")
        c2.metric("Total Trades", trades)
        c3.metric("Win Rate", f"{win_rate:.1f}%")
        c4.metric("Total Return", f"{total_return:.1f}%")

        # ---------------------------
        # Equity Curve (per trade)
        # ---------------------------
        fig = go.Figure()
        fig.add_trace(go.Scatter(y=equity, mode='lines', name="Equity"))
        fig.update_layout(title="Equity Curve (by trade)", template="plotly_dark", height=550)
        st.plotly_chart(fig, use_container_width=True)

        # ---------------------------
        # Trade-Level Stats
        # ---------------------------
        trades_df = pd.DataFrame(trades_list)

        if not trades_df.empty:
            # Basic PnL stats
            wins_df = trades_df[trades_df["pnl"] > 0]
            losses_df = trades_df[trades_df["pnl"] < 0]

            avg_win = wins_df["pnl"].mean() if not wins_df.empty else 0.0
            avg_loss = losses_df["pnl"].mean() if not losses_df.empty else 0.0

            trades_df["cum_pnl"] = trades_df["pnl"].cumsum()
            trades_df["cum_max"] = trades_df["cum_pnl"].cummax()
            trades_df["dd"] = trades_df["cum_max"] - trades_df["cum_pnl"]
            max_dd = trades_df["dd"].max() if not trades_df["dd"].empty else 0.0

            st.subheader("Trade Statistics")
            c5, c6, c7 = st.columns(3)
            c5.metric("Avg Win", f"${avg_win:,.2f}")
            c6.metric("Avg Loss", f"${avg_loss:,.2f}")
            c7.metric("Max Drawdown (P&L)", f"${max_dd:,.2f}")

            with st.expander("Show trade log (first 100 trades)"):
                st.dataframe(trades_df.head(100))

    else:
        st.info("Click RUN BACKTEST to simulate deterministic reversals.")

If you still get an error, paste the exact traceback and I’ll pinpoint the line.
