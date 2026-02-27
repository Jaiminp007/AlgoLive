# --- Tempest Momentum: Trend Surfing Strategy ---
# Catches strong momentum waves using CVD divergence and order flow
# OPTIMIZED: Reduced position size, increased cooldown, wider targets
import numpy as np
import pandas as pd

_last_trade_tick = 0
_trend_lock = None  # Lock onto a trend direction

def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    '''
    Tempest Momentum: Rides strong trends using momentum indicators.
    Waits for multiple confirmation signals before entering.
    '''
    global _last_trade_tick, _trend_lock
    
    if agent_state is None:
        agent_state = {'entry_prices': {}, 'current_pnl': {}, 'custom': {}}
    
    # Trade high-momentum assets
    symbols = ['BTC', 'ETH', 'SOL', 'NVDA', 'TSLA']
    
    # INCREASED COOLDOWN: 180 ticks (3 minutes) to reduce overtrading
    if tick - _last_trade_tick < 180:
        return ("HOLD", None, 0)
    
    # === EXIT LOGIC ===
    for sym in symbols:
        qty = portfolio.get(sym, 0)
        if qty == 0:
            continue
        
        pnl_info = agent_state.get('current_pnl', {}).get(sym, {})
        pnl_pct = pnl_info.get('pnl_percent', 0) / 100.0
        
        data = market_data.get(sym, {})
        cvd = data.get('cvd_divergence', 0) or 0
        
        # WIDER PROFIT TARGET: 1.2% (must exceed 2x transaction costs)
        momentum_reversal = (qty > 0 and cvd < -0.3) or (qty < 0 and cvd > 0.3)
        
        if pnl_pct > 0.012:
            _last_trade_tick = tick
            _trend_lock = None
            action = "SELL" if qty > 0 else "BUY"
            return (action, sym, abs(qty))
        
        # Exit on momentum reversal with decent profit (0.5%)
        if momentum_reversal and pnl_pct > 0.005:
            _last_trade_tick = tick
            _trend_lock = None
            action = "SELL" if qty > 0 else "BUY"
            return (action, sym, abs(qty))
        
        # WIDER STOP LOSS: -0.8% (give trades room to breathe)
        if pnl_pct < -0.008:
            _last_trade_tick = tick
            _trend_lock = None
            action = "SELL" if qty > 0 else "BUY"
            return (action, sym, abs(qty))
    
    # === ENTRY LOGIC: Momentum Wave Detection ===
    best_sym = None
    best_score = 0
    
    for sym in symbols:
        if portfolio.get(sym, 0) != 0:
            continue
        
        data = market_data.get(sym, {})
        if not data:
            continue
        
        price = data.get('price', 0)
        if price <= 0:
            continue
        
        # Gather momentum signals
        obi = data.get('obi_weighted', 0) or 0
        ofi = data.get('ofi', 0) or 0
        cvd = data.get('cvd_divergence', 0) or 0
        taker_ratio = data.get('taker_ratio', 1.0) or 1.0
        sentiment = data.get('sentiment', 0) or 0
        parkinson_vol = data.get('parkinson_vol', 0) or 0
        
        # Score-based entry
        score = 0
        
        # Order book signals
        if obi > 0.15:
            score += 1.5
        elif obi < -0.15:
            score -= 1.5
        
        # Order flow imbalance
        if ofi > 20:
            score += 1
        elif ofi < -20:
            score -= 1
        
        # CVD divergence (strong trend indicator)
        if cvd > 0.4:
            score += 1.5
        elif cvd < -0.4:
            score -= 1.5
        
        # Taker ratio (aggressive buying/selling)
        if taker_ratio > 1.2:
            score += 1
        elif taker_ratio < 0.8:
            score -= 1
        
        # Sentiment boost
        if sentiment > 0.3:
            score += 0.5
        elif sentiment < -0.3:
            score -= 0.5
        
        # Volatility filter: Prefer medium volatility
        if 0.01 < parkinson_vol < 0.03:
            score *= 1.2
        elif parkinson_vol > 0.04:
            score *= 0.8  # Too volatile, reduce confidence
        
        # Price trend confirmation using history
        prices = data.get('history', [])
        if len(prices) >= 20:
            sma_10 = np.mean(prices[-10:])
            sma_20 = np.mean(prices[-20:])
            if price > sma_10 > sma_20:  # Uptrend
                score += 0.5
            elif price < sma_10 < sma_20:  # Downtrend
                score -= 0.5
        
        if abs(score) > abs(best_score):
            best_score = score
            best_sym = sym
    
    # Enter only on VERY strong signals (score >= 4 or <= -4)
    if best_sym and abs(best_score) >= 4:
        price = market_data[best_sym]['price']
        
        # REDUCED POSITION SIZE: 6% of cash (was 20%)
        qty = (cash_balance * 0.06) / price
        
        _last_trade_tick = tick
        _trend_lock = 'LONG' if best_score > 0 else 'SHORT'
        
        if best_score > 0:
            return ("BUY", best_sym, qty)
        else:
            return ("SELL", best_sym, qty)
    
    return ("HOLD", None, 0)
