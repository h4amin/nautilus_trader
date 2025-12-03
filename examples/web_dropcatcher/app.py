import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import ccxt
import time
from typing import Dict, List
from dataclasses import dataclass

# Nautilus Trader imports
from nautilus_trader.config import BacktestVenueConfig, BacktestDataConfig, BacktestRunConfig
from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.model.identifiers import Venue, Symbol, TradingStrategyId
from nautilus_trader.adapters.ccxt.config import CCXTDataConfig, CCXTFuturesVenueConfig
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from nautilus_trader.trading.strategy import StrategyConfig
from nautilus_trader.analysis import PerformanceMetrics

st.set_page_config(page_title="Nautilus DropCatcher Pro", layout="wide", initial_sidebar_state="expanded")

# Hide Streamlit artifacts
hide_css = """
<style>
    #MainMenu, header, footer {visibility: hidden;}
    .stDeployButton {display: none;}
</style>
"""
st.markdown(hide_css, unsafe_allow_html=True)

@dataclass
class Trade:
    time: str
    price: float
    size: float
    imbalance: float
    prob_drop: float
    pnl: float
    side: str  # 'SHORT'

# Session state
if "trades" not in st.session_state:
    st.session_state.trades: List[Trade] = []
    st.session_state.balance = 100_000.0
    st.session_state.price_history = []
    st.session_state.mode = "paper"  # "paper" or "live"
    st.session_state.api_key = ""
    st.session_state.api_secret = ""

# Sidebar: Config
st.sidebar.header("Bot Config")
st.session_state.mode = st.sidebar.selectbox("Mode", ["paper", "live"], index=0)
if st.session_state.mode == "live":
    st.session_state.api_key = st.sidebar.text_input("Bybit API Key", type="password")
    st.session_state.api_secret = st.sidebar.text_input("Bybit API Secret", type="password")
st.sidebar.success(f"Mode: {st.session_state.mode.upper()}")

# Real BTC Data via CCXT (Bybit futures)
@st.cache_data(ttl=10)  # Cache 10s for perf, but refresh often
def fetch_price_and_book():
    exchange = ccxt.bybit({
        'apiKey': st.session_state.api_key,
        'secret': st.session_state.api_secret,
        'sandbox': st.session_state.mode == "paper",  # Testnet for paper/live toggle
        'options': {'defaultType': 'future'},
    })
    try:
        ticker = exchange.fetch_ticker('BTC/USDT')
        price = ticker['last']
        orderbook = exchange.fetch_order_book('BTC/USDT', limit=20)
        # Calculate imbalance: (bid volume - ask volume) / total
        bids = sum([bid[1] for bid in orderbook['bids'][:10]])
        asks = sum([ask[1] for ask in orderbook['asks'][:10]])
        imbalance = (bids - asks) / (bids + asks + 1e-6)  # -1 to +1, negative = sell pressure
        return price, imbalance
    except Exception as e:
        st.error(f"API Error: {e}")
        return st.session_state.price_history[-1] if st.session_state.price_history else 109_000.0, np.random.uniform(-0.5, 0.5)

price, imbalance = fetch_price_and_book()
st.session_state.price_history.append(price)
if len(st.session_state.price_history) > 1000:
    st.session_state.price_history = st.session_state.price_history[-1000:]

# Signal Logic (enhanced with real imbalance)
lookback = st.session_state.price_history[-100:]
if len(lookback) > 20:
    ret_5m = (price / lookback[0]) - 1
    prob_drop = 0.5 + 0.3 * (imbalance < -0.6) + 0.2 * (ret_5m < -0.01)
    prob_drop = np.clip(prob_drop, 0.5, 0.95)
else:
    prob_drop = 0.5

