import numpy as np

# Global tick counter for cooldown (safe across logic execution within a session)
_last_trade_tick = 0 

def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    '''
    Institutional-grade Market Microstructure Strategy.
    Fuses DeepLOB (OBI), Stoikov (Micro-price), and Order Flow Imbalance (OFI).
    '''
    global _last_trade_tick

    # Initialize persistent state
    if agent_state is None:
        agent_state = {'entry_prices': {}, 'current_pnl': {}, 'custom': {}}
    if 'peak_prices' not in agent_state['custom']:
        agent_state['custom']['peak_prices'] = {}

    symbols = ['BTC', 'ETH', 'SOL']

    # --- 1. COOLDOWN & PERSISTENCE CHECK ---
    if tick - _last_trade_tick < 60:
        return ("HOLD", None, 0)

    # --- 2. EXIT LOGIC (TP, SL, & TRAILING STOP) ---
    for sym in symbols:
        qty = portfolio.get(sym, 0)
        if qty == 0: continue

        current_price = market_data[sym]['price']
        pnl_info = agent_state.get('current_pnl', {}).get(sym, {})
        # Convert pnl_percent from "0.35" to 0.0035
        pnl_pct = pnl_info.get('pnl_percent', 0) / 100.0

        # Update Trailing Stop Peak Price
        prev_peak = agent_state['custom']['peak_prices'].get(sym, 0)
        if qty > 0: # Long
            agent_state['custom']['peak_prices'][sym] = max(prev_peak, current_price)
        else: # Short
            agent_state['custom']['peak_prices'][sym] = min(prev_peak, current_price) if prev_peak != 0 else current_price

        # Trailing Stop Calculation (2% from peak)
        peak = agent_state['custom']['peak_prices'][sym]
        trailing_exit = False
        if qty > 0 and current_price < (peak * 0.98): trailing_exit = True
        if qty < 0 and current_price > (peak * 1.02): trailing_exit = True

        # Execution of Exit
        # Target > 0.50% to cover 0.20% round-trip costs
        if pnl_pct > 0.005 or pnl_pct < -0.003 or trailing_exit:
            _last_trade_tick = tick
            agent_state['custom']['peak_prices'][sym] = 0 # Reset peak
            return ("SELL" if qty > 0 else "BUY", sym, abs(qty))

    # --- 3. ENTRY LOGIC (SCORING & VOLUME FILTER) ---
    best_sym = None
    best_score = 0

    for sym in symbols:
        if portfolio.get(sym, 0) != 0: continue # Single position per coin

        data = market_data.get(sym, {})
        if not data or 'volumes' not in data: continue

        # Volume Spike Filter (1.5x rolling average)
        recent_vols = data['volumes'][-10:] if len(data['volumes']) >= 10 else data['volumes']
        avg_vol = sum(recent_vols) / len(recent_vols) if recent_vols else 1
        if data['volume'] < (avg_vol * 1.5): continue

        # Signal 1: DeepLOB Multi-Level OBI
        obi = data.get('obi_weighted', 0)
        
        # Signal 2: Stoikov Fair Value Gap
        micro_price = data.get('micro_price', data['price'])
        fv_gap = (micro_price - data['price']) / data['price']
        
        # Signal 3: Order Flow Imbalance (OFI)
        ofi = data.get('ofi', 0)
        
        # Signal 4: Sentiment
        sentiment = data.get('sentiment', 0)

        # Composite Alpha Score
        score = 0
        if obi > 0.1: score += 1
        if obi < -0.1: score -= 1
        if fv_gap > 0.0002: score += 1 # Microprice premium
        if fv_gap < -0.0002: score -= 1
        if ofi > 50: score += 1
        if ofi < -50: score -= 1
        if sentiment > 0.3: score += 1
        if sentiment < -0.3: score -= 1

        if abs(score) > abs(best_score):
            best_score = score
            best_sym = sym

    # --- 4. EXECUTION ---
    if best_sym and abs(best_score) >= 2:
        price = market_data[best_sym]['price']
        # Risk 20% of cash balance
        qty = (cash_balance * 0.20) / price
        _last_trade_tick = tick
        
        if best_score >= 2:
            return ("BUY", best_sym, qty)
        elif best_score <= -2:
            return ("SELL", best_sym, qty) # Open Short

    return ("HOLD", None, 0)