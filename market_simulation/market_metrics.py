import numpy as np
import pandas as pd

class CryptoMetrics:
    """
    Standalone library to calculate HFT alpha signals for AlgoClash agents.
    Input: Pandas DataFrame with columns ['open', 'high', 'low', 'close', 'volume', 'buy_volume', 'sell_volume', 'funding_rate', 'open_interest']
    """

    @staticmethod
    def calculate_parkinson_volatility(high, low, window=14):
        """
        Standard Deviation estimates volatility based on close-to-close.
        Parkinson uses High-Low range, which is far better for crypto HFT 
        as it captures the true 'travel' of price during the candle.
        """
        # Formula: sqrt(1 / (4 * ln(2)) * mean(ln(H/L)^2))
        const = 1.0 / (4.0 * np.log(2.0))
        # Handle zero division safety
        high = high.replace(0, np.nan)
        low = low.replace(0, np.nan)
        
        log_hl_ratio = np.log(high / low)
        
        # Rolling window calculation
        vol = np.sqrt(const * (log_hl_ratio ** 2).rolling(window=window).mean())
        return vol.fillna(0.0)

    @staticmethod
    def calculate_cvd_divergence(price, buy_vol, sell_vol, window=20):
        """
        Detects divergence between Price and Cumulative Volume Delta (CVD).
        Returns a score: 
         1.0 (Bullish Convergence), -1.0 (Bearish Divergence), 0.0 (Neutral)
        """
        # 1. Calculate Delta and CVD
        delta = buy_vol - sell_vol
        cvd = delta.cumsum()
        
        # High-Speed Correlation Approach:
        # If Price is UP but CVD is DOWN => Divergence (-1)
        
        price_change = price.diff(window)
        cvd_change = cvd.diff(window)
        
        divergence_score = pd.Series(0.0, index=price.index)
        
        # Vectorized logic
        # Bullish Div: Price Down, CVD Up (Absorption)
        bullish_div = (price_change < 0) & (cvd_change > 0)
        
        # Bearish Div: Price Up, CVD Down (Exhaustion)
        bearish_div = (price_change > 0) & (cvd_change < 0)
        
        # Healthy Trend: Price Up, CVD Up
        healthy_bull = (price_change > 0) & (cvd_change > 0)
        
        divergence_score[bullish_div] = 0.5   # Absorption buying
        divergence_score[bearish_div] = -1.0  # WARNING: Trap
        divergence_score[healthy_bull] = 0.2  # Trend confirmation
        
        return divergence_score.fillna(0.0)

    @staticmethod
    def calculate_funding_velocity(funding_rates, window=8):
        """
        Measures the rate of change in funding rates.
        Rapid spikes in funding often precede liquidations.
        """
        return funding_rates.diff(window).fillna(0.0)

    @staticmethod
    def calculate_taker_ratio(buy_vol, sell_vol, window=10):
        """
        Ratio of Aggressive Buys vs Aggressive Sells.
        Smoothed over a window to remove noise.
        """
        rolling_buy = buy_vol.rolling(window=window).sum()
        rolling_sell = sell_vol.rolling(window=window).sum()
        
        # Avoid division by zero
        ratio = rolling_buy / (rolling_sell.replace(0, 1))
        return ratio.fillna(1.0)
