# --- Generated Algorithm Code Below ---
import numpy as np
import pandas as pd

# Use agent_state for persistence - NO global variables!
_last_trade_tick = 0  # Only this is safe as a global (just a counter)

def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    '''
    Institutional-grade algo with State Persistence and Fee Awareness.
    agent_state provides entry_prices and current_pnl - USE THESE!
    '''
    global _last_trade_tick

    # Handle backward compatibility
    if agent_state is None:
        agent_state = {'entry_prices': {}, 'current_pnl': {}, 'custom': {}}

    symbols = ['BTC', 'ETH', 'SOL']

    # Cooldown
    if tick - _last_trade_tick < 60:
        return ("HOLD", None, 0)

    # Initialize custom state if needed
    if 'custom' not in agent_state:
        agent_state['custom'] = {}
    if 'high_water_mark' not in agent_state['custom']:
        agent_state['custom']['high_water_mark'] = {}
    if 'low_water_mark' not in agent_state['custom']:
        agent_state['custom']['low_water_mark'] = {}

    # 1. EXIT LOGIC - Use agent_state['current_pnl'] for reliable PnL tracking
    for sym in symbols:
        qty = portfolio.get(sym, 0)
        if qty == 0: continue

        data = market_data.get(sym, {})
        if not data: continue

        price = data['price']

        pnl_info = agent_state['current_pnl'].get(sym, {})
        pnl_pct = pnl_info.get('pnl_percent', 0) / 100.0  # Convert from % to decimal

        # TAKE PROFIT (0.50% target to beat 0.20% costs)
        if pnl_pct > 0.005:
            agent_state['custom']['high_water_mark'].pop(sym, None)
            agent_state['custom']['low_water_mark'].pop(sym, None)
            _last_trade_tick = tick
            action = "SELL" if qty > 0 else "BUY"
            return (action, sym, abs(qty))

        # STOP LOSS (-0.30%)
        if pnl_pct < -0.003:
            agent_state['custom']['high_water_mark'].pop(sym, None)
            agent_state['custom']['low_water_mark'].pop(sym, None)
            _last_trade_tick = tick
            action = "SELL" if qty > 0 else "BUY"
            return (action, sym, abs(qty))

        # TRAILING STOP (2% from peak/trough)
        if qty > 0:  # Long position
            hwm = agent_state['custom']['high_water_mark'].get(sym, price)
            hwm = max(hwm, price)
            agent_state['custom']['high_water_mark'][sym] = hwm
            if price < hwm * 0.98:
                agent_state['custom']['high_water_mark'].pop(sym, None)
                agent_state['custom']['low_water_mark'].pop(sym, None)
                _last_trade_tick = tick
                return ("SELL", sym, qty)
        elif qty < 0:  # Short position
            lwm = agent_state['custom']['low_water_mark'].get(sym, price)
            lwm = min(lwm, price)
            agent_state['custom']['low_water_mark'][sym] = lwm
            if price > lwm * 1.02:
                agent_state['custom']['low_water_mark'].pop(sym, None)
                agent_state['custom']['high_water_mark'].pop(sym, None)
                _last_trade_tick = tick
                return ("BUY", sym, abs(qty))

    # 2. ENTRY LOGIC - Find best opportunity
    best_sym = None
    best_score = 0

    for sym in symbols:
        if portfolio.get(sym, 0) != 0: continue  # Already in position

        data = market_data.get(sym, {})
        if not data: continue

        price = data['price']
        volume = data['volume']
        volumes = data.get('volumes', [])

        # Volume Spike Filter
        if len(volumes) > 0:
            avg_vol = np.mean(volumes[-10:]) if len(volumes) >= 10 else np.mean(volumes)
            if volume <= 1.5 * avg_vol:
                continue
        else:
            continue  # No historical volumes, skip

        # Avoid high volatility
        par_vol = data.get('parkinson_vol', 0)
        if par_vol > 0.03:
            continue

        # Calculate signals for score
        obi = data.get('obi_weighted', 0)
        ofi = data.get('ofi', 0)
        sentiment = data.get('sentiment', 0)
        attention = data.get('attention', 0)
        micro_price = data.get('micro_price', price)
        cvd = data.get('cvd_divergence', 0)
        taker = data.get('taker_ratio', 1)
        funding_vel = data.get('funding_rate_velocity', 0)

        # Fair Value Gap
        fvg = (micro_price - price) / price

        score = 0
        # DeepLOB (obi_weighted)
        if obi > 0.1: score += 1
        elif obi < -0.1: score -= 1

        # Order Flow Imbalance
        if ofi > 100: score += 1
        elif ofi < -100: score -= 1

        # NLP Sentiment
        if sentiment > 0.2: score += 1
        elif sentiment < -0.2: score -= 1

        # Attention (search volume delta)
        if attention > 1.0: score += 1
        elif attention < 0.8: score -= 1

        # Stoikov Fair Value Gap
        if fvg > 0.001: score += 1
        elif fvg < -0.001: score -= 1

        # Additional signals
        if cvd > 0.5: score += 1
        elif cvd < -0.5: score -= 1
        if taker > 1.1: score += 1
        elif taker < 0.9: score -= 1
        if funding_vel > 0.005: score += 1
        elif funding_vel < -0.005: score -= 1

        if abs(score) > abs(best_score):
            best_score = score
            best_sym = sym

    if best_sym and abs(best_score) >= 2:
        price = market_data[best_sym]['price']
        qty = (cash_balance * 0.20) / price

        _last_trade_tick = tick

        if best_score > 0:
            # Set high water mark for long
            agent_state['custom']['high_water_mark'][best_sym] = price
            return ("BUY", best_sym, qty)
        else:
            # Set low water mark for short
            agent_state['custom']['low_water_mark'][best_sym] = price
            return ("SELL", best_sym, qty)  # Short Sell

    return ("HOLD", None, 0)