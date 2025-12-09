# --- Conservative Captain (Trend Follower) ---
# Uses EMA Golden Cross / Death Cross strategy
# Buys on Golden Cross (short EMA > long EMA), Sells on Death Cross

# Global state variables
_prices = []
_entry_price = None
_entry_tick = None
_position_type = None
_trade_count = 0
_window_size = 100
_prev_short_ema = None
_prev_long_ema = None

def calculate_ema(prices, period):
    """Exponential Moving Average with safety check"""
    if len(prices) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    return ema

def execute_trade(ticker, price, tick, cash_balance, shares_held):
    """
    Conservative Captain - Trend Following EMA Strategy
    
    - BUY on Golden Cross: Short EMA crosses ABOVE Long EMA
    - SELL on Death Cross: Short EMA crosses BELOW Long EMA
    """
    global _prices, _entry_price, _entry_tick, _position_type, _trade_count
    global _prev_short_ema, _prev_long_ema
    
    _prices.append(price)
    
    # Limit history to prevent memory leak
    if len(_prices) > _window_size:
        _prices.pop(0)
    
    # Need enough data for EMA 26
    if len(_prices) < 26:
        return "HOLD"
    
    # End-of-day liquidation
    if tick >= 375:
        if shares_held != 0:
            return ("BUY", abs(shares_held)) if shares_held < 0 else ("SELL", abs(shares_held))
        return "HOLD"
    
    # Calculate EMAs
    short_ema = calculate_ema(_prices, 12)
    long_ema = calculate_ema(_prices, 26)
    
    if short_ema is None or long_ema is None:
        return "HOLD"
    
    # Initialize previous EMAs on first calculation
    if _prev_short_ema is None or _prev_long_ema is None:
        _prev_short_ema = short_ema
        _prev_long_ema = long_ema
        return "HOLD"
    
    # Detect Golden Cross: Short EMA crosses ABOVE Long EMA
    golden_cross = (_prev_short_ema <= _prev_long_ema) and (short_ema > long_ema)
    
    # Detect Death Cross: Short EMA crosses BELOW Long EMA
    death_cross = (_prev_short_ema >= _prev_long_ema) and (short_ema < long_ema)
    
    # Update previous values for next tick
    _prev_short_ema = short_ema
    _prev_long_ema = long_ema
    
    # Handle existing position
    if shares_held != 0 and _entry_price is not None:
        # Stop loss: -1.5%
        stop_loss_pct = 0.015
        # Take profit: +2%
        take_profit_pct = 0.02
        # Max hold: 50 ticks (trend trades hold longer)
        max_hold_ticks = 50
        
        if shares_held > 0:  # Long position
            stop_price = _entry_price * (1 - stop_loss_pct)
            profit_price = _entry_price * (1 + take_profit_pct)
            
            # Death Cross Exit (main signal)
            if death_cross:
                _entry_price = None
                _entry_tick = None
                _position_type = None
                _trade_count += 1
                return ("SELL", shares_held)
            
            # Stop loss
            if price <= stop_price:
                _entry_price = None
                _entry_tick = None
                _position_type = None
                return ("SELL", shares_held)
            
            # Take profit
            if price >= profit_price:
                _entry_price = None
                _entry_tick = None
                _position_type = None
                _trade_count += 1
                return ("SELL", shares_held)
            
            # Time-based exit
            if tick >= _entry_tick + max_hold_ticks:
                _entry_price = None
                _entry_tick = None
                _position_type = None
                return ("SELL", shares_held)
    
    # Entry logic - only when flat
    if shares_held == 0:
        # Golden Cross - BUY signal
        if golden_cross:
            _entry_price = price
            _entry_tick = tick
            _position_type = 'long'
            return ("BUY", 300)
    
    return "HOLD"
