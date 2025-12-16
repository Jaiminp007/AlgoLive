import ccxt
import pandas as pd
from datetime import datetime
import time

class DataFeed:
    def __init__(self):
        # Use Binance Global public API for accurate pricing
        # Rate limits are handled by ccxt
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
        })
        self.symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT", "BNB/USDT", "ZEC/USDT", "TRX/USDT", "SUI/USDT", "LINK/USDT", "PEPE/USDT", "SHIB/USDT", "WIF/USDT", "ADA/USDT", "AVAX/USDT"]
        self.symbol_map = {
            "BTC/USDT": "BTC",
            "ETH/USDT": "ETH",
            "SOL/USDT": "SOL",
            "XRP/USDT": "XRP",
            "DOGE/USDT": "DOGE",
            "BNB/USDT": "BNB",
            "ZEC/USDT": "ZEC",
            "TRX/USDT": "TRX",
            "SUI/USDT": "SUI",
            "LINK/USDT": "LINK",
            "PEPE/USDT": "PEPE",
            "SHIB/USDT": "SHIB",
            "WIF/USDT": "WIF",
            "ADA/USDT": "ADA",
            "AVAX/USDT": "AVAX"
        }
        self.interval = "1h"

    def get_ticker(self):
        """Legacy: Returns BTC ticker for backward compatibility."""
        try:
            ticker = self.exchange.fetch_ticker("BTC/USDT")
            return {
                "price": float(ticker['last']),
                "volume": float(ticker['baseVolume']),
                "symbol": "BTC",
                "timestamp": int(datetime.now().timestamp() * 1000)
            }
        except:
            return None

    def get_multi_tickers(self):
        """
        Fetches Tickers for ALL tracked symbols.
        Returns: { 'BTC': {price, volume...}, 'ETH': {...} }
        """
        try:
            tickers = self.exchange.fetch_tickers(self.symbols)
            result = {}
            timestamp = int(datetime.now().timestamp() * 1000)
            
            for pair, data in tickers.items():
                short_name = self.symbol_map.get(pair, pair)
                result[short_name] = {
                    "price": float(data['last']),
                    "volume": float(data['baseVolume']),
                    "bid": float(data['bid'] or 0),
                    "ask": float(data['ask'] or 0),
                    "timestamp": timestamp
                }
            return result
        except Exception as e:
            print(f"Error fetching multi-tickers: {e}")
            return {}

    def get_order_book(self, limit=5):
        """Fetches Order Book for BTC (Legacy support)."""
        try:
            order_book = self.exchange.fetch_order_book("BTC/USDT", limit=limit)
            return {'bids': order_book['bids'], 'asks': order_book['asks']}
        except:
            return {'bids': [], 'asks': []}

    def get_historical_data(self, limit=100, timeframe='1m'):
        """
        Fetches historical data for ALL symbols.
        Returns: { 'BTC': [candles], 'ETH': [candles] }
        """
        try:
            all_history = {}
            for pair in self.symbols:
                short_name = self.symbol_map[pair]
                ohlcv = self.exchange.fetch_ohlcv(pair, timeframe=timeframe, limit=limit)
                
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
                # Rate limit safety
                time.sleep(0.1)
            
            return all_history
        except Exception as e:
            print(f"Exception fetching historical: {e}")
            return {}

    def get_funding_rates(self):
        """
        Fetches Funding Rates for all symbols. 
        Returns: { 'BTC': 0.0001, 'ETH': 0.0002 ... }
        """
        try:
            # fetchFundingRates is supported by Binance
            rates = self.exchange.fetch_funding_rates(self.symbols)
            result = {}
            for pair, data in rates.items():
                short_name = self.symbol_map.get(pair, pair)
                result[short_name] = data['fundingRate']
            return result
        except Exception as e:
            # print(f"Funding Rate Error: {e}") # Suppress to avoid spam if spot-only
            return {}

    def get_news(self):
        """Mock news."""
        return [
            "Bitcoin surges past $95k as institutional demand grows.",
            "SEC approves new crypto regulations, market optimistic.",
            "Inflation data comes in lower than expected, risk assets rally.",
            "Tech giants explore Bitcoin treasury integration.",
            "Mining difficulty increases, causing hash rate adjustments."
        ]

    def get_market_snapshot(self):
        """
        Fetches comprehensive market data: Tickers + Order Books.
        Returns: { 
            'BTC': { 
                'price': ..., 
                'volume': ..., 
                'bids': [[p,v], ...], 
                'asks': [[p,v], ...] 
            }, 
            ... 
        }
        """
        snapshot = {}
        try:
            # 1. Get Tickers (Fast)
            tickers = self.exchange.fetch_tickers(self.symbols)
            timestamp = int(datetime.now().timestamp() * 1000)
            
            for pair, data in tickers.items():
                short_name = self.symbol_map.get(pair, pair)
                
                # Basic Ticker Data
                snapshot[short_name] = {
                    "price": float(data['last']),
                    "volume": float(data['baseVolume']),
                    "high": float(data['high'] or data['last']),
                    "low": float(data['low'] or data['last']),
                    "open": float(data['open'] or data['last']),
                    "bid": float(data['bid'] or 0),
                    "ask": float(data['ask'] or 0),
                    "timestamp": timestamp,
                    # Fallbacks for Order Book if fetch fails
                    "bids": [],
                    "asks": []
                }

                # 2. Get Order Book (Slower - Be careful with rate limits)
                # For high-freq, we might want to use Async CCXT, but for now we try/except per symbol
                # or simplified flow.
                try:
                    # Limit 10 for DeepLOB lite
                    ob = self.exchange.fetch_order_book(pair, limit=10)
                    snapshot[short_name]['bids'] = ob['bids']
                    snapshot[short_name]['asks'] = ob['asks']
                except Exception as e:
                    # Order book fetch failed (rate limit?), keep empty list
                    pass
                    
            return snapshot
            
        except Exception as e:
            print(f"Snapshot Error: {e}")
            return {}
