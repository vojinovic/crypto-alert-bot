import streamlit as st
import pandas as pd
from pathlib import Path

CSV_FILE = Path("spread_log.csv")

st.set_page_config(
    page_title="Crypto Spread Scanner",
    layout="wide"
)

st.title("Crypto Spread Scanner Dashboard")

if not CSV_FILE.exists():
    st.warning("spread_log.csv još ne postoji. Pusti bota da napravi bar jedan scan.")
    st.stop()

df = pd.read_csv(
    CSV_FILE,
    names=[
        "timestamp",
        "symbol",
        "buy_exchange",
        "sell_exchange",
        "gross_spread",
        "net_spread"
    ]
)

df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

st.sidebar.header("Filters")

min_net_spread = st.sidebar.slider(
    "Minimum Net Spread %",
    min_value=-1.0,
    max_value=2.0,
    value=0.0,
    step=0.05
)

selected_symbols = st.sidebar.multiselect(
    "Symbols",
    sorted(df["symbol"].dropna().unique())
)

selected_buy_exchanges = st.sidebar.multiselect(
    "Buy Exchanges",
    sorted(df["buy_exchange"].dropna().unique())
)

selected_sell_exchanges = st.sidebar.multiselect(
    "Sell Exchanges",
    sorted(df["sell_exchange"].dropna().unique())
)

filtered = df[df["net_spread"] >= min_net_spread]

if selected_symbols:
    filtered = filtered[filtered["symbol"].isin(selected_symbols)]

if selected_buy_exchanges:
    filtered = filtered[filtered["buy_exchange"].isin(selected_buy_exchanges)]

if selected_sell_exchanges:
    filtered = filtered[filtered["sell_exchange"].isin(selected_sell_exchanges)]

col1, col2, col3, col4 = st.columns(4)

col1.metric("Total Logged Rows", len(df))
col2.metric("Filtered Rows", len(filtered))

if not df.empty:
    col3.metric("Best Net Spread", f"{df['net_spread'].max():.2f}%")
    col4.metric("Best Gross Spread", f"{df['gross_spread'].max():.2f}%")

st.divider()

st.subheader("Top Net Spreads")

top_spreads = filtered.sort_values(
    by="net_spread",
    ascending=False
).head(20)

st.dataframe(
    top_spreads,
    use_container_width=True,
    hide_index=True
)

st.subheader("Best Average Net Spread By Symbol")

symbol_stats = (
    filtered
    .groupby("symbol")
    .agg(
        avg_net_spread=("net_spread", "mean"),
        max_net_spread=("net_spread", "max"),
        count=("net_spread", "count")
    )
    .sort_values(by="max_net_spread", ascending=False)
    .reset_index()
)

st.dataframe(
    symbol_stats.head(20),
    use_container_width=True,
    hide_index=True
)

st.subheader("Buy Exchange Stats")

buy_stats = (
    filtered[filtered["net_spread"] > 0]
    .groupby("buy_exchange")
    .agg(
        buy_signals=("net_spread", "count"),
        avg_net_spread=("net_spread", "mean"),
        max_net_spread=("net_spread", "max")
    )
    .sort_values(by="buy_signals", ascending=False)
    .reset_index()
)

st.dataframe(
    buy_stats,
    use_container_width=True,
    hide_index=True
)

st.subheader("Sell Exchange Stats")

sell_stats = (
    filtered[filtered["net_spread"] > 0]
    .groupby("sell_exchange")
    .agg(
        sell_signals=("net_spread", "count"),
        avg_net_spread=("net_spread", "mean"),
        max_net_spread=("net_spread", "max")
    )
    .sort_values(by="sell_signals", ascending=False)
    .reset_index()
)

st.dataframe(
    sell_stats,
    use_container_width=True,
    hide_index=True
)

st.subheader("Net Spread Over Time")

chart_data = (
    filtered
    .dropna(subset=["timestamp"])
    .sort_values("timestamp")
)

if not chart_data.empty:
    st.line_chart(
        chart_data,
        x="timestamp",
        y="net_spread"
    )
else:
    st.info("Nema dovoljno podataka za chart.")
