def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    nvda = market_data.get('NVDA', {})
    price = nvda.get('price', 0) or 0
    qty = portfolio.get('NVDA', 0)  # Get current quantity of NVDA in portfolio

    if price > 0 and cash_balance > 100:
        # Here, I will consider a simple threshold or strategy to make a purchase.
        return ("BUY", "NVDA", cash_balance // price * 0.1)  # Buy a fraction of what we can
    return ("HOLD", None, 0)