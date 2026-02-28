def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    # Extract BNB and BTC market data
    bnb = market_data.get('BNB', {})
    btc = market_data.get('BTC', {})
    
    # Price data
    bnb_price = bnb.get('price', 0) or 0
    btc_price = btc.get('price', 0) or 0
    
    # Portfolio quantities
    bnb_qty = portfolio.get('BNB', 0)
    btc_qty = portfolio.get('BTC', 0)
    
    # Strategy: Price Ratio Mean Reversion (BNB/BTC)
    if bnb_price > 0 and btc_price > 0:  # Ensure valid price data
        price_ratio = bnb_price / btc_price
        
        # Initialize agent_state for our price ratio tracking (safe defaults from persistent state)
        if agent_state is None:
            agent_state = {}
        if 'price_ratio_mean' not in agent_state:
            agent_state['price_ratio_mean'] = price_ratio
        if 'price_ratio_std' not in agent_state:
            agent_state['price_ratio_std'] = 0.0

        # Update price ratio statistics using exponential moving average (EMA)
        decay = 0.01  # Controls EMA smoothing
        agent_state['price_ratio_mean'] = (
            (1 - decay) * agent_state['price_ratio_mean'] + decay * price_ratio
        )
        agent_state['price_ratio_std'] = (
            (1 - decay) * agent_state['price_ratio_std'] + decay * abs(price_ratio - agent_state['price_ratio_mean'])
        )
        
        # Decide trading thresholds
        upper_threshold = agent_state['price_ratio_mean'] + 2 * agent_state['price_ratio_std']
        lower_threshold = agent_state['price_ratio_mean'] - 2 * agent_state['price_ratio_std']
        
        # Trading Logic for mean-reversion
        if price_ratio > upper_threshold and bnb_qty > 0:  # BNB is overvalued, sell BNB for BTC
            sell_qty = min(bnb_qty, 0.1)  # Limit trade size to 0.1 BNB
            return ("SELL", "BNB", sell_qty)
        elif price_ratio < lower_threshold and cash_balance >= bnb_price * 0.1:  # BNB is undervalued, buy BNB
            buy_qty = min(cash_balance / bnb_price, 0.1)  # Limit trade size to 0.1 BNB
            return ("BUY", "BNB", buy_qty)
    
    # Default action
    return ("HOLD", None, 0), agent_state