# --- Generated Algorithm Code Below ---
import numpy as np
import pandas as pd

# Global state
_last_trade_tick = 0
_entry_price = {}

def execute_strategy(market_data, tick, cash_balance, portfolio):
    '''
    "The Scalper" (Mean Reversion)
    Strategy: Profiting from overextended price moves using Bollinger Bands and RSI.
    - Buy when Price < Lower Band AND RSI < 30 (Oversold)
    - Sell when Price > Upper Band AND RSI > 70 (Overbought)
    - Symbols: BTC, ETH, SOL
    '''
    global _last_trade_tick, _entry_price
    
    symbols = ['BTC', 'ETH', 'SOL']
    
    # Cooldown: Wait 20 ticks (short scalping window)
    if tick - _last_trade_tick < 20:
        return ("HOLD", None, 0)
    
    best_sym = None
    best_signal = 0 # 1 for Buy, -1 for Sell
    
    for sym in symbols:
        data = market_data.get(sym, {})
        if not data: continue
        
        # Get History
        history = data.get('history', [])
        if len(history) < 20: continue
        
        prices = pd.Series(history)
        
        # --- CALCULATE INDICATORS ---
        
        # 1. Bollinger Bands (20, 2)
        sma = prices.rolling(window=20).mean()
        std = prices.rolling(window=20).std()
        upper_band = sma + (2 * std)
        lower_band = sma - (2 * std)
        
        current_price = prices.iloc[-1]
        cur_upper = upper_band.iloc[-1]
        cur_lower = lower_band.iloc[-1]
        
        # 2. RSI (14)
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, 1) # Safety
        rsi = 100 - (100 / (1 + rs))
        cur_rsi = rsi.iloc[-1]
        
        # --- SIGNAL LOGIC ---
        
        # ENTRY LONG: Price below Lower Band + RSI < 30
        if current_price < cur_lower and cur_rsi < 30:
            if portfolio.get(sym, 0) == 0: # Only if flat
                best_sym = sym
                best_signal = 1
                
        # ENTRY SHORT (or Exit Long): Price above Upper Band + RSI > 70
        elif current_price > cur_upper and cur_rsi > 70:
             if portfolio.get(sym, 0) == 0:
                 best_sym = sym
                 best_signal = -1
    
    # EXECUTE ENTRY
    if best_sym:
        price = market_data[best_sym].get('price', 0)
        if price > 0:
            if best_signal == 1:
                # Buy
                qty = (cash_balance * 0.30) / price # Aggressive sizing for scalps
                _entry_price[best_sym] = price
                _last_trade_tick = tick
                return ("BUY", best_sym, qty)
            elif best_signal == -1:
                # Short
                qty = (cash_balance * 0.30) / price
                _entry_price[best_sym] = price
                _last_trade_tick = tick
                return ("SELL", best_sym, qty)

    # EXIT MANAGEMENT (TP/SL) check for existing positions
    for sym in symbols:
        qty = portfolio.get(sym, 0)
        if qty == 0: continue
        
        current_price = market_data.get(sym, {}).get('price', 0)
        entry = _entry_price.get(sym, current_price)
        if current_price <= 0 or entry <= 0: continue
        
        # Recalculate Bands (Simplified for exit check speed)
        # Ideally we reuse valid calcs, but for safety we check simple PnL or Band reversion
        
        pnl_pct = (current_price / entry) - 1.0 if qty > 0 else (entry / current_price) - 1.0
        
        # SCALP TARGETS
        # Take Profit: Quick 0.5%
        if pnl_pct > 0.005:
            _entry_price.pop(sym, None)
            _last_trade_tick = tick
            action = "SELL" if qty > 0 else "BUY"
            return (action, sym, abs(qty))
            
        # Stop Loss: Tight 1%
        if pnl_pct < -0.01:
            _entry_price.pop(sym, None)
            _last_trade_tick = tick
            action = "SELL" if qty > 0 else "BUY"
            return (action, sym, abs(qty))
            
    return ("HOLD", None, 0)