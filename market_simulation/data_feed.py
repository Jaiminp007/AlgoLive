import ccxt
import pandas as pd
from datetime import datetime, timedelta
import time
import os
import yfinance as yf
import numpy as np

# Timezone handling for market hours
try:
    import pytz
    ET_TIMEZONE = pytz.timezone('America/New_York')
except ImportError:
    ET_TIMEZONE = None
    print("Warning: pytz not installed. Market hours detection may be inaccurate.")

# FinancialDatasets.ai integration
try:
    from .financial_datasets_provider import FinancialDatasetsProvider
except ImportError:
    try:
        from financial_datasets_provider import FinancialDatasetsProvider
    except ImportError:
        FinancialDatasetsProvider = None

# Configuration
ASSET_CLASS = os.getenv("ASSET_CLASS", "CRYPTO")  # 'STOCK' or 'CRYPTO'

# Stock API polling interval (5 minutes = 300 seconds)
STOCK_POLL_INTERVAL_SECONDS = 300

class DataFeed:
    def __init__(self):
        # --- HYBRID CONFIGURATION ---
        # Stock symbols with good fundamental data coverage
        self.stock_symbols = ["AAPL", "TSLA", "NVDA", "MSFT", "GOOGL", "AMZN", "META"]

        # Using Binance (USDT pairs - supports more cryptos including SOL)
        self.crypto_symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]

        # Combined Symbols for Arena
        self.crypto_map = {
            "BTC/USDT": "BTC", "ETH/USDT": "ETH", "SOL/USDT": "SOL", "BNB/USDT": "BNB"
        }

        # Short names for crypto
        self.crypto_short_names = ["BTC", "ETH", "SOL", "BNB"]

        # Special Synthetic Assets
        self.synthetic_assets = []

        # Configure symbols based on ASSET_CLASS
        if ASSET_CLASS == "CRYPTO":
            # Crypto only mode
            self.symbols = list(self.crypto_map.values())  # ['BTC', 'ETH', 'SOL']
            self.symbol_map = self.crypto_map.copy()
            self.stock_symbols = []  # Disable stocks
            print(f"DataFeed: CRYPTO mode - trading {self.symbols}")
        else:
            # Stock + Crypto hybrid mode
            self.symbols = [s for s in self.stock_symbols if s != 'SPY'] + self.synthetic_assets + list(self.crypto_map.values())
            self.symbol_map = {s: s for s in self.stock_symbols}
            self.symbol_map.update(self.crypto_map)
            # Map synthetics
            for s in self.synthetic_assets: self.symbol_map[s] = s
            print(f"DataFeed: STOCK mode - trading {self.symbols}")

        self.interval = "1m"

        # --- STOCK API THROTTLING & CACHING ---
        self._last_stock_fetch_time = 0  # Timestamp of last stock API call
        self._stock_price_cache = {}  # {symbol: {price data dict}}
        
        # --- INIT FINANCIALDATASETS.AI (PRIMARY) ---
        self.fd_provider = None
        if FinancialDatasetsProvider and os.getenv('FINANCIAL_DATASETS_API_KEY'):
            try:
                self.fd_provider = FinancialDatasetsProvider()
                print("DataFeed: FinancialDatasets.ai initialized as PRIMARY data source")
            except Exception as e:
                print(f"DataFeed: FinancialDatasets.ai initialization failed: {e}")
                print("DataFeed: Falling back to Coinbase/Yahoo Finance")
        else:
            print("DataFeed: FINANCIAL_DATASETS_API_KEY not set. Using Coinbase/Yahoo as primary.")

        # --- INIT YAHOO FINANCE (STOCKS - FALLBACK) ---
        print(f"DataFeed: Initializing Stocks (fallback): {self.stock_symbols}")
        self.tickers = yf.Tickers(" ".join(self.stock_symbols)) if self.stock_symbols else None

        # Simulation State for After-Hours (Stocks Only)
        self.real_prices = {}
        self.current_sim_prices = {}
        self.last_update_times = {}

        # --- INIT BINANCE (CRYPTO - FALLBACK) ---
        print(f"DataFeed: Initializing Crypto via Binance (fallback): {self.crypto_symbols}")
        try:
            self.exchange = ccxt.binance({
                'enableRateLimit': True,
            })
            # Test connection
            self.exchange.load_markets()
            print("DataFeed: Binance initialized successfully")
        except Exception as e:
            print(f"DataFeed: Binance unavailable ({e}), will use CoinGecko fallback")
            self.exchange = None

    def is_stock_market_open(self) -> bool:
        """
        Check if US stock market is currently open.
        Market hours: 9:30 AM - 4:30 PM Eastern Time, Monday-Friday.
        Returns True during market hours, False otherwise.
        """
        if ET_TIMEZONE:
            now_et = datetime.now(ET_TIMEZONE)
        else:
            # Fallback: assume UTC-5 (EST) - not accurate for DST
            now_et = datetime.utcnow() - timedelta(hours=5)
        
        # Check weekday (0=Monday, 6=Sunday)
        if now_et.weekday() >= 5:  # Saturday or Sunday
            return False
        
        # Market opens at 9:30 AM, closes at 4:30 PM (16:30)
        market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now_et.replace(hour=16, minute=30, second=0, microsecond=0)
        
        return market_open <= now_et <= market_close

    def _should_fetch_stocks(self) -> bool:
        """
        Determines if we should make a stock API call.
        Returns True only if:
        1. Stock market is open, AND
        2. At least STOCK_POLL_INTERVAL_SECONDS (5 min) since last fetch
        """
        if not self.is_stock_market_open():
            return False
        
        current_time = time.time()
        elapsed = current_time - self._last_stock_fetch_time
        
        return elapsed >= STOCK_POLL_INTERVAL_SECONDS



    def get_market_snapshot(self):
        """
        Fetches comprehensive market data.
        Priority: FinancialDatasets.ai (PRIMARY) -> Coinbase/Yahoo (FALLBACK)
        
        OPTIMIZATION: 
        - Crypto: Always fetched (free API)
        - Stocks: Only fetched when market is open AND 5 min since last fetch
        - Returns cached stock prices when market is closed or throttled
        """
        snapshot = {}
        timestamp = int(datetime.now().timestamp() * 1000)
        
        # Check market status for stocks
        stock_market_open = self.is_stock_market_open()
        should_fetch_stocks = self._should_fetch_stocks()
        
        # --- FETCH OR CACHE STOCKS ---
        if should_fetch_stocks:
            # Market is open and 5 min elapsed - make API call
            self._last_stock_fetch_time = time.time()
            print(f"DataFeed: Fetching live stock prices (market open, 5min interval)")
            
            for sym in self.stock_symbols:
                data = None
                data_source = 'fallback'

                # 1. Try FinancialDatasets.ai (PRIMARY)
                if self.fd_provider:
                    try:
                        fd_data = self.fd_provider.get_price_snapshot(sym)
                        if fd_data and fd_data.get('price'):
                            price = float(fd_data['price'])
                            day_change = float(fd_data.get('day_change', 0) or 0)
                            spread = price * 0.0002
                            bid = price - (spread / 2)
                            ask = price + (spread / 2)

                            data = {
                                "price": price,
                                "volume": 0,
                                "high": price * 1.001,
                                "low": price * 0.999,
                                "open": price - day_change,
                                "bid": float(bid),
                                "ask": float(ask),
                                "timestamp": fd_data.get('time_milliseconds', timestamp),
                                "bids": [[bid, 100]],
                                "asks": [[ask, 100]],
                                "market_cap": fd_data.get('market_cap'),
                                "day_change": day_change,
                                "day_change_percent": fd_data.get('day_change_percent'),
                            }
                            data_source = 'financial_datasets'
                    except Exception as e:
                        print(f"FD Stock Error ({sym}): {e}")

                # 2. Fallback to Yahoo Finance
                if data is None and self.tickers:
                    try:
                        ticker = self.tickers.tickers[sym]
                        try:
                            full_info = ticker.info
                            base_price = (full_info.get('postMarketPrice') or
                                         full_info.get('preMarketPrice') or
                                         full_info.get('currentPrice') or
                                         full_info.get('regularMarketPrice'))
                            if base_price is None:
                                price = float(ticker.fast_info.last_price)
                            else:
                                price = float(base_price)
                        except:
                            price = float(ticker.fast_info.last_price)

                        if price:
                            spread = price * 0.0002
                            bid = price - (spread / 2)
                            ask = price + (spread / 2)

                            data = {
                                "price": float(price),
                                "volume": 0,
                                "high": price * 1.001,
                                "low": price * 0.999,
                                "open": price,
                                "bid": float(bid),
                                "ask": float(ask),
                                "timestamp": timestamp,
                                "bids": [[bid, 100]],
                                "asks": [[ask, 100]]
                            }
                    except Exception as e:
                        pass

                if data:
                    data['data_source'] = data_source
                    data['market_status'] = 'open'
                    snapshot[sym] = data
                    # Update cache
                    self._stock_price_cache[sym] = data.copy()
        else:
            # Market closed or throttled - use cached prices
            reason = 'closed' if not stock_market_open else 'throttled'
            for sym in self.stock_symbols:
                if sym in self._stock_price_cache:
                    cached_data = self._stock_price_cache[sym].copy()
                    cached_data['market_status'] = 'closed'
                    cached_data['data_source'] = 'cache'
                    snapshot[sym] = cached_data

        # --- SYNTHETIC ASSETS (0DTE) ---
        if "SPY" in snapshot:
            spy_data = snapshot["SPY"]
            spy_price = spy_data['price']
            spy_open = spy_data.get('open', spy_price)

            raw_change = (spy_price - spy_open) / spy_open if spy_open else 0
            leverage = 100.0
            dte_change = raw_change * leverage
            dte_price = 1.0 * (1.0 + dte_change)
            if dte_price < 0.01:
                dte_price = 0.01

            noise = np.random.normal(0, 0.02)
            dte_price = dte_price * (1 + noise)

            snapshot["SPY_0DTE"] = {
                "price": float(dte_price),
                "volume": spy_data['volume'] * 0.1,
                "high": dte_price * 1.05,
                "low": dte_price * 0.95,
                "open": 1.0,
                "bid": dte_price * 0.99,
                "ask": dte_price * 1.01,
                "timestamp": timestamp,
                "bids": [[dte_price * 0.99, 1000]],
                "asks": [[dte_price * 1.01, 1000]],
                "data_source": "synthetic",
                "market_status": snapshot["SPY"].get('market_status', 'closed')
            }

        # --- FETCH CRYPTO (BINANCE/COINGECKO - always use for real-time) ---
        # Note: Crypto APIs are free, always fetch live data
        try:
            if self.exchange:
                # Try Binance first
                tickers = self.exchange.fetch_tickers(self.crypto_symbols)

                for pair, data in tickers.items():
                    short_name = self.crypto_map.get(pair)
                    if not short_name:
                        continue

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
                        "asks": [],
                        "data_source": "binance",
                        "market_status": "open"  # Crypto is always open
                    }
            else:
                # Fallback to CoinGecko (no auth required, free tier)
                self._fetch_crypto_from_coingecko(snapshot, timestamp)
        except Exception as e:
            print(f"Crypto Fetch Error: {e}")
            # Try CoinGecko fallback
            try:
                self._fetch_crypto_from_coingecko(snapshot, timestamp)
            except Exception as e2:
                print(f"CoinGecko Fallback Error: {e2}")
        
        # Add global market status flag for frontend
        snapshot['_market_status'] = 'open' if stock_market_open else 'closed'
        snapshot['_stock_market_open'] = stock_market_open
                
        return snapshot

    def _fetch_crypto_from_coingecko(self, snapshot, timestamp):
        """
        Fallback method to fetch crypto prices from CoinGecko (no auth required).
        Used when Binance is blocked or unavailable.
        """
        import requests
        
        # CoinGecko API (free tier, no auth)
        coingecko_ids = {
            'BTC': 'bitcoin',
            'ETH': 'ethereum',
            'SOL': 'solana',
            'BNB': 'binancecoin'
        }
        
        for short_name, gecko_id in coingecko_ids.items():
            try:
                url = f"https://api.coingecko.com/api/v3/simple/price"
                params = {
                    'ids': gecko_id,
                    'vs_currencies': 'usd',
                    'include_24hr_vol': 'true',
                    'include_24hr_change': 'true'
                }
                response = requests.get(url, params=params, timeout=5)
                
                if response.status_code == 200:
                    data = response.json().get(gecko_id, {})
                    price = data.get('usd', 0)
                    volume = data.get('usd_24h_vol', 0)
                    change = data.get('usd_24h_change', 0)
                    
                    # Estimate high/low from change
                    high = price * (1 + abs(change) / 200) if change > 0 else price
                    low = price * (1 - abs(change) / 200) if change < 0 else price
                    open_price = price * (1 - change / 100)
                    
                    snapshot[short_name] = {
                        "price": float(price),
                        "volume": float(volume),
                        "high": float(high),
                        "low": float(low),
                        "open": float(open_price),
                        "bid": float(price * 0.9999),  # Estimated
                        "ask": float(price * 1.0001),  # Estimated
                        "timestamp": timestamp,
                        "bids": [],
                        "asks": [],
                        "data_source": "coingecko",
                        "market_status": "open"
                    }
            except Exception as e:
                print(f"CoinGecko fetch failed for {short_name}: {e}")

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
            
        # --- CRYPTO HISTORY (BINANCE/COINGECKO) ---
        try:
            if self.exchange:
                # Use Binance if available
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
            else:
                # Fallback: Use current CoinGecko prices as history
                print("DataFeed: Using live prices for crypto history (Binance unavailable)")
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

    # =========================================================================
    # FUNDAMENTAL DATA METHODS (FinancialDatasets.ai)
    # =========================================================================

    def get_insider_trades(self, symbol: str) -> list:
        """
        Get insider trading activity for a symbol.
        Returns list of insider trade records or empty list.
        """
        if not self.fd_provider:
            return []
        try:
            return self.fd_provider.get_insider_trades(symbol)
        except Exception as e:
            print(f"DataFeed: Insider trades error ({symbol}): {e}")
            return []

    def get_insider_sentiment(self, symbol: str) -> float:
        """
        Calculate net insider sentiment for a symbol.
        Returns float between -1.0 (net selling) and 1.0 (net buying).
        """
        if not self.fd_provider:
            return 0.0
        try:
            return self.fd_provider.calculate_insider_sentiment(symbol)
        except Exception as e:
            print(f"DataFeed: Insider sentiment error ({symbol}): {e}")
            return 0.0

    def get_institutional_ownership(self, symbol: str) -> list:
        """
        Get institutional ownership data for a symbol.
        Returns list of institutional holders or empty list.
        """
        if not self.fd_provider:
            return []
        try:
            return self.fd_provider.get_institutional_ownership(symbol)
        except Exception as e:
            print(f"DataFeed: Institutional error ({symbol}): {e}")
            return []

    def get_institutional_change(self, symbol: str) -> float:
        """
        Calculate quarter-over-quarter change in institutional ownership.
        Returns percentage change.
        """
        if not self.fd_provider:
            return 0.0
        try:
            return self.fd_provider.calculate_institutional_change(symbol)
        except Exception as e:
            print(f"DataFeed: Institutional change error ({symbol}): {e}")
            return 0.0

    def get_financial_metrics(self, symbol: str) -> dict:
        """
        Get key financial metrics for a symbol.
        Returns dict with revenue_growth, profit_margin, pe_ratio, etc.
        """
        if not self.fd_provider:
            return {}
        try:
            return self.fd_provider.get_financial_metrics(symbol)
        except Exception as e:
            print(f"DataFeed: Financial metrics error ({symbol}): {e}")
            return {}

    def get_segmented_financials(self, symbol: str) -> dict:
        """Get segmented financial data."""
        if not self.fd_provider:
            return {}
        try:
            return self.fd_provider.get_segmented_financials(symbol)
        except Exception as e:
            print(f"DataFeed: Segmented financials error ({symbol}): {e}")
            return {}

    def get_sec_filings(self, symbol: str) -> list:
        """Get recent SEC filings."""
        if not self.fd_provider:
            return []
        try:
            return self.fd_provider.get_sec_filings(symbol)
        except Exception as e:
            print(f"DataFeed: SEC filings error ({symbol}): {e}")
            return []

    def get_news_with_sentiment(self, symbol: str, limit: int = 10) -> list:
        """
        Get news for a symbol with pre-calculated sentiment from FinancialDatasets.ai.
        Returns list of news articles with sentiment scores.
        """
        if not self.fd_provider:
            return []
        try:
            return self.fd_provider.get_news(symbol, limit)
        except Exception as e:
            print(f"DataFeed: News sentiment error ({symbol}): {e}")
            return []

    def get_aggregated_sentiment(self, symbol: str, limit: int = 10) -> float:
        """
        Get aggregated sentiment score from recent news.
        Returns float between -1.0 (bearish) and 1.0 (bullish).
        """
        if not self.fd_provider:
            return 0.0
        try:
            return self.fd_provider.get_aggregated_sentiment(symbol, limit)
        except Exception as e:
            print(f"DataFeed: Aggregated sentiment error ({symbol}): {e}")
            return 0.0

    def get_fundamental_data(self, symbol: str) -> dict:
        """
        Get comprehensive fundamental data for a symbol.
        Combines insider sentiment, institutional change, and financial metrics.
        """
        return {
            'insider_sentiment': self.get_insider_sentiment(symbol),
            'institutional_change': self.get_institutional_change(symbol),
            'financial_metrics': self.get_financial_metrics(symbol),
            'news_sentiment': self.get_aggregated_sentiment(symbol),
            'segmented_financials': self.get_segmented_financials(symbol),
            'sec_filings': self.get_sec_filings(symbol),
        }

    def is_crypto(self, symbol: str) -> bool:
        """Check if a symbol is a cryptocurrency."""
        return symbol in self.crypto_short_names

    def is_stock(self, symbol: str) -> bool:
        """Check if a symbol is a stock."""
        return symbol in self.stock_symbols

    def get_data_source_status(self) -> dict:
        """Get status of all data sources."""
        return {
            'primary': {
                'name': 'FinancialDatasets.ai',
                'active': self.fd_provider is not None,
                'status': self.fd_provider.get_status() if self.fd_provider else None
            },
            'fallback': {
                'crypto': 'Binance (via CCXT)',
                'stocks': 'Yahoo Finance'
            },
            'symbols': {
                'stocks': self.stock_symbols,
                'crypto': self.crypto_short_names
            }
        }