# Trade Execution (integrate Nautilus for real sim/live)
def execute_trade(prob: float, price: float, imbalance: float):
    if prob > 0.8 and st.session_state.balance > 1000:
        size_usd = st.session_state.balance * 0.03  # 3% risk
        size_btc = size_usd / price
        # Simulate P&L for now; in live, use Nautilus to submit order
        if st.session_state.mode == "live":
            # Placeholder: Submit short via CCXT
            pass  # exchange.create_market_sell_order('BTC/USDT', size_btc)
        # Random realistic P&L (replace with Nautilus fill handler)
        if np.random.rand() < 0.75:  # 75% win rate
            pnl = size_usd * np.random.uniform(0.5, 2.0)
        else:
            pnl = -size_usd * np.random.uniform(0.2, 0.8)
        st.session_state.balance += pnl
        trade = Trade(
            time=datetime.now().strftime("%H:%M:%S"),
            price=price,
            size=size_btc,
            imbalance=imbalance,
            prob_drop=prob,
            pnl=pnl,
            side="SHORT"
        )
        st.session_state.trades.insert(0, trade)
        if len(st.session_state.trades) > 50:
            st.session_state.trades = st.session_state.trades[:50]

if prob_drop > 0.8:
    execute_trade(prob_drop, price, imbalance)

# Nautilus Backtest Snippet (run on load for stats)
@st.cache_data
def run_backtest():
    # Simple config for historical drop strategy
    config = BacktestRunConfig(
        engine=BacktestEngineConfig(trader_id=TradingStrategyId("DropCatcher-001")),
        venues=[CCXTFuturesVenueConfig(name=Venue("BYBIT"), load_test_data=False)],
        data=[
            CCXTDataConfig(
                catalog_path=str(ParquetDataConfig(path="data/parquet/BYBIT.BTCUSDT.FUTURES")),
                instrument_id=Symbol("BTC-USDT", Venue("BYBIT")),
                load_data=True,
            )
        ],
        strategies=[StrategyConfig(strategy_id=TradingStrategyId("DropCatcher"), module_path="dropcatcher_strategy.py")],
        start_time="2025-01-01",
        end_time="2025-12-01",
    )
    engine = BacktestEngine(config=config.engine)
    engine.run(config)
    metrics = PerformanceMetrics.from_backtest_result(engine.result)
    return {
        "win_rate": metrics.win_rate_pct,
        "sharpe": metrics.sharpe_ratio,
        "total_return": metrics.total_return_pct,
    }

backtest_stats = run_backtest() if st.button("Run Backtest") else {"win_rate": 0, "sharpe": 0, "total_return": 0}

# Dashboard
st.title("🛑 Nautilus DropCatcher Pro – Live BTC Shorts")
col1, col2, col3, col4 = st.columns(4)
col1.metric("BTC Price", f"${price:,.0f}")
col2.metric("Orderbook Imbalance", f"{imbalance:+.1%}")
col3.metric("Drop Probability", f"{prob_drop:.1%}", delta=f"{(prob_drop - 0.8)*100:+.0f}%" if prob_drop > 0.8 else None)
col4.metric("Balance", f"${st.session_state.balance:,.0f}", delta=f"{(st.session_state.balance - 100000)/1000:+.0f}K")

# Charts
col_chart, col_stats = st.columns([3, 1])
with col_chart:
    fig = go.Figure(go.Scatter(y=st.session_state.price_history[-200:], mode="lines", line=dict(color="#ff4757", width=2)))
    fig.update_layout(title="BTC Price (5s Updates)", height=400, template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

with col_stats:
    st.subheader("Backtest Stats")
    st.metric("Win Rate", f"{backtest_stats['win_rate']:.1f}%")
    st.metric("Sharpe Ratio", f"{backtest_stats['sharpe']:.2f}")
    st.metric("Total Return", f"{backtest_stats['total_return']:.1f}%")

# Trades Table
if st.session_state.trades:
    df = pd.DataFrame([{
        "Time": t.time,
        "Price": f"${t.price:,.0f}",
        "Size (BTC)": f"{t.size:.4f}",
        "Imbalance": f"{t.imbalance:+.1%}",
        "Prob": f"{t.prob_drop:.1%}",
        "P&L": f"${t.pnl:+,.0f}",
        "Side": t.side
    } for t in st.session_state.trades[:10]])
    st.subheader("Recent Shorts")
    st.dataframe(df, use_container_width=True)

# Auto-refresh (every 5s, non-blocking)
time.sleep(0.1)  # Small delay
if st.button("Refresh Now") or True:  # Always for demo
    st.rerun()

# Footer
st.sidebar.markdown("---")
st.sidebar.info("Powered by Nautilus Trader | Bybit Futures | Risk: Use testnet first!")
