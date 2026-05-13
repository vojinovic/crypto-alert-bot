import ccxt
import time
import csv
from collections import Counter
from datetime import datetime, UTC

exchange_names = [
    'gateio',
    'mexc',
    'kucoin',
    'bitget',
    'bybit',
    'coinex',
    'bingx',
    'bitmart',
    'lbank',
    'digifinex',
    'bitrue'
]

symbols = [
    'INJ/USDT', 'ALT/USDT', 'WLD/USDT', 'JUP/USDT', 'SATS/USDT',
    'ORDI/USDT', 'PENDLE/USDT', 'ZRO/USDT', 'CFX/USDT', 'FLOKI/USDT',
    'TURBO/USDT', 'CATI/USDT', 'PIXEL/USDT', 'PORTAL/USDT', 'CYBER/USDT',
    'SUI/USDT', 'SEI/USDT', 'TIA/USDT', 'ARB/USDT', 'OP/USDT',
    'BRETT/USDT', 'POPCAT/USDT', 'MEW/USDT', 'BOME/USDT', 'MYRO/USDT',
    'NEIRO/USDT', 'MOODENG/USDT', 'GOAT/USDT', 'PONKE/USDT', 'TNSR/USDT'
]

ORDERBOOK_LIMIT = 20
SIMULATED_TRADE_USDT = 100
SCAN_INTERVAL_SECONDS = 60

ESTIMATED_TOTAL_FEES_PERCENT = 0.20
MIN_DISPLAY_NET_SPREAD = 0.20

CSV_FILE = 'spread_log.csv'

best_since_start = None


def calculate_liquidity(orders):
    total = 0

    for order in orders:
        price = order[0]
        amount = order[1]
        total += price * amount

    return total


def simulate_market_buy(asks, usdt_amount):
    remaining_usdt = usdt_amount
    total_tokens = 0

    for order in asks:
        price = order[0]
        amount = order[1]
        order_value = price * amount

        if remaining_usdt >= order_value:
            total_tokens += amount
            remaining_usdt -= order_value
        else:
            total_tokens += remaining_usdt / price
            remaining_usdt = 0
            break

    if total_tokens == 0:
        return None

    return {
        'tokens_bought': total_tokens,
        'average_price': usdt_amount / total_tokens
    }


def simulate_market_sell(bids, token_amount):
    remaining_tokens = token_amount
    total_usdt_received = 0

    for order in bids:
        price = order[0]
        amount = order[1]

        if remaining_tokens >= amount:
            total_usdt_received += price * amount
            remaining_tokens -= amount
        else:
            total_usdt_received += price * remaining_tokens
            remaining_tokens = 0
            break

    return total_usdt_received


