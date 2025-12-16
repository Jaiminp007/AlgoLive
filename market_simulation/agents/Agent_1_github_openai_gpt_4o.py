# Global state
_entry_price = {}
_last_trade_tick = 0  # COOLDOWN TRACKER

def execute_strategy(market_data, tick, cash_balance, portfolio):
    '''
    Multi-currency momentum strategy for BTC, ETH, SOL.
    '''
    global _entry_price, _last_trade_tick
    
    # ===== COOLDOWN CHECK =====
    # Wait 60 ticks (~ 60 seconds) between trades
    if tick - _last_trade_tick < 60:
        return ("HOLD", None, 0)
    
    # 0. Hot-Swap Reconstruction
    for sym, qty in portfolio.items():
        if qty != 0 and sym not in _entry_price:
            current_p = market_data.get(sym, {}).get('price', 0)
            if current_p: 
                _entry_price[sym] = current_p

    # ===== EXIT LOGIC (Check Existing Positions First) =====
    for sym, qty in portfolio.items():
        if qty == 0: 
            continue
        data = market_data.get(sym, {})
        if not data or 'price' not in data: 
            continue
        
        price = data['price']
        entry_price = _entry_price.get(sym, price)
        if entry_price == 0: 
            continue
        
        # Calculate PnL (%)
        pnl_pct = (price / entry_price) - 1.0
        
        # Take profit at +3% to +5%
        if pnl_pct > 0.03:
            _entry_price.pop(sym, None)
            _last_trade_tick = tick  # COOLDOWN
            return ("SELL", sym, qty)
        
        # Stop-loss at -5%
        if pnl_pct < -0.05:
            _entry_price.pop(sym, None)
            _last_trade_tick = tick  # COOLDOWN
            return ("SELL", sym, qty)
    
    # ===== ENTRY LOGIC (Find the best momentum candidate) =====
    if not market_data: 
        return ("HOLD", None, 0)
    
    best_sym = None
    best_score = -999
    
    for sym, data in market_data.items():
        if sym not in ["BTC", "ETH", "SOL"]: 
            continue
        if not isinstance(data, dict) or 'price' not in data: 
            continue
        if portfolio.get(sym, 0) != 0: 
            continue  # Skip already held assets
        
        # Extract signals
        price = data['price']
        obi = data.get('obi_weighted', 0.0)
        ofi = data.get('ofi', 0.0)
        micro_price = data.get('micro_price', price)
        sentiment = data.get('sentiment', 0.0)
        attention = data.get('attention', 0.0)
        
        # Calculate score
        score = 0
        
        # Regime filter: Sentiment & Attention
        if sentiment > 0.6 and attention > 1.0:
            score += 3
        
        # Setup: Order Book Imbalance
        if obi > 0.1:
            score += 5
        
        # Trigger: Order Flow Imbalance
        if ofi > 30:
            score += 4
        elif ofi < -30:
            score -= 3
        
        # Fair Value Gap
        if price < micro_price * 0.995:  # Price below fair value
            score += 3
        
        # Update best candidate
        if score > best_score:
            best_score = score
            best_sym = sym
    
    # ===== EXECUTE BUY (Score >= 5) =====
    if best_sym and best_score >= 5:
        data = market_data[best_sym]
        price = data['price']
        
        # Position sizing: Risk 5%
        qty = (cash_balance * 0.05) / price
        
        # Ensure minimum viable quantity
        if qty > 0 and cash_balance >= price * qty:
            _entry_price[best_sym] = price
            _last_trade_tick = tick  # COOLDOWN
            return ("BUY", best_sym, qty)
    
    return ("HOLD", None, 0)