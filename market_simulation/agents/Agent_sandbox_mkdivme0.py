def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    TICKER = "BTC"
    
    if TICKER not in market_data:
        return ("HOLD", None, 0)
        
    data = market_data[TICKER]
    
    # Corrected: Safe access to obi_weighted
    obi = data.get('obi_weighted', 0) or 0  # Handle None/undefined
    signal = obi * 1.5
    
    # Corrected: Safe access to price
    price = data.get('price', 0) or 0
    
    if price <= 0:
        return ("HOLD", None, 0)
    
    if signal > 0.3:
        quantity = cash_balance * 0.5 / price
        return ("BUY", TICKER, quantity)
    elif signal < -0.3:
        quantity = cash_balance * 0.5 / price
        return ("SELL", TICKER, quantity)
    
    return ("HOLD", None, 0)