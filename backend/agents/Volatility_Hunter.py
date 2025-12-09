# --- Volatility Hunter (Breakout Trader) ---
# Uses Bollinger Bands to identify volatility breakouts
# Buys on upper band breakout, Sells on lower band breakdown

# Global state variables
_prices = []
_entry_price = None
_entry_tick = None
_position_type = None
_trade_count = 0
_window_size = 100
_entry_middle_band = None

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """Bollinger Bands with safety check"""
    if len(prices) < period:
        return None, None, None
    sma = sum(prices[-period:]) / period
    variance = sum((p - sma) ** 2 for p in prices[-period:]) / period
    std = variance ** 0.5
    return sma - std_dev * std, sma, sma + std_dev * std

def calculate_bandwidth(lower, middle, upper):
    """Calculate Bollinger Band Width (volatility measure)"""
    if middle == 0 or middle is None:
        return None
    return ((upper - lower) / middle) * 100

def execute_trade(ticker, price, tick, cash_balance, shares_held):
    """
    Volatility Hunter - Bollinger Bands Breakout Strategy
    
    - BUY when price breaks ABOVE upper band (momentum breakout)
    - SELL when price breaks BELOW lower band (panic exit)
    - Also exits when price returns to middle band (momentum fading)
    
    Opportunistic sniper that thrives on explosive price movements.
    """
    global _prices, _entry_price, _entry_tick, _position_type, _trade_count
    global _entry_middle_band
    
    _prices.append(price)
    
    # Limit history to prevent memory leak
    if len(_prices) > _window_size:
        _prices.pop(0)
    
    # Need enough data for Bollinger Bands (period 20)
    if len(_prices) < 20:
        return "HOLD"
    
    # End-of-day liquidation
    if tick >= 375:
        if shares_held != 0:
            return ("BUY", abs(shares_held)) if shares_held < 0 else ("SELL", abs(shares_held))
        return "HOLD"
    
    # Calculate Bollinger Bands
    lower_band, middle_band, upper_band = calculate_bollinger_bands(_prices, 20, 2)
    
    if lower_band is None or middle_band is None or upper_band is None:
        return "HOLD"
    
    bandwidth = calculate_bandwidth(lower_band, middle_band, upper_band)
    
    # Handle existing position
    if shares_held != 0 and _entry_price is not None:
        # Breakout trades: wider stops but exit on momentum fade
        stop_loss_pct = 0.01   # 1% stop loss
        take_profit_pct = 0.02  # 2% take profit
        max_hold_ticks = 30    # Hold longer for momentum plays
        
        if shares_held > 0:  # Long position
            stop_price = _entry_price * (1 - stop_loss_pct)
            profit_price = _entry_price * (1 + take_profit_pct)
            
            # Breakdown Exit - price crashes below lower band (panic exit!)
            if price < lower_band:
                _entry_price = None
                _entry_tick = None
                _position_type = None
                _entry_middle_band = None
                return ("SELL", shares_held)
            
            # Momentum Fade Exit - price returns to middle band
            if price < middle_band:
                _entry_price = None
                _entry_tick = None
                _position_type = None
                _entry_middle_band = None
                _trade_count += 1
                return ("SELL", shares_held)
            
            # Stop loss
            if price <= stop_price:
                _entry_price = None
                _entry_tick = None
                _position_type = None
                _entry_middle_band = None
                return ("SELL", shares_held)
            
            # Take profit
            if price >= profit_price:
                _entry_price = None
                _entry_tick = None
                _position_type = None
                _entry_middle_band = None
                _trade_count += 1
                return ("SELL", shares_held)
            
            # Time-based exit
            if tick >= _entry_tick + max_hold_ticks:
                _entry_price = None
                _entry_tick = None
                _position_type = None
                _entry_middle_band = None
                return ("SELL", shares_held)
        
        elif shares_held < 0:  # Short position
            stop_price = _entry_price * (1 + stop_loss_pct)
            profit_price = _entry_price * (1 - take_profit_pct)
            
            # Breakout Up Exit - price breaks above upper band
            if price > upper_band:
                _entry_price = None
                _entry_tick = None
                _position_type = None
                _entry_middle_band = None
                return ("BUY", abs(shares_held))
            
            # Momentum Fade Exit - price returns to middle band
            if price > middle_band:
                _entry_price = None
                _entry_tick = None
                _position_type = None
                _entry_middle_band = None
                _trade_count += 1
                return ("BUY", abs(shares_held))
            
            # Stop loss
            if price >= stop_price:
                _entry_price = None
                _entry_tick = None
                _position_type = None
                _entry_middle_band = None
                return ("BUY", abs(shares_held))
            
            # Take profit
            if price <= profit_price:
                _entry_price = None
                _entry_tick = None
                _position_type = None
                _entry_middle_band = None
                _trade_count += 1
                return ("BUY", abs(shares_held))
            
            # Time-based exit
            if tick >= _entry_tick + max_hold_ticks:
                _entry_price = None
                _entry_tick = None
                _position_type = None
                _entry_middle_band = None
                return ("BUY", abs(shares_held))
    
    # Entry logic - only when flat
    if shares_held == 0:
        # Volume breakout UP - price breaks above upper band
        if price > upper_band:
            _entry_price = price
            _entry_tick = tick
            _position_type = 'long'
            _entry_middle_band = middle_band
            return ("BUY", 350)
        
        # Volume breakout DOWN - price breaks below lower band
        if price < lower_band:
            _entry_price = price
            _entry_tick = tick
            _position_type = 'short'
            _entry_middle_band = middle_band
            return ("SELL", 350)
    
    return "HOLD"
