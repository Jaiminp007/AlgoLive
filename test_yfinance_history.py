import yfinance as yf
import time

symbols = ["AAPL", "NVDA", "TSLA", "AMD", "MSFT", "GOOGL", "AMZN", "META", "SPY", "QQQ"]
print(f"Testing HISTORY fetch for {len(symbols)} symbols...")

start = time.time()
try:
    data = yf.download(symbols, period="1d", interval="1m", group_by='ticker', threads=True, progress=False)
    print("Download complete.")
    print(f"Shape: {data.shape}")
except Exception as e:
    print(f"FAILED: {e}")

print(f"Total time: {time.time() - start:.2f}s")
