# --- HYPER Aggressive Scalper (Ultra High-Frequency) ---
# Trades on EVERY tiny price movement
# Almost no restrictions - trades constantly!

# Global state variables
_prices = []
_entry_price = None
_entry_tick = None
_position_type = None
_trade_count = 0
_window_size = 50
_last_trade_tick = -10  # Allow immediate first trade

def execute_trade(ticker, price, tick, cash_balance, shares_held):
    """
    HYPER Aggressive Scalper - Trades on ANY movement!
    
    - Trades every 2-3 ticks
    - Uses tiny RSI deviations from 50 as signals
    - Very tight stops: 0.1% profit, 0.15% loss
    """
    global _prices, _entry_price, _entry_tick, _position_type, _trade_count, _last_trade_tick
    
    _prices.append(price)
    
    # Limit history
    if len(_prices) > _window_size:
        _prices.pop(0)
    
    # Need minimal data - just 5 prices
    if len(_prices) < 5:
        return "HOLD"
    
    # Short cooldown - trade every 2 ticks minimum
    cooldown = 2
    if tick - _last_trade_tick < cooldown:
        return "HOLD"
    
    # Simple momentum: compare current price to 3-tick ago
    price_3_ago = _prices[-4] if len(_prices) >= 4 else _prices[0]
    momentum = ((price - price_3_ago) / price_3_ago) * 100
    
    # Simple RSI-like: count up vs down moves
    if len(_prices) >= 10:
        ups = sum(1 for i in range(1, 10) if _prices[-i] > _prices[-i-1])
        rsi_approx = ups * 10  # 0-90 range
    else:
        rsi_approx = 50
    
    # Handle existing position - VERY TIGHT stops
    if shares_held != 0 and _entry_price is not None:
        take_profit_pct = 0.001   # 0.1% profit target (tiny!)
        stop_loss_pct = 0.0015   # 0.15% stop loss
        max_hold = 10  # Max 10 ticks
        
        if shares_held > 0:  # Long
            pnl = (price - _entry_price) / _entry_price
            
            if pnl >= take_profit_pct:
                _entry_price = None
                _entry_tick = None
                _trade_count += 1
                _last_trade_tick = tick
                return ("SELL", shares_held)
            
            if pnl <= -stop_loss_pct:
                _entry_price = None
                _entry_tick = None
                _last_trade_tick = tick
                return ("SELL", shares_held)
            
            # Momentum reversal exit
            if momentum > 0.05:
                _entry_price = None
                _entry_tick = None
                _trade_count += 1
                _last_trade_tick = tick
                return ("SELL", shares_held)
            
            if tick - _entry_tick >= max_hold:
                _entry_price = None
                _entry_tick = None
                _last_trade_tick = tick
                return ("SELL", shares_held)
        
        else:  # Short
            pnl = (_entry_price - price) / _entry_price
            
            if pnl >= take_profit_pct:
                _entry_price = None
                _entry_tick = None
                _trade_count += 1
                _last_trade_tick = tick
                return ("BUY", abs(shares_held))
            
            if pnl <= -stop_loss_pct:
                _entry_price = None
                _entry_tick = None
                _last_trade_tick = tick
                return ("BUY", abs(shares_held))
            
            if momentum < -0.05:
                _entry_price = None
                _entry_tick = None
                _trade_count += 1
                _last_trade_tick = tick
                return ("BUY", abs(shares_held))
            
            if tick - _entry_tick >= max_hold:
                _entry_price = None
                _entry_tick = None
                _last_trade_tick = tick
                return ("BUY", abs(shares_held))
    
    # Entry logic - VERY EASY triggers
    if shares_held == 0:
        # BUY: Price dipped slightly OR RSI below 45
        if momentum < -0.01 or rsi_approx < 45:
            _entry_price = price
            _entry_tick = tick
            _position_type = 'long'
            _last_trade_tick = tick
            return ("BUY", 500)
        
        # SELL: Price spiked slightly OR RSI above 55
        if momentum > 0.01 or rsi_approx > 55:
            _entry_price = price
            _entry_tick = tick
            _position_type = 'short'
            _last_trade_tick = tick
            return ("SELL", 500)
    
    return "HOLD"
