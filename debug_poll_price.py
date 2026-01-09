import yfinance as yf
import time

symbol = "TSLA"
ticker = yf.Ticker(symbol)

print(f"Polling {symbol} for 10 seconds...")
for i in range(5):
    try:
        # Force fetch of info
        info = ticker.info
        price = (info.get('postMarketPrice') or 
                 info.get('preMarketPrice') or 
                 info.get('currentPrice') or 
                 info.get('regularMarketPrice'))
                 
        print(f"Time {i}: {price}")
    except Exception as e:
        print(f"Error: {e}")
    time.sleep(2)
