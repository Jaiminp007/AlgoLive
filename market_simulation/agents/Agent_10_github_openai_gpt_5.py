# --- Generated Algorithm Code Below ---
import numpy as np
import pandas as pd

# Global state
_last_trade_tick = 0
_entry_price = {}
_trailing_stop = {}

def execute_strategy(market_data, tick, cash_balance, portfolio):
    '''
    "The Trend Hunter" (Momentum)
    Strategy: Riding established trends using MACD and EMA 50.
    - Buy: Price > EMA 50 AND MACD > Signal (Bullish)
    - Sell: Price < EMA 50 AND MACD < Signal (Bearish)
    - Exit: Trend Reversal or Trailing Stop
    '''
    global _last_trade_tick, _entry_price, _trailing_stop
    
    symbols = ['BTC', 'ETH', 'SOL']
    
    # Cooldown (Trend strategy is slower, wait 60 ticks)
    if tick - _last_trade_tick < 60:
        return ("HOLD", None, 0)
    
    for sym in symbols:
        data = market_data.get(sym, {})
        if not data: continue
        
        history = data.get('history', [])
        # Need adequate history for EMA 50
        if len(history) < 55: continue
        
        prices = pd.Series(history)
        current_price = prices.iloc[-1]
        
        # --- CALCULATE INDICATORS ---
        
        # 1. EMA 50 (Trend Filter)
        ema50 = prices.ewm(span=50, adjust=False).mean().iloc[-1]
        
        # 2. MACD (12, 26, 9)
        ema12 = prices.ewm(span=12, adjust=False).mean()
        ema26 = prices.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        
        cur_macd = macd.iloc[-1]
        cur_signal = signal.iloc[-1]
        
        # Check current position
        qty = portfolio.get(sym, 0)
        
        # --- EXIT LOGIC (Trailing Stop & Reversal) ---
        if qty != 0:
            # Trailing Stop Update
            start_price = _entry_price.get(sym, current_price)
            if qty > 0: # LONG
                stop_price = _trailing_stop.get(sym, start_price * 0.98) # Start 2% risk
                # Trail up: If price moves up, move stop to 2% below high watermark
                if current_price > start_price:
                    new_stop = current_price * 0.98
                    if new_stop > stop_price:
                        _trailing_stop[sym] = new_stop
                
                # Check Stop Hit OR Reversal Signal (MACD Cross Under)
                if current_price < _trailing_stop.get(sym, 0) or (cur_macd < cur_signal):
                    _entry_price.pop(sym, None)
                    _trailing_stop.pop(sym, None)
                    _last_trade_tick = tick
                    return ("SELL", sym, abs(qty))
                    
            elif qty < 0: # SHORT
                stop_price = _trailing_stop.get(sym, start_price * 1.02)
                # Trail down
                if current_price < start_price:
                    new_stop = current_price * 1.02
                    if new_stop < stop_price:
                        _trailing_stop[sym] = new_stop
                
                # Check Stop Hit OR Reversal Signal (MACD Cross Over)
                if current_price > _trailing_stop.get(sym, float('inf')) or (cur_macd > cur_signal):
                    _entry_price.pop(sym, None)
                    _trailing_stop.pop(sym, None)
                    _last_trade_tick = tick
                    return ("BUY", sym, abs(qty))
        
        # --- ENTRY LOGIC ---
        else: # No position
            # Bullish Trend Entry
            if current_price > ema50 and cur_macd > cur_signal:
                qty = (cash_balance * 0.25) / current_price
                _entry_price[sym] = current_price
                _trailing_stop[sym] = current_price * 0.98 # Initial Stop
                _last_trade_tick = tick
                return ("BUY", sym, qty)
            
            # Bearish Trend Entry
            elif current_price < ema50 and cur_macd < cur_signal:
                qty = (cash_balance * 0.25) / current_price
                _entry_price[sym] = current_price
                _trailing_stop[sym] = current_price * 1.02 # Initial Stop
                _last_trade_tick = tick
                return ("SELL", sym, qty)

    return ("HOLD", None, 0)