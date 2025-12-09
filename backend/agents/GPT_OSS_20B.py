import pandas as pd
import numpy as np

class GPT_OSS_20B:
    def __init__(self):
        # Trading state
        self.history = []              # list of dicts with keys: timestamp, price
        self.position = "NONE"         # "LONG", "SHORT", "NONE"
        self.entry_price = 0.0
        self.entry_time = 0

        # Parameters
        self.sma_window = 20           # Simple Moving Average window
        self.threshold_pct = 0.005     # 0.5% deviation from SMA for entry
        self.stop_loss_pct = 0.015     # 1.5% stop loss
        self.take_profit_pct = 0.025   # 2.5% take profit

        # Max history size to keep memory bounded
        self.max_history = 200

    def _update_history(self, tick_data):
        """Append tick data to history and keep max size."""
        # Ensure required keys exist
        if 'price' not in tick_data or 'timestamp' not in tick_data:
            return  # Ignore incomplete data
        # Append in order of receipt
        self.history.append({'timestamp': tick_data['timestamp'], 'price': float(tick_data['price'])})
        if len(self.history) > self.max_history:
            # Remove oldest entries
            self.history = self.history[-self.max_history:]

    def _compute_sma(self, df):
        """Compute SMA for the given dataframe."""
        if len(df) < self.sma_window:
            return None
        return df['price'].rolling(window=self.sma_window).mean().iloc[-1]

    def trade(self, tick_data):
        """
        Process a new tick and return trading decision.

        Parameters
        ----------
        tick_data : dict
            Dictionary with keys 'price', 'symbol', 'timestamp'.

        Returns
        -------
        dict
            {'action': "BUY"|"SELL"|"HOLD", 'reason': str}
        """
        # Validate input
        if not isinstance(tick_data, dict):
            return {"action": "HOLD", "reason": "Invalid tick data format"}
        if 'price' not in tick_data or 'timestamp' not in tick_data:
            return {"action": "HOLD", "reason": "Missing price or timestamp"}

        current_price = float(tick_data['price'])
        current_timestamp = tick_data['timestamp']

        # Update history with latest tick
        self._update_history(tick_data)

        # Convert history to DataFrame for calculations
        if not self.history:
            return {"action": "HOLD", "reason": "No historical data"}

        df = pd.DataFrame(self.history)
        if df.empty:
            return {"action": "HOLD", "reason": "History dataframe empty"}

        sma = self._compute_sma(df)
        if sma is None:
            # Not enough data to compute SMA
            return {"action": "HOLD", "reason": f"Need at least {self.sma_window} data points for SMA"}

        # Position logic
        if self.position == "NONE":
            if current_price > sma * (1 + self.threshold_pct):
                self.position = "LONG"
                self.entry_price = current_price
                self.entry_time = current_timestamp
                return {
                    "action": "BUY",
                    "reason": f"Price {current_price:.2f} above SMA {sma:.2f} by {self.threshold_pct*100:.1f}% (Long entry)"
                }
            elif current_price < sma * (1 - self.threshold_pct):
                self.position = "SHORT"
                self.entry_price = current_price
                self.entry_time = current_timestamp
                return {
                    "action": "SELL",
                    "reason": f"Price {current_price:.2f} below SMA {sma:.2f} by {self.threshold_pct*100:.1f}% (Short entry)"
                }
            else:
                return {"action": "HOLD", "reason": "Price within SMA tolerance; no position"}

        elif self.position == "LONG":
            # Check exit conditions
            tp_price = self.entry_price * (1 + self.take_profit_pct)
            sl_price = self.entry_price * (1 - self.stop_loss_pct)
            if current_price >= tp_price:
                self.position = "NONE"
                return {
                    "action": "SELL",
                    "reason": f"Take profit reached at {current_price:.2f} (Target {tp_price:.2f})"
                }
            elif current_price <= sl_price:
                self.position = "NONE"
                return {
                    "action": "SELL",
                    "reason": f"Stop loss triggered at {current_price:.2f} (Stop {sl_price:.2f})"
                }
            else:
                return {"action": "HOLD", "reason": "Long position active"}

        elif self.position == "SHORT":
            # For short positions, profit is when price decreases
            tp_price = self.entry_price * (1 - self.take_profit_pct)
            sl_price = self.entry_price * (1 + self.stop_loss_pct)
            if current_price <= tp_price:
                self.position = "NONE"
                return {
                    "action": "BUY",
                    "reason": f"Take profit reached at {current_price:.2f} (Target {tp_price:.2f})"
                }
            elif current_price >= sl_price:
                self.position = "NONE"
                return {
                    "action": "BUY",
                    "reason": f"Stop loss triggered at {current_price:.2f} (Stop {sl_price:.2f})"
                }
            else:
                return {"action": "HOLD", "reason": "Short position active"}

        # Fallback
        return {"action": "HOLD", "reason": "Unhandled state"}
