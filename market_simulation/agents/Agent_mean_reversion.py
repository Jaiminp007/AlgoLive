# --- Mean Reversion: Buy the Dip Strategy ---
# Buys when price drops significantly below its recent average (oversold),
# sells when price recovers back above average. Works with price history only.

def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    symbols = ['BTC', 'ETH', 'SOL', 'BNB']

    custom = (agent_state or {}).get('custom', {})
    last_trade = custom.get('last_trade_tick', 0)
    if tick - last_trade < 20:
        return ("HOLD", None, 0)

    # === EXIT: Sell when price recovers ===
    for sym in symbols:
        qty = portfolio.get(sym, 0)
        if qty <= 0:
            continue
        data = market_data.get(sym, {})
        prices = data.get('history', [])
        price = data.get('price', 0)
        if len(prices) < 10 or price <= 0:
            continue
        avg = sum(prices[-20:]) / len(prices[-20:]) if len(prices) >= 20 else sum(prices) / len(prices)
        # Sell if price recovered above average + 0.5%
        if price >= avg * 1.005:
            if agent_state and 'custom' in agent_state:
                agent_state['custom']['last_trade_tick'] = tick
            return ("SELL", sym, qty)
        # Stop loss if -1.5% below average
        if price < avg * 0.985:
            if agent_state and 'custom' in agent_state:
                agent_state['custom']['last_trade_tick'] = tick
            return ("SELL", sym, qty)

    # === ENTRY: Buy the dip ===
    best_sym = None
    best_dip = 0
    for sym in symbols:
        if portfolio.get(sym, 0) != 0:
            continue
        data = market_data.get(sym, {})
        if not data:
            continue
        prices = data.get('history', [])
        price = data.get('price', 0)
        if len(prices) < 10 or price <= 0:
            continue
        avg = sum(prices[-20:]) / len(prices[-20:]) if len(prices) >= 20 else sum(prices) / len(prices)
        dip_pct = (avg - price) / avg  # positive = price below average = dip
        # Buy if price is 0.5% below average (clear dip)
        if dip_pct > 0.005 and dip_pct > best_dip:
            best_dip = dip_pct
            best_sym = sym

    if best_sym:
        price = market_data[best_sym]['price']
        qty = (cash_balance * 0.25) / price
        if qty > 0:
            if agent_state and 'custom' in agent_state:
                agent_state['custom']['last_trade_tick'] = tick
            return ("BUY", best_sym, qty)

    return ("HOLD", None, 0)
