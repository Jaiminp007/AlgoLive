# --- Apex Crypto: Multi-Signal ROI Strategy ---
# Strategy: EMA crossover (8/21) + RSI overbought/oversold filter
#            + Volume surge confirmation + Trailing stop + Take profit
# Focuses exclusively on BTC, ETH, SOL for real crypto ROI.

# ─── Pure-Python technical indicator helpers ───────────────────────────────────

def _ema(prices, period):
    """Exponential Moving Average."""
    if len(prices) < period:
        return sum(prices) / len(prices)
    k = 2.0 / (period + 1)
    ema = sum(prices[:period]) / period
    for p in prices[period:]:
        ema = p * k + ema * (1 - k)
    return ema

def _rsi(prices, period=14):
    """Relative Strength Index (0-100)."""
    if len(prices) < period + 1:
        return 50.0  # neutral default
    deltas = [prices[i+1] - prices[i] for i in range(len(prices)-1)]
    gains  = [max(d, 0) for d in deltas[-period:]]
    losses = [abs(min(d, 0)) for d in deltas[-period:]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1 + rs))

def _vol_surge(volumes, window=10, threshold=1.4):
    """True if recent 5-bar volume is above threshold × 10-bar average."""
    if len(volumes) < window:
        return False
    avg = sum(volumes[-window:]) / window
    recent = sum(volumes[-5:]) / 5
    return avg > 0 and recent > avg * threshold

# ─── Constants ─────────────────────────────────────────────────────────────────
SYMBOLS       = ['BTC', 'ETH', 'SOL']
FAST          = 8      # fast EMA period
SLOW          = 21     # slow EMA period
RSI_PERIOD    = 14
RSI_BUY_MAX   = 65     # don't buy if RSI above this (overbought)
RSI_SELL_MIN  = 35     # don't short if RSI below this (oversold)
TAKE_PROFIT   = 0.025  # 2.5% gain → take profit
STOP_LOSS     = 0.018  # 1.8% loss → stop loss
TRAIL_PCT     = 0.012  # 1.2% trailing stop from peak
POSITION_PCT  = 0.28   # use 28% of cash per position (max ~3 positions)
COOLDOWN      = 12     # minimum ticks between buys per symbol
MIN_HISTORY   = 25     # need at least 25 bars before trading

# ─── State keys stored inside agent_state['custom'] ────────────────────────────
# peak[sym]       – highest price seen while in a long position
# last_buy[sym]   – tick of last buy for cooldown
# entry[sym]      – entry price for the position


def execute_strategy(market_data, tick, cash_balance, portfolio,
                     market_state=None, agent_state=None):
    """
    Apex Crypto – multi-signal long-only strategy for BTC / ETH / SOL.

    Entry  : fast EMA > slow EMA (uptrend) AND RSI not overbought AND volume surge
    Exit   : trailing stop hit OR take-profit hit OR trend reversal (fast < slow)
    Sizing : fixed 28 % of available cash per position (max 3 open at once)
    """
    if agent_state is None:
        agent_state = {}

    custom = agent_state.get('custom', {})
    if not isinstance(custom, dict):
        custom = {}

    decisions = []   # collect (action, sym, qty)

    # ── 1. EXIT LOGIC (check every open position) ──────────────────────────────
    for sym in SYMBOLS:
        qty = portfolio.get(sym, 0)
        if qty <= 0:
            continue

        data = market_data.get(sym, {})
        price = data.get('price', 0)
        history = data.get('history', [])
        if price <= 0:
            continue

        entry = custom.get(f'entry_{sym}', price)
        peak  = custom.get(f'peak_{sym}',  price)

        # Update trailing peak
        if price > peak:
            peak = price
            custom[f'peak_{sym}'] = peak

        gain_pct = (price - entry) / entry if entry > 0 else 0
        drop_from_peak = (peak - price) / peak if peak > 0 else 0

        sell = False
        reason = ''

        # Hard stop loss
        if gain_pct <= -STOP_LOSS:
            sell = True
            reason = 'STOP_LOSS'

        # Trailing stop (only triggers after we've gained ≥ 0.5%)
        elif gain_pct > 0.005 and drop_from_peak >= TRAIL_PCT:
            sell = True
            reason = 'TRAIL_STOP'

        # Take profit
        elif gain_pct >= TAKE_PROFIT:
            sell = True
            reason = 'TAKE_PROFIT'

        # Trend reversal exit
        elif len(history) >= SLOW:
            fast_ema = _ema(history, FAST)
            slow_ema = _ema(history, SLOW)
            if fast_ema < slow_ema * 0.999:  # fast crossed below slow
                sell = True
                reason = 'TREND_REVERSAL'

        if sell:
            print(f"[Apex] EXIT {sym} qty={qty:.4f} reason={reason} gain={gain_pct*100:.2f}%", flush=True)
            custom[f'peak_{sym}']  = 0
            custom[f'entry_{sym}'] = 0
            return ('SELL', sym, qty)

    # ── 2. ENTRY LOGIC (find best opportunity) ─────────────────────────────────
    # Count open positions
    open_positions = sum(1 for s in SYMBOLS if portfolio.get(s, 0) > 0)

    # Hard cap: no more than 2 positions at once to keep cash reserve
    if open_positions >= 2:
        agent_state['custom'] = custom
        return ('HOLD', None, 0)

    best_sym   = None
    best_score = 0.0

    for sym in SYMBOLS:
        if portfolio.get(sym, 0) > 0:
            continue  # already in this position

        data = market_data.get(sym, {})
        if not data:
            continue

        price   = data.get('price', 0)
        history = data.get('history', [])
        volumes = data.get('volumes', [])

        if price <= 0 or len(history) < MIN_HISTORY:
            continue

        # Cooldown: don't re-enter too quickly
        last_buy = custom.get(f'last_buy_{sym}', 0)
        if tick - last_buy < COOLDOWN:
            continue

        # Indicators
        fast_ema = _ema(history, FAST)
        slow_ema = _ema(history, SLOW)
        rsi      = _rsi(history, RSI_PERIOD)
        vol_ok   = _vol_surge(volumes) if volumes else True  # if no vol data, relax filter

        # Trend strength: how much is fast above slow?
        trend_strength = (fast_ema - slow_ema) / slow_ema if slow_ema > 0 else 0

        # Conditions
        uptrend    = fast_ema > slow_ema
        rsi_ok     = rsi < RSI_BUY_MAX       # not overbought
        rsi_strong = rsi > 40                # some momentum

        if uptrend and rsi_ok and rsi_strong and trend_strength > 0.0005:
            # Score: combine trend strength + volume confirmation + RSI momentum
            score = trend_strength * 1000
            if vol_ok:
                score *= 1.5
            score += (rsi - 40) / 30.0     # add RSI momentum bonus

            if score > best_score:
                best_score = score
                best_sym = sym

    if best_sym and cash_balance > 100:
        price = market_data[best_sym]['price']
        qty = (cash_balance * POSITION_PCT) / price

        if qty > 0:
            custom[f'entry_{best_sym}']    = price
            custom[f'peak_{best_sym}']     = price
            custom[f'last_buy_{best_sym}'] = tick
            agent_state['custom'] = custom
            print(f"[Apex] ENTER {best_sym} qty={qty:.4f} @ {price:.2f} score={best_score:.4f}", flush=True)
            return ('BUY', best_sym, qty)

    agent_state['custom'] = custom
    return ('HOLD', None, 0)
