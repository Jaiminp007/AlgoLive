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

    # Handle backward compatibility and ensure structure
    if agent_state is None:
        agent_state = {'entry_prices': {}, 'current_pnl': {}, 'custom': {}}
    if 'custom' not in agent_state:
        agent_state['custom'] = {}

    symbols = ['BTC', 'ETH', 'SOL']

    # Cooldown
    if tick - _last_trade_tick < 60:
        return ("HOLD", None, 0)

    # 1. EXIT LOGIC - Use agent_state['current_pnl'] for reliable PnL tracking
    for sym in symbols:
        qty = portfolio.get(sym, 0)
        if qty == 0:
            # Clean up custom state if flat
            if sym in agent_state['custom']:
                del agent_state['custom'][sym]
            continue

        data = market_data.get(sym, {})
        if not data: continue
        
        price = data.get('price', 0)
        pnl_info = agent_state.get('current_pnl', {}).get(sym, {})
        # pnl_percent is stored as e.g. 0.35 for 0.35%
        pnl_pct = pnl_info.get('pnl_percent', 0) / 100.0 

        # Initialize or update Peak Price for Trailing Stop
        if sym not in agent_state['custom']:
            agent_state['custom'][sym] = {'peak_price': price}
        
        # --- TRAILING STOP LOGIC (2% from peak) ---
        if qty > 0: # Long Position
            if price > agent_state['custom'][sym]['peak_price']:
                agent_state['custom'][sym]['peak_price'] = price
            
            # Exit if price drops 2% from peak
            if price < agent_state['custom'][sym]['peak_price'] * 0.98:
                _last_trade_tick = tick
                return ("SELL", sym, abs(qty))
        
        else: # Short Position
            if price < agent_state['custom'][sym]['peak_price']:
                agent_state['custom'][sym]['peak_price'] = price
            
            # Exit if price rises 2% from peak
            if price > agent_state['custom'][sym]['peak_price'] * 1.02:
                _last_trade_tick = tick
                return ("BUY", sym, abs(qty))

        # --- HARD STOP LOSS (-0.30%) ---
        if pnl_pct < -0.003:
            _last_trade_tick = tick
            action = "SELL" if qty > 0 else "BUY"
            return (action, sym, abs(qty))

        # --- TAKE PROFIT (0.50% target to beat 0.20% costs) ---
        if pnl_pct > 0.005:
            _last_trade_tick = tick
            action = "SELL" if qty > 0 else "BUY"
            return (action, sym, abs(qty))

    # 2. ENTRY LOGIC - Find best opportunity
    best_sym = None
    best_score = 0

    for sym in symbols:
        if portfolio.get(sym, 0) != 0: continue  # Already in position

        data = market_data.get(sym, {})
        if not data: continue

        # --- VOLUME SPIKE FILTER ---
        # Only enter if Volume > 1.5x Rolling Average
        volumes = data.get('volumes', [])
        if len(volumes) < 10: continue
        vol_avg = np.mean(volumes)
        if data.get('volume', 0) <= 1.5 * vol_avg:
            continue

        obi = data.get('obi_weighted', 0)
        ofi = data.get('ofi', 0)
        sentiment = data.get('sentiment', 0)
        micro_price = data.get('micro_price', 0)
        price = data.get('price', 0)

        score = 0
        
        # DeepLOB Signal (Order Book Imbalance)
        if obi > 0.1: score += 1
        elif obi < -0.1: score -= 1

        # Order Flow Imbalance (OFI)
        if ofi > 10: score += 1
        elif ofi < -10: score -= 1

        # Semantic Alpha (Sentiment)
        if sentiment > 0.2: score += 1
        elif sentiment < -0.2: score -= 1

        # Fair Value Gap (Stoikov Micro-Price vs Market Price)
        # Trade towards Micro-price (Gap > 0.1%)
        gap_pct = (micro_price - price) / price
        if gap_pct > 0.001: score += 1
        elif gap_pct < -0.001: score -= 1

        if abs(score) > abs(best_score):
            best_score = score
            best_sym = sym

    # Execute Entry if Score Threshold Met (Score >= 2 or <= -2)
    if best_sym and abs(best_score) >= 2:
        price = market_data[best_sym]['price']
        qty = (cash_balance * 0.20) / price

        # Initialize Peak Price for Trailing Stop
        agent_state['custom'][best_sym] = {'peak_price': price}
        
        _last_trade_tick = tick

        if best_score > 0:
            return ("BUY", best_sym, qty)
        else:
            return ("SELL", best_sym, qty)  # Short Sell

    return ("HOLD", None, 0)