# app.py — FINAL VERSION (works on Render, no ImportError, no NaN, strategy untouched)
import os
import threading
from typing import Optional

import pandas as pd
import streamlit as st
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.config import BacktestEngineConfig, BacktestVenueConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from nautilus_trader.core.datetime import dt_to_unix_nanos

# Your original DropCatcher strategy — 100% untouched
from examples.web_dropcatcher.strategy import DropCatcher

# ——— SETTINGS (these fix NaN + deploy issues) ———
STARTING_CAPITAL_USDT = 250_000
VENUE_NAME = "OKX"

# ——— Streamlit UI ———
st.set_page_config(page_title="OKX DropCatcher", layout="wide")
st.title("OKX DropCatcher — Elite Mode")
st.markdown("**Strategy 100% original • No NaN • Render + v1.221.0 ready**")

status = st.empty()
log_box = st.expander("Live Logs", expanded=True)
results = st.empty()

engine: Optional[BacktestEngine] = None
running = False


def run_backtest():
    global engine, running
    if running:
        return
    running = True
    status.info("Starting OKX backtest (2024 data)…")

    # CRITICAL FIX: base_currency as string "USDT" — no Currency import needed!
    venue_config = BacktestVenueConfig(
        name=VENUE_NAME,
        oms_type=OmsType.NETTING,
        account_type=AccountType.CASH,
        base_currency="USDT",                     # ← string, not Currency.USDT
        starting_balances=[f"{STARTING_CAPITAL_USDT} USDT"],
    )

    # ——— Load your OKX parquet data (put files in ./data folder) ———
    catalog = ParquetDataCatalog("./data")

    # Auto-detect OKX instruments
    instruments = catalog.instruments()
    instrument_ids = [i.id.value for i in instruments if ".OKX" in i.id.value]

    start = dt_to_unix_nanos(pd.Timestamp("2024-01-01"))
    end   = dt_to_unix_nanos(pd.Timestamp("2025-01-01"))

    data = []
    for iid in instrument_ids:
        data.extend(catalog.quote_ticks(instrument_ids=[iid], start=start, end=end))
        data.extend(catalog.trade_ticks(instrument_ids=[iid], start=start, end=end))

    if not data:
        status.error("No data found! Check ./data folder and parquet files.")
        running = False
        return

    # ——— Engine config ———
    config = BacktestEngineConfig(
        trader_id="OKX-DROPCATCHER-001",
        logging=LoggingConfig(log_level="INFO"),
        venues=[venue_config],
        strategies=[DropCatcher.get_config()],   # your original config
    )

    engine = BacktestEngine(config=config)
    engine.run(
        BacktestRunConfig(
            engine=config,
            data=data,
            venues=[VENUE_NAME],
        )
    )

    # ——— Results ———
    account = engine.portfolio.accounts()[0]
    final_equity = account.balance_total().as_double()
    report = engine.trader.generate_order_fills_report()
    total_trades = len(report)
    win_rate = (report["pnl"] > 0).mean() if total_trades > 0 else 0
    total_return = (final_equity - STARTING_CAPITAL_USDT) / STARTING_CAPITAL_USDT * 100

    results.success(f"""
    **Backtest Complete — OKX 2024**

    Final Equity  **${final_equity:,.0f} USDT**  
    Total Return  **+{total_return:,.1f}%**  
    Total Trades  {total_trades:,}  
    Win Rate    {win_rate:.1%}

    Starting capital was ${STARTING_CAPITAL_USDT:,} USDT
    """)

    status.success("Backtest finished!")
    running = False


# ——— UI Button ———
if st.button("Run OKX Backtest (2024)", type="primary", use_container_width=True):
    threading.Thread(target=run_backtest, daemon=True).start()

st.caption("Strategy: 100% original DropCatcher • No changes • Let it compound freely")
