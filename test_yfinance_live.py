import yfinance as yf
import time
from datetime import datetime

symbols = ["AAPL", "NVDA", "TSLA", "AMD", "MSFT", "GOOGL", "AMZN", "META", "SPY", "QQQ"]
print(f"Testing fetch for {len(symbols)} symbols...")

start = time.time()
tickers = yf.Tickers(" ".join(symbols))

print("Tickers object created. Accessing fast_info...")

for sym in symbols:
    try:
        t0 = time.time()
        info = tickers.tickers[sym].fast_info
        price = info.last_price
        print(f"{sym}: {price} (took {time.time() - t0:.2f}s)")
    except Exception as e:
        print(f"{sym}: FAILED {e}")

print(f"Total time: {time.time() - start:.2f}s")
