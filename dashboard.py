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


def build_exchange_link(exchange, symbol):
    pair = symbol.replace("/", "")

    exchange = exchange.lower()

    urls = {
        "bybit": f"https://www.bybit.com/en/trade/spot/{pair}",
        "bingx": f"https://bingx.com/en-us/spot/{pair}",
        "kucoin": f"https://www.kucoin.com/trade/{symbol.replace('/', '-')}",
        "gateio": f"https://www.gate.io/trade/{pair}",
        "bitget": f"https://www.bitget.com/spot/{pair}",
        "mexc": f"https://www.mexc.com/exchange/{pair}",
        "coinex": f"https://www.coinex.com/en/exchange/{pair}",
        "lbank": f"https://www.lbank.com/trade/{pair.lower()}",
        "digifinex": f"https://www.digifinex.com/en-ww/exchange/{symbol.replace('/', '_')}",
        "bitrue": f"https://www.bitrue.com/trade/{pair}",
        "bitmart": f"https://www.bitmart.com/trade/en-US?symbol={pair}",
    }

    return urls.get(exchange, "#")


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

df["route"] = (
    df["symbol"] + " | " +
    df["buy_exchange"].str.upper() + " -> " +
    df["sell_exchange"].str.upper()
)

route_counts = df.groupby("route")["route"].transform("count")

df["min_liquidity"] = df[["buy_liquidity", "sell_liquidity"]].min(axis=1)

df["liquidity_factor"] = (df["min_liquidity"] / 1000).clip(upper=5)

df["recurrence_factor"] = (route_counts / 10).clip(upper=3)

df["quality_score"] = (
    df["net_spread"].clip(lower=0) *
    (1 + df["liquidity_factor"]) *
    (1 + df["recurrence_factor"])
)

st.sidebar.header("Filters")

min_net_spread = st.sidebar.slider(
    "Minimum Net Spread %",
    min_value=-1.0,
    max_value=2.0,
    value=0.0,
    step=0.05
)

min_quality_score = st.sidebar.slider(
    "Minimum Quality Score",
    min_value=0.0,
    max_value=20.0,
    value=0.0,
    step=0.5
)

min_buy_liquidity = st.sidebar.slider(
    "Minimum Buy Liquidity $",
    min_value=0,
    max_value=100000,
    value=0,
    step=100
)

min_sell_liquidity = st.sidebar.slider(
    "Minimum Sell Liquidity $",
    min_value=0,
    max_value=100000,
    value=0,
    step=100
)

selected_symbols = st.sidebar.multiselect(
    "Symbols",
    sorted(df["symbol"].dropna().unique())
)

filtered = df[
    (df["net_spread"] >= min_net_spread) &
    (df["quality_score"] >= min_quality_score) &
    (df["buy_liquidity"] >= min_buy_liquidity) &
    (df["sell_liquidity"] >= min_sell_liquidity)
].copy()

if selected_symbols:
    filtered = filtered[filtered["symbol"].isin(selected_symbols)]

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("Total Loaded Rows", len(df))
col2.metric("Filtered Rows", len(filtered))
col3.metric("Best Net Spread", f"{df['net_spread'].max():.2f}%")
col4.metric("Best Gross Spread", f"{df['gross_spread'].max():.2f}%")
col5.metric("Best Quality Score", f"{df['quality_score'].max():.2f}")

st.divider()

st.subheader("Top Quality Opportunities")

top_quality = filtered.sort_values(
    by="quality_score",
    ascending=False
).head(30).copy()

display_df = top_quality.copy()

display_df["buy_exchange"] = display_df.apply(
    lambda row:
    f'<a href="{build_exchange_link(row["buy_exchange"], row["symbol"])}" target="_blank">{row["buy_exchange"]}</a>',
    axis=1
)

display_df["sell_exchange"] = display_df.apply(
    lambda row:
    f'<a href="{build_exchange_link(row["sell_exchange"], row["symbol"])}" target="_blank">{row["sell_exchange"]}</a>',
    axis=1
)

html_table = display_df[
    [
        "timestamp",
        "symbol",
        "buy_exchange",
        "sell_exchange",
        "net_spread",
        "gross_spread",
        "buy_liquidity",
        "sell_liquidity",
        "quality_score"
    ]
].to_html(
    escape=False,
    index=False
)

st.subheader("Top Quality Opportunities")

top_quality = filtered.sort_values(
    by="quality_score",
    ascending=False
).head(30).copy()

display_df = top_quality.copy()

display_df["BUY LINK"] = display_df.apply(
    lambda row:
    build_exchange_link(row["buy_exchange"], row["symbol"]),
    axis=1
)

display_df["SELL LINK"] = display_df.apply(
    lambda row:
    build_exchange_link(row["sell_exchange"], row["symbol"]),
    axis=1
)

st.dataframe(
    display_df[
        [
            "timestamp",
            "symbol",
            "buy_exchange",
            "sell_exchange",
            "net_spread",
            "gross_spread",
            "buy_liquidity",
            "sell_liquidity",
            "quality_score",
            "BUY LINK",
            "SELL LINK"
        ]
    ],
    use_container_width=True,
    hide_index=True,
    column_config={
        "BUY LINK": st.column_config.LinkColumn(
            "BUY",
            display_text="Open Buy Pair"
        ),
        "SELL LINK": st.column_config.LinkColumn(
            "SELL",
            display_text="Open Sell Pair"
        )
    }
)

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
            avg_sell_liquidity=("sell_liquidity", "mean"),
            avg_quality_score=("quality_score", "mean"),
            max_quality_score=("quality_score", "max")
        )
        .sort_values(by=["max_quality_score", "count"], ascending=False)
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
        avg_quality_score=("quality_score", "mean"),
        max_quality_score=("quality_score", "max"),
        avg_buy_liquidity=("buy_liquidity", "mean"),
        avg_sell_liquidity=("sell_liquidity", "mean"),
        count=("net_spread", "count")
    )
    .sort_values(by="max_quality_score", ascending=False)
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
            avg_quality_score=("quality_score", "mean"),
            max_quality_score=("quality_score", "max"),
            avg_buy_liquidity=("buy_liquidity", "mean")
        )
        .sort_values(by="max_quality_score", ascending=False)
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
            avg_quality_score=("quality_score", "mean"),
            max_quality_score=("quality_score", "max"),
            avg_sell_liquidity=("sell_liquidity", "mean")
        )
        .sort_values(by="max_quality_score", ascending=False)
        .reset_index()
    )

    st.dataframe(sell_stats, use_container_width=True, hide_index=True)

st.subheader("Buy/Sell Exchange Matrix")

if not positive.empty:
    matrix = pd.pivot_table(
        positive,
        values="quality_score",
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
