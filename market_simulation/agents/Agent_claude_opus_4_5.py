# --- Institutional-Grade HFT Algorithm ---
# Fuses DeepLOB (OBI), Stoikov (Micro-Price), Order Flow, and NLP Signals
# Supports Long & Short positions with State-Based Regime Detection

import numpy as np

# Module-level counter (safe - just tracks ticks)
_last_trade_tick = 0


def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    """
    Institutional-grade algo with multi-signal fusion and state persistence.
    
    Signal Categories:
    1. MICROSTRUCTURE: obi_weighted, micro_price, ofi
    2. MARKET INTERNALS: funding_rate_velocity, cvd_divergence, taker_ratio, parkinson_vol
    3. SEMANTIC/ATTENTION: sentiment, attention
    
    Args:
        market_data: Dict of symbol -> signal data
        tick: Current tick number
        cash_balance: Available cash
        portfolio: Dict of symbol -> quantity held
        market_state: Optional market regime info
        agent_state: Persistent state dict (entry_prices, current_pnl, custom)
    
    Returns:
        Tuple of (ACTION, SYMBOL, QUANTITY)
    """
    global _last_trade_tick
    
    # === INITIALIZATION ===
    if agent_state is None:
        agent_state = {'entry_prices': {}, 'current_pnl': {}, 'custom': {}}
    
    # Initialize custom state for tracking
    custom = agent_state.get('custom', {})
    if 'peak_prices' not in custom:
        custom['peak_prices'] = {}
    if 'volume_history' not in custom:
        custom['volume_history'] = {'BTC': [], 'ETH': [], 'SOL': []}
    if 'regime' not in custom:
        custom['regime'] = 'NEUTRAL'  # BULLISH, BEARISH, NEUTRAL, VOLATILE
    agent_state['custom'] = custom
    
    # Target symbols (best liquidity)
    SYMBOLS = ['BTC', 'ETH', 'SOL']
    
    # === CONFIGURATION ===
    CONFIG = {
        'cooldown_ticks': 60,
        'position_size_pct': 0.20,      # 20% of cash per trade
        'take_profit_pct': 0.005,       # 0.50% (beats 0.20% round-trip costs)
        'stop_loss_pct': -0.003,        # -0.30%
        'trailing_stop_pct': 0.02,      # 2% from peak
        'volume_spike_multiplier': 1.5, # Entry only on volume spikes
        'min_entry_score': 2,           # Minimum conviction for entry
        'max_volatility': 0.05,         # Skip entry if Parkinson vol too high
    }
    
    # === COOLDOWN CHECK ===
    if tick - _last_trade_tick < CONFIG['cooldown_ticks']:
        return ("HOLD", None, 0)
    
    # === PHASE 1: EXIT MANAGEMENT (Priority) ===
    exit_signal = _check_exits(
        SYMBOLS, portfolio, market_data, agent_state, custom, tick, CONFIG
    )
    if exit_signal[0] != "HOLD":
        _last_trade_tick = tick
        return exit_signal
    
    # === PHASE 2: REGIME DETECTION ===
    regime = _detect_regime(SYMBOLS, market_data, custom)
    custom['regime'] = regime
    
    # === PHASE 3: ENTRY SIGNALS ===
    entry_signal = _find_best_entry(
        SYMBOLS, portfolio, market_data, cash_balance, custom, regime, CONFIG
    )
    if entry_signal[0] != "HOLD":
        _last_trade_tick = tick
        # Update peak price tracking for new position
        sym = entry_signal[1]
        price = market_data.get(sym, {}).get('price', 0)
        custom['peak_prices'][sym] = price
        return entry_signal
    
    return ("HOLD", None, 0)


