import ccxt
import pandas as pd
from datetime import datetime, timedelta
import time
import os
import yfinance as yf
import numpy as np

# Configuration
ASSET_CLASS = os.getenv("ASSET_CLASS", "STOCK") # 'STOCK' or 'CRYPTO'

class DataFeed:
    def __init__(self):
        # --- HYBRID CONFIGURATION ---
        self.stock_symbols = []
        self.crypto_symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        
        # Combined Symbols for Arena
        self.crypto_map = {
            "BTC/USDT": "BTC", "ETH/USDT": "ETH", "SOL/USDT": "SOL"
        }
        
        # Special Synthetic Assets
        self.synthetic_assets = []
        
        self.symbols = [s for s in self.stock_symbols if s != 'SPY'] + self.synthetic_assets + list(self.crypto_map.values())
        self.symbol_map = {s: s for s in self.stock_symbols}
        self.symbol_map.update(self.crypto_map)
        # Map synthetics
        for s in self.synthetic_assets: self.symbol_map[s] = s
        
        self.interval = "1m"
        
        # --- INIT YAHOO FINANCE (STOCKS) ---
        print(f"DataFeed: Initializing Stocks: {self.stock_symbols}")
        self.tickers = yf.Tickers(" ".join(self.stock_symbols))
        
        # Simulation State for After-Hours (Stocks Only)
        self.real_prices = {}
        self.current_sim_prices = {}
        self.last_update_times = {}
        
        # --- INIT BINANCE (CRYPTO) ---
        print(f"DataFeed: Initializing Crypto: {self.crypto_symbols}")
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
        })

    def get_market_snapshot(self):
        """
        Fetches comprehensive market data from both Yahoo (Stocks) and Binance (Crypto).
        """
        snapshot = {}
        timestamp = int(datetime.now().timestamp() * 1000)

        # --- FETCH STOCKS (YAHOO) ---
        try:
            # yfinance fast_info is efficient for snapshots
            stock_count = 0
            for sym in self.stock_symbols:
                try:
                    ticker = self.tickers.tickers[sym]
                    
                    # Try to get Extended Hours Data (Real-time)
                    # Note: ticker.info is slower but contains 'postMarketPrice'
                    # fast_info is fast but only has 'last_price' (often stuck at close)
                    try:
                        full_info = ticker.info 
                        # Priority: Post-Market > Pre-Market > Regular Market > Fast Info
                        base_price = (full_info.get('postMarketPrice') or 
                                 full_info.get('preMarketPrice') or 
                                 full_info.get('currentPrice') or 
                                 full_info.get('regularMarketPrice'))
                        
                        if base_price is None:
                            price = float(ticker.fast_info.last_price)
                        else:
                            price = float(base_price) 
                            
                        # Removed Jitter per user feedback - Pure Data Only

                    except:
                        # Fallback to fast_info if full info fails or is too slow
                        price = float(ticker.fast_info.last_price)

                    if price is None:
                        price = float(ticker.fast_info.last_price)
                    
                    # Mock Order Book
                    spread = price * 0.0002
                    bid = price - (spread / 2)
                    ask = price + (spread / 2)
                    
                    snapshot[sym] = {
                        "price": float(price),
                        "volume": 0, 
                        # Use simulated OHLC based on this price to keep charts valid
                        "high": price * 1.001,
                        "low": price * 0.999,
                        "open": price,
                        "bid": float(bid),
                        "ask": float(ask),
                        "timestamp": timestamp,
                        "bids": [[bid, 100]],
                        "asks": [[ask, 100]]
                    }
                    stock_count += 1
                    stock_count += 1
                except Exception as e:
                    pass
            
            # --- SYNTHETIC ASSETS (0DTE) ---
            if "SPY" in snapshot:
                spy_data = snapshot["SPY"]
                spy_price = spy_data['price']
                spy_open = spy_data['open']
                
                # 0DTE Logic: 50x Leverage on intraday move
                # Base price starts at 1.00 each day (simulated)
                raw_change = (spy_price - spy_open) / spy_open
                leverage = 100.0 # Extreme leverage for 0DTE
                
                dte_change = raw_change * leverage
                dte_price = 1.0 * (1.0 + dte_change)
                if dte_price < 0.01: dte_price = 0.01 # Don't go to zero
                
                # Jitter it heavily
                noise = np.random.normal(0, 0.02) # 2% noise
                dte_price = dte_price * (1 + noise)
                
                snapshot["SPY_0DTE"] = {
                    "price": float(dte_price),
                    "volume": spy_data['volume'] * 0.1, # Fake volume
                    "high": dte_price * 1.05,
                    "low": dte_price * 0.95,
                    "open": 1.0,
                    "bid": dte_price * 0.99,
                    "ask": dte_price * 1.01,
                    "timestamp": timestamp,
                    "bids": [[dte_price * 0.99, 1000]],
                    "asks": [[dte_price * 1.01, 1000]]
                }
        except Exception as e:
            print(f"Stock Fetch Error: {e}")

        # --- FETCH CRYPTO (BINANCE) ---
        try:
            # Only fetch the tickers we care about
            tickers = self.exchange.fetch_tickers(self.crypto_symbols)
            
            for pair, data in tickers.items():
                short_name = self.crypto_map.get(pair)
                if not short_name: continue
                
                snapshot[short_name] = {
                    "price": float(data['last']),
                    "volume": float(data['baseVolume']),
                    "high": float(data['high'] or data['last']),
                    "low": float(data['low'] or data['last']),
                    "open": float(data['open'] or data['last']),
                    "bid": float(data['bid'] or 0),
                    "ask": float(data['ask'] or 0),
                    "timestamp": timestamp,
                    "bids": [],
                    "asks": []
                }
        except Exception as e:
            print(f"Crypto Fetch Error: {e}")
                
        return snapshot

    def get_historical_data(self, limit=100, timeframe='1Min'):
        """
        Fetches historical data for ALL symbols (Stocks + Crypto).
        """
        all_history = {}
        
        # --- STOCK HISTORY (YAHOO) ---
        try:
            # Map timeframe
            yf_interval = "1m" if timeframe in ['1Min', '1m'] else timeframe
            period = "1d" if limit < 390 else "5d"
            
            data = yf.download(self.stock_symbols, period=period, interval=yf_interval, group_by='ticker', threads=False, progress=False)
            
            for sym in self.stock_symbols:
                try:
                    if len(self.stock_symbols) > 1:
                        df = data[sym].copy()
                    else:
                        df = data.copy()
                        
                    df = df.dropna()
                    
                    history = []
                    for index, row in df.iterrows():
                        history.append({
                            'timestamp': int(index.timestamp() * 1000),
                            'open': float(row['Open']),
                            'high': float(row['High']),
                            'low': float(row['Low']),
                            'close': float(row['Close']),
                            'volume': float(row['Volume'])
                        })
                        
                    if len(history) > limit:
                        history = history[-limit:]
                        
                    all_history[sym] = history
                except Exception as e:
                    pass
            
            # --- SYNTHETIC HISTORY (0DTE) ---
            if "SPY" in all_history and "SPY_0DTE" in self.synthetic_assets:
                spy_hist = all_history["SPY"]
                dte_hist = []
                
                # Base 1.0
                # We need to simulate intraday moves for past candles. 
                # Ideally, we just take SPY candles and apply leverage to their % change from previous close.
                # Simplified: Just emulate price action normalized to 1.0 start
                
                start_price = 1.0
                prev_price = start_price
                
                for i, candle in enumerate(spy_hist):
                    if i == 0:
                        dte_candle = candle.copy()
                        dte_candle['open'] = start_price
                        dte_candle['high'] = start_price * 1.01
                        dte_candle['low'] = start_price * 0.99
                        dte_candle['close'] = start_price
                        dte_hist.append(dte_candle)
                        continue
                        
                    prev_spy = spy_hist[i-1]['close']
                    curr_spy = candle['close']
                    spy_ret = (curr_spy - prev_spy) / prev_spy
                    
                    lev = 50.0 
                    dte_ret = spy_ret * lev
                    
                    # Apply to previous DTE price
                    curr_price = prev_price * (1 + dte_ret)
                    if curr_price < 0.01: curr_price = 0.01
                    
                    dte_candle = candle.copy()
                    dte_candle['open'] = prev_price
                    dte_candle['close'] = curr_price
                    dte_candle['high'] = max(prev_price, curr_price) * 1.02
                    dte_candle['low'] = min(prev_price, curr_price) * 0.98
                    dte_hist.append(dte_candle)
                    
                    prev_price = curr_price
                    
                all_history["SPY_0DTE"] = dte_hist

        except Exception as e:
            print(f"yfinance History Error: {e}")
            
        # --- CRYPTO HISTORY (BINANCE) ---
        try:
            tf = '1m' # CCXT default
            for pair in self.crypto_symbols:
                short_name = self.crypto_map[pair]
                try:
                    ohlcv = self.exchange.fetch_ohlcv(pair, timeframe=tf, limit=limit)
                    
                    data = []
                    for candle in ohlcv:
                        data.append({
                            'timestamp': candle[0],
                            'open': candle[1],
                            'high': candle[2],
                            'low': candle[3],
                            'close': candle[4],
                            'volume': candle[5]
                        })
                    all_history[short_name] = data
                    time.sleep(0.1) # Rate limit
                except Exception as e:
                    print(f"Error fetching history for {pair}: {e}")
        except Exception as e:
            print(f"Crypto History Error: {e}")
                
        return all_history

    def get_funding_rates(self):
        """No funding rates for spot stocks. Returns empty or mock."""
        return {}

    def get_news(self):
        """Fetch real news related to assets with Sentiment Analysis."""
        headlines = []
        try:
             # Get news for the first few symbols
             raw_news = []
             # Rotate symbols to get variety (just first 3 for speed)
             for sym in self.stock_symbols[:3]:
                ticker = self.tickers.tickers[sym]
                news = ticker.news
                if news:
                    for n in news[:1]: # Top 1 per symbol
                        title = n.get('title', '')
                        if title and title not in [x['title'] for x in raw_news]:
                            raw_news.append({'title': title, 'symbol': sym})
             
             # Analyze Sentiment
             from textblob import TextBlob
             for item in raw_news:
                 blob = TextBlob(item['title'])
                 sentiment = blob.sentiment.polarity # -1.0 to 1.0
                 headlines.append({
                     'title': item['title'],
                     'symbol': item['symbol'],
                     'sentiment': sentiment,
                     'timestamp': int(time.time())
                 })
                 
             if headlines:
                 return headlines
        except Exception as e:
             print(f"News Fetch Error: {e}")
             pass
        
        # Fallback Mock News
        return [
            {'title': "Market volatility increases ahead of Fed meeting.", 'symbol': 'Macro', 'sentiment': -0.2, 'timestamp': int(time.time())},
            {'title': "Tech sector rallies on strong earnings reports.", 'symbol': 'Tech', 'sentiment': 0.6, 'timestamp': int(time.time())},
            {'title': "Bitcoin breaks resistance levels.", 'symbol': 'BTC', 'sentiment': 0.5, 'timestamp': int(time.time())}
        ]
