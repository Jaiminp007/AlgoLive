"""
AlgoClash Cortex - News Feed
Fetches live crypto news from CryptoPanic API with caching and sentiment scoring.
"""

import os
import time
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime


class NewsFeed:
    """
    Fetches live crypto news from CryptoPanic API.
    Features:
    - Rate-limited caching (5-minute TTL)
    - Graceful degradation (mock news if API fails)
    - Integration with FinBERT sentiment scoring
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('CRYPTOPANIC_API_KEY')
        self.base_url = "https://cryptopanic.com/api/developer/v2/posts/"
        
        # Cache settings
        self.cache: List[Dict] = []
        self.cache_time: float = 0
        self.cache_ttl: int = 300  # 5 minutes
        
        # Breaking news detection
        self.breaking_keywords = [
            'crash', 'hack', 'exploit', 'sec', 'regulation', 'ban',
            'etf', 'approval', 'halving', 'surge', 'plunge', 'emergency'
        ]
        
        # Mock news fallback
        self.mock_news = [
            {"title": "Bitcoin holds steady above $97,000 as market consolidates", "source": "CoinDesk", "sentiment": "neutral"},
            {"title": "Institutional demand continues as ETF inflows remain strong", "source": "Bloomberg", "sentiment": "bullish"},
            {"title": "Ethereum developers announce next upgrade timeline", "source": "Decrypt", "sentiment": "neutral"},
            {"title": "Federal Reserve signals steady policy, crypto markets stable", "source": "Reuters", "sentiment": "neutral"},
            {"title": "Major exchange reports record trading volume this quarter", "source": "CryptoNews", "sentiment": "bullish"},
        ]
    
    def get_latest_news(self, currencies: List[str] = ["BTC", "ETH"], limit: int = 10) -> List[Dict]:
        """
        Fetches latest crypto news.
        
        Args:
            currencies: List of currency symbols to filter by
            limit: Maximum number of news items to return
        
        Returns:
            List of news items with title, source, and sentiment
        """
        # Check cache
        if self._is_cache_valid():
            return self.cache[:limit]
        
        # Try API fetch
        try:
            news = self._fetch_from_api(currencies, limit)
            if news:
                self.cache = news
                self.cache_time = time.time()
                return news
        except Exception as e:
            print(f"NewsFeed: API error: {e}")
        
        # Fallback to mock (but keep existing cache if we have it)
        if self.cache:
            return self.cache[:limit]
        
        return self.mock_news[:limit]
    
    def get_news_digest(self, sentiment_engine=None) -> Dict[str, Any]:
        """
        Returns a structured news digest with aggregate sentiment.
        
        Args:
            sentiment_engine: Optional SentimentSignalGenerator for FinBERT scoring
        
        Returns:
            Dict with headlines, aggregate_sentiment, and breaking_alert
        """
        news = self.get_latest_news()
        
        if not news:
            return {
                "headlines": [],
                "aggregate_sentiment": 0.0,
                "breaking_alert": None
            }
        
        # Extract headlines
        headlines = [item.get('title', '') for item in news[:5]]
        
        # Calculate aggregate sentiment
        aggregate_sentiment = self._calculate_aggregate_sentiment(news, sentiment_engine)
        
        # Check for breaking news
        breaking_alert = self._detect_breaking_news(news)
        
        return {
            "headlines": headlines,
            "aggregate_sentiment": round(aggregate_sentiment, 3),
            "breaking_alert": breaking_alert
        }
    
    def _is_cache_valid(self) -> bool:
        """Check if cache is still fresh."""
        return self.cache and (time.time() - self.cache_time) < self.cache_ttl
    
    def _fetch_from_api(self, currencies: List[str], limit: int) -> List[Dict]:
        """
        Fetches news from CryptoPanic API.
        
        Free tier: No API key needed for public posts, but rate limited.
        With API key: Higher rate limits and more features.
        """
        params = {
            "currencies": ",".join(currencies),
            "filter": "important",  # Only important posts
            "public": "true",
        }
        
        if self.api_key:
            params["auth_token"] = self.api_key
        
        try:
            response = requests.get(
                self.base_url,
                params=params,
                timeout=10,
                headers={"User-Agent": "AlgoClash/1.0"}
            )
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                news = []
                for item in results[:limit]:
                    # Extract CryptoPanic sentiment votes
                    votes = item.get('votes', {})
                    positive = votes.get('positive', 0)
                    negative = votes.get('negative', 0)
                    
                    if positive > negative:
                        sentiment = "bullish"
                    elif negative > positive:
                        sentiment = "bearish"
                    else:
                        sentiment = "neutral"
                    
                    news.append({
                        "title": item.get('title', ''),
                        "source": item.get('source', {}).get('title') if item.get('source') else item.get('domain', 'CryptoPanic'),
                        "url": item.get('url', ''),
                        "published_at": item.get('published_at', ''),
                        "sentiment": sentiment,
                        "votes_positive": positive,
                        "votes_negative": negative
                    })
                
                return news
            
            elif response.status_code == 429:
                print("NewsFeed: Rate limited. Using cache/mock.")
                return []
            
            else:
                print(f"NewsFeed: API returned {response.status_code}")
                return []
                
        except requests.exceptions.Timeout:
            print("NewsFeed: Request timeout")
            return []
        except requests.exceptions.RequestException as e:
            print(f"NewsFeed: Request error: {e}")
            return []
    
    def _calculate_aggregate_sentiment(
        self, 
        news: List[Dict], 
        sentiment_engine
    ) -> float:
        """
        Calculates aggregate sentiment score.
        Uses FinBERT if available, otherwise uses CryptoPanic votes.
        
        Returns: Score between -1 (very bearish) and 1 (very bullish)
        """
        if not news:
            return 0.0
        
        # Try FinBERT scoring
        if sentiment_engine and hasattr(sentiment_engine, 'get_sentiment_score'):
            try:
                scores = []
                for item in news[:5]:  # Limit to 5 for performance
                    title = item.get('title', '')
                    if title:
                        score = sentiment_engine.get_sentiment_score(title)
                        scores.append(score)
                
                if scores:
                    return sum(scores) / len(scores)
            except Exception as e:
                print(f"NewsFeed: FinBERT error: {e}")
        
        # Fallback to vote-based sentiment
        bullish_count = sum(1 for n in news if n.get('sentiment') == 'bullish')
        bearish_count = sum(1 for n in news if n.get('sentiment') == 'bearish')
        total = len(news)
        
        if total == 0:
            return 0.0
        
        # Score: (bullish - bearish) / total
        return (bullish_count - bearish_count) / total
    
    def _detect_breaking_news(self, news: List[Dict]) -> Optional[str]:
        """
        Detects breaking/urgent news based on keywords.
        
        Returns: Breaking alert string or None
        """
        if not news:
            return None
        
        # Check most recent news item
        latest = news[0]
        title = latest.get('title', '').lower()
        
        for keyword in self.breaking_keywords:
            if keyword in title:
                return latest.get('title', '')
        
        return None


# Standalone test
if __name__ == "__main__":
    import json
    
    nf = NewsFeed()
    
    print("=== Fetching News ===")
    news = nf.get_latest_news()
    print(f"Got {len(news)} news items:")
    for item in news[:3]:
        print(f"  - [{item.get('sentiment', 'n/a')}] {item.get('title', 'No title')}")
    
    print("\n=== News Digest ===")
    digest = nf.get_news_digest()
    print(json.dumps(digest, indent=2))