def _check_exits(symbols, portfolio, market_data, agent_state, custom, tick, config):
    """
    Multi-layered exit logic:
    1. Take Profit (>0.50%)
    2. Stop Loss (<-0.30%)
    3. Trailing Stop (2% from peak)
    4. Signal Reversal Exit
    """
    current_pnl = agent_state.get('current_pnl', {})
    peak_prices = custom.get('peak_prices', {})
    
    for sym in symbols:
        qty = portfolio.get(sym, 0)
        if qty == 0:
            continue
        
        data = market_data.get(sym, {})
        if not data:
            continue
            
        price = data.get('price', 0)
        if price <= 0:
            continue
        
        # Get P&L info from agent_state (reliable source)
        pnl_info = current_pnl.get(sym, {})
        pnl_pct = pnl_info.get('pnl_percent', 0) / 100.0  # Convert % to decimal
        
        # Determine position direction
        is_long = qty > 0
        
        # --- EXIT CONDITION 1: TAKE PROFIT ---
        if pnl_pct > config['take_profit_pct']:
            action = "SELL" if is_long else "BUY"
            return (action, sym, abs(qty))
        
        # --- EXIT CONDITION 2: STOP LOSS ---
        if pnl_pct < config['stop_loss_pct']:
            action = "SELL" if is_long else "BUY"
            return (action, sym, abs(qty))
        
        # --- EXIT CONDITION 3: TRAILING STOP ---
        if sym in peak_prices:
            peak = peak_prices[sym]
            
            # Update peak for long positions
            if is_long and price > peak:
                peak_prices[sym] = price
                peak = price
            # Update peak (trough) for short positions
            elif not is_long and price < peak:
                peak_prices[sym] = price
                peak = price
            
            # Check trailing stop
            if is_long:
                drawdown = (peak - price) / peak
                if drawdown > config['trailing_stop_pct']:
                    return ("SELL", sym, abs(qty))
            else:  # Short position
                drawup = (price - peak) / peak
                if drawup > config['trailing_stop_pct']:
                    return ("BUY", sym, abs(qty))
        
        # --- EXIT CONDITION 4: SIGNAL REVERSAL ---
        # Exit long if signals turn strongly bearish (and vice versa)
        obi = data.get('obi_weighted', 0)
        ofi = data.get('ofi', 0)
        sentiment = data.get('sentiment', 0)
        
        if is_long and obi < -0.3 and ofi < -50 and sentiment < -0.5:
            # Strong bearish reversal - exit long
            if pnl_pct > 0:  # Only if profitable
                return ("SELL", sym, abs(qty))
        
        elif not is_long and obi > 0.3 and ofi > 50 and sentiment > 0.5:
            # Strong bullish reversal - exit short
            if pnl_pct > 0:
                return ("BUY", sym, abs(qty))
    
    return ("HOLD", None, 0)


def _detect_regime(symbols, market_data, custom):
    """
    Detect market regime using aggregate signals.
    Returns: BULLISH, BEARISH, NEUTRAL, or VOLATILE
    """
    bullish_count = 0
    bearish_count = 0
    volatility_sum = 0
    valid_symbols = 0
    
    for sym in symbols:
        data = market_data.get(sym, {})
        if not data:
            continue
        
        valid_symbols += 1
        
        # Aggregate directional signals
        obi = data.get('obi_weighted', 0)
        sentiment = data.get('sentiment', 0)
        cvd_div = data.get('cvd_divergence', 0)
        funding_vel = data.get('funding_rate_velocity', 0)
        
        if obi > 0.1 and sentiment > 0:
            bullish_count += 1
        elif obi < -0.1 and sentiment < 0:
            bearish_count += 1
        
        # Track volatility
        parkinson_vol = data.get('parkinson_vol', 0)
        volatility_sum += parkinson_vol
    
    if valid_symbols == 0:
        return 'NEUTRAL'
    
    avg_vol = volatility_sum / valid_symbols
    
    # High volatility regime
    if avg_vol > 0.04:
        return 'VOLATILE'
    
    # Directional regimes
    if bullish_count >= 2:
        return 'BULLISH'
    elif bearish_count >= 2:
        return 'BEARISH'
    
    return 'NEUTRAL'


