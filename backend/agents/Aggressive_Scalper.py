# --- Aggressive Scalper (High-Frequency Mean Reversion) ---
# AGGRESSIVE VERSION: Wider RSI thresholds + momentum signals
# Trades frequently, aiming for small but consistent gains

# Global state variables
_prices = []
_entry_price = None
_entry_tick = None
_position_type = None
_trade_count = 0
_window_size = 100
_last_trade_tick = 0
_cooldown = 3  # Minimum ticks between trades

def calculate_sma(prices, period):
    """Simple Moving Average"""
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period

def calculate_rsi(prices, period=14):
    """Relative Strength Index with division safety"""
    if len(prices) < period + 1:
        return 50  # Neutral default
    gains, losses = [], []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        gains.append(max(0, change))
        losses.append(max(0, -change))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_momentum(prices, period=5):
    """Price momentum (rate of change)"""
    if len(prices) < period + 1:
        return 0
    old_price = prices[-period-1]
    if old_price == 0:
        return 0
    return ((prices[-1] - old_price) / old_price) * 100

def execute_trade(ticker, price, tick, cash_balance, shares_held):
    """
    AGGRESSIVE Scalper - High-Frequency Mean Reversion
    
    MUCH WIDER thresholds for frequent trading:
    - BUY when RSI < 45 (slightly oversold) OR momentum dip
    - SELL when RSI > 55 (slightly overbought) OR momentum spike
    
    Trades every few ticks, targeting small 0.1-0.3% moves.
    """
    global _prices, _entry_price, _entry_tick, _position_type, _trade_count, _last_trade_tick
    
    _prices.append(price)
    
    # Limit history
    if len(_prices) > _window_size:
        _prices.pop(0)
    
    # Need enough data
    if len(_prices) < 15:
        return "HOLD"
    
    # End-of-day liquidation
    if tick >= 375:
        if shares_held != 0:
            return ("BUY", abs(shares_held)) if shares_held < 0 else ("SELL", abs(shares_held))
        return "HOLD"
    
    # Calculate indicators
    rsi = calculate_rsi(_prices, 14)
    momentum = calculate_momentum(_prices, 5)
    sma_fast = calculate_sma(_prices, 5)
    sma_slow = calculate_sma(_prices, 20)
    
    # Price deviation from SMA
    sma_deviation = 0
    if sma_slow is not None and sma_slow != 0:
        sma_deviation = ((price - sma_slow) / sma_slow) * 100
    
    # AGGRESSIVE thresholds
    RSI_BUY = 45      # Buy when slightly oversold
    RSI_SELL = 55     # Sell when slightly overbought
    RSI_STRONG_BUY = 35
    RSI_STRONG_SELL = 65
    
    # Handle existing position - TIGHT stops for scalping
    if shares_held != 0 and _entry_price is not None:
        stop_loss_pct = 0.002   # 0.2% stop loss (tight!)
        take_profit_pct = 0.003  # 0.3% take profit (quick!)
        max_hold_ticks = 15     # Very quick trades
        
        if shares_held > 0:  # Long position
            pnl_pct = (price - _entry_price) / _entry_price
            
            # Quick profit taking
            if pnl_pct >= take_profit_pct:
                _entry_price = None
                _entry_tick = None
                _position_type = None
                _trade_count += 1
                _last_trade_tick = tick
                return ("SELL", shares_held)
            
            # Stop loss
            if pnl_pct <= -stop_loss_pct:
                _entry_price = None
                _entry_tick = None
                _position_type = None
                _last_trade_tick = tick
                return ("SELL", shares_held)
            
            # RSI reversal exit
            if rsi > RSI_SELL:
                _entry_price = None
                _entry_tick = None
                _position_type = None
                _trade_count += 1
                _last_trade_tick = tick
                return ("SELL", shares_held)
            
            # Time exit
            if tick >= _entry_tick + max_hold_ticks:
                _entry_price = None
                _entry_tick = None
                _position_type = None
                _last_trade_tick = tick
                return ("SELL", shares_held)
        
        elif shares_held < 0:  # Short position
            pnl_pct = (_entry_price - price) / _entry_price
            
            # Quick profit taking
            if pnl_pct >= take_profit_pct:
                _entry_price = None
                _entry_tick = None
                _position_type = None
                _trade_count += 1
                _last_trade_tick = tick
                return ("BUY", abs(shares_held))
            
            # Stop loss
            if pnl_pct <= -stop_loss_pct:
                _entry_price = None
                _entry_tick = None
                _position_type = None
                _last_trade_tick = tick
                return ("BUY", abs(shares_held))
            
            # RSI reversal exit
            if rsi < RSI_BUY:
                _entry_price = None
                _entry_tick = None
                _position_type = None
                _trade_count += 1
                _last_trade_tick = tick
                return ("BUY", abs(shares_held))
            
            # Time exit
            if tick >= _entry_tick + max_hold_ticks:
                _entry_price = None
                _entry_tick = None
                _position_type = None
                _last_trade_tick = tick
                return ("BUY", abs(shares_held))
    
    # Entry logic - AGGRESSIVE (frequent entries)
    if shares_held == 0:
        # Cooldown check - don't spam trades
        if tick - _last_trade_tick < _cooldown:
            return "HOLD"
        
        # LONG entries
        buy_signal = False
        
        # Signal 1: RSI oversold
        if rsi < RSI_BUY:
            buy_signal = True
        
        # Signal 2: Strong momentum dip (quick bounce expected)
        if momentum < -0.15:
            buy_signal = True
        
        # Signal 3: Price below fast SMA (mean reversion)
        if sma_fast is not None and price < sma_fast * 0.999:
            buy_signal = True
        
        # Signal 4: Price well below slow SMA
        if sma_deviation < -0.2:
            buy_signal = True
        
        if buy_signal:
            _entry_price = price
            _entry_tick = tick
            _position_type = 'long'
            _last_trade_tick = tick
            qty = 400 if rsi < RSI_STRONG_BUY else 300
            return ("BUY", qty)
        
        # SHORT entries
        sell_signal = False
        
        # Signal 1: RSI overbought
        if rsi > RSI_SELL:
            sell_signal = True
        
        # Signal 2: Strong momentum spike (pullback expected)
        if momentum > 0.15:
            sell_signal = True
        
        # Signal 3: Price above fast SMA
        if sma_fast is not None and price > sma_fast * 1.001:
            sell_signal = True
        
        # Signal 4: Price well above slow SMA
        if sma_deviation > 0.2:
            sell_signal = True
        
        if sell_signal:
            _entry_price = price
            _entry_tick = tick
            _position_type = 'short'
            _last_trade_tick = tick
            qty = 400 if rsi > RSI_STRONG_SELL else 300
            return ("SELL", qty)
    
    return "HOLD"
