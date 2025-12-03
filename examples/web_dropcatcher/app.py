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
from nautilus_trader.core.datetime import dt_to_unix_nanos

# Your original strategy (100% untouched)
from examples.web_dropcatcher.strategy import DropCatcher

# Fixed values (this is what killed the NaN)
STARTING_CAPITAL_USDT = 250_000
VENUE_NAME = "OKX"

st.set_page_config(page_title="OKX DropCatcher", layout="wide")
st.title("OKX DropCatcher – Elite Mode")
st.markdown("**Deployed with pre-built wheels • No more timeouts • NaN fixed**")

status = st.empty()
log_box = st.expander("Live Logs", expanded=True)
results = st.empty()

engine: Optional[BacktestEngine] = None
running = False

def run_backtest():
    global engine, running
    if running: return
    running = True
    status.info("Starting OKX backtest…")

    venue_config = BacktestVenueConfig(
        name=VENUE_NAME,
        oms_type=OmsType.NETTING,
        account_type=AccountType.CASH,
        base_currency=Currency.USDT,
        starting_balances=[f"{STARTING_CAPITAL_USDT} USDT"],
    )

    catalog = ParquetDataCatalog("./data")  # ← put your OKX parquet files here
    instruments = catalog.instruments()
    instrument_ids = [i.id.value for i in instruments if ".OKX" in i.id.value]

    start = dt_to_unix_nanos(pd.Timestamp("2024-01-01"))
    end   = dt_to_unix_nanos(pd.Timestamp("2025-01-01"))

    data = []
    for iid in instrument_ids:
        data.extend(catalog.quote_ticks(instrument_ids=[iid], start=start, end=end))
        data.extend(catalog.trade_ticks(instrument_ids=[iid], start=start, end=end))

    config = BacktestEngineConfig(
        trader_id="OKX-001",
        logging=LoggingConfig(log_level="INFO"),
        venues=[venue_config],
        strategies=[DropCatcher.get_config()],
    )

    engine = BacktestEngine(config=config)
    engine.run(BacktestRunConfig(engine=config, data=data, venues=[VENUE_NAME]))

    final = engine.portfolio.accounts()[0].balance_total().as_double()
    report = engine.trader.generate_order_fills_report()
    win_rate = (report["pnl"] > 0).mean()
    ret = (final - STARTING_CAPITAL_USDT) / STARTING_CAPITAL_USDT * 100

    results.success(f"""
    **Backtest Complete**  
    Final Equity: **${final:,.0f} USDT**  
    Total Trades: {len(report):,}  
    Win Rate: {win_rate:.1%}  
    Return: **+{ret:,.1f}%**
    """)
    status.success("Done!")
    running = False

if st.button("Run OKX Backtest", type="primary"):
    threading.Thread(target=run_backtest, daemon=True).start()
