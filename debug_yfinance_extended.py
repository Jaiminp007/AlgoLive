import yfinance as yf
import json

symbols = ["TSLA", "NVDA", "AAPL"]
tickers = yf.Tickers(" ".join(symbols))

print("--- FAST INFO ---")
for sym in symbols:
    try:
        info = tickers.tickers[sym].fast_info
        print(f"\n{sym}:")
        print(f"  last_price: {info.last_price}")
        print(f"  previous_close: {info.previous_close}")
        # explicit check for likely attributes
        # fast_info is a class, let's explore dir
        # print("  Attributes:", dir(info))
    except Exception as e:
        print(f"Error {sym}: {e}")

print("\n--- FULL INFO (Slower, but might have 'postMarketPrice') ---")
# Only check one to avoid rate limits/slowdown
sym = "TSLA"
try:
    # Force complete fetch
    full_info = tickers.tickers[sym].info 
    
    interesting_keys = ['currentPrice', 'regularMarketPrice', 'postMarketPrice', 'preMarketPrice', 'ask', 'bid', 'regularMarketOpen', 'regularMarketDayHigh', 'regularMarketDayLow']
    
    print(f"\n{sym} Full Info subset:")
    for k in interesting_keys:
        print(f"  {k}: {full_info.get(k)}")
        
except Exception as e:
    print(f"Error fetching full info: {e}")