def _find_best_entry(symbols, portfolio, market_data, cash_balance, custom, regime, config):
    """
    Multi-signal fusion for entry decisions.
    
    Scoring System:
    - OBI (Order Book Imbalance): ±2 points
    - OFI (Order Flow Imbalance): ±2 points
    - Fair Value Gap (Micro-price): ±2 points
    - Sentiment: ±1 point
    - Attention: ±1 point
    - Funding Rate Velocity: ±1 point
    - CVD Divergence: ±1 point
    - Taker Ratio: ±1 point
    
    Entry requires |score| >= min_entry_score
    """
    best_symbol = None
    best_score = 0
    best_price = 0
    
    volume_history = custom.get('volume_history', {})
    
    for sym in symbols:
        # Skip if already in position
        if portfolio.get(sym, 0) != 0:
            continue
        
        data = market_data.get(sym, {})
        if not data:
            continue
        
        price = data.get('price', 0)
        volume = data.get('volume', 0)
        
        if price <= 0:
            continue
        
        # === VOLUME SPIKE FILTER ===
        vol_hist = volume_history.get(sym, [])
        vol_hist.append(volume)
        if len(vol_hist) > 20:
            vol_hist = vol_hist[-20:]
        volume_history[sym] = vol_hist
        
        if len(vol_hist) >= 5:
            avg_volume = np.mean(vol_hist[:-1])  # Exclude current
            if avg_volume > 0 and volume < avg_volume * config['volume_spike_multiplier']:
                continue  # Skip - no volume confirmation
        
        # === VOLATILITY FILTER ===
        parkinson_vol = data.get('parkinson_vol', 0)
        if parkinson_vol > config['max_volatility']:
            continue  # Too volatile - skip
        
        # === SIGNAL SCORING ===
        score = 0
        
        # 1. ORDER BOOK IMBALANCE (DeepLOB) - High weight
        obi = data.get('obi_weighted', 0)
        if obi > 0.2:
            score += 2
        elif obi > 0.1:
            score += 1
        elif obi < -0.2:
            score -= 2
        elif obi < -0.1:
            score -= 1
        
        # 2. ORDER FLOW IMBALANCE - High weight
        ofi = data.get('ofi', 0)
        if ofi > 50:
            score += 2
        elif ofi > 20:
            score += 1
        elif ofi < -50:
            score -= 2
        elif ofi < -20:
            score -= 1
        
        # 3. FAIR VALUE GAP (Stoikov Micro-Price) - High weight
        micro_price = data.get('micro_price', price)
        fv_gap_pct = (micro_price - price) / price if price > 0 else 0
        
        if fv_gap_pct > 0.002:  # Undervalued by 0.2%+
            score += 2
        elif fv_gap_pct > 0.001:
            score += 1
        elif fv_gap_pct < -0.002:  # Overvalued
            score -= 2
        elif fv_gap_pct < -0.001:
            score -= 1
        
        # 4. SENTIMENT (NLP) - Medium weight
        sentiment = data.get('sentiment', 0)
        if sentiment > 0.5:
            score += 1
        elif sentiment > 0.2:
            score += 0.5
        elif sentiment < -0.5:
            score -= 1
        elif sentiment < -0.2:
            score -= 0.5
        
        # 5. ATTENTION (Search Volume) - Low weight
        attention = data.get('attention', 1.0)
        if attention > 1.5:
            score += 1
        elif attention < 0.5:
            score -= 0.5
        
        # 6. FUNDING RATE VELOCITY - Contrarian signal
        funding_vel = data.get('funding_rate_velocity', 0)
        if funding_vel > 0.02:  # Overleveraged longs
            score -= 1  # Fade the crowd
        elif funding_vel < -0.02:  # Overleveraged shorts
            score += 1
        
        # 7. CVD DIVERGENCE - Confirmation signal
        cvd_div = data.get('cvd_divergence', 0)
        if cvd_div > 0.5:
            score += 1
        elif cvd_div < -0.5:
            score -= 1
        
        # 8. TAKER RATIO - Aggression signal
        taker_ratio = data.get('taker_ratio', 1.0)
        if taker_ratio > 1.3:  # Aggressive buyers
            score += 1
        elif taker_ratio < 0.7:  # Aggressive sellers
            score -= 1
        
        # === REGIME ADJUSTMENT ===
        if regime == 'BULLISH' and score > 0:
            score += 0.5  # Boost long signals in bull regime
        elif regime == 'BEARISH' and score < 0:
            score -= 0.5  # Boost short signals in bear regime
        elif regime == 'VOLATILE':
            score *= 0.5  # Reduce conviction in volatile regime
        
        # Track best opportunity
        if abs(score) > abs(best_score):
            best_score = score
            best_symbol = sym
            best_price = price
    
    # === ENTRY DECISION ===
    if best_symbol and abs(best_score) >= config['min_entry_score']:
        # Calculate position size (20% of cash)
        qty = (cash_balance * config['position_size_pct']) / best_price
        
        if best_score > 0:
            return ("BUY", best_symbol, qty)
        else:
            return ("SELL", best_symbol, qty)  # Short sell
    
    return ("HOLD", None, 0)


# === UTILITY FUNCTIONS ===

def calculate_signal_strength(data):
    """
    Calculate overall signal strength for monitoring.
    Returns value between -1.0 (strong short) and 1.0 (strong long).
    """
    if not data:
        return 0.0
    
    weights = {
        'obi_weighted': 0.25,
        'ofi': 0.20,
        'micro_price_gap': 0.20,
        'sentiment': 0.15,
        'cvd_divergence': 0.10,
        'taker_ratio': 0.10,
    }
    
    score = 0.0
    
    # Normalize each signal to [-1, 1] range
    obi = np.clip(data.get('obi_weighted', 0), -1, 1)
    score += obi * weights['obi_weighted']
    
    ofi = np.clip(data.get('ofi', 0) / 100, -1, 1)
    score += ofi * weights['ofi']
    
    price = data.get('price', 1)
    micro = data.get('micro_price', price)
    gap = np.clip((micro - price) / price * 100, -1, 1) if price > 0 else 0
    score += gap * weights['micro_price_gap']
    
    sentiment = np.clip(data.get('sentiment', 0), -1, 1)
    score += sentiment * weights['sentiment']
    
    cvd = np.clip(data.get('cvd_divergence', 0), -1, 1)
    score += cvd * weights['cvd_divergence']
    
    taker = data.get('taker_ratio', 1.0)
    taker_norm = np.clip((taker - 1.0) / 0.5, -1, 1)
    score += taker_norm * weights['taker_ratio']
    
    return np.clip(score, -1, 1)


