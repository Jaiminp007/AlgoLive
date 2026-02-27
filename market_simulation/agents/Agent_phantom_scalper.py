# --- Phantom Scalper: Micro-Price Arbitrage ---
# Exploits Stoikov fair-value gaps for lightning-fast scalps
# OPTIMIZED: Wider targets, reduced position size, better cooldowns
import numpy as np
import pandas as pd

_last_trade_tick = 0
_consecutive_losses = 0

def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    '''
    Phantom Scalper: Trades the gap between market price and micro-price (Stoikov fair value).
    High-frequency approach with tight risk management.
    '''
    global _last_trade_tick, _consecutive_losses
    
    if agent_state is None:
        agent_state = {'entry_prices': {}, 'current_pnl': {}, 'custom': {}}
    
    # Primary focus on high-liquidity crypto
    symbols = ['BTC', 'ETH', 'SOL']
    
    # INCREASED COOLDOWN: 150 base + penalty (was 30)
    cooldown = 150 + (_consecutive_losses * 30)
    if tick - _last_trade_tick < cooldown:
        return ("HOLD", None, 0)
    
    # === EXIT LOGIC ===
    for sym in symbols:
        qty = portfolio.get(sym, 0)
        if qty == 0:
            continue
        
        pnl_info = agent_state.get('current_pnl', {}).get(sym, {})
        pnl_pct = pnl_info.get('pnl_percent', 0) / 100.0
        
        # WIDER PROFIT TARGET: 0.8% (was 0.35%)
        if pnl_pct > 0.008:
            _last_trade_tick = tick
            _consecutive_losses = max(0, _consecutive_losses - 1)  # Reduce loss counter on win
            action = "SELL" if qty > 0 else "BUY"
            return (action, sym, abs(qty))
        
        # WIDER STOP LOSS: -0.5% (was -0.25%)
        if pnl_pct < -0.005:
            _last_trade_tick = tick
            _consecutive_losses += 1
            action = "SELL" if qty > 0 else "BUY"
            return (action, sym, abs(qty))
    
    # === ENTRY LOGIC: Micro-Price Gap Trading ===
    best_opportunity = None
    best_gap = 0
    
    for sym in symbols:
        if portfolio.get(sym, 0) != 0:
            continue
        
        data = market_data.get(sym, {})
        if not data:
            continue
        
        price = data.get('price', 0)
        micro_price = data.get('micro_price', price)
        obi = data.get('obi_weighted', 0) or 0
        
        if price <= 0 or micro_price <= 0:
            continue
        
        # Calculate fair value gap (%)
        gap = ((micro_price - price) / price) * 100
        
        # Volume filter: Only trade when there's order book support
        volumes = data.get('volumes', [])
        if len(volumes) >= 10:
            recent_vol = np.mean(volumes[-5:]) if volumes else 0
            avg_vol = np.mean(volumes[-20:]) if len(volumes) >= 20 else recent_vol
            vol_surge = recent_vol > (avg_vol * 1.2) if avg_vol > 0 else False
        else:
            vol_surge = False
        
        # Entry conditions:
        # 1. Significant gap (micro_price vs price)
        # 2. Order book supports the direction
        # 3. Volume confirmation (optional boost)
        
        score = 0
        if gap > 0.05 and obi > 0.1:  # Undervalued + bid support
            score = gap + (obi * 0.5)
            if vol_surge:
                score *= 1.3
        elif gap < -0.05 and obi < -0.1:  # Overvalued + ask pressure
            score = gap + (obi * 0.5)  # Both negative = strong short signal
            if vol_surge:
                score *= 1.3
        
        if abs(score) > abs(best_gap):
            best_gap = score
            best_opportunity = (sym, gap, obi)
    
    # Execute if we found a good opportunity (INCREASED threshold from 0.1 to 0.15)
    if best_opportunity and abs(best_gap) > 0.15:
        sym, gap, obi = best_opportunity
        price = market_data[sym]['price']
        
        # REDUCED POSITION SIZE: 5% of cash (was 15%)
        qty = (cash_balance * 0.05) / price
        
        _last_trade_tick = tick
        
        if gap > 0:  # Price below fair value -> BUY
            return ("BUY", sym, qty)
        else:  # Price above fair value -> SHORT
            return ("SELL", sym, qty)
    
    return ("HOLD", None, 0)
