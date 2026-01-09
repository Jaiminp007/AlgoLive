# ==================== IMPORTS ====================
import numpy as np

# ==================== GLOBAL STATE ====================
# Only a tick‑counter is safe as a module‑level variable.
# All other state lives inside `agent_state`.
_last_trade_tick = 0


# ==================== HELPER FUNCTIONS ====================
def _rolling_volume_ma(vol_series, window=5):
    """
    Simple moving average of the most recent `window` volume observations.
    Returns 0 if not enough data yet.
    """
    if len(vol_series) < window:
        return 0.0
    return np.mean(vol_series[-window:])


def _update_peak_and_check_stop(sym, price, agent_state, portfolio):
    """
    Update peak price and decide whether the trailing‑stop (‑0.30 %) is hit.
    Returns None if we stay in the trade, otherwise the action string
    ('SELL' to close the position).
    """
    # Retrieve or initialise the peak price for this symbol.
    peaks = agent_state.setdefault('custom', {}).setdefault('peak_price', {})
    cur_peak = peaks.get(sym, price)               # start with entry price
    # Update to the highest price seen so far.
    new_peak = max(cur_peak, price)
    peaks[sym] = new_peak

    # Compute stop‑price (‑0.30 % from the peak).
    stop_price = new_peak * (1 - 0.003)

    # If current price falls below stop, signal exit.
    if price <= stop_price:
        # Return "SELL" regardless of whether we are long or short.
        return "SELL"
    return None


def _calculate_score(data):
    """
    Composite micro‑structure score.
    • OBI_weighted  → +1 / –1 for bullish / bearish imbalance.
    • OFI          → +1 / –1 for strong aggressive flow.
    • Sentiment    → +1 / –1 for positive / negative news.
    • Micro‑price gap direction → +1 if price < micro_price (undervalued),
                                   –1 if price > micro_price (overvalued).
    Returns a signed integer in the range [-4, +4].
    """
    score = 0
    obi = data.get('obi_weighted', 0)
    ofi = data.get('ofi', 0)
    sentiment = data.get('sentiment', 0)
    micro_price = data.get('micro_price', 0.0)
    price = data.get('price', 0.0)

    # OBI bias
    if obi > 0.1:
        score += 1
    elif obi < -0.1:
        score -= 1

    # Order‑flow imbalance
    if ofi > 10:
        score += 1
    elif ofi < -10:
        score -= 1

    # Sentiment direction
    if sentiment > 0.2:
        score += 1
    elif sentiment < -0.2:
        score -= 1

    # Fair‑value‑gap direction (trade toward micro_price)
    if micro_price > price:
        score += 1            # undervalued → long bias
    elif micro_price < price:
        score -= 1            # overvalued → short bias

    return score


# ==================== MAIN STRATEGY ====================
def execute_strategy(
    market_data,
    tick,
    cash_balance,
    portfolio,
    market_state=None,
    agent_state=None,
):
    """
    Execute a single tick of the institutional‑grade micro‑structure strategy.

    Parameters
    ----------
    market_data : dict
        `market_data[symbol]` contains price, volume, OBI, micro_price, etc.
    tick : int
        Current simulation tick.
    cash_balance : float
        Cash available for new trades.
    portfolio : dict
        Current holdings: `portfolio[symbol] = quantity`.
    market_state, agent_state : dict or None
        Persistent state containers supplied by the arena.

    Returns
    -------
    tuple
        (ACTION, SYMBOL, QUANTITY) where ACTION ∈ {"BUY","SELL","HOLD"}.
    """

    # ------------------------------------------------------------------
    # 0️⃣  Back‑compat handling (the arena may call without agent_state)
    # ------------------------------------------------------------------
    if agent_state is None:
        agent_state = {'entry_prices': {}, 'current_pnl': {}, 'custom': {}}

    # ------------------------------------------------------------------
    # 1️⃣  Cooldown enforcement (60 ticks after any trade)
    # ------------------------------------------------------------------
    global _last_trade_tick
    if tick - _last_trade_tick < 60:
        return ("HOLD", None, 0.0)

    # ------------------------------------------------------------------
    # 2️⃣  EXIT LOGIC (profit‑target & stop‑loss, plus trailing‑stop)
    # ------------------------------------------------------------------
    for sym in ['BTC', 'ETH', 'SOL']:
        qty = portfolio.get(sym, 0.0)
        if qty == 0.0:          # no position → nothing to close
            continue

        # ---- PnL information (persisted by the arena) ----
        pnl_info = agent_state.get('current_pnl', {}).get(sym, {})
        pnl_pct = pnl_info.get('pnl_percent', 0) / 100.0   # % → decimal

        # ---- Secure profit (> 0.50 % to beat total 0.20 % cost) ----
        if pnl_pct > 0.005:
            _last_trade_tick = tick
            return ("SELL", sym, abs(qty))

        # ---- Tight stop‑loss (‑0.30 %) ----
        if pnl_pct < -0.003:
            _last_trade_tick = tick
            return ("SELL", sym, abs(qty))

        # ---- Trailing‑stop (‑0.30 % from the recorded peak) ----
        stop_signal = _update_peak_and_check_stop(sym, market_data[sym]['price'],
                                                  agent_state, portfolio)
        if stop_signal:
            _last_trade_tick = tick
            return (stop_signal, sym, abs(qty))

    # ------------------------------------------------------------------
    # 3️⃣  ENTRY LOGIC – find the best opportunity among the top‑3 coins
    # ------------------------------------------------------------------
    best_sym = None
    best_score = 0

    for sym in symbols:
        # Skip if we already hold a position (single‑position policy)
        if portfolio.get(sym, 0.0) != 0.0:
            continue

        data = market_data.get(sym, {})
        if not data:
            continue

        # ---- Volume‑spike filter (current volume > 1.5 × 5‑tick SMA) ----
        vol_series = data.get('volumes', [])
        vol_ma = _rolling_volume_ma(vol_series, window=5)
        if vol_ma == 0.0 or data.get('volume', 0.0) <= 1.5 * vol_ma:
            continue          # not a sufficiently strong spike

        # ---- Composite micro‑structure score ----
        score = _calculate_score(data)

        # Keep the signal with the largest absolute score
        if abs(score) > abs(best_score):
            best_score = score
            best_sym = sym

    # ------------------------------------------------------------------
    # 4️⃣  POST‑ENTRY: act on the strongest qualified signal
    # ------------------------------------------------------------------
    if best_sym and abs(best_score) >= 2:
        price = market_data[best_sym]['price']
        qty = (cash_balance * 0.20) / price          # 20 % of cash risked

        # Record the entry price for future PnL calculations (optional)
        agent_state.setdefault('entry_prices', {})[best_sym] = price

        _last_trade_tick = tick

        # Positive score → BUY (long); negative score → SELL (short)
        action = "BUY" if best_score > 0 else "SELL"
        return (action, best_sym, qty)

    # ------------------------------------------------------------------
    # 5️⃣  No actionable signal → stay in cash
    # ------------------------------------------------------------------
    return ("HOLD", None, 0.0)


# ------------------- END OF SCRIPT -------------------