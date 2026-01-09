# --- Generated Algorithm Code Below ---
import numpy as np
import pandas as pd

# Use agent_state for persistence - NO global variables!
_last_trade_tick = 0  # Only this is safe as a global (just a counter)

def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    '''
    Institutional-grade, state-based microstructure + Stoikov FV + NLP/attention fusion.
    - Trades ONLY BTC/ETH/SOL
    - Volume spike entry filter (vol > 1.5x rolling avg)
    - Fee-aware profit taking (never take profit < +0.50%)
    - Tight stop (-0.30%)
    - Trailing stop (2% from best price) ARMED only after +0.50% reached
    - Supports SHORT selling (SELL to open when flat)
    '''
    global _last_trade_tick

    # Handle backward compatibility
    if agent_state is None:
        agent_state = {'entry_prices': {}, 'current_pnl': {}, 'custom': {}}
    agent_state.setdefault('entry_prices', {})
    agent_state.setdefault('current_pnl', {})
    agent_state.setdefault('custom', {})

    # Persistent custom state (NO globals)
    custom = agent_state['custom']
    custom.setdefault('trail', {})        # per-sym: {'peak': float, 'trough': float, 'armed': bool}
    custom.setdefault('entry_tick', {})   # per-sym: int tick when we last entered

    symbols = ['BTC', 'ETH', 'SOL']

    # Cooldown (after ANY trade)
    if tick - _last_trade_tick < 60:
        return ("HOLD", None, 0)

    # -----------------------------
    # 1) EXIT LOGIC (stateful)
    # -----------------------------
    for sym in symbols:
        qty = portfolio.get(sym, 0.0)
        if qty == 0:
            continue

        data = market_data.get(sym, {})
        if not data:
            continue

        price = float(data.get('price', 0.0))
        if price <= 0:
            continue

        pnl_info = agent_state.get('current_pnl', {}).get(sym, {})
        pnl_pct = pnl_info.get('pnl_percent', 0.0) / 100.0  # Convert from % to decimal

        # Initialize trail state if missing
        tstate = custom['trail'].setdefault(sym, {'peak': price, 'trough': price, 'armed': False})

        # Update best favorable price since entry
        if qty > 0:  # long
            tstate['peak'] = max(float(tstate.get('peak', price)), price)
        else:        # short
            tstate['trough'] = min(float(tstate.get('trough', price)), price)

        # Arm trailing stop ONLY after we have reached the minimum profit threshold at least once
        # (prevents "profit taking" exits below +0.50%).
        if pnl_pct >= 0.005:
            tstate['armed'] = True

        # STOP LOSS (-0.30%) ALWAYS ACTIVE
        if pnl_pct < -0.003:
            _last_trade_tick = tick
            # close long -> SELL, close short -> BUY
            action = "SELL" if qty > 0 else "BUY"
            # clear trailing state for symbol
            custom['trail'].pop(sym, None)
            custom['entry_tick'].pop(sym, None)
            return (action, sym, abs(qty))

        # TAKE PROFIT: Only allowed if pnl_pct > +0.50%
        # To be more "state-based" (and to let trailing matter), we only exit for profit
        # when alpha weakens / mean-reversion completes.
        if pnl_pct > 0.005:
            obi = float(data.get('obi_weighted', 0.0))
            ofi = float(data.get('ofi', 0.0))
            sentiment = float(data.get('sentiment', 0.0))
            micro_price = float(data.get('micro_price', price))
            fvg = (micro_price - price) / price  # fair value gap as fraction

            # If the FV gap is basically closed OR microstructure flips against us -> secure profit
            alpha_weaken = False
            if qty > 0:
                # long: want +fvg, +obi, +ofi, +sent
                if fvg < 0.0002 or obi < 0.0 or ofi < 0.0 or sentiment < 0.0:
                    alpha_weaken = True
            else:
                # short: want -fvg, -obi, -ofi, -sent
                if fvg > -0.0002 or obi > 0.0 or ofi > 0.0 or sentiment > 0.0:
                    alpha_weaken = True

            if alpha_weaken:
                _last_trade_tick = tick
                action = "SELL" if qty > 0 else "BUY"
                custom['trail'].pop(sym, None)
                custom['entry_tick'].pop(sym, None)
                return (action, sym, abs(qty))

        # TRAILING STOP (2% from best favorable price), ARMED only after +0.50% was reached
        if tstate.get('armed', False):
            if qty > 0:
                peak = float(tstate.get('peak', price))
                if price <= peak * (1.0 - 0.02):
                    _last_trade_tick = tick
                    custom['trail'].pop(sym, None)
                    custom['entry_tick'].pop(sym, None)
                    return ("SELL", sym, abs(qty))
            else:
                trough = float(tstate.get('trough', price))
                if price >= trough * (1.0 + 0.02):
                    _last_trade_tick = tick
                    custom['trail'].pop(sym, None)
                    custom['entry_tick'].pop(sym, None)
                    return ("BUY", sym, abs(qty))

    # -----------------------------
    # 2) ENTRY LOGIC (best opportunity)
    # -----------------------------
    best_sym = None
    best_score = 0

    for sym in symbols:
        # Only one position per symbol; also avoid stacking across symbols if Arena allows:
        if portfolio.get(sym, 0.0) != 0.0:
            continue

        data = market_data.get(sym, {})
        if not data:
            continue

        price = float(data.get('price', 0.0))
        if price <= 0:
            continue

        # Volume spike filter (MANDATORY)
        vol = float(data.get('volume', 0.0))
        vols = data.get('volumes', []) or []
        if len(vols) >= 5:
            window = vols[-20:] if len(vols) >= 20 else vols
            vol_avg = float(np.mean(window)) if np.mean(window) > 0 else 0.0
        else:
            vol_avg = 0.0

        if vol_avg <= 0 or vol <= 1.5 * vol_avg:
            continue  # do NOT enter without a spike

        # Signals
        obi = float(data.get('obi_weighted', 0.0))          # DeepLOB OBI
        ofi = float(data.get('ofi', 0.0))                  # Order Flow Imbalance
        sentiment = float(data.get('sentiment', 0.0))      # NLP sentiment
        attention = float(data.get('attention', 1.0))      # attention delta
        micro_price = float(data.get('micro_price', price))# Stoikov FV
        fvg = (micro_price - price) / price                # Fair Value Gap fraction

        funding_vel = float(data.get('funding_rate_velocity', 0.0))
        cvd_div = float(data.get('cvd_divergence', 0.0))
        taker_ratio = float(data.get('taker_ratio', 1.0))
        pvol = float(data.get('parkinson_vol', 0.0))

        # Regime / state-based thresholding (higher vol => demand stronger confluence)
        entry_th = 2
        if pvol >= 0.04:
            entry_th = 3
        if pvol >= 0.06:
            entry_th = 4

        # Scoring (confluence)
        score = 0

        # --- Microstructure core ---
        # OBI
        if obi > 0.10: score += 1
        if obi < -0.10: score -= 1
        if obi > 0.30: score += 1
        if obi < -0.30: score -= 1

        # OFI
        if ofi > 10: score += 1
        if ofi < -10: score -= 1
        if ofi > 50: score += 1
        if ofi < -50: score -= 1

        # --- Stoikov fair value (trade towards micro_price) ---
        # Require a meaningful gap (avoid noise)
        if fvg > 0.0008: score += 1
        if fvg < -0.0008: score -= 1
        if fvg > 0.0020: score += 1
        if fvg < -0.0020: score -= 1

        # --- NLP / Attention ---
        if sentiment > 0.20: score += 1
        if sentiment < -0.20: score -= 1
        if sentiment > 0.60: score += 1
        if sentiment < -0.60: score -= 1

        # Attention amplifies sentiment
        if attention > 1.05 and sentiment > 0.20: score += 1
        if attention < 0.95 and sentiment < -0.20: score -= 1

        # --- Internals / confirmation ---
        if taker_ratio > 1.05: score += 1
        if taker_ratio < 0.95: score -= 1

        if cvd_div > 0.30: score += 1
        if cvd_div < -0.30: score -= 1

        # Funding velocity: if strongly positive, penalize longs (crowded), boost shorts slightly
        if funding_vel > 0.02:
            score -= 1
        if funding_vel < -0.02:
            score += 1

        # Confluence sanity: if OBI and sentiment strongly disagree, dampen (avoid false positives)
        if (obi > 0.15 and sentiment < -0.2) or (obi < -0.15 and sentiment > 0.2):
            score = int(np.sign(score) * max(0, abs(score) - 1))

        # Pick best absolute score
        if abs(score) > abs(best_score):
            best_score = score
            best_sym = sym

        # NOTE: entry_th is per-symbol; we apply it later to chosen best_sym using its pvol.
        # To keep consistent, store per-symbol thresholds in custom if desired (not necessary).

    if best_sym is not None:
        data = market_data.get(best_sym, {})
        price = float(data.get('price', 0.0))
        if price > 0:
            pvol = float(data.get('parkinson_vol', 0.0))
            entry_th = 2
            if pvol >= 0.04: entry_th = 3
            if pvol >= 0.06: entry_th = 4

            if abs(best_score) >= entry_th:
                qty = (cash_balance * 0.20) / price  # 20% risk per trade, FLOAT qty

                _last_trade_tick = tick
                custom['entry_tick'][best_sym] = tick

                # Initialize trailing state at entry
                if best_score > 0:
                    custom['trail'][best_sym] = {'peak': price, 'trough': price, 'armed': False}
                    return ("BUY", best_sym, qty)
                else:
                    custom['trail'][best_sym] = {'peak': price, 'trough': price, 'armed': False}
                    return ("SELL", best_sym, qty)  # Short Sell (SELL to open)

    return ("HOLD", None, 0)
