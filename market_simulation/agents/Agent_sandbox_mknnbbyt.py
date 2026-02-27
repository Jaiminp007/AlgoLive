def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    sol_price = market_data.get('SOL', {}).get('price', 0) or 0
    btc_price = market_data.get('BTC', {}).get('price', 0) or 0
    sol_qty = portfolio.get('SOL', 0)
    btc_qty = portfolio.get('BTC', 0)

    # Strategy: SOL/BTC price ratio mean-reversion
    if 'price_ratio_mean' not in agent_state: 
        # Initialize agent state with the first tick
        if sol_price > 0 and btc_price > 0:
            price_ratio = sol_price / btc_price
            agent_state['price_ratios'] = [price_ratio]
            agent_state['price_ratio_mean'] = price_ratio
            agent_state['price_ratio_std'] = 0
        return ("HOLD", None, 0)
    
    # Update and calculate rolling mean and std deviation of SOL/BTC ratio
    if sol_price > 0 and btc_price > 0:
        price_ratio = sol_price / btc_price
        agent_state['price_ratios'].append(price_ratio)
        if len(agent_state['price_ratios']) > 50:  # Rolling window of 50 ticks
            agent_state['price_ratios'].pop(0)
        agent_state['price_ratio_mean'] = sum(agent_state['price_ratios']) / len(agent_state['price_ratios'])
        agent_state['price_ratio_std'] = (sum([(x - agent_state['price_ratio_mean']) ** 2 for x in agent_state['price_ratios']]) / len(agent_state['price_ratios'])) ** 0.5

        upper_bound = agent_state['price_ratio_mean'] + 2 * agent_state['price_ratio_std']
        lower_bound = agent_state['price_ratio_mean'] - 2 * agent_state['price_ratio_std']

        # Buy SOL and sell BTC when ratio is below lower bound
        if price_ratio < lower_bound and btc_qty > 0:
            sell_amount = min(btc_qty, cash_balance / btc_price) * 0.1
            return ("SELL", "BTC", sell_amount)
        # Buy BTC and sell SOL when ratio is above upper bound
        elif price_ratio > upper_bound and sol_qty > 0:
            sell_amount = min(sol_qty, cash_balance / sol_price) * 0.1
            return ("SELL", "SOL", sell_amount)

    return ("HOLD", None, 0)