import numpy as np

# Global tick tracker for cooldown (as permitted by template)
_last_trade_tick = 0 

def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    """
    HFT Quant Strategy: Market Microstructure + NLP Alpha Fusion.
    Integrates DeepLOB Imbalance, Stoikov Fair Value, and Sentiment Analysis.
    """
    global _last_trade_tick

    # --- 1. PERSISTENCE & INITIALIZATION ---
    if agent_state is None:
        agent_state = {'entry_prices': {}, 'current_pnl': {}, 'custom': {}}
    
    # Initialize custom state for trailing stops if not present
    if 'peak_prices' not in agent_state['custom']:
        agent_state['custom']['peak_prices'] = {}

    symbols = ['BTC', 'ETH', 'SOL']
    
    # Cooldown Logic (60 ticks)
    if tick - _last_trade_tick < 60:
        return ("HOLD", None, 0)

    # --- 2. EXIT LOGIC (Take Profit, Stop Loss, Trailing Stop) ---
    for sym in symbols:
        qty = portfolio.get(sym, 0)
        if qty == 0:
            continue

        # Fetch market data and state
        data = market_data.get(sym, {})
        if not data: continue
        
        curr_price = data['price']
        pnl_info = agent_state.get('current_pnl', {}).get(sym, {})
        # agent_state['current_pnl'][sym]['pnl_percent'] is typically provided as a whole number (e.g., 0.35)
        pnl_pct = pnl_info.get('pnl_percent', 0) / 100.0 

        # Update Trailing Stop Peak Price
        prev_peak = agent_state['custom']['peak_prices'].get(sym, curr_price)
        if qty > 0: # Long
            new_peak = max(prev_peak, curr_price)
            trailing_drop = (new_peak - curr_price) / new_peak
        else: # Short
            new_peak = min(prev_peak, curr_price)
            trailing_drop = (curr_price - new_peak) / new_peak
        
        agent_state['custom']['peak_prices'][sym] = new_peak

        # A. TAKE PROFIT (PnL > 0.50% to cover ~0.20% round-trip costs)
        if pnl_pct > 0.005:
            _last_trade_tick = tick
            return ("SELL" if qty > 0 else "BUY", sym, abs(qty))

        # B. HARD STOP LOSS (-0.30%)
        if pnl_pct < -0.003:
            _last_trade_tick = tick
            return ("SELL" if qty > 0 else "BUY", sym, abs(qty))
            
        # C. TRAILING STOP (2% drop from peak)
        if trailing_drop > 0.02:
            _last_trade_tick = tick
            return ("SELL" if qty > 0 else "BUY", sym, abs(qty))

    # --- 3. ENTRY LOGIC (Alpha Fusion) ---
    best_sym = None
    best_score = 0

    for sym in symbols:
        if portfolio.get(sym, 0) != 0:
            continue # Avoid wash trading / over-allocation

        data = market_data.get(sym, {})
        if not data: continue

        # A. Volume Spike Filter (1.5x Rolling Average)
        hist_vols = data.get('volumes', [])
        curr_vol = data.get('volume', 0)
        if len(hist_vols) > 0:
            avg_vol = sum(hist_vols) / len(hist_vols)
            if curr_vol < (1.5 * avg_vol):
                continue

        # B. Signal Extraction
        obi = data.get('obi_weighted', 0)    # DeepLOB
        ofi = data.get('ofi', 0)             # Order Flow
        sentiment = data.get('sentiment', 0) # NLP
        micro_price = data.get('micro_price', data['price'])
        price = data['price']

        # C. Scoring System
        score = 0
        
        # Microstructure (DeepLOB & OFI)
        if obi > 0.1: score += 1
        if obi < -0.1: score -= 1
        if ofi > 50: score += 1
        if ofi < -50: score -= 1
        
        # Fair Value Gap (Stoikov)
        fv_gap = (micro_price - price) / price
        if fv_gap > 0.0005: score += 1   # Price undervalued
        if fv_gap < -0.0005: score -= 1  # Price overvalued
        
        # Semantic Alpha
        if sentiment > 0.3: score += 1
        if sentiment < -0.3: score -= 1

        # Track strongest conviction
        if abs(score) > abs(best_score):
            best_score = score
            best_sym = sym

    # --- 4. EXECUTION ---
    if best_sym and abs(best_score) >= 2:
        price = market_data[best_sym]['price']
        # Position Sizing: 20% Risk per trade
        qty = (cash_balance * 0.20) / price
        
        _last_trade_tick = tick
        
        # Reset peak price for new position
        agent_state['custom']['peak_prices'][best_sym] = price

        if best_score >= 2:
            return ("BUY", best_sym, qty)
        elif best_score <= -2:
            return ("SELL", best_sym, qty) # Short Sell entry

    return ("HOLD", None, 0)