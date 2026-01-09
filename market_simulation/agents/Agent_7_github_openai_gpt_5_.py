# --- Generated Algorithm Code Below ---
import numpy as np
import pandas as pd

# Global state
_last_trade_tick = 0
_entry_price = {}
_atr_stop = {}

def execute_strategy(market_data, tick, cash_balance, portfolio):
    '''
    "The Breakout Predator" (Volatility)
    Strategy: Catching explosive moves on high volume breakouts using Donchian Channels.
    - Buy: Price > 20-period High AND Volume > 1.5x Avg
    - Sell: Price < 20-period Low AND Volume > 1.5x Avg
    - Exit: ATR-based Trailing Stop
    '''
    global _last_trade_tick, _entry_price, _atr_stop
    
    symbols = ['BTC', 'ETH', 'SOL']
    
    # Cooldown (Breakouts happen fast, check often but ensure no rapid churn)
    if tick - _last_trade_tick < 10:
        return ("HOLD", None, 0)
    
    for sym in symbols:
        data = market_data.get(sym, {})
        if not data: continue
        
        history = data.get('history', [])
        volumes = data.get('volumes', [])
        
        if len(history) < 25 or len(volumes) < 25: continue
        
        prices = pd.Series(history)
        vols = pd.Series(volumes)
        current_price = prices.iloc[-1]
        current_vol = vols.iloc[-1]
        
        # --- CALCULATE INDICATORS ---
        
        # 1. Donchian Channels (20)
        # We look at the High/Low of the PREVIOUS 20 candles to define the "Range"
        # We breakout if CURRENT price > that Range High
        recent_prices = prices.iloc[-21:-1] # Exclude current candle for valid breakout check
        range_high = recent_prices.max()
        range_low = recent_prices.min()
        
        # 2. Volume Multiplier
        avg_vol = vols.iloc[-21:-1].mean()
        vol_spike = current_vol > (1.2 * avg_vol) # 1.2x spike factor
        
        # 3. ATR (Average True Range) for Stops
        # Simple approximation: Mean of Abs Differences
        tr = prices.diff().abs().rolling(window=14).mean().iloc[-1]
        if pd.isna(tr) or tr == 0: tr = current_price * 0.01 # Fallback 1%
        
        # Check Position
        qty = portfolio.get(sym, 0)
        
        # --- EXIT LOGIC (ATR Trailing) ---
        if qty != 0:
            qty_abs = abs(qty)
            entry = _entry_price.get(sym, current_price)
            stop_level = _atr_stop.get(sym, 0)
            
            # Long Exit
            if qty > 0:
                # Update Trailing Stop: Move UP if price moves UP (Stop = High - 2*ATR)
                # We use specific High watermark tracking effectively:
                new_stop = current_price - (2 * tr)
                if new_stop > stop_level:
                    _atr_stop[sym] = new_stop
                    stop_level = new_stop
                    
                if current_price < stop_level:
                    _entry_price.pop(sym, None)
                    _atr_stop.pop(sym, None)
                    _last_trade_tick = tick
                    return ("SELL", sym, qty_abs)
            
            # Short Exit
            if qty < 0:
                # Update Trailing Stop: Move DOWN if price moves DOWN (Stop = Low + 2*ATR)
                new_stop = current_price + (2 * tr)
                if stop_level == 0 or new_stop < stop_level:
                    _atr_stop[sym] = new_stop
                    stop_level = new_stop
                    
                if current_price > stop_level:
                    _entry_price.pop(sym, None)
                    _atr_stop.pop(sym, None)
                    _last_trade_tick = tick
                    return ("BUY", sym, qty_abs)
        
        # --- ENTRY LOGIC ---
        else:
            # Bullish Breakout
            if current_price > range_high and vol_spike:
                qty = (cash_balance * 0.25) / current_price
                _entry_price[sym] = current_price
                _atr_stop[sym] = current_price - (2 * tr) # Initial Stop
                _last_trade_tick = tick
                return ("BUY", sym, qty)
            
            # Bearish Breakout
            if current_price < range_low and vol_spike:
                qty = (cash_balance * 0.25) / current_price
                _entry_price[sym] = current_price
                _atr_stop[sym] = current_price + (2 * tr) # Initial Stop
                _last_trade_tick = tick
                return ("SELL", sym, qty)

    return ("HOLD", None, 0)