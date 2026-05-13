import os
import streamlit as st
import pandas as pd
import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL")

st.set_page_config(
    page_title="Crypto Spread Scanner",
    layout="wide"
)

st.title("Crypto Spread Scanner Dashboard")

if not DATABASE_URL:
    st.error("DATABASE_URL is missing.")
    st.stop()


def load_data():
    conn = psycopg2.connect(DATABASE_URL)

    query = """
        SELECT
            timestamp,
            symbol,
            buy_exchange,
            sell_exchange,
            gross_spread,
            net_spread,
            buy_liquidity,
            sell_liquidity,
            simulated_trade_usdt
        FROM spreads
        ORDER BY timestamp DESC
        LIMIT 50000;
    """

    df = pd.read_sql(query, conn)
    conn.close()

    return df


try:
    df = load_data()

except Exception as e:
    st.error(f"Database read error: {e}")
    st.stop()

if df.empty:
    st.warning("Database is empty. Wait for the worker to finish a scan.")
    st.stop()

df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

numeric_cols = [
    "gross_spread",
    "net_spread",
    "buy_liquidity",
    "sell_liquidity",
    "simulated_trade_usdt"
]

for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")

st.sidebar.header("Filters")

min_net_spread = st.sidebar.slider(
    "Minimum Net Spread %",
    min_value=-1.0,
    max_value=2.0,
    value=0.0,
    step=0.05
)

min_buy_liquidity = st.sidebar.slider(
    "Minimum Buy Liquidity $",
    min_value=0,
    max_value=10000,
    value=0,
    step=100
)

min_sell_liquidity = st.sidebar.slider(
    "Minimum Sell Liquidity $",
    min_value=0,
    max_value=10000,
    value=0,
    step=100
)

selected_symbols = st.sidebar.multiselect(
    "Symbols",
    sorted(df["symbol"].dropna().unique())
)

filtered = df[
    (df["net_spread"] >= min_net_spread) &
    (df["buy_liquidity"] >= min_buy_liquidity) &
    (df["sell_liquidity"] >= min_sell_liquidity)
].copy()

if selected_symbols:
    filtered = filtered[filtered["symbol"].isin(selected_symbols)]

col1, col2, col3, col4 = st.columns(4)

col1.metric("Total Loaded Rows", len(df))
col2.metric("Filtered Rows", len(filtered))
col3.metric("Best Net Spread", f"{df['net_spread'].max():.2f}%")
col4.metric("Best Gross Spread", f"{df['gross_spread'].max():.2f}%")

st.divider()

st.subheader("Top Net Spreads With Liquidity")

top_spreads = filtered.sort_values(
    by="net_spread",
    ascending=False
).head(30)

st.dataframe(
    top_spreads,
    use_container_width=True,
    hide_index=True
)

positive = filtered[filtered["net_spread"] > 0].copy()

st.subheader("Top Recurring Routes")

if not positive.empty:
    route_stats = (
        positive
        .groupby(["symbol", "buy_exchange", "sell_exchange"])
        .agg(
            count=("net_spread", "count"),
            avg_net_spread=("net_spread", "mean"),
            max_net_spread=("net_spread", "max"),
            avg_buy_liquidity=("buy_liquidity", "mean"),
            avg_sell_liquidity=("sell_liquidity", "mean")
        )
        .sort_values(by=["count", "max_net_spread"], ascending=False)
        .reset_index()
    )

    st.dataframe(
        route_stats.head(30),
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("No positive recurring routes found.")

st.subheader("Best Symbols")

symbol_stats = (
    filtered
    .groupby("symbol")
    .agg(
        avg_net_spread=("net_spread", "mean"),
        max_net_spread=("net_spread", "max"),
        avg_buy_liquidity=("buy_liquidity", "mean"),
        avg_sell_liquidity=("sell_liquidity", "mean"),
        count=("net_spread", "count")
    )
    .sort_values(by="max_net_spread", ascending=False)
    .reset_index()
)

st.dataframe(
    symbol_stats.head(30),
    use_container_width=True,
    hide_index=True
)

st.subheader("Buy Exchange Stats")

if not positive.empty:
    buy_stats = (
        positive
        .groupby("buy_exchange")
        .agg(
            buy_signals=("net_spread", "count"),
            avg_net_spread=("net_spread", "mean"),
            max_net_spread=("net_spread", "max"),
            avg_buy_liquidity=("buy_liquidity", "mean")
        )
        .sort_values(by="buy_signals", ascending=False)
        .reset_index()
    )

    st.dataframe(buy_stats, use_container_width=True, hide_index=True)

st.subheader("Sell Exchange Stats")

if not positive.empty:
    sell_stats = (
        positive
        .groupby("sell_exchange")
        .agg(
            sell_signals=("net_spread", "count"),
            avg_net_spread=("net_spread", "mean"),
            max_net_spread=("net_spread", "max"),
            avg_sell_liquidity=("sell_liquidity", "mean")
        )
        .sort_values(by="sell_signals", ascending=False)
        .reset_index()
    )

    st.dataframe(sell_stats, use_container_width=True, hide_index=True)

st.subheader("Buy/Sell Exchange Matrix")

if not positive.empty:
    matrix = pd.pivot_table(
        positive,
        values="net_spread",
        index="buy_exchange",
        columns="sell_exchange",
        aggfunc="max",
        fill_value=0
    )

    st.dataframe(matrix, use_container_width=True)

st.subheader("Net Spread Over Time")

chart_data = (
    filtered
    .dropna(subset=["timestamp"])
    .sort_values("timestamp")
)

if not chart_data.empty:
    chart_df = chart_data[["timestamp", "net_spread"]].set_index("timestamp")
    st.line_chart(chart_df)
else:
    st.info("No chart data available.")