def write_to_csv(rows):
    with open(CSV_FILE, 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(rows)


def scan_market():
    global best_since_start

    print("\n====================================")
    print("STARTING NEW SCAN")
    print("====================================")

    all_spreads = []
    csv_rows = []
    best_this_scan = None

    exchange_stats = {
        exchange: {
            'buy_count': 0,
            'sell_count': 0,
            'total_net_spread': 0,
            'spread_count': 0
        }
        for exchange in exchange_names
    }

    for symbol in symbols:
        print(f"Scanning {symbol}...")

        prices = []

        for name in exchange_names:
            try:
                exchange_class = getattr(ccxt, name)

                exchange = exchange_class({
                    'enableRateLimit': True
                })

                orderbook = exchange.fetch_order_book(
                    symbol,
                    limit=ORDERBOOK_LIMIT
                )

                if not orderbook['bids'] or not orderbook['asks']:
                    continue

                prices.append({
                    'exchange': name,
                    'bids': orderbook['bids'],
                    'asks': orderbook['asks'],
                    'bid_liquidity': calculate_liquidity(orderbook['bids']),
                    'ask_liquidity': calculate_liquidity(orderbook['asks'])
                })

            except Exception:
                continue

        if len(prices) < 2:
            continue

        token_spreads = []

        for buy_exchange in prices:
            for sell_exchange in prices:
                if buy_exchange['exchange'] == sell_exchange['exchange']:
                    continue

                simulated_buy = simulate_market_buy(
                    buy_exchange['asks'],
                    SIMULATED_TRADE_USDT
                )

                if simulated_buy is None:
                    continue

                tokens_bought = simulated_buy['tokens_bought']

                usdt_received = simulate_market_sell(
                    sell_exchange['bids'],
                    tokens_bought
                )

                gross_spread = (
                    (usdt_received - SIMULATED_TRADE_USDT)
                    / SIMULATED_TRADE_USDT
                ) * 100

                net_spread = gross_spread - ESTIMATED_TOTAL_FEES_PERCENT

                buy_liquidity = buy_exchange['ask_liquidity']
                sell_liquidity = sell_exchange['bid_liquidity']

                spread_data = {
                    'timestamp': datetime.now(UTC).isoformat(),
                    'symbol': symbol,
                    'buy_exchange': buy_exchange['exchange'],
                    'sell_exchange': sell_exchange['exchange'],
                    'gross_spread': gross_spread,
                    'net_spread': net_spread,
                    'buy_liquidity': buy_liquidity,
                    'sell_liquidity': sell_liquidity,
                    'simulated_trade_usdt': SIMULATED_TRADE_USDT
                }

                token_spreads.append(spread_data)
                all_spreads.append(spread_data)

                csv_rows.append([
                    spread_data['timestamp'],
                    symbol,
                    buy_exchange['exchange'],
                    sell_exchange['exchange'],
                    round(gross_spread, 4),
                    round(net_spread, 4),
                    round(buy_liquidity, 2),
                    round(sell_liquidity, 2),
                    SIMULATED_TRADE_USDT
                ])

                if best_this_scan is None or net_spread > best_this_scan['net_spread']:
                    best_this_scan = spread_data

                if best_since_start is None or net_spread > best_since_start['net_spread']:
                    best_since_start = spread_data

                if net_spread > 0:
                    exchange_stats[buy_exchange['exchange']]['buy_count'] += 1
                    exchange_stats[sell_exchange['exchange']]['sell_count'] += 1
                    exchange_stats[buy_exchange['exchange']]['total_net_spread'] += net_spread
                    exchange_stats[buy_exchange['exchange']]['spread_count'] += 1
                    exchange_stats[sell_exchange['exchange']]['total_net_spread'] += net_spread
                    exchange_stats[sell_exchange['exchange']]['spread_count'] += 1

        filtered_spreads = [
            item for item in token_spreads
            if item['net_spread'] >= MIN_DISPLAY_NET_SPREAD
        ]

        if filtered_spreads:
            best = sorted(
                filtered_spreads,
                key=lambda x: x['net_spread'],
                reverse=True
            )[0]

            sell_counter = Counter(item['sell_exchange'] for item in filtered_spreads)
            buy_counter = Counter(item['buy_exchange'] for item in filtered_spreads)

            dominant_sell = sell_counter.most_common(1)[0]
            dominant_buy = buy_counter.most_common(1)[0]

            print("\n------------------------------------")
            print(f"TOKEN ALERT: {symbol}")
            print("------------------------------------")

            print(
                f"Best Net Spread: {best['net_spread']:.2f}% | "
                f"BUY {best['buy_exchange'].upper()} "
                f"-> SELL {best['sell_exchange'].upper()} | "
                f"BUY LIQ: ${best['buy_liquidity']:.2f} | "
                f"SELL LIQ: ${best['sell_liquidity']:.2f}"
            )

            print(
                f"Most Common BUY Exchange: {dominant_buy[0].upper()} "
                f"({dominant_buy[1]} times)"
            )

            print(
                f"Most Common SELL Exchange: {dominant_sell[0].upper()} "
                f"({dominant_sell[1]} times)"
            )

            if dominant_sell[1] >= 3:
                print("⚠️ POSSIBLE SINGLE EXCHANGE PREMIUM DETECTED")

    write_to_csv(csv_rows)

    top_spreads = sorted(
        [
            item for item in all_spreads
            if item['net_spread'] >= MIN_DISPLAY_NET_SPREAD
        ],
        key=lambda x: x['net_spread'],
        reverse=True
    )[:10]

    print("\n====================================")
    print(f"TOP NET SPREADS ABOVE {MIN_DISPLAY_NET_SPREAD}%")
    print("====================================\n")

    if not top_spreads:
        print("No net spreads above display threshold.")

    for item in top_spreads:
        print(
            f"{item['symbol']} | "
            f"Gross: {item['gross_spread']:.2f}% | "
            f"Net: {item['net_spread']:.2f}% | "
            f"BUY {item['buy_exchange'].upper()} "
            f"-> SELL {item['sell_exchange'].upper()} | "
            f"BUY LIQ: ${item['buy_liquidity']:.2f} | "
            f"SELL LIQ: ${item['sell_liquidity']:.2f}"
        )

    print("\n====================================")
    print("PEAK TRACKING")
    print("====================================\n")

    if best_this_scan:
        print(
            f"Best This Scan: {best_this_scan['symbol']} | "
            f"Net: {best_this_scan['net_spread']:.2f}% | "
            f"BUY {best_this_scan['buy_exchange'].upper()} "
            f"-> SELL {best_this_scan['sell_exchange'].upper()} | "
            f"BUY LIQ: ${best_this_scan['buy_liquidity']:.2f} | "
            f"SELL LIQ: ${best_this_scan['sell_liquidity']:.2f}"
        )

    if best_since_start:
        print(
            f"Best Since Start: {best_since_start['symbol']} | "
            f"Net: {best_since_start['net_spread']:.2f}% | "
            f"BUY {best_since_start['buy_exchange'].upper()} "
            f"-> SELL {best_since_start['sell_exchange'].upper()} | "
            f"BUY LIQ: ${best_since_start['buy_liquidity']:.2f} | "
            f"SELL LIQ: ${best_since_start['sell_liquidity']:.2f} | "
            f"Time: {best_since_start['timestamp']}"
        )

    print("\n====================================")
    print("EXCHANGE STATS")
    print("====================================\n")

    for exchange, stats in exchange_stats.items():
        avg_net_spread = 0

        if stats['spread_count'] > 0:
            avg_net_spread = stats['total_net_spread'] / stats['spread_count']

        print(
            f"{exchange.upper()} | "
            f"BUY SIGNALS: {stats['buy_count']} | "
            f"SELL SIGNALS: {stats['sell_count']} | "
            f"AVG NET SPREAD: {avg_net_spread:.2f}%"
        )


while True:
    scan_market()

    print(f"\nWaiting {SCAN_INTERVAL_SECONDS} seconds before next scan...")

    time.sleep(SCAN_INTERVAL_SECONDS)