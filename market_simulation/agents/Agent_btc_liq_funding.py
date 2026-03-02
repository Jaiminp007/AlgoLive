# --- BTC Liquidation & Funding Arbitrage ---
# Adapts the provided robust strategy into the Algoclash format.
# 1) Detects volume spikes & price dislocations (catching knives)
# 2) Emulates a ladder of limit buys by using virtual entries
# 3) Evaluates sentiment / funding velocity for risk bounds.
import math

# ─── Pure-Python technical indicator proxies ───────────────────────────────────

def _ema(prices, period):
    if len(prices) < period:
        return sum(prices) / max(len(prices), 1)
    k = 2.0 / (period + 1)
    ema_val = sum(prices[:period]) / period
    for p in prices[period:]:
        ema_val = p * k + ema_val * (1 - k)
    return ema_val

def _atr_proxy(prices, period=14):
    """Approximates ATR using absolute close-to-close differences."""
    if len(prices) < period + 1:
        return prices[-1] * 0.01 if prices else 0.01
    trs = [abs(prices[i] - prices[i-1]) for i in range(1, len(prices))]
    avg = sum(trs[-period:]) / period
    return max(avg, 1e-9)

def _vwap(prices, volumes, lookback=60):
    if len(prices) == 0:
        return 0.0
    lb = min(len(prices), lookback)
    sub_p = prices[-lb:]
    sub_v = volumes[-lb:]
    pv = sum(p * v for p, v in zip(sub_p, sub_v))
    v_total = sum(sub_v)
    return pv / v_total if v_total > 0 else sub_p[-1]

def _zscore(series, lookback=60):
    if len(series) < 2:
        return 0.0
    lb = min(len(series), lookback)
    sub = series[-lb:]
    mu = sum(sub) / lb
    var = sum((x - mu)**2 for x in sub) / lb
    sd = math.sqrt(var)
    if sd == 0:
        return 0.0
    return (sub[-1] - mu) / sd

# ─── Constants ─────────────────────────────────────────────────────────────────
SYMBOLS = ['BTC', 'ETH', 'SOL']

# Liquidation & Entry
VWAP_LB = 60
ATR_LB = 14
VOL_Z_THRESH = 2.0
DISLOC_ATR_THRESH = 1.2

# Synthetic Ladder (Tiers of dislocation to catch knives)
LADDER_LEVELS = [1.5, 2.5, 3.5]
LADDER_WEIGHTS = [0.5, 0.3, 0.2]
LADDER_TTL = 20  # Ticks (minutes) to keep virtual orders alive

# Risk Sizing
RISK_PER_TRADE = 0.01
MAX_POS_PCT = 0.35
STOP_ATR_MULT = 1.2
MAX_STOP_PCT = 0.03
TRAIL_ACTIVATE = 0.8
TRAIL_ATR = 0.6
TIME_STOP_TICKS = 240

# Risk Off Adjustments
SENTIMENT_RISK_OFF = -0.3   # Natively provided sentiment score < -0.3 is risk-off
DEPTH_MULT_RISK = 1.5       # Require deeper dislocation in bad sentiment
SIZE_MULT_RISK = 0.25       # Reduce size in bad sentiment

