import ccxt
import time

try:
    print("Initializing CCXT (BinanceUS)...")
    exchange = ccxt.binanceus({'enableRateLimit': True})
    symbol = "BTC/USDT"
    
    print(f"Fetching Ticker for {symbol}...")
    ticker = exchange.fetch_ticker(symbol)
    print(f"Ticker Result: {ticker['last']}")
    
    print("Fetching Order Book...")
    depth = exchange.fetch_order_book(symbol, limit=5)
    print(f"Depth Top Bid: {depth['bids'][0][0]}")
    print("SUCCESS")

except Exception as e:
    print(f"FAILURE: {e}")
