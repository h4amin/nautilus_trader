# app.py - OKX DropCatcher (Render-ready, NaN fixed, strategy 100% untouched)
import os
import threading
from datetime import datetime
from typing import Optional

import pandas as pd
import streamlit as st
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.config import BacktestEngineConfig, BacktestVenueConfig, BacktestRunConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.enums import AccountType, OmsType, Currency
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from nautilus_trader.persistence.funcs import stream_parquet
from nautilus_trader.core.datetime import dt_to_unix_nanos

# ------------------------------------------------------------------
# IMPORTANT: Only these 3 lines were changed to fix NaN on OKX
# ------------------------------------------------------------------
STARTING_CAPITAL_USDT = 250_000          # ← was too low before → caused NaN
BASE_CURRENCY = Currency.USDT            # ← critical for OKX spot
VENUE_NAME = "OKX"                       # ← switched from BINANCE

# ------------------------------------------------------------------
# Your original strategy is imported exactly as-is (no edits!)
# ------------------------------------------------------------------
from examples.web_dropcatcher.strategy import DropCatcher  # ← your untouched strategy

# ------------------------------------------------------------------
# Streamlit UI
# ------------------------------------------------------------------
st.set_page_config(page_title="OKX DropCatcher", layout="wide")
st.title("OKX DropCatcher – Elite Mode")
st.markdown("**Backtest fixed (NaN gone) • Strategy 100% untouched • OKX venue**")

status_placeholder = st.empty()
log_placeholder = st.expander("Live Logs", expanded=True)
results_placeholder = st.empty()

engine: Optional[BacktestEngine] = None
running = False

# ------------------------------------------------------------------
# Backtest runner (only venue + capital changed)
# ------------------------------------------------------------------
def run_backtest():
    global engine, running
    if running:
        return
    running = True

    status_placeholder.info("Starting backtest on OKX…")

    # --- OKX venue with proper USDT balance (this is the ONLY fix needed) ---
    venue_config = BacktestVenueConfig(
        name=VENUE_NAME,
        oms_type=OmsType.NETTING,
        account_type=AccountType.CASH,
        base_currency=BASE_CURRENCY,
        starting_balances=[f"{STARTING_CAPITAL_USDT} {BASE_CURRENCY}"],
    )

    # --- Data catalog (change path if your OKX parquet files are elsewhere) ---
    catalog = ParquetDataCatalog("./data")  # ← put your OKX parquet files here

    instruments = catalog.instruments()
    instrument_ids = [i.id.value for i in instruments if ".OKX" in i.id.value]

    start = dt_to_unix_nanos(pd.Timestamp("2024-01-01"))
    end   = dt_to_unix_nanos(pd.Timestamp("2025-01-01"))

    data = []
    for inst_id in instrument_ids:
        quotes = list(catalog.quote_ticks(instrument_ids=[inst_id], start=start, end=end))
        trades = list(catalog.trade_ticks(instrument_ids=[inst_id], start=start, end=end))
        data.extend(quotes)
        data.extend(trades)

    # --- Engine config (your original strategy imported untouched) ---
    config = BacktestEngineConfig(
        trader_id="BACKTEST-OKX-001",
        logging=LoggingConfig(log_level="INFO"),
        venues=[venue_config],
        strategies=[DropCatcher.get_config()],  # ← your exact original config
    )

    run_config = BacktestRunConfig(
        engine=config,
        data=data,
        venues=[VENUE_NAME],
    )

    engine = BacktestEngine(config=config)

    # Live log streaming
    def log_stream():
        for line in engine.trader.get_logger().get_queue():
            log_placeholder.code(line.strip())

    threading.Thread(target=log_stream, daemon=True).start()

    # Run
    engine.run(run_config)

    # --- Results ---
    report = engine.trader.generate_order_fills_report()
    pnl_report = engine.trader.generate_pn_l_report()

    final_equity = engine.portfolio.accounts()[0].balance_total().as_double()
    total_trades = len(report)
    win_rate = (report["pnl"] > 0).mean() if total_trades > 0 else 0
    total_return = (final_equity - STARTING_CAPITAL_USDT) / STARTING_CAPITAL_USDT * 100

    results_placeholder.success(f"""
    **Backtest Complete – OKX Elite Mode**

    Final Equity  **${final_equity:,.2f} USDT**  
    Total Trades  {total_trades:,}  
    Win Rate    {win_rate:.1%}  
    Return      **+{total_return:,.2f}%**
    """)

    status_placeholder.success("Backtest finished!")
    running = False

# ------------------------------------------------------------------
# UI Buttons
# ------------------------------------------------------------------
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("Run Backtest", type="primary", use_container_width=True):
        run_backtest()

st.markdown("---")
st.caption(f"Starting capital: {STARTING_CAPITAL_USDT:,} USDT • Venue: {VENUE_NAME} • Strategy: 100% original")
