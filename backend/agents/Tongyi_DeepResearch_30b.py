

import pandas as pd
import numpy as np

class Tongyi_DeepResearch_30b:
    def __init__(self):
        self.history = []
        self.position = "NONE"
        self.entry_price = 0.0
        self.entry_time = 0
        self.equity = 0.0
        self.stop_loss = 0.0
        self.take_profit = 0.0
        
        # Strategy parameters
        self.rsi_period = 14
        self.bb_period = 20
        self.atr_period = 14
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.ema_short = 50
        self.ema_long = 200
        self.obv_threshold = 500
        self.min_profit_pct = 0.001
        self.max_hold_time = 3600*4  # 4 hours
        
    def _calculate_rsi(self, series, period):
        delta = series.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)
    
    def _calculate_macd(self, series):
        macd_line = series.ewm(span=self.macd_fast, adjust=False).mean() - series.ewm(span=self.macd_slow, adjust=False).mean()
        signal_line = macd_line.ewm(span=self.macd_signal, adjust=False).mean()
        return macd_line, signal_line
    
    def _calculate_bollinger_bands(self, df):
        sma = df['close'].rolling(self.bb_period).mean()
        std = df['close'].rolling(self.bb_period).std()
        return sma + 2*std, sma - 2*std
    
    def _calculate_atr(self, df):
        tr = np.maximum(
            df['high'] - df['low'],
            np.maximum(abs(df['high'] - df['close'].shift()), 
                       abs(df['low'] - df['close'].shift()))
        )
        return tr.rolling(self.atr_period).mean()
    
    def _calculate_obv(self, df):
        return np.sign(df['close'].diff()) * df['volume'].cumsum()

    def trade(self, tick_data):
        # Initialize default response
        result = {'action': 'HOLD', 'reason': 'Initial state'}
        
        # Update market data history
        self.history.append({
            'timestamp': tick_data['timestamp'],
            'open': tick_data['price'],
            'high': tick_data['price'],
            'low': tick_data['price'],
            'close': tick_data['price'],
            'volume': 1  # Simplified volume for demonstration
        })
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame(self.history)
        if len(df) < max(self.macd_slow, self.ema_long, self.bb_period)*2:
            return {'action': 'HOLD', 'reason': 'Insufficient data'}
        
        # Calculate technical indicators
        df['rsi'] = self._calculate_rsi(df['close'], self.rsi_period)
        df['macd'], df['signal'] = self._calculate_macd(df['close'])
        df['upper_bb'], df['lower_bb'] = self._calculate_bollinger_bands(df)
        df['atr'] = self._calculate_atr(df)
        df['obv'] = self._calculate_obv(df)
        df['ema_short'] = df['close'].ewm(span=self.ema_short, adjust=False).mean()
        df['ema_long'] = df['close'].ewm(span=self.ema_long, adjust=False).mean()
        df['vwap'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
        
        current = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >=2 else current
        
        # Position management
        if self.position != "NONE":
            # Check exit conditions first
            exit_reason = None
            profit_pct = (current['close'] - self.entry_price)/self.entry_price if self.position == "LONG" \
                else (self.entry_price - current['close'])/self.entry_price
            
            # Check time-based exit
            if (tick_data['timestamp'] - self.entry_time) > self.max_hold_time:
                exit_reason = "Max holding time reached"
            elif profit_pct >= self.min_profit_pct:
                exit_reason = "Target profit achieved"
            elif current['rsi'] > 70 and self.position == "LONG":
                exit_reason = "Overbought RSI"
            elif current['rsi'] < 30 and self.position == "SHORT":
                exit_reason = "Oversold RSI"
            elif current['close'] < self.stop_loss and self.position == "LONG":
                exit_reason = "Stop loss triggered (LONG)"
            elif current['close'] > self.stop_loss and self.position == "SHORT":
                exit_reason = "Stop loss triggered (SHORT)"
            
            if exit_reason:
                self.position = "NONE"
                return {
                    'action': 'SELL' if self.position == "LONG" else 'BUY',
                    'reason': exit_reason
                }
        
        # Entry conditions
        entry_reason = []
        
        # Bullish conditions
        bullish_trend = current['ema_short'] > current['ema_long']
        bullish_macd = (current['macd'] > current['signal']) and (prev['macd'] <= prev['signal'])
        bullish_rsi = (current['rsi'] > 50) and (current['rsi'] < 70)
        bullish_volume = current['obv'] > (df['obv'].quantile(0.7))
        
        if all([bullish_trend, bullish_macd, bullish_rsi, bullish_volume]):
            entry_reason.append("Bullish convergence")
            
        # Bearish conditions
        bearish_trend = current['ema_short'] < current['ema_long']
        bearish_macd = (current['macd'] < current['signal']) and (prev['macd'] >= prev['signal'])
        bearish_rsi = (current['rsi'] < 50) and (current['rsi'] > 30)
        
        if all([bearish_trend, bearish_macd, bearish_rsi]):
            entry_reason.append("Bearish convergence")
            
        # Execute trade if conditions met
        if entry_reason and self.position == "NONE":
            action = 'BUY' if 'Bullish' in entry_reason[0] else 'SELL'
            self.position = 'LONG' if action == 'BUY' else 'SHORT'
            self.entry_price = current['close']
            self.entry_time = tick_data['timestamp']
            # Dynamic stop loss based on ATR
            self.stop_loss = current['close'] - 1.5*current['atr'] if action == 'BUY' \
                else current['close'] + 1.5*current['atr']
            return {
                'action': action,
                'reason': ", ".join(entry_reason)
            }
            
        return result