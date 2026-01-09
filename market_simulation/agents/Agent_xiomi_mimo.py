import numpy as np
import pandas as pd

# Global counter for cooldown management (safe as it's just a counter)
_last_trade_tick = 0

def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    '''
    Institutional-grade algorithm combining DeepLOB, Stoikov, and NLP signals.
    Implements state-based trading with volume filtering, trailing stops, and fair valuedict): Predictive alpha signals for each symbol
        tick (int): Current market tick
        cash_balance (float): Available cash for trading
        portfolio (dict): Current positions (symbol: quantity)
        market_state: gaps.

    Args:
        market_data ( Reserved for future use
        agent_state (dict): Persistent state across reloads

    Returns:
        tuple: (ACTION, SYMBOL, QUANTITY) - "BUY"/"SELL"/"HOLD", symbol, trade quantity
    '''
    global _last_trade_tick

    # Initialize agent_state if not provided (backward compatibility)
    if agent_state is None:
        agent_state = {
            'entry_prices': {},
            'current_pnl': {},
            'custom': {}
        }

    # Initialize custom state if not exists
    if 'custom' not in agent_state:
        agent_state['custom'] = {}

    # Only trade top 3 liquid coins
    symbols = ['BTC', 'ETH', 'SOL']

    # Cooldown enforcement (60 ticks after any trade)
    if tick - _last_trade_tick < 60:
        return ("HOLD", None, 0)

    # ===== EXIT LOGIC (Priority 1) =====
    # Check existing positions for take profit or stop loss
    for sym in symbols:
        qty = portfolio.get(sym, 0)
        if qty == 0:
            continue

        # Get current PnL from agent_state (persistent across reloads)
        pnl_info = agent_state.get('current_pnl', {}).get(sym, {})
        pnl_pct = pnl_info.get('pnl_percent', 0) / 100.0  # Convert % to decimal

        # TAKE PROFIT: > 0.50% to beat 0.20% round-trip costs
        if pnl_pct > 0.005:
            _last_trade_tick = tick
            action = "SELL" if qty > 0 else "BUY"  # Close position
            return (action, sym, abs(qty))

        # STOP LOSS: -0.30% tight stop
        if pnl_pct < -0.003:
            _last_trade_tick = tick
            action = "SELL" if qty > 0 else "BUY"  # Close position
            return (action, sym, abs(qty))

        # TRAILING STOP: Track peak price, exit if drops 2% from peak
        # Store peak price in custom state
        peak_key = f"{sym}_peak"
        current_peak = agent_state['custom'].get(peak_key, 0)
        current_price = market_data[sym]['price']

        if current_price > current_peak:
            agent_state['custom'][peak_key] = current_price

        if current_peak > 0 and current_price < current_peak * 0.98:  # 2% drop
            _last_trade_tick = tick
            action = "SELL" if qty > 0 else "BUY"
            return (action, sym, abs(qty))

    # ===== ENTRY LOGIC (Priority 2) =====
    best_sym = None
    best_score = 0
    best_direction = 0

    for sym in symbols:
        # Skip if already in position
        if portfolio.get(sym, 0) != 0:
            continue

        data = market_data.get(sym, {})
        if not data:
            continue

        # ===== VOLUME SPIKE FILTER =====
        current_volume = data.get('volume', 0)
        historical_volumes = data.get('volumes', [])

        # Calculate rolling average (last 20 periods)
        if len(historical_volumes) >= 5:  # Minimum data requirement
            rolling_avg = np.mean(historical_volumes[-20:])  # Last 20 periods
            volume_ratio = current_volume / rolling_avg if rolling_avg > 0 else 0

            # Only proceed if volume > 1.5x rolling average
            if volume_ratio < 1.5:
                continue
        else:
            # Insufficient history, skip to avoid false signals
            continue

        # ===== SIGNAL FUSION & SCORING =====
        score = 0

        # 1. DeepLOB Order Book Imbalance
        obi = data.get('obi_weighted', 0)
        if obi > 0.1:      # Strong bid support
            score += 2
        elif obi < -0.1:   # Strong ask pressure
            score -= 2

        # 2. Stoikov Fair Value Gap
        micro_price = data.get('micro_price', 0)
        price = data.get('price', 0)
        fair_value_gap = micro_price - price

        # Trade towards micro-price (fair value)
        if fair_value_gap > 0:  # Undervalued
            score += 2
        elif fair_value_gap < 0:  # Overvalued
            score -= 2

        # 3. Order Flow Imbalance
        ofi = data.get('ofi', 0)
        if ofi > 50:      # Strong aggressive buying
            score += 1
        elif ofi < -50:   # Strong aggressive selling
            score -= 1

        # 4. NLP Sentiment
        sentiment = data.get('sentiment', 0)
        if sentiment > 0.3:     # Very positive
            score += 1
        elif sentiment < -0.3:  # Very negative
            score -= 1

        # 5. Advanced Microstructure Filters
        taker_ratio = data.get('taker_ratio', 1.0)
        cvd_divergence = data.get('cvd_divergence', 0)

        # Taker dominance suggests momentum
        if taker_ratio > 1.2:
            score += 1
        elif taker_ratio < 0.8:
            score -= 1

        # CVD divergence detection
        if cvd_divergence > 0.5:
            score += 1
        elif cvd_divergence < -0.5:
            score -= 1

        # ===== ENTRY DECISION =====
        # Long if score >= 2, Short if score <= -2
        if score >= 2 and score > best_score:
            best_score = score
            best_sym = sym
            best_direction = 1  # Long
        elif score <= -2 and abs(score) > abs(best_score):
            best_score = score
            best_sym = sym
            best_direction = -1  # Short

    # ===== EXECUTE TRADE =====
    if best_sym is not None and abs(best_score) >= 2:
        price = market_data[best_sym]['price']

        # Position sizing: 20% of cash balance
        qty = (cash_balance * 0.20) / price

        # Ensure minimum quantity for practicality
        if qty < 0.0001:  # Very small trade size
            return ("HOLD", None, 0)

        _last_trade_tick = tick

        if best_direction == 1:  # Long
            return ("BUY", best_sym, qty)
        else:  # Short (direction == -1)
            return ("SELL", best_sym, qty)

    # No actionable signal
    return ("HOLD", None, 0)
