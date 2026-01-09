# --- Generated Algorithm Code Below ---
import numpy as np
import pandas as pd

# Use agent_state for persistence - NO global variables!
_last_trade_tick = 0  # Only this is safe as a global (just a counter)

def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    '''
    Institutional-grade algo with State Persistence and Fee Awareness.
    agent_state provides entry_prices and current_pnl - USE THESE!
    '''
    global _last_trade_tick

    # Handle backward compatibility
    if agent_state is None:
        agent_state = {'entry_prices': {}, 'current_pnl': {}, 'custom': {}}
    
    # Initialize custom state for peak/trough tracking
    if 'custom' not in agent_state:
        agent_state['custom'] = {}
    if 'peak_prices' not in agent_state['custom']:
        agent_state['custom']['peak_prices'] = {}
    if 'trough_prices' not in agent_state['custom']:
        agent_state['custom']['trough_prices'] = {}

    symbols = ['BTC', 'ETH', 'SOL']

    # Cooldown
    if tick - _last_trade_tick < 60:
        return ("HOLD", None, 0)

    # 1. EXIT LOGIC - Enhanced with Trailing Stop
    for sym in symbols:
        qty = portfolio.get(sym, 0)
        if qty == 0: continue

        current_price = market_data.get(sym, {}).get('price', 0)
        if current_price == 0: continue

        # Update peak/trough prices and check trailing stops
        if qty > 0:  # Long position
            if sym in agent_state['custom']['peak_prices']:
                peak_price = agent_state['custom']['peak_prices'][sym]
                # Update peak if new high reached
                if current_price > peak_price:
                    agent_state['custom']['peak_prices'][sym] = current_price
                    peak_price = current_price
                # Trailing stop: exit if price drops 2% from peak
                if current_price < peak_price * 0.98:
                    _last_trade_tick = tick
                    # Clean up state
                    agent_state['custom']['peak_prices'].pop(sym, None)
                    agent_state['custom']['trough_prices'].pop(sym, None)
                    return ("SELL", sym, abs(qty))
        else:  # Short position (qty < 0)
            if sym in agent_state['custom']['trough_prices']:
                trough_price = agent_state['custom']['trough_prices'][sym]
                # Update trough if new low reached
                if current_price < trough_price:
                    agent_state['custom']['trough_prices'][sym] = current_price
                    trough_price = current_price
                # Trailing stop for shorts: exit if price rises 2% from trough
                if current_price > trough_price * 1.02:
                    _last_trade_tick = tick
                    # Clean up state
                    agent_state['custom']['peak_prices'].pop(sym, None)
                    agent_state['custom']['trough_prices'].pop(sym, None)
                    return ("BUY", sym, abs(qty))

        # Traditional PnL-based exits (after trailing stop check)
        pnl_info = agent_state.get('current_pnl', {}).get(sym, {})
        pnl_pct = pnl_info.get('pnl_percent', 0) / 100.0  # Convert from % to decimal

        # TAKE PROFIT (0.50% target to beat 0.20% costs)
        if pnl_pct > 0.005:
            _last_trade_tick = tick
            # Clean up state
            agent_state['custom']['peak_prices'].pop(sym, None)
            agent_state['custom']['trough_prices'].pop(sym, None)
            action = "SELL" if qty > 0 else "BUY"
            return (action, sym, abs(qty))

        # STOP LOSS (-0.30%)
        if pnl_pct < -0.003:
            _last_trade_tick = tick
            # Clean up state
            agent_state['custom']['peak_prices'].pop(sym, None)
            agent_state['custom']['trough_prices'].pop(sym, None)
            action = "SELL" if qty > 0 else "BUY"
            return (action, sym, abs(qty))

    # 2. ENTRY LOGIC - Find best opportunity with volume filter
    best_sym = None
    best_score = 0

    for sym in symbols:
        if portfolio.get(sym, 0) != 0: continue  # Already in position

        data = market_data.get(sym, {})
        if not data: continue

        price = data.get('price', 0)
        if price == 0: continue

        # Volume Spike Filter (1.5x rolling average)
        volumes = data.get('volumes', [])
        current_volume = data.get('volume', 0)
        volume_spike = False
        
        if len(volumes) >= 20 and current_volume > 0:
            rolling_avg_volume = np.mean(volumes[-20:])
            if rolling_avg_volume > 0:
                volume_spike = current_volume > (rolling_avg_volume * 1.5)

        if not volume_spike:
            continue  # Skip if no volume spike

        # Get signals
        obi = data.get('obi_weighted', 0)
        ofi = data.get('ofi', 0)
        sentiment = data.get('sentiment', 0)
        micro_price = data.get('micro_price', price)
        
        # Fair Value Gap (Stoikov)
        fair_value_gap = (micro_price - price) / price if price != 0 else 0

        # Enhanced scoring system
        score = 0
        
        # Microstructure signals (DeepLOB physics)
        if obi > 0.1: score += 1    # Strong bid support
        if obi < -0.1: score -= 1   # Strong ask pressure
        
        # Order flow signals
        if ofi > 10: score += 1     # Net aggressive buying
        if ofi < -10: score -= 1    # Net aggressive selling
        
        # NLP sentiment signals
        if sentiment > 0.2: score += 1  # Positive sentiment
        if sentiment < -0.2: score -= 1 # Negative sentiment
        
        # Fair value gap (Stoikov alpha)
        if fair_value_gap > 0.001: score += 1  # Market undervalued
        if fair_value_gap < -0.001: score -= 1 # Market overvalued
        
        # Volume spike confidence boost
        if volume_spike:
            if score > 0: score += 0.5  # Extra confidence for long
            if score < 0: score -= 0.5  # Extra confidence for short

        if abs(score) > abs(best_score):
            best_score = score
            best_sym = sym

    # Execute trade if score threshold met
    if best_sym and abs(best_score) >= 2:
        price = market_data[best_sym]['price']
        qty = (cash_balance * 0.20) / price  # 20% risk per trade

        _last_trade_tick = tick
        
        # Initialize peak/trough tracking for new position
        if best_score > 0:  # Long entry
            agent_state['custom']['peak_prices'][best_sym] = price
            agent_state['custom']['trough_prices'].pop(best_sym, None)  # Clean up short tracking
            return ("BUY", best_sym, qty)
        else:  # Short entry (SELL to open)
            agent_state['custom']['trough_prices'][best_sym] = price
            agent_state['custom']['peak_prices'].pop(best_sym, None)  # Clean up long tracking
            return ("SELL", best_sym, qty)  # Short Sell

    return ("HOLD", None, 0)