def get_strategy_info():
    """Return strategy metadata for the arena."""
    return {
        'name': 'DeepLOB-Stoikov Fusion',
        'version': '1.0.0',
        'author': 'HFT Quant',
        'description': 'Multi-signal fusion using microstructure, order flow, and NLP signals',
        'risk_profile': 'MODERATE',
        'target_symbols': ['BTC', 'ETH', 'SOL'],
        'parameters': {
            'take_profit': '0.50%',
            'stop_loss': '0.30%',
            'trailing_stop': '2.0%',
            'position_size': '20%',
            'cooldown': '60 ticks',
        }
    }


# === TEST HARNESS ===
if __name__ == "__main__":
    # Simulate market data for testing
    test_market_data = {
        'BTC': {
            'price': 98000.0,
            'volume': 1500.0,
            'history': [97500, 97800, 98000],
            'volumes': [1000, 1200, 1500],
            'obi_weighted': 0.35,
            'micro_price': 98150.0,
            'ofi': 75.0,
            'funding_rate_velocity': 0.005,
            'cvd_divergence': 0.3,
            'taker_ratio': 1.25,
            'parkinson_vol': 0.018,
            'sentiment': 0.6,
            'attention': 1.3,
        },
        'ETH': {
            'price': 3500.0,
            'volume': 800.0,
            'history': [3450, 3480, 3500],
            'volumes': [600, 700, 800],
            'obi_weighted': -0.15,
            'micro_price': 3485.0,
            'ofi': -25.0,
            'funding_rate_velocity': -0.01,
            'cvd_divergence': -0.2,
            'taker_ratio': 0.85,
            'parkinson_vol': 0.022,
            'sentiment': -0.1,
            'attention': 0.9,
        },
        'SOL': {
            'price': 180.0,
            'volume': 500.0,
            'history': [175, 178, 180],
            'volumes': [400, 450, 500],
            'obi_weighted': 0.05,
            'micro_price': 180.5,
            'ofi': 10.0,
            'funding_rate_velocity': 0.0,
            'cvd_divergence': 0.1,
            'taker_ratio': 1.05,
            'parkinson_vol': 0.025,
            'sentiment': 0.2,
            'attention': 1.1,
        },
    }
    
    # Test state
    test_agent_state = {
        'entry_prices': {},
        'current_pnl': {},
        'custom': {},
    }
    
    # Run test
    print("=== HFT Strategy Test ===\n")
    print(f"Strategy Info: {get_strategy_info()['name']}")
    print(f"Version: {get_strategy_info()['version']}\n")
    
    # Test entry (no positions)
    result = execute_strategy(
        market_data=test_market_data,
        tick=100,
        cash_balance=100000.0,
        portfolio={'BTC': 0, 'ETH': 0, 'SOL': 0},
        market_state=None,
        agent_state=test_agent_state
    )
    print(f"Entry Test (Tick 100): {result}")
    
    # Simulate being in a BTC long position with profit
    test_agent_state['current_pnl']['BTC'] = {
        'pnl_percent': 0.6,  # 0.6% profit
        'pnl_usd': 588.0,
        'entry_price': 98000.0,
        'current_price': 98588.0,
    }
    test_agent_state['custom']['peak_prices'] = {'BTC': 98600.0}
    
    result = execute_strategy(
        market_data=test_market_data,
        tick=200,
        cash_balance=80000.0,
        portfolio={'BTC': 0.2, 'ETH': 0, 'SOL': 0},
        market_state=None,
        agent_state=test_agent_state
    )
    print(f"Exit Test (Tick 200, 0.6% profit): {result}")
    
    # Test signal strength calculation
    btc_strength = calculate_signal_strength(test_market_data['BTC'])
    eth_strength = calculate_signal_strength(test_market_data['ETH'])
    print(f"\nSignal Strengths:")
    print(f"  BTC: {btc_strength:.3f} (Bullish)" if btc_strength > 0 else f"  BTC: {btc_strength:.3f}")
    print(f"  ETH: {eth_strength:.3f} (Bearish)" if eth_strength < 0 else f"  ETH: {eth_strength:.3f}")
    
    print("\n=== Test Complete ===")