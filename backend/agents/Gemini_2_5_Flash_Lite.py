# --- Generated Algorithm Code Below ---

# Global scalping state variables
_prices = []
_entry_price = None
_entry_tick = None
_position_type = None
_trade_count = 0
_window_size = 100 # Keep a reasonable history for indicators

# Constants for risk management
STOP_LOSS_PCT = 0.003  # 0.3%
TAKE_PROFIT_PCT = 0.005 # 0.5%
MAX_TICKS_PER_TRADE = 25
LEVERAGE = 2 # Simulate leverage effect for quantity calculation
TRADE_QUANTITY_BASE = 200 # Base quantity of shares/contracts

def calculate_sma(prices, period):
    """Simple Moving Average with safety check"""
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period

def calculate_ema(prices, period):
    """Exponential Moving Average with safety check"""
    if len(prices) < period:
        return None
    multiplier = 2 / (period + 1)
    # Calculate initial EMA more robustly if data is sparse at the start
    if len(prices) < period * 2: # Use a smaller portion if not enough to fill initial period reliably for EMA calc
        initial_period = max(1, len(prices) // 2)
        ema = sum(prices[:initial_period]) / initial_period
        for price in prices[initial_period:]:
            ema = (price - ema) * multiplier + ema
    else:
        ema = sum(prices[:period]) / period
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
    return ema

def calculate_rsi(prices, period=14):
    """Relative Strength Index with division safety"""
    if len(prices) < period + 1:
        return 50  # Neutral default
    gains, losses = [], []
    # Ensure we have enough data for the lookback period of RSI
    if len(prices) < period + 1:
        return 50 # Not enough data for meaningful RSI

    # Calculate price changes
    changes = [prices[i] - prices[i-1] for i in range(len(prices) - period -1, len(prices) - 1)]

    for change in changes:
        gains.append(max(0, change))
        losses.append(max(0, -change))

    # Check if we have any periods to average
    if not gains or not losses:
        return 50 # Neutral if no changes observed

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100  # All gains, no losses
    if avg_gain == 0:
        return 0 # All losses, no gains

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """Bollinger Bands with safety check"""
    if len(prices) < period:
        return None, None, None
    # Ensure enough data for standard deviation calculation
    if len(prices) < period * 2: # Use a more conservative check for STD
        return None, None, None

    relevant_prices = prices[-period:]
    sma = sum(relevant_prices) / period
    
    # Calculate variance safely
    variance_sum = sum((p - sma) ** 2 for p in relevant_prices)
    if period == 0: # Should not happen if len(prices) < period check is correct, but for absolute safety
        return None, None, None
    variance = variance_sum / period
    std = variance ** 0.5
    
    return sma - std_dev * std, sma, sma + std_dev * std

def execute_trade(ticker, price, tick, cash_balance, shares_held):
    """
    Main trading function called on each tick.
    
    Args:
        ticker: Symbol being traded
        price: Current price
        tick: Current tick number (0-389 for a trading day)
        cash_balance: Available cash
        shares_held: Current position (positive=long, negative=short, 0=flat)
    
    Returns:
        "HOLD" or ("BUY"|"SELL", quantity)
    """
    global _prices, _entry_price, _entry_tick, _position_type, _trade_count
    
    _prices.append(price)
    
    # Limit history to prevent memory leak
    if len(_prices) > _window_size:
        _prices.pop(0)
    
    # --- Indicator Calculations ---
    # Ensure we have enough data for all indicators
    min_data_for_indicators = 30 #rsi period (14) + a bit buffer for other calcs
    if len(_prices) < min_data_for_indicators:
        return "HOLD"

    sma_short = calculate_sma(_prices, 20)
    sma_long = calculate_sma(_prices, 50)
    ema = calculate_ema(_prices, 12)
    rsi = calculate_rsi(_prices, 14)
    bb_lower, bb_middle, bb_upper = calculate_bollinger_bands(_prices, 20, 2)

    # --- State Management and Exits ---
    
    # End-of-day liquidation (tick 375+)
    if tick >= 375:
        if shares_held != 0:
            # Safely determine liquidation order
            if shares_held > 0:
                return ("SELL", abs(shares_held))
            else:
                return ("BUY", abs(shares_held))
        return "HOLD"
        
    # Time-based exit for current position (stop holding for too long)
    if _entry_tick is not None and (tick - _entry_tick) >= MAX_TICKS_PER_TRADE:
        if shares_held > 0:
            return ("SELL", abs(shares_held))
        elif shares_held < 0:
            return ("BUY", abs(shares_held))
        # Reset state if position was closed due to time limit
        _entry_price = None
        _entry_tick = None
        _position_type = None

    # Stop-loss and Take-profit checks for open positions
    if shares_held != 0 and _entry_price is not None:
        # Long position exit logic
        if shares_held > 0:
            if price <= _entry_price * (1 - STOP_LOSS_PCT):
                return ("SELL", abs(shares_held))
            if price >= _entry_price * (1 + TAKE_PROFIT_PCT):
                return ("SELL", abs(shares_held))
        # Short position exit logic
        elif shares_held < 0:
            if price >= _entry_price * (1 + STOP_LOSS_PCT):
                return ("BUY", abs(shares_held))
            if price <= _entry_price * (1 - TAKE_PROFIT_PCT):
                return ("BUY", abs(shares_held))

    # --- Entry Logic ---
    
    # Calculate potential trade quantity with leverage
    # Ensure we have enough cash to cover margin requirements and trade size
    trade_quantity = int(TRADE_QUANTITY_BASE * LEVERAGE)
    # Further refine quantity based on available cash for this trade for safety
    # This is a simplified approach; real leverage involves margin accounts
    if cash_balance > 0:
        max_possible_quantity_based_on_cash = int(cash_balance / price) # With 1x leverage, cash is king
        trade_quantity = min(trade_quantity, max_possible_quantity_based_on_cash, TRADE_QUANTITY_BASE * 4) # Cap for safety
    else:
        # If no cash and holding short, we might still be able to manage
        if shares_held >= 0: # Only allow if not short and no cash
            return "HOLD"


    # If currently flat, look for entry signals
    if shares_held == 0:
        # Long Entry Signal: RSI oversold, price bouncing off lower Bollinger Band,
        # short SMA crossing above long SMA, EMA above shorter SMA
        if rsi is not None and bb_lower is not None and sma_short is not None and sma_long is not None and ema is not None:
            if rsi < 30 and price <= bb_lower and sma_short > sma_long and ema > sma_short:
                _entry_price = price
                _entry_tick = tick
                _position_type = "LONG"
                _trade_count += 1
                return ("BUY", trade_quantity)

        # Short Entry Signal: RSI overbought, price rejected from upper Bollinger Band,
        # short SMA crossing below long SMA, EMA below shorter SMA
        elif rsi is not None and bb_upper is not None and sma_short is not None and sma_long is not None and ema is not None:
            if rsi > 70 and price >= bb_upper and sma_short < sma_long and ema < sma_short:
                _entry_price = price
                _entry_tick = tick
                _position_type = "SHORT"
                _trade_count += 1
                return ("SELL", trade_quantity)
                
    return "HOLD"