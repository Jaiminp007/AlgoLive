"""
AlgoClash Cortex - Analyst Engine
Computes structured Market State every 5 minutes for agent decision-making.
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional
from collections import deque

# Import existing quant modules
try:
    from market_simulation.quant_features import calculate_multilevel_obi
    from market_simulation.market_metrics import CryptoMetrics
except ImportError:
    # Fallback for standalone testing
    calculate_multilevel_obi = None
    CryptoMetrics = None


class Analyst:
    """
    The Analyst computes a structured "Market State" JSON payload.
    This payload is designed to give agents high-level intelligence
    without requiring them to compute complex indicators themselves.
    """
    
    def __init__(self):
        self.last_state = {}
        self.ema_short = 20
        self.ema_long = 50
        self.rsi_period = 14
        self.volatility_window = 14
        self.swing_lookback = 20
    
    def compute_state(
        self, 
        market_history: Dict[str, deque], 
        news_feed=None,
        sentiment_engine=None,
        order_book_snapshot: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Main entry point. Computes structured market state.
        
        Args:
            market_history: Dict of symbol -> deque of price/volume data
            news_feed: Optional NewsFeed instance for news digest
            sentiment_engine: Optional SentimentSignalGenerator for scoring
            order_book_snapshot: Optional current order book data
        
        Returns:
            Structured market state JSON
        """
        timestamp = int(datetime.now().timestamp() * 1000)
        
        # Use BTC as the primary reference (bellwether)
        btc_history = market_history.get('BTC', deque())
        
        if len(btc_history) < 30:
            # Not enough data for meaningful analysis
            return self._empty_state(timestamp)
        
        # Convert to DataFrame for calculations
        df = pd.DataFrame(list(btc_history))
        
        # Calculate all components
        market_regime = self._compute_market_regime(df, order_book_snapshot)
        technical_signals = self._compute_technical_signals(df)
        risk_metrics = self._compute_risk_metrics(df)
        
        # News digest (if available)
        news_digest = self._compute_news_digest(news_feed, sentiment_engine)
        
        state = {
            "market_regime": market_regime,
            "technical_signals": technical_signals,
            "risk_metrics": risk_metrics,
            "news_digest": news_digest,
            "timestamp": timestamp
        }
        
        self.last_state = state
        return state
    
    def _empty_state(self, timestamp: int) -> Dict[str, Any]:
        """Returns a neutral state when insufficient data is available."""
        return {
            "market_regime": {
                "trend": "UNKNOWN",
                "volatility": "UNKNOWN",
                "order_book_imbalance": "BALANCED"
            },
            "technical_signals": {
                "rsi_14": 50.0,
                "ema_cross": "NONE",
                "support_level": 0.0,
                "resistance_level": 0.0
            },
            "risk_metrics": {
                "current_drawdown": 0.0,
                "sharpe_est": 0.0,
                "volatility_regime": "UNKNOWN"
            },
            "news_digest": {
                "headlines": [],
                "aggregate_sentiment": 0.0,
                "breaking_alert": None
            },
            "timestamp": timestamp
        }
    
    def _compute_market_regime(
        self, 
        df: pd.DataFrame, 
        order_book_snapshot: Optional[Dict]
    ) -> Dict[str, str]:
        """
        Computes market regime: trend, volatility, order book imbalance.
        """
        prices = df['price'].values
        
        # --- TREND ---
        # Use EMA crossover + price position relative to EMAs
        ema_short = self._calculate_ema(prices, self.ema_short)
        ema_long = self._calculate_ema(prices, self.ema_long)
        current_price = prices[-1]
        
        # Trend strength based on EMA separation and price position
        ema_diff_pct = ((ema_short - ema_long) / ema_long) * 100 if ema_long > 0 else 0
        price_above_ema = current_price > ema_short
        
        if ema_diff_pct > 1.0 and price_above_ema:
            trend = "STRONG_UPTREND"
        elif ema_diff_pct > 0.2 and price_above_ema:
            trend = "UPTREND"
        elif ema_diff_pct < -1.0 and not price_above_ema:
            trend = "STRONG_DOWNTREND"
        elif ema_diff_pct < -0.2 and not price_above_ema:
            trend = "DOWNTREND"
        else:
            trend = "SIDEWAYS"
        
        # --- VOLATILITY ---
        # Use Parkinson volatility if available, else simple std
        if 'high' in df.columns and 'low' in df.columns and CryptoMetrics:
            try:
                parkinson = CryptoMetrics.calculate_parkinson_volatility(
                    df['high'], df['low'], window=self.volatility_window
                )
                vol_value = float(parkinson.iloc[-1]) if len(parkinson) > 0 else 0
            except:
                vol_value = float(np.std(prices[-self.volatility_window:]) / np.mean(prices[-self.volatility_window:]))
        else:
            vol_value = float(np.std(prices[-self.volatility_window:]) / np.mean(prices[-self.volatility_window:]))
        
        # Classify volatility (thresholds calibrated for crypto)
        if vol_value > 0.03:
            volatility = "EXTREME"
        elif vol_value > 0.015:
            volatility = "HIGH"
        elif vol_value > 0.005:
            volatility = "MEDIUM"
        else:
            volatility = "LOW"
        
        # --- ORDER BOOK IMBALANCE ---
        if order_book_snapshot and calculate_multilevel_obi:
            btc_ob = order_book_snapshot.get('BTC', {})
            obi = calculate_multilevel_obi({
                'bids': btc_ob.get('bids', []),
                'asks': btc_ob.get('asks', [])
            })
        else:
            obi = 0.0
        
        if obi > 0.3:
            ob_imbalance = "BID_HEAVY"
        elif obi < -0.3:
            ob_imbalance = "ASK_HEAVY"
        else:
            ob_imbalance = "BALANCED"
        
        return {
            "trend": trend,
            "volatility": volatility,
            "order_book_imbalance": ob_imbalance
        }
    
    def _compute_technical_signals(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Computes technical indicators: RSI, EMA cross, support/resistance.
        """
        prices = df['price'].values
        
        # --- RSI-14 ---
        rsi = self._calculate_rsi(prices, self.rsi_period)
        
        # --- EMA CROSS ---
        ema_short = self._calculate_ema(prices, self.ema_short)
        ema_long = self._calculate_ema(prices, self.ema_long)
        
        # Check for recent cross (within last 5 data points)
        if len(prices) >= self.ema_long + 5:
            ema_short_prev = self._calculate_ema(prices[:-5], self.ema_short)
            ema_long_prev = self._calculate_ema(prices[:-5], self.ema_long)
            
            if ema_short > ema_long and ema_short_prev <= ema_long_prev:
                ema_cross = "GOLDEN_CROSS"
            elif ema_short < ema_long and ema_short_prev >= ema_long_prev:
                ema_cross = "DEATH_CROSS"
            else:
                ema_cross = "NONE"
        else:
            ema_cross = "NONE"
        
        # --- SUPPORT / RESISTANCE ---
        support, resistance = self._find_support_resistance(prices)
        
        return {
            "rsi_14": round(rsi, 2),
            "ema_cross": ema_cross,
            "support_level": round(support, 2),
            "resistance_level": round(resistance, 2)
        }
    
    def _compute_risk_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Computes risk metrics: drawdown, estimated Sharpe, volatility regime.
        """
        prices = df['price'].values
        
        # --- CURRENT DRAWDOWN ---
        # Calculate from peak within the data window
        peak = np.max(prices)
        current = prices[-1]
        drawdown = ((current - peak) / peak) * 100 if peak > 0 else 0
        
        # --- SHARPE ESTIMATE ---
        # Simple rolling Sharpe (annualized estimate)
        returns = np.diff(prices) / prices[:-1]
        if len(returns) > 10:
            mean_ret = np.mean(returns)
            std_ret = np.std(returns)
            # Annualize assuming 1-minute data (525600 minutes/year)
            # But we're doing simple estimate, so use hourly scaling (60 data points)
            sharpe = (mean_ret / std_ret) * np.sqrt(60) if std_ret > 0 else 0
        else:
            sharpe = 0.0
        
        # --- VOLATILITY REGIME ---
        std_pct = (np.std(prices[-20:]) / np.mean(prices[-20:])) * 100 if len(prices) >= 20 else 0
        if std_pct > 3:
            vol_regime = "EXTREME"
        elif std_pct > 1.5:
            vol_regime = "HIGH"
        elif std_pct > 0.5:
            vol_regime = "MEDIUM"
        else:
            vol_regime = "LOW"
        
        return {
            "current_drawdown": round(drawdown, 2),
            "sharpe_est": round(sharpe, 3),
            "volatility_regime": vol_regime
        }
    
    def _compute_news_digest(
        self, 
        news_feed, 
        sentiment_engine
    ) -> Dict[str, Any]:
        """
        Computes news digest with sentiment scoring.
        """
        if not news_feed:
            return {
                "headlines": [],
                "aggregate_sentiment": 0.0,
                "breaking_alert": None
            }
        
        try:
            return news_feed.get_news_digest(sentiment_engine)
        except Exception as e:
            print(f"Analyst: News digest error: {e}")
            return {
                "headlines": [],
                "aggregate_sentiment": 0.0,
                "breaking_alert": None
            }
    
    # ==================== HELPER FUNCTIONS ====================
    
    def _calculate_ema(self, prices: np.ndarray, period: int) -> float:
        """Calculate Exponential Moving Average."""
        if len(prices) < period:
            return float(np.mean(prices)) if len(prices) > 0 else 0.0
        
        multiplier = 2 / (period + 1)
        ema = np.mean(prices[:period])  # SMA for first period
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return float(ema)
    
    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """Calculate Relative Strength Index."""
        if len(prices) < period + 1:
            return 50.0  # Neutral
        
        deltas = np.diff(prices)
        gains = np.maximum(deltas, 0)
        losses = np.abs(np.minimum(deltas, 0))
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return float(rsi)
    
    def _find_support_resistance(self, prices: np.ndarray) -> tuple:
        """
        Simple swing high/low detection for support and resistance.
        """
        lookback = min(self.swing_lookback, len(prices) - 1)
        if lookback < 3:
            current = prices[-1]
            return current * 0.98, current * 1.02
        
        recent_prices = prices[-lookback:]
        
        # Find local minima (support) and maxima (resistance)
        support = float(np.min(recent_prices))
        resistance = float(np.max(recent_prices))
        
        return support, resistance


# Standalone test
if __name__ == "__main__":
    from collections import deque
    
    # Create mock data
    mock_history = deque([{
        'timestamp': i,
        'price': 97000 + i * 10 + np.random.randn() * 50,
        'high': 97000 + i * 10 + 30,
        'low': 97000 + i * 10 - 20,
        'volume': 100 + np.random.rand() * 50,
        'buy_volume': 60,
        'sell_volume': 40
    } for i in range(100)])
    
    analyst = Analyst()
    state = analyst.compute_state({'BTC': mock_history})
    
    import json
    print(json.dumps(state, indent=2))
