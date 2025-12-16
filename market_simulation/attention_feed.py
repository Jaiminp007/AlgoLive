"""
Attention Feed - Google Trends Integration
Measures retail interest/attention for crypto assets.
Uses caching to avoid rate limits.
"""
import os
import time
import warnings

# Suppress pytrends FutureWarning about fillna
warnings.filterwarnings('ignore', category=FutureWarning, module='pytrends')

# Optional import - graceful fallback if not installed
try:
    from pytrends.request import TrendReq
    PYTRENDS_AVAILABLE = True
except ImportError:
    PYTRENDS_AVAILABLE = False
    print("Warning: pytrends not installed. Run: pip install pytrends")


class AttentionFeed:
    def __init__(self):
        self.cache = {}  # {symbol: attention_score}
        self.last_update = 0
        self.update_interval = 3600  # 1 hour to avoid rate limits
        
        # Map crypto symbols to Google search terms
        self.search_terms = {
            'BTC': 'Bitcoin',
            'ETH': 'Ethereum', 
            'SOL': 'Solana',
            'XRP': 'XRP',
            'DOGE': 'Dogecoin',
            'BNB': 'Binance Coin',
            'ADA': 'Cardano',
            'AVAX': 'Avalanche'
        }
        
        self.pytrends = None
        if PYTRENDS_AVAILABLE:
            try:
                self.pytrends = TrendReq(hl='en-US', tz=360, timeout=(10, 25))
                print("AttentionFeed: PyTrends initialized.")
            except Exception as e:
                print(f"AttentionFeed: Failed to init PyTrends: {e}")
    
    def get_attention(self, symbols=None):
        """
        Get attention scores for specified symbols.
        Returns dict: {symbol: attention_score}
        
        Attention score interpretation:
        - 0.0 - 0.5: Low interest
        - 0.5 - 1.0: Normal interest  
        - 1.0 - 2.0: Above average interest
        - 2.0+: High attention / viral
        """
        if symbols is None:
            symbols = ['BTC', 'ETH', 'SOL']
        
        current_time = time.time()
        
        # Return cached values if still fresh
        if current_time - self.last_update < self.update_interval and self.cache:
            return {sym: self.cache.get(sym, 0.0) for sym in symbols}
        
        # If PyTrends not available, return zeros
        if not PYTRENDS_AVAILABLE or self.pytrends is None:
            return {sym: 0.0 for sym in symbols}
        
        try:
            # Get search terms for requested symbols
            terms = [self.search_terms.get(sym, sym) for sym in symbols[:5]]  # Max 5 terms
            
            # Build payload and fetch data
            self.pytrends.build_payload(terms, timeframe='now 7-d', geo='', gprop='')
            df = self.pytrends.interest_over_time()
            
            if df.empty:
                print("AttentionFeed: No data returned from Google Trends")
                return {sym: 0.0 for sym in symbols}
            
            # Calculate attention velocity (current vs average)
            result = {}
            for sym in symbols:
                term = self.search_terms.get(sym, sym)
                if term in df.columns:
                    recent = df[term].iloc[-24:].mean()  # Last 24 hours
                    overall = df[term].mean()  # Full 7 days
                    
                    if overall > 0:
                        # Attention = ratio of recent to average (1.0 = normal)
                        attention = recent / overall
                    else:
                        attention = 0.0
                    
                    result[sym] = round(attention, 2)
                else:
                    result[sym] = 0.0
            
            # Update cache
            self.cache = result
            self.last_update = current_time
            
            print(f"AttentionFeed: Updated - {result}")
            return result
            
        except Exception as e:
            print(f"AttentionFeed: Error fetching trends: {e}")
            # Return cached values on error
            return {sym: self.cache.get(sym, 0.0) for sym in symbols}
