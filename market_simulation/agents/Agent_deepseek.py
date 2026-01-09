# --- INSTITUTIONAL QUANT ALGO: DEEP MICROSTRUCTURE FUSION ---
import numpy as np

# Global cooldown counter - safe as it's just a tick tracker
_last_trade_tick = 0

def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    '''
    Institutional HFT Algo: Fuses DeepLOB, Stoikov, & NLP signals with fee-aware risk management.
    Uses agent_state for persistent tracking - NO global position variables.
    '''
    global _last_trade_tick
    
    # Initialize agent_state if None (backward compatibility)
    if agent_state is None:
        agent_state = {'entry_prices': {}, 'current_pnl': {}, 'custom': {}}
    
    # Initialize custom state if needed
    if 'custom' not in agent_state:
        agent_state['custom'] = {}
    if 'peak_prices' not in agent_state['custom']:
        agent_state['custom']['peak_prices'] = {}
    if 'volume_avg' not in agent_state['custom']:
        agent_state['custom']['volume_avg'] = {}
    if 'trade_history' not in agent_state['custom']:
        agent_state['custom']['trade_history'] = []
    
    symbols = ['BTC', 'ETH', 'SOL']
    
    # === 1. COOLDOWN CHECK ===
    if tick - _last_trade_tick < 60:
        return ("HOLD", None, 0)
    
    # === 2. EXIT LOGIC (Trailing Stop, Profit Target, Stop Loss) ===
    for sym in symbols:
        qty = portfolio.get(sym, 0)
        if qty == 0:
            continue
        
        # Get current data
        data = market_data.get(sym, {})
        if not data:
            continue
        
        current_price = data.get('price', 0)
        if current_price == 0:
            continue
        
        # Get entry price from agent_state
        entry_price = agent_state.get('entry_prices', {}).get(sym, 0)
        if entry_price == 0:
            entry_price = current_price  # Fallback
        
        # Get PnL info
        pnl_info = agent_state.get('current_pnl', {}).get(sym, {})
        pnl_pct = pnl_info.get('pnl_percent', 0) / 100.0  # Convert % to decimal
        
        # Update peak price for trailing stop (LONG positions)
        if qty > 0:  # Long position
            if sym not in agent_state['custom']['peak_prices']:
                agent_state['custom']['peak_prices'][sym] = current_price
            else:
                agent_state['custom']['peak_prices'][sym] = max(
                    agent_state['custom']['peak_prices'][sym],
                    current_price
                )
            
            # Trailing stop (2% from peak) for longs
            peak_price = agent_state['custom']['peak_prices'][sym]
            if current_price < peak_price * 0.98:
                _last_trade_tick = tick
                return ("SELL", sym, abs(qty))
        
        # Update trough price for trailing stop (SHORT positions)
        elif qty < 0:  # Short position
            if sym not in agent_state['custom']['peak_prices']:
                agent_state['custom']['peak_prices'][sym] = current_price
            else:
                agent_state['custom']['peak_prices'][sym] = min(
                    agent_state['custom']['peak_prices'][sym],
                    current_price
                )
            
            # Trailing stop (2% from trough) for shorts
            trough_price = agent_state['custom']['peak_prices'][sym]
            if current_price > trough_price * 1.02:
                _last_trade_tick = tick
                return ("BUY", sym, abs(qty))  # Buy to cover short
        
        # Take Profit (0.50% minimum to beat 0.20% costs)
        if pnl_pct > 0.005:
            _last_trade_tick = tick
            action = "SELL" if qty > 0 else "BUY"
            return (action, sym, abs(qty))
        
        # Stop Loss (-0.30%)
        if pnl_pct < -0.003:
            _last_trade_tick = tick
            action = "SELL" if qty > 0 else "BUY"
            return (action, sym, abs(qty))
    
    # === 3. VOLUME SPIKE CALCULATION ===
    # Update volume averages (rolling 20-period)
    for sym in symbols:
        data = market_data.get(sym, {})
        if not data:
            continue
        
        current_volume = data.get('volume', 0)
        hist_volumes = data.get('volumes', [])
        
        # Calculate average volume
        if len(hist_volumes) > 0:
            lookback = min(20, len(hist_volumes))
            avg_volume = np.mean(hist_volumes[-lookback:])
            agent_state['custom']['volume_avg'][sym] = avg_volume
    
    # === 4. ENTRY SIGNAL GENERATION ===
    best_sym = None
    best_score = -float('inf')
    
    for sym in symbols:
        # Skip if already in position
        if portfolio.get(sym, 0) != 0:
            continue
        
        data = market_data.get(sym, {})
        if not data:
            continue
        
        # Extract signals
        price = data.get('price', 0)
        volume = data.get('volume', 0)
        obi = data.get('obi_weighted', 0)
        micro_price = data.get('micro_price', price)
        ofi = data.get('ofi', 0)
        sentiment = data.get('sentiment', 0)
        attention = data.get('attention', 1.0)
        funding_vel = data.get('funding_rate_velocity', 0)
        cvd_div = data.get('cvd_divergence', 0)
        taker_ratio = data.get('taker_ratio', 1.0)
        parkinson_vol = data.get('parkinson_vol', 0.01)
        
        if price == 0:
            continue
        
        # === VOLUME SPIKE FILTER ===
        avg_volume = agent_state['custom']['volume_avg'].get(sym, volume)
        volume_spike = volume > (1.5 * avg_volume) if avg_volume > 0 else True
        
        if not volume_spike:
            continue  # Skip entry if no volume spike
        
        # === SIGNAL FUSION SCORING ===
        score = 0.0
        
        # 1. Order Book Imbalance (DeepLOB)
        if obi > 0.1:
            score += 1.2
        elif obi < -0.1:
            score -= 1.2
        
        # 2. Fair Value Gap (Stoikov)
        fair_value_gap = (micro_price - price) / price
        if abs(fair_value_gap) > 0.0002:  # 0.02% threshold
            score += np.sign(fair_value_gap) * 1.5
        
        # 3. Order Flow Imbalance
        if ofi > 20:
            score += 1.0
        elif ofi < -20:
            score -= 1.0
        
        # 4. Sentiment & Attention
        if sentiment > 0.2:
            score += 0.8 * min(attention, 2.0)  # Scale by attention
        elif sentiment < -0.2:
            score -= 0.8 * min(attention, 2.0)
        
        # 5. Funding Rate Momentum
        if funding_vel > 0.005:
            score -= 0.5  # Positive funding -> favor shorts
        elif funding_vel < -0.005:
            score += 0.5  # Negative funding -> favor longs
        
        # 6. CVD Divergence (Smart Money)
        if cvd_div > 0.3:
            score += 0.7
        elif cvd_div < -0.3:
            score -= 0.7
        
        # 7. Taker Ratio (Aggressive vs Passive)
        if taker_ratio > 1.2:
            score += 0.4  # Aggressive buying
        elif taker_ratio < 0.8:
            score -= 0.4  # Aggressive selling
        
        # 8. Volatility Adjustment
        if parkinson_vol > 0.03:
            score *= 0.7  # Reduce position confidence in high vol
        
        # === ENTRY DECISION ===
        if abs(score) > abs(best_score) and abs(score) >= 2.0:
            best_score = score
            best_sym = sym
    
    # === 5. EXECUTE ENTRY ===
    if best_sym and abs(best_score) >= 2.0:
        data = market_data[best_sym]
        price = data['price']
        
        # Position sizing: 20% of cash
        qty = (cash_balance * 0.20) / price
        
        # Store entry price in agent_state for future reference
        if 'entry_prices' not in agent_state:
            agent_state['entry_prices'] = {}
        agent_state['entry_prices'][best_sym] = price
        
        # Initialize peak price tracking
        agent_state['custom']['peak_prices'][best_sym] = price
        
        # Record trade
        trade_record = {
            'tick': tick,
            'symbol': best_sym,
            'action': 'BUY' if best_score > 0 else 'SELL',
            'price': price,
            'quantity': qty,
            'score': best_score
        }
        agent_state['custom']['trade_history'].append(trade_record)
        
        # Keep only last 20 trades
        if len(agent_state['custom']['trade_history']) > 20:
            agent_state['custom']['trade_history'].pop(0)
        
        _last_trade_tick = tick
        
        if best_score > 0:
            return ("BUY", best_sym, qty)
        else:
            return ("SELL", best_sym, qty)  # Short Sell
    
    return ("HOLD", None, 0)