def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    if agent_state is None:
        agent_state = {}
    custom = agent_state.get('custom', {})
    if not isinstance(custom, dict):
        custom = {}

    # Track how long the algo has been live
    if 'algo_start_tick' not in custom:
        custom['algo_start_tick'] = tick
        print(f"[BTC_Liq] Agent INITIALIZED at tick {tick}")
        
    algo_live_ticks = tick - custom['algo_start_tick']
    
    # Log uptime every 60 ticks (approx 1 hour if 1 tick = 1 min, or 1 min if 1 tick = 1 sec)
    if algo_live_ticks > 0 and algo_live_ticks % 60 == 0:
        print(f"[BTC_Liq] UPTIME: Algorithm has been live for {algo_live_ticks} ticks.")

    # Check open positions / manage them
    for sym in SYMBOLS:
        qty = portfolio.get(sym, 0)
        data = market_data.get(sym, {})
        if not data or qty <= 0:
            continue
            
        price = data.get('price', 0)
        history = data.get('history', [])
        if price <= 0 or not history:
            continue
            
        entry_price = custom.get(f'entry_price_{sym}', price)
        entry_tick = custom.get(f'entry_tick_{sym}', tick)
        peak_price = custom.get(f'peak_price_{sym}', price)
        pos_atr = custom.get(f'pos_atr_{sym}', 0.0)
        
        if price > peak_price:
            peak_price = price
            custom[f'peak_price_{sym}'] = peak_price
            
        # Hard Stop Loss
        stop_dist = min(STOP_ATR_MULT * pos_atr, entry_price * MAX_STOP_PCT)
        stop_px = entry_price - stop_dist
        
        # Trailing Take Profit
        activate_px = entry_price + (TRAIL_ACTIVATE * pos_atr)
        trail_px = peak_price - (TRAIL_ATR * pos_atr)
        
        sell_reason = None
        if price <= stop_px:
            sell_reason = "HARD_STOP"
        elif peak_price >= activate_px and price <= trail_px:
            sell_reason = "TRAIL_STOP"
        elif tick - entry_tick >= TIME_STOP_TICKS:
            sell_reason = "TIME_STOP"
            
        # Funding Norm Exit (if funding flipped positive or stopped bleeding)
        funding_vel = data.get('funding_rate_velocity', 0)
        if funding_vel > 0 and price >= entry_price * 1.001:
            sell_reason = "FUNDING_NORM_EXIT"
            
        if sell_reason:
            print(f"[BTC_Liq] EXIT {sym} @ {price:.2f} due to {sell_reason}")
            # Clear state on exit
            custom[f'entry_price_{sym}'] = 0
            custom[f'peak_price_{sym}'] = 0
            custom[f'pos_atr_{sym}'] = 0
            agent_state['custom'] = custom
            return ("SELL", sym, qty)

    # We evaluate entry if we have no active ladder and no existing position
    open_positions = sum(1 for s in SYMBOLS if portfolio.get(s, 0) > 0)
    has_active_ladders = any(len(custom.get(f'ladder_{s}', [])) > 0 for s in SYMBOLS)
    
    if open_positions > 0 or has_active_ladders:
        # Check active virtual ladders if we have cash
        for sym in SYMBOLS:
            ladder = custom.get(f'ladder_{sym}', [])
            if not ladder or portfolio.get(sym, 0) > 0:
                continue
                
            data = market_data.get(sym, {})
            price = data.get('price', 0)
            if price <= 0:
                continue
                
            # Filter expired ladders
            valid_ladder = []
            trade_qty = 0
            # Ladder is a list of dicts: {'price': px, 'qty': q, 'expire': tick}
            for tier in ladder:
                if tick > tier['expire']:
                    continue
                if price <= tier['price'] and cash_balance > 0:
                    # Catch the knife
                    available_cash = cash_balance - (trade_qty * price)
                    qty_to_buy = min(tier['qty'], available_cash / price)
                    if qty_to_buy > 0:
                        trade_qty += qty_to_buy
                else:
                    valid_ladder.append(tier)
                    
            if trade_qty > 0:
                # Execute Market Buy
                print(f"[BTC_Liq] LADDER FILL {sym} qty={trade_qty:.4f}")
                custom[f'ladder_{sym}'] = valid_ladder
                custom[f'entry_price_{sym}'] = price
                custom[f'peak_price_{sym}'] = price
                custom[f'entry_tick_{sym}'] = tick
                custom[f'pos_atr_{sym}'] = _atr_proxy(data.get('history', []))
                agent_state['custom'] = custom
                return ("BUY", sym, trade_qty)
                
            custom[f'ladder_{sym}'] = valid_ladder
            
        agent_state['custom'] = custom
        return ("HOLD", None, 0)

    # ─── Liquidation Detection & Ladder Placement ───
    best_sym = None
    best_disloc = 0
    best_atr = 0
    risk_off = False
    
    for sym in SYMBOLS:
        data = market_data.get(sym, {})
        history = data.get('history', [])
        volumes = data.get('volumes', [])
        price = data.get('price', 0)
        
        if len(history) < VWAP_LB or price <= 0:
            continue
            
        sentiment = data.get('sentiment', 0.0)
        is_risk_off = sentiment < SENTIMENT_RISK_OFF
        
        # Calculate proxies
        atr_val = _atr_proxy(history, ATR_LB)
        vwap_val = _vwap(history, volumes, VWAP_LB)
        vol_z = _zscore(volumes, VWAP_LB)
        
        dislocation = (vwap_val - price) / atr_val if atr_val > 0 else 0
        
        # Event Trigger
        if vol_z >= VOL_Z_THRESH and dislocation >= DISLOC_ATR_THRESH:
            if dislocation > best_disloc:
                best_disloc = dislocation
                best_sym = sym
                best_atr = atr_val
                risk_off = is_risk_off

    # Place Virtual Ladder
    if best_sym and best_atr > 0:
        data = market_data.get(best_sym, {})
        price = data.get('price', 0)
        
        depth_mult = DEPTH_MULT_RISK if risk_off else 1.0
        size_mult = SIZE_MULT_RISK if risk_off else 1.0
        
        stop_dist = min(STOP_ATR_MULT * best_atr, price * MAX_STOP_PCT)
        if stop_dist > 0:
            # Approx equity as cash + portfolio value (if any)
            # Since we only place ladder if 0 positions, equity is roughly cash
            risk_usd = cash_balance * RISK_PER_TRADE
            max_pos_usd = cash_balance * MAX_POS_PCT
            
            qty_by_risk = risk_usd / stop_dist
            qty_by_max = max_pos_usd / max(price, 1e-9)
            base_qty = min(qty_by_risk, qty_by_max) * size_mult
            
            if base_qty * price > 10:  # Avoid dust ladders
                ladder_tiers = []
                for k, w in zip(LADDER_LEVELS, LADDER_WEIGHTS):
                    tier_px = price - (k * best_atr * depth_mult)
                    tier_qty = base_qty * w
                    if tier_px > 0 and tier_qty > 0:
                        ladder_tiers.append({
                            'price': tier_px,
                            'qty': tier_qty,
                            'expire': tick + LADDER_TTL
                        })
                if ladder_tiers:
                    custom[f'ladder_{best_sym}'] = ladder_tiers
                    print(f"[BTC_Liq] PLACING LADDER for {best_sym} (Disloc: {best_disloc:.2f})")
                    
    agent_state['custom'] = custom
    return ("HOLD", None, 0)
