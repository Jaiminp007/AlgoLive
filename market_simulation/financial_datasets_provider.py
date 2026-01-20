"""
FinancialDatasets.ai API Provider
Primary data source for AlgoClash trading arena.
Provides: prices, news, insider trades, institutional ownership, financial statements.
"""

import os
import time
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict


class FinancialDatasetsProvider:
    """
    Primary data provider using FinancialDatasets.ai API.
    Features:
    - Multi-tier caching with appropriate TTLs
    - Rate limit tracking and backoff
    - Request retry logic
    - Graceful error handling
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('FINANCIAL_DATASETS_API_KEY')
        if not self.api_key:
            raise ValueError("FINANCIAL_DATASETS_API_KEY is required")

        self.base_url = "https://api.financialdatasets.ai"
        self.headers = {"X-API-KEY": self.api_key}

        # Cache storage with timestamps
        self._cache = defaultdict(dict)

        # Cache TTLs in seconds
        self.CACHE_TTL = {
            'price_snapshot': 1,        # Real-time prices
            'historical': 300,          # 5 minutes
            'news': 300,                # 5 minutes
            'insider_trades': 3600,     # 1 hour
            'institutional': 3600,      # 1 hour
            'financials': 86400,        # 24 hours
            'metrics': 86400,           # 24 hours
        }

        # Rate limiting
        self.rate_limit = int(os.getenv('FD_RATE_LIMIT', '60'))
        self._request_times = []

        # Crypto symbol mapping (FinancialDatasets uses different format)
        self.crypto_symbols = {
            'BTC': 'X:BTCUSD',
            'ETH': 'X:ETHUSD',
            'SOL': 'X:SOLUSD',
            'BNB': 'X:BNBUSD',
            'DOGE': 'X:DOGEUSD',
            'XRP': 'X:XRPUSD',
            'ADA': 'X:ADAUSD',
        }

        print(f"FinancialDatasetsProvider: Initialized with API key ending in ...{self.api_key[-4:]}")

    # =========================================================================
    # CACHING UTILITIES
    # =========================================================================

    def _get_cache(self, cache_type: str, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        cache = self._cache[cache_type]
        if key in cache:
            data, timestamp = cache[key]
            ttl = self.CACHE_TTL.get(cache_type, 60)
            if time.time() - timestamp < ttl:
                return data
        return None

    def _set_cache(self, cache_type: str, key: str, value: Any):
        """Store value in cache with current timestamp."""
        self._cache[cache_type][key] = (value, time.time())

    def _clear_cache(self, cache_type: str = None):
        """Clear cache (all or specific type)."""
        if cache_type:
            self._cache[cache_type].clear()
        else:
            self._cache.clear()

    # =========================================================================
    # RATE LIMITING
    # =========================================================================

    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        now = time.time()
        # Remove requests older than 1 minute
        self._request_times = [t for t in self._request_times if now - t < 60]
        return len(self._request_times) < self.rate_limit

    def _record_request(self):
        """Record a request for rate limiting."""
        self._request_times.append(time.time())

    # =========================================================================
    # HTTP REQUEST HANDLING
    # =========================================================================

    def _make_request(
        self,
        endpoint: str,
        params: Dict = None,
        retries: int = 2,
        timeout: int = 10
    ) -> Optional[Dict]:
        """
        Make HTTP request to FinancialDatasets.ai API.

        Args:
            endpoint: API endpoint path (e.g., '/prices/snapshot')
            params: Query parameters
            retries: Number of retry attempts
            timeout: Request timeout in seconds

        Returns:
            JSON response dict or None on failure
        """
        if not self._check_rate_limit():
            print(f"FD: Rate limit reached, waiting...")
            time.sleep(1)

        url = f"{self.base_url}{endpoint}"

        for attempt in range(retries + 1):
            try:
                self._record_request()
                response = requests.get(
                    url,
                    params=params,
                    headers=self.headers,
                    timeout=timeout
                )

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    # Rate limited - exponential backoff
                    wait_time = 2 ** attempt
                    print(f"FD: Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                elif response.status_code == 404:
                    # No data available for this ticker
                    return None
                else:
                    print(f"FD: Request failed ({response.status_code}): {endpoint}")

            except requests.exceptions.Timeout:
                print(f"FD: Request timeout: {endpoint}")
            except requests.exceptions.RequestException as e:
                print(f"FD: Request error: {e}")

            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))

        return None

    # =========================================================================
    # PRICE DATA
    # =========================================================================

    def get_price_snapshot(self, ticker: str) -> Optional[Dict]:
        """
        Get real-time price snapshot for a stock ticker.

        Args:
            ticker: Stock symbol (e.g., 'AAPL', 'TSLA')

        Returns:
            Dict with price, day_change, day_change_percent, market_cap, time
        """
        # Check cache
        cached = self._get_cache('price_snapshot', ticker)
        if cached:
            return cached

        data = self._make_request('/prices/snapshot', {'ticker': ticker})

        if data and 'snapshot' in data:
            result = data['snapshot']
            self._set_cache('price_snapshot', ticker, result)
            return result

        return None

    def get_historical_prices(
        self,
        ticker: str,
        interval: str = 'minute',
        interval_multiplier: int = 1,
        start_date: str = None,
        end_date: str = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get historical OHLCV price data.

        Args:
            ticker: Stock symbol
            interval: 'minute', 'day', 'week', 'month', 'year'
            interval_multiplier: Multiplier for interval
            start_date: Start date YYYY-MM-DD (defaults to 1 day ago)
            end_date: End date YYYY-MM-DD (defaults to today)
            limit: Max records

        Returns:
            List of dicts with open, close, high, low, volume, time
        """
        # Set default dates
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        cache_key = f"{ticker}_{interval}_{interval_multiplier}_{start_date}_{end_date}"
        cached = self._get_cache('historical', cache_key)
        if cached:
            return cached

        data = self._make_request('/prices', {
            'ticker': ticker,
            'interval': interval,
            'interval_multiplier': interval_multiplier,
            'start_date': start_date,
            'end_date': end_date,
            'limit': limit
        })

        if data and 'prices' in data:
            result = data['prices']
            self._set_cache('historical', cache_key, result)
            return result

        return []

    def get_crypto_prices(
        self,
        ticker: str,
        interval: str = 'minute',
        interval_multiplier: int = 1,
        start_date: str = None,
        end_date: str = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get historical crypto price data.

        Args:
            ticker: Crypto symbol (e.g., 'BTC', 'ETH', 'SOL')
            interval: 'minute', 'day', 'week', 'month', 'year'

        Returns:
            List of OHLCV candles
        """
        # Map to FinancialDatasets format
        fd_ticker = self.crypto_symbols.get(ticker, f"X:{ticker}USD")

        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        cache_key = f"crypto_{ticker}_{interval}_{start_date}_{end_date}"
        cached = self._get_cache('historical', cache_key)
        if cached:
            return cached

        data = self._make_request('/crypto/prices', {
            'ticker': fd_ticker,
            'interval': interval,
            'interval_multiplier': interval_multiplier,
            'start_date': start_date,
            'end_date': end_date,
            'limit': limit
        })

        if data and 'prices' in data:
            result = data['prices']
            self._set_cache('historical', cache_key, result)
            return result

        return []

    # =========================================================================
    # NEWS DATA
    # =========================================================================

    def get_news(self, ticker: str, limit: int = 10) -> List[Dict]:
        """
        Get company news with pre-calculated sentiment.

        Args:
            ticker: Stock symbol
            limit: Max number of articles (max 100)

        Returns:
            List of dicts with title, source, sentiment, date, url
        """
        cache_key = f"{ticker}_{limit}"
        cached = self._get_cache('news', cache_key)
        if cached:
            return cached

        data = self._make_request('/news', {
            'ticker': ticker,
            'limit': min(limit, 100)
        })

        if data and 'news' in data:
            result = data['news']
            self._set_cache('news', cache_key, result)
            return result

        return []

    def get_aggregated_sentiment(self, ticker: str, limit: int = 10) -> float:
        """
        Calculate aggregate sentiment score from recent news.

        Returns:
            Float between -1.0 (bearish) and 1.0 (bullish)
        """
        news = self.get_news(ticker, limit)
        if not news:
            return 0.0

        sentiment_scores = []
        for article in news:
            sentiment = article.get('sentiment', 'neutral')
            if isinstance(sentiment, str):
                # Convert text sentiment to numeric
                sentiment_map = {
                    'positive': 1.0,
                    'bullish': 1.0,
                    'negative': -1.0,
                    'bearish': -1.0,
                    'neutral': 0.0
                }
                score = sentiment_map.get(sentiment.lower(), 0.0)
            else:
                score = float(sentiment)
            sentiment_scores.append(score)

        return sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0

    # =========================================================================
    # INSIDER TRADES
    # =========================================================================

    def get_insider_trades(self, ticker: str, limit: int = 50) -> List[Dict]:
        """
        Get insider trading activity (buys/sells by executives).

        Args:
            ticker: Stock symbol
            limit: Max number of trades

        Returns:
            List of insider trade records
        """
        cached = self._get_cache('insider_trades', ticker)
        if cached:
            return cached

        data = self._make_request('/insider-trades', {
            'ticker': ticker,
            'limit': limit
        })

        if data and 'insider_trades' in data:
            result = data['insider_trades']
            self._set_cache('insider_trades', ticker, result)
            return result

        return []

    def calculate_insider_sentiment(self, ticker: str, days: int = 90) -> float:
        """
        Calculate net insider sentiment from recent trades.

        Returns:
            Float between -1.0 (net selling) and 1.0 (net buying)
        """
        trades = self.get_insider_trades(ticker)
        if not trades:
            return 0.0

        # Filter to recent trades
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        recent_trades = [
            t for t in trades
            if t.get('transaction_date', '2000-01-01') >= cutoff_date
        ]

        if not recent_trades:
            return 0.0

        # Calculate net buying/selling
        total_buy_value = 0.0
        total_sell_value = 0.0

        for trade in recent_trades:
            trade_type = trade.get('transaction_type', '').lower()
            value = abs(float(trade.get('value', 0) or 0))

            if 'buy' in trade_type or 'acquire' in trade_type:
                total_buy_value += value
            elif 'sell' in trade_type or 'dispose' in trade_type:
                total_sell_value += value

        total = total_buy_value + total_sell_value
        if total == 0:
            return 0.0

        # Net ratio: -1 (all selling) to +1 (all buying)
        return (total_buy_value - total_sell_value) / total

    # =========================================================================
    # INSTITUTIONAL OWNERSHIP
    # =========================================================================

    def get_institutional_ownership(self, ticker: str) -> List[Dict]:
        """
        Get institutional ownership data (13F filings).

        Args:
            ticker: Stock symbol

        Returns:
            List of institutional holders with shares and values
        """
        cached = self._get_cache('institutional', ticker)
        if cached:
            return cached

        # Use longer timeout for institutional data (can be slow)
        data = self._make_request('/institutional-ownership', {'ticker': ticker}, timeout=30)

        if data and 'ownership' in data:
            result = data['ownership']
            self._set_cache('institutional', ticker, result)
            return result

        return []

    def calculate_institutional_change(self, ticker: str) -> float:
        """
        Calculate quarter-over-quarter change in institutional ownership.

        Returns:
            Percentage change in institutional ownership
        """
        ownership = self.get_institutional_ownership(ticker)
        if not ownership or len(ownership) < 2:
            return 0.0

        # Get most recent and previous quarter totals
        sorted_data = sorted(
            ownership,
            key=lambda x: x.get('report_date', '2000-01-01'),
            reverse=True
        )

        if len(sorted_data) < 2:
            return 0.0

        current_shares = float(sorted_data[0].get('shares', 0) or 0)
        previous_shares = float(sorted_data[1].get('shares', 0) or 0)

        if previous_shares == 0:
            return 0.0

        return ((current_shares - previous_shares) / previous_shares) * 100

    # =========================================================================
    # FINANCIAL STATEMENTS
    # =========================================================================

    def get_financial_statements(
        self,
        ticker: str,
        statement_type: str = 'income-statements',
        period: str = 'quarterly',
        limit: int = 4
    ) -> List[Dict]:
        """
        Get financial statements.

        Args:
            ticker: Stock symbol
            statement_type: 'income-statements', 'balance-sheets', 'cash-flow-statements'
            period: 'annual', 'quarterly', 'ttm'
            limit: Number of statements

        Returns:
            List of financial statement records
        """
        cache_key = f"{ticker}_{statement_type}_{period}"
        cached = self._get_cache('financials', cache_key)
        if cached:
            return cached

        data = self._make_request(f'/financials/{statement_type}', {
            'ticker': ticker,
            'period': period,
            'limit': limit
        })

        # Response key varies by statement type
        key_map = {
            'income-statements': 'income_statements',
            'balance-sheets': 'balance_sheets',
            'cash-flow-statements': 'cash_flow_statements'
        }
        response_key = key_map.get(statement_type, 'income_statements')

        if data and response_key in data:
            result = data[response_key]
            self._set_cache('financials', cache_key, result)
            return result

        return []

    def get_financial_metrics(self, ticker: str) -> Dict:
        """
        Calculate key financial metrics from statements.

        Returns:
            Dict with revenue_growth, profit_margin, pe_ratio, earnings_surprise
        """
        cache_key = f"metrics_{ticker}"
        cached = self._get_cache('metrics', cache_key)
        if cached:
            return cached

        metrics = {
            'revenue_growth': None,
            'profit_margin': None,
            'pe_ratio': None,
            'earnings_surprise': None,
            'earnings_per_share': None,
        }

        try:
            # Get income statements
            income = self.get_financial_statements(ticker, 'income-statements', 'quarterly', 8)

            if income and len(income) >= 2:
                latest = income[0]
                previous = income[4] if len(income) > 4 else income[-1]  # YoY comparison

                # Revenue Growth (YoY)
                current_rev = float(latest.get('revenue', 0) or 0)
                prev_rev = float(previous.get('revenue', 0) or 0)
                if prev_rev > 0:
                    metrics['revenue_growth'] = ((current_rev - prev_rev) / prev_rev) * 100

                # Profit Margin
                net_income = float(latest.get('net_income', 0) or 0)
                if current_rev > 0:
                    metrics['profit_margin'] = net_income / current_rev

                # EPS
                metrics['earnings_per_share'] = float(latest.get('earnings_per_share', 0) or 0)

            # Get price for P/E calculation
            snapshot = self.get_price_snapshot(ticker)
            if snapshot and metrics['earnings_per_share']:
                price = float(snapshot.get('price', 0) or 0)
                eps = metrics['earnings_per_share']
                if eps > 0:
                    metrics['pe_ratio'] = price / (eps * 4)  # Annualize quarterly EPS

        except Exception as e:
            print(f"FD: Error calculating metrics for {ticker}: {e}")

        self._set_cache('metrics', cache_key, metrics)
        return metrics

    # =========================================================================
    # SEGMENTED FINANCIALS & SEC FILINGS
    # =========================================================================

    def get_segmented_financials(self, ticker: str, period: str = 'annual', limit: int = 5) -> Dict:
        """
        Get segmented financial data (business & geographic).
        
        Args:
            ticker: Stock symbol
            period: 'annual' or 'quarterly'
            limit: Number of periods
            
        Returns:
            Dict containing 'business_segments' and 'geographic_segments' lists
        """
        cache_key = f"segments_{ticker}_{period}"
        cached = self._get_cache('financials', cache_key)
        if cached:
            return cached

        data = self._make_request('/financials/segmented', {
            'ticker': ticker,
            'period': period,
            'limit': limit
        })

        if data:
            # result structure usually has "search_results" or direct keys
            # Verify API response structure. Docs say it returns list of objects
            # but let's store the raw response for flexibility.
            self._set_cache('financials', cache_key, data)
            return data

        return {}

    def get_sec_filings(self, ticker: str, limit: int = 20) -> List[Dict]:
        """
        Get recent SEC filings (8-K, 10-K, 10-Q, etc.).
        
        Args:
            ticker: Stock symbol
            limit: Number of filings to retrieve
            
        Returns:
            List of filing records (type, date, url)
        """
        cache_key = f"filings_{ticker}"
        cached = self._get_cache('financials', cache_key)
        if cached:
            return cached

        data = self._make_request('/filings', {
            'ticker': ticker,
            'limit': limit
        })

        if data and 'filings' in data:
            result = data['filings']
            self._set_cache('financials', cache_key, result)
            return result

        return []

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_available_stock_tickers(self) -> List[str]:
        """Get list of available stock tickers."""
        data = self._make_request('/prices/snapshot/tickers')
        if data and 'tickers' in data:
            return data['tickers']
        return []

    def is_available(self) -> bool:
        """Check if API is reachable and key is valid."""
        try:
            # Try a simple request
            data = self._make_request('/prices/snapshot', {'ticker': 'AAPL'}, retries=1, timeout=5)
            return data is not None
        except:
            return False

    def get_status(self) -> Dict:
        """Get provider status information."""
        return {
            'name': 'FinancialDatasets.ai',
            'api_key_set': bool(self.api_key),
            'rate_limit': self.rate_limit,
            'requests_last_minute': len(self._request_times),
            'cache_sizes': {k: len(v) for k, v in self._cache.items()},
            'is_available': self.is_available()
        }


# Standalone test
if __name__ == "__main__":
    import json

    provider = FinancialDatasetsProvider()

    print("=== Testing FinancialDatasetsProvider ===\n")

    # Test price snapshot
    print("1. Price Snapshot (AAPL):")
    snapshot = provider.get_price_snapshot('AAPL')
    print(json.dumps(snapshot, indent=2) if snapshot else "No data")

    # Test news
    print("\n2. News (AAPL):")
    news = provider.get_news('AAPL', limit=3)
    for article in news[:3]:
        print(f"  - {article.get('title', 'No title')[:60]}... ({article.get('sentiment', 'N/A')})")

    # Test insider sentiment
    print("\n3. Insider Sentiment (AAPL):")
    insider = provider.calculate_insider_sentiment('AAPL')
    print(f"  Score: {insider:.2f}")

    # Test financial metrics
    print("\n4. Financial Metrics (AAPL):")
    metrics = provider.get_financial_metrics('AAPL')
    print(json.dumps(metrics, indent=2))

    # Test crypto
    print("\n5. Crypto Prices (BTC):")
    crypto = provider.get_crypto_prices('BTC', limit=5)
    if crypto:
        print(f"  Latest: ${crypto[-1].get('close', 0):,.2f}")

    print("\n=== Status ===")
    print(json.dumps(provider.get_status(), indent=2))
