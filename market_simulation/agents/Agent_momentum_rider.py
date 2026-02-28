# --- Momentum Rider: Simple Moving Average Crossover ---
# Buys when short-term MA crosses above long-term MA, sells when it crosses below.
# Works with just price history - no exotic signals needed.

_position = {}  # {symbol: qty}

def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    global _position

    symbols = ['BTC', 'ETH', 'SOL']

    # Wait for cooldown to avoid overtrading
    custom = (agent_state or {}).get('custom', {})
    last_trade = custom.get('last_trade_tick', 0)
    if tick - last_trade < 30:
        return ("HOLD", None, 0)

    # === EXIT LOGIC ===
    for sym in symbols:
        qty = portfolio.get(sym, 0)
        if qty <= 0:
            continue
        data = market_data.get(sym, {})
        prices = data.get('history', [])
        if len(prices) < 5:
            continue
        # Exit if short MA drops below long MA (trend reversal)
        short_ma = sum(prices[-5:]) / 5
        long_ma = sum(prices[-20:]) / 20 if len(prices) >= 20 else short_ma
        if short_ma < long_ma * 0.999:
            if agent_state and 'custom' in agent_state:
                agent_state['custom']['last_trade_tick'] = tick
            return ("SELL", sym, qty)

    # === ENTRY LOGIC: MA Crossover ===
    for sym in symbols:
        if portfolio.get(sym, 0) != 0:
            continue
        data = market_data.get(sym, {})
        if not data:
            continue
        prices = data.get('history', [])
        price = data.get('price', 0)
        if price <= 0 or len(prices) < 10:
            continue

        short_ma = sum(prices[-5:]) / 5
        long_ma = sum(prices[-15:]) / 15 if len(prices) >= 15 else sum(prices) / len(prices)

        # Strong uptrend: short MA clearly above long MA
        if short_ma > long_ma * 1.001:
            qty = (cash_balance * 0.20) / price  # Use 20% of cash
            if qty > 0:
                if agent_state and 'custom' in agent_state:
                    agent_state['custom']['last_trade_tick'] = tick
                return ("BUY", sym, qty)

    return ("HOLD", None, 0)
