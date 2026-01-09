# --- Institutional-Grade Strategy Code Below ---
import numpy as np

_last_trade_tick = 0  # Safe to use (global tick guard)

def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    global _last_trade_tick

    if agent_state is None:
        agent_state = {'entry_prices': {}, 'current_pnl': {}, 'custom': {}}

    agent_state.setdefault('entry_prices', {})
    agent_state.setdefault('current_pnl', {})
    agent_state.setdefault('custom', {})

    symbols = ['BTC', 'ETH', 'SOL']
    
    # Tick-based cooldown to avoid overtrading
    if tick - _last_trade_tick < 60:
        return ("HOLD", None, 0)

    # === EXIT LOGIC (Profit-taking / Stop Loss / Trailing Stop) ===
    for sym in symbols:
        qty = portfolio.get(sym, 0)
        if qty == 0:
            continue

        pnl_info = agent_state['current_pnl'].get(sym, {})
        pnl_pct = pnl_info.get('pnl_percent', 0) / 100.0  # Convert to decimal
        entry_price = pnl_info.get('entry_price', None)
        current_price = pnl_info.get('current_price', None)

        if entry_price is None or current_price is None:
            continue

        # Initialize peak tracker
        peak_key = f'{sym}_peak'
        peak_price = agent_state['custom'].get(peak_key, entry_price)

        # Update peak if current price is higher (LONG) or lower (SHORT)
        if qty > 0 and current_price > peak_price:
            agent_state['custom'][peak_key] = current_price
        elif qty < 0 and current_price < peak_price:
            agent_state['custom'][peak_key] = current_price

        peak_price = agent_state['custom'].get(peak_key, entry_price)

        # --- Take Profit ---
        if pnl_pct > 0.005:
            _last_trade_tick = tick
            action = "SELL" if qty > 0 else "BUY"
            return (action, sym, abs(qty))

        # --- Stop Loss ---
        if pnl_pct < -0.003:
            _last_trade_tick = tick
            action = "SELL" if qty > 0 else "BUY"
            return (action, sym, abs(qty))

        # --- Trailing Stop ---
        trail_threshold = 0.02  # 2%
        if qty > 0 and current_price < peak_price * (1 - trail_threshold):
            _last_trade_tick = tick
            return ("SELL", sym, qty)
        elif qty < 0 and current_price > peak_price * (1 + trail_threshold):
            _last_trade_tick = tick
            return ("BUY", sym, abs(qty))

    # === ENTRY LOGIC ===
    best_sym = None
    best_score = 0

    for sym in symbols:
        if portfolio.get(sym, 0) != 0:
            continue  # Already in a position

        data = market_data.get(sym, {})
        if not data:
            continue

        price = data['price']
        volume = data['volume']
        volumes_hist = data.get('volumes', [])

        # --- Volume Spike Filter ---
        if len(volumes_hist) >= 20:
            avg_vol = np.mean(volumes_hist[-20:])
            if volume < 1.5 * avg_vol:
                continue

        # --- Signal Components ---
        obi = data.get('obi_weighted', 0)
        ofi = data.get('ofi', 0)
        sentiment = data.get('sentiment', 0)
        attention = data.get('attention', 0)
        micro_price = data.get('micro_price', price)

        # --- Fair Value Gap ---
        fv_gap = (micro_price - price) / price  # Directional alpha

        score = 0
        # DeepLOB/OBI
        if obi > 0.1: score += 1
        if obi < -0.1: score -= 1

        # Order Flow
        if ofi > 10: score += 1
        if ofi < -10: score -= 1

        # NLP Sentiment
        if sentiment > 0.2: score += 1
        if sentiment < -0.2: score -= 1

        # Google Trends Attention
        if attention > 1.0: score += 1
        if attention < 0.5: score -= 1

        # Stoikov Fair Value Signal
        if fv_gap > 0.001: score += 1
        if fv_gap < -0.001: score -= 1

        # Select the highest scoring symbol
        if abs(score) > abs(best_score):
            best_score = score
            best_sym = sym

    # --- Execute Trade ---
    if best_sym and abs(best_score) >= 2:
        direction = "BUY" if best_score > 0 else "SELL"
        price = market_data[best_sym]['price']
        qty = (cash_balance * 0.20) / price  # 20% cash risk
        _last_trade_tick = tick

        return (direction, best_sym, qty)

    return ("HOLD", None, 0)
