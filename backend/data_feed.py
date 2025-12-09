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
        self.symbol = "BTC/USDT"
        self.interval = "1h"

    def get_ticker(self):
        """
        Fetches Ticker Data: Price, Volume, Spread.
        Returns: {price, volume, bid, ask, timestamp}
        """
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            return {
                "price": float(ticker['last']),
                "volume": float(ticker['baseVolume']), # 24h Volume
                "bid": float(ticker['bid']),
                "ask": float(ticker['ask']),
                "symbol": "BTC/USD", 
                "timestamp": int(datetime.now().timestamp() * 1000)
            }
        except Exception as e:
            print(f"Error fetching ticker: {e}")
            return None

    def get_price(self):
        """Legacy wrapper for compatibility."""
        ticker = self.get_ticker()
        if ticker:
            return ticker
        return None

    def get_order_book(self, limit=5):
        """
        Fetches Order Book (Depth).
        Returns: {'bids': [[price, qty], ...], 'asks': [[price, qty], ...]}
        """
        try:
            order_book = self.exchange.fetch_order_book(self.symbol, limit=limit)
            return {
                'bids': order_book['bids'],
                'asks': order_book['asks']
            }
        except Exception as e:
            print(f"Error fetching order book: {e}")
            return {'bids': [], 'asks': []}

    def get_historical_data(self, limit=100, timeframe='1m'):
        """Fetches historical OHLCV data. Returns List[Dict]."""
        try:
            # ccxt fetch_ohlcv supports limit
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, timeframe=timeframe, limit=limit)
            
            # Format: [timestamp, open, high, low, close, volume]
            data = []
            for candle in ohlcv:
                data.append({
                    'timestamp': candle[0],
                    'open': candle[1],
                    'high': candle[2],
                    'low': candle[3],
                    'close': candle[4],
                    'price': candle[4], # Backward compatibility alias
                    'volume': candle[5]
                })
            
            return data
        except Exception as e:
            print(f"Exception fetching historical: {e}")
            return []

    def get_news(self):
        """Mock news."""
        return [
            "Bitcoin surges past $95k as institutional demand grows.",
            "SEC approves new crypto regulations, market optimistic.",
            "Inflation data comes in lower than expected, risk assets rally.",
            "Tech giants explore Bitcoin treasury integration.",
            "Mining difficulty increases, causing hash rate adjustments."
        ]
