# --- Generated Algorithm Code Below ---
import numpy as np
import pandas as pd
from collections import deque

# Global state tracking (only safe globals are counters and time references)
_last_trade_tick = 0
_position_states = {}  # Track peak prices for trailing stops
_trailing_stops = {}   # Store trailing stop levels

def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    '''
    Institutional-grade algo with State Persistence, Fee Awareness, and Trailing Stops.
    Combines DeepLOB (OBI), Stoikov (Micro Price), and NLP (Sentiment) signals.
    '''
    global _last_trade_tick, _position_states, _trailing_stops

    # Handle backward compatibility
    if agent_state is None:
        agent_state = {'entry_prices': {}, 'current_pnl': {}, 'custom': {}}

    symbols = ['BTC', 'ETH', 'SOL']

    # Cooldown logic (60 ticks)
    if tick - _last_trade_tick < 60:
        return ("HOLD", None, 0)

    # 1. POSITION MANAGEMENT & EXIT LOGIC
    for sym in symbols:
        current_qty = portfolio.get(sym, 0)
        if current_qty == 0:
            # Clear position state if no position
            _position_states.pop(sym, None)
            _trailing_stops.pop(sym, None)
            continue

        data = market_data.get(sym, {})
        if not data: continue

        current_price = data['price']
        entry_price = agent_state['entry_prices'].get(sym, current_price)
        
        # Calculate PnL (in decimal form)
        pnl_pct = agent_state['current_pnl'].get(sym, {}).get('pnl_percent', 0) / 100.0

        # Initialize position state on first tick in position
        if sym not in _position_states:
            _position_states[sym] = {
                'peak_price': current_price,
                'entry_tick': tick,
                'is_long': current_qty > 0
            }
        
        # Update peak price for trailing stop
        if current_qty > 0:  # Long position
            _position_states[sym]['peak_price'] = max(_position_states[sym]['peak_price'], current_price)
        else:  # Short position
            _position_states[sym]['peak_price'] = min(_position_states[sym]['peak_price'], current_price)

        # 1A. TRAILING STOP (2% from peak)
        peak_price = _position_states[sym]['peak_price']
        if current_qty > 0 and (peak_price - current_price) / peak_price >= 0.02:
            # Long trailing stop hit
            _last_trade_tick = tick
            return ("SELL", sym, abs(current_qty))
        elif current_qty < 0 and (current_price - peak_price) / peak_price >= 0.02:
            # Short trailing stop hit
            _last_trade_tick = tick
            return ("BUY", sym, abs(current_qty))

        # 1B. STOP-LOSS (-0.30% from entry)
        if pnl_pct < -0.003:
            _last_trade_tick = tick
            action = "SELL" if current_qty > 0 else "BUY"
            return (action, sym, abs(current_qty))

        # 1C. TAKE PROFIT (0.50% minimum to beat costs)
        if pnl_pct > 0.005:
            _last_trade_tick = tick
            action = "SELL" if current_qty > 0 else "BUY"
            return (action, sym, abs(current_qty))

    # 2. ENTRY LOGIC - Signal Fusion & Volume Filter
    best_sym = None
    best_score = 0
    best_direction = 0

    for sym in symbols:
        if portfolio.get(sym, 0) != 0: continue  # Already in position

        data = market_data.get(sym, {})
        if not data: continue

        # Required signal components
        obi = data.get('obi_weighted', 0)
        ofi = data.get('ofi', 0)
        sentiment = data.get('sentiment', 0)
        micro_price = data.get('micro_price', data.get('price', 0))
        price = data.get('price', 0)
        volumes = data.get('volumes', [])
        
        # Skip if insufficient volume data
        if len(volumes) < 20: continue

        # 2A. Volume Spike Filter (1.5x rolling average)
        recent_vol = data.get('volume', 0)
        avg_volume = np.mean(volumes[-20:])
        volume_spike = recent_vol > (1.5 * avg_volume)

        if not volume_spike: continue

        # 2B. Fair Value Gap (Micro Price vs Current Price)
        fvg = (micro_price - price) / price  # Percentage difference

        # 2C. Signal Scoring
        score = 0
        
        # OBI Signal
        if obi > 0.1: score += 1
        elif obi < -0.1: score -= 1
        
        # OFI Signal
        if ofi > 10: score += 1
        elif ofi < -10: score -= 1
        
        # Sentiment Signal
        if sentiment > 0.2: score += 1
        elif sentiment < -0.2: score -= 1
        
        # Fair Value Gap Signal (Micro Price > Price = Bullish)
        if fvg > 0.002: score += 1  # 0.2% undervaluation
        elif fvg < -0.002: score -= 1  # 0.2% overvaluation

        # 2D. Advanced Microstructure Filters
        taker_ratio = data.get('taker_ratio', 1.0)
        cvd_divergence = data.get('cvd_divergence', 0)
        
        if taker_ratio > 1.2: score += 0.5  # Aggressive buying pressure
        if taker_ratio < 0.8: score -= 0.5  # Aggressive selling pressure
        
        if cvd_divergence < -0.3: score -= 0.5  # Potential reversal signal
        if cvd_divergence > 0.3: score += 0.5  # Momentum confirmation

        # 2E. Determine Direction (Long vs Short)
        direction = 1 if score > 0 else -1 if score < 0 else 0

        # 2F. Entry Threshold (Score >= 2 for Long, <= -2 for Short)
        if abs(score) >= 2:
            if abs(score) > abs(best_score):
                best_score = score
                best_sym = sym
                best_direction = direction

    # 3. Execute Entry
    if best_sym:
        price = market_data[best_sym]['price']
        
        # Position sizing (20% of cash)
        qty = (cash_balance * 0.20) / price
        
        _last_trade_tick = tick
        
        # Record entry price
        agent_state['entry_prices'][best_sym] = price
        
        if best_direction > 0:
            return ("BUY", best_sym, qty)
        else:
            return ("SELL", best_sym, qty)  # Short Sell

    return ("HOLD", None, 0)