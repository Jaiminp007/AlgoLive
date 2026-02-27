# OPTIMIZED: Reduced thresholds, added cooldown, proper position management
_last_trade_tick = 0

def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    global _last_trade_tick
    
    TICKER = "BTC"
    
    if TICKER not in market_data:
        return ("HOLD", None, 0)
    
    if agent_state is None:
        agent_state = {'entry_prices': {}, 'current_pnl': {}, 'custom': {}}
        
    data = market_data[TICKER]
    
    # OBI weighted signal (now with real order book data)
    obi = data.get('obi_weighted', 0) or 0
    
    price = data.get('price', 0) or 0
    if price <= 0:
        return ("HOLD", None, 0)
    
    # COOLDOWN: 120 ticks (2 minutes)
    if tick - _last_trade_tick < 120:
        return ("HOLD", None, 0)
    
    # === EXIT LOGIC (if we have a position) ===
    qty = portfolio.get(TICKER, 0)
    if qty != 0:
        pnl_info = agent_state.get('current_pnl', {}).get(TICKER, {})
        pnl_pct = pnl_info.get('pnl_percent', 0) / 100.0
        
        # Take profit at 1.0%
        if pnl_pct > 0.01:
            _last_trade_tick = tick
            action = "SELL" if qty > 0 else "BUY"
            return (action, TICKER, abs(qty))
        
        # Stop loss at -0.6%
        if pnl_pct < -0.006:
            _last_trade_tick = tick
            action = "SELL" if qty > 0 else "BUY"
            return (action, TICKER, abs(qty))
        
        return ("HOLD", None, 0)
    
    # === ENTRY LOGIC (OBI signal) ===
    # LOWERED threshold to 0.1 (was 0.2 after * 1.5)
    if obi > 0.1:
        _last_trade_tick = tick
        quantity = cash_balance * 0.06 / price  # 6% position
        return ("BUY", TICKER, quantity)
    elif obi < -0.1:
        _last_trade_tick = tick
        quantity = cash_balance * 0.06 / price  # 6% position
        return ("SELL", TICKER, quantity)
    
    return ("HOLD", None, 0)