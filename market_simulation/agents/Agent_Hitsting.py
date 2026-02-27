# --- Hydra Correlation: Multi-Asset Arbitrage ---
# Exploits correlations between crypto assets and cross-market signals
# OPTIMIZED: Wider targets, reduced position size, better cooldowns
import numpy as np
import pandas as pd

_last_trade_tick = 0
_spread_history = []  # Track BTC/ETH spread for mean reversion

def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    '''
    Hydra Correlation: Multi-headed strategy that exploits cross-asset relationships.
    1. BTC/ETH spread mean reversion
    2. Risk-on/risk-off regime detection
    3. Relative strength rotation
    '''
    global _last_trade_tick, _spread_history
    
    if agent_state is None:
        agent_state = {'entry_prices': {}, 'current_pnl': {}, 'custom': {}}
    
    # Core assets for correlation trading
    crypto_core = ['BTC', 'ETH', 'SOL']
    risk_assets = ['NVDA', 'TSLA']  # High-beta stocks
    all_symbols = crypto_core + risk_assets
    
    # INCREASED COOLDOWN: 200 ticks (~3.3 minutes, was 50)
    if tick - _last_trade_tick < 200:
        return ("HOLD", None, 0)
    
    # === EXIT LOGIC ===
    for sym in all_symbols:
        qty = portfolio.get(sym, 0)
        if qty == 0:
            continue
        
        pnl_info = agent_state.get('current_pnl', {}).get(sym, {})
        pnl_pct = pnl_info.get('pnl_percent', 0) / 100.0
        
        # WIDER PROFIT TARGET: 1.0% (was 0.55%)
        if pnl_pct > 0.01:
            _last_trade_tick = tick
            action = "SELL" if qty > 0 else "BUY"
            return (action, sym, abs(qty))
        
        # WIDER STOP LOSS: -0.7% (was -0.35%)
        if pnl_pct < -0.007:
            _last_trade_tick = tick
            action = "SELL" if qty > 0 else "BUY"
            return (action, sym, abs(qty))
    
    # === STRATEGY 1: BTC/ETH Spread Mean Reversion ===
    btc_data = market_data.get('BTC', {})
    eth_data = market_data.get('ETH', {})
    
    btc_price = btc_data.get('price', 0)
    eth_price = eth_data.get('price', 0)
    
    spread_signal = None
    if btc_price > 0 and eth_price > 0:
        # BTC/ETH ratio (normally around 15-20)
        ratio = btc_price / eth_price
        _spread_history.append(ratio)
        
        # Keep limited history
        if len(_spread_history) > 100:
            _spread_history = _spread_history[-100:]
        
        if len(_spread_history) >= 30:
            mean_ratio = np.mean(_spread_history)
            std_ratio = np.std(_spread_history)
            
            if std_ratio > 0:
                z_score = (ratio - mean_ratio) / std_ratio
                
                # Trade spread extremes
                if z_score > 1.5:  # BTC outperforming -> Buy ETH (expect reversion)
                    spread_signal = ('ETH', 'BUY', abs(z_score))
                elif z_score < -1.5:  # ETH outperforming -> Buy BTC
                    spread_signal = ('BTC', 'BUY', abs(z_score))
    
    # === STRATEGY 2: Regime Detection (Risk-On vs Risk-Off) ===
    regime_signal = None
    
    # Use BTC as risk barometer
    btc_obi = btc_data.get('obi_weighted', 0) or 0
    btc_cvd = btc_data.get('cvd_divergence', 0) or 0
    btc_sentiment = btc_data.get('sentiment', 0) or 0
    
    regime_score = btc_obi + (btc_cvd * 0.5) + (btc_sentiment * 0.3)
    
    if regime_score > 0.5:  # Risk-On -> Buy high-beta assets
        # Find the strongest high-beta asset
        for sym in ['NVDA', 'TSLA', 'SOL']:
            if portfolio.get(sym, 0) != 0:
                continue
            
            data = market_data.get(sym, {})
            sym_obi = data.get('obi_weighted', 0) or 0
            
            if sym_obi > 0.1:
                regime_signal = (sym, 'BUY', regime_score)
                break
    
    elif regime_score < -0.5:  # Risk-Off -> Short high-beta
        for sym in ['TSLA', 'NVDA']:  # More volatile stocks
            if portfolio.get(sym, 0) != 0:
                continue
            
            data = market_data.get(sym, {})
            sym_obi = data.get('obi_weighted', 0) or 0
            
            if sym_obi < -0.1:
                regime_signal = (sym, 'SELL', abs(regime_score))
                break
    
    # === STRATEGY 3: Relative Strength Rotation ===
    rs_signal = None
    
    # Calculate relative strength for each crypto
    rs_scores = {}
    for sym in crypto_core:
        if portfolio.get(sym, 0) != 0:
            continue
        
        data = market_data.get(sym, {})
        prices = data.get('history', [])
        
        if len(prices) >= 20:
            # 10-period return vs 20-period return
            ret_10 = (prices[-1] - prices[-10]) / prices[-10] if prices[-10] != 0 else 0
            ret_20 = (prices[-1] - prices[-20]) / prices[-20] if prices[-20] != 0 else 0
            
            # RS score: recent momentum + acceleration
            rs = ret_10 + (ret_10 - ret_20)
            rs_scores[sym] = rs
    
    if rs_scores:
        # Find strongest and weakest
        strongest = max(rs_scores, key=rs_scores.get)
        weakest = min(rs_scores, key=rs_scores.get)
        
        if rs_scores[strongest] > 0.01:  # Positive momentum
            rs_signal = (strongest, 'BUY', rs_scores[strongest])
        elif rs_scores[weakest] < -0.01:  # Negative momentum
            rs_signal = (weakest, 'SELL', abs(rs_scores[weakest]))
    
    # === COMBINE SIGNALS ===
    # Prioritize by signal strength
    signals = []
    
    if spread_signal:
        sym, action, strength = spread_signal
        if portfolio.get(sym, 0) == 0:
            signals.append((sym, action, strength * 1.5, 'spread'))  # Weight spread signals
    
    if regime_signal:
        sym, action, strength = regime_signal
        if portfolio.get(sym, 0) == 0:
            signals.append((sym, action, strength * 1.2, 'regime'))
    
    if rs_signal:
        sym, action, strength = rs_signal
        if portfolio.get(sym, 0) == 0:
            signals.append((sym, action, strength * 100, 'rs'))  # Scale RS to comparable range
    
    # Execute the strongest signal
    if signals:
        signals.sort(key=lambda x: x[2], reverse=True)
        best = signals[0]
        sym, action, strength, strategy = best
        
        # INCREASED minimum strength requirement (was 0.8)
        min_strength = 1.2
        if strength >= min_strength:
            price = market_data.get(sym, {}).get('price', 0)
            if price > 0:
                # REDUCED POSITION SIZE: 6% of cash (was 18%)
                qty = (cash_balance * 0.06) / price
                
                _last_trade_tick = tick
                
                return (action, sym, qty)
    
    return ("HOLD", None, 0)