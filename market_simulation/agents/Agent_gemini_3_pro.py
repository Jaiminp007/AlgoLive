# --- Generated Algorithm Code Below ---
import numpy as np
import pandas as pd

# Use agent_state for persistence - NO global variables for state!
# Only _last_trade_tick is safe as a global counter to persist across function calls
_last_trade_tick = 0 

def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    '''
    Institutional-grade algo with State Persistence and Fee Awareness.
    Fuses DeepLOB (OBI), Order Flow Imbalance (OFI), and Sentiment for alpha generation.
    '''
    global _last_trade_tick

    # 1. Initialize State if missing (Handle backward compatibility)
    if agent_state is None:
        agent_state = {'entry_prices': {}, 'current_pnl': {}, 'custom': {}}

    symbols = ['BTC', 'ETH', 'SOL']

    # 2. Global Cooldown Filter (60 ticks)
    if tick - _last_trade_tick < 60:
        return ("HOLD", None, 0)

    # 3. EXIT LOGIC (Priority) - Manage Open Positions
    # Iterate through currently held positions to check stops/targets
    for sym in symbols:
        qty = portfolio.get(sym, 0)
        
        # If we have a position (Long or Short), check PnL
        if qty != 0:
            # Retrieve PnL data calculated by the Arena engine
            pnl_info = agent_state.get('current_pnl', {}).get(sym, {})
            # Note: Arena usually passes 'pnl_percent' as a percentage (e.g., 0.5 for 0.5%)
            # We convert to decimal for comparison if needed, or compare directly.
            # Assuming 'pnl_percent' is strictly Percentage (e.g. 1.0 = 1%).
            # Based on prompt instructions: "0.50% target" -> pnl_pct > 0.50 
            # OR decimal based on the prompt's condition "if pnl_pct > 0.005".
            # Let's align with the PROMPT'S explicit code snippet logic:
            # "pnl_pct = pnl_info.get('pnl_percent', 0) / 100.0" implies raw value is %
            
            raw_pnl_pct = pnl_info.get('pnl_percent', 0)
            pnl_decimal = raw_pnl_pct / 100.0

            # --- EXIT RULE 1: TAKE PROFIT (> 0.50% net) ---
            # Must cover ~0.20% round-trip costs (fees + slippage)
            if pnl_decimal > 0.005: 
                _last_trade_tick = tick
                # If Long (qty > 0), SELL to close. If Short (qty < 0), BUY to cover.
                action = "SELL" if qty > 0 else "BUY"
                return (action, sym, abs(qty))

            # --- EXIT RULE 2: STOP LOSS (-0.30%) ---
            # Tight stop to preserve capital
            if pnl_decimal < -0.003:
                _last_trade_tick = tick
                action = "SELL" if qty > 0 else "BUY"
                return (action, sym, abs(qty))

            # --- EXIT RULE 3: TRAILING STOP (Custom Implementation) ---
            # We can track peak price in agent_state['custom'] if needed, 
            # but strict TP/SL is prioritized here for safety.

    # 4. ENTRY LOGIC - Scan for High-Alpha Setup
    # Only enter if we are not already in a trade (simplification for safety)
    # or if we allow multiple positions (logic below assumes one trade per tick).
    
    best_sym = None
    best_score = 0
    
    for sym in symbols:
        # Skip if we already have a position in this asset
        if portfolio.get(sym, 0) != 0: continue

        data = market_data.get(sym, {})
        if not data: continue

        # --- Alpha Signals ---
        obi = data.get('obi_weighted', 0)        # Microstructure Pressure
        ofi = data.get('ofi', 0)                 # Order Flow Imbalance
        sentiment = data.get('sentiment', 0)     # NLP Signal
        micro_price = data.get('micro_price', 0) # Stoikov Fair Value
        price = data.get('price', 0)
        
        # --- Volume Filter ---
        # Ensure current volume is active (spike detection)
        current_vol = data.get('volume', 0)
        hist_vols = data.get('volumes', [])
        avg_vol = np.mean(hist_vols) if hist_vols else 1.0
        
        if current_vol < (1.5 * avg_vol):
            continue # Skip low energy environments

        # --- Scoring Engine ---
        score = 0
        
        # Signal 1: Order Book Imbalance (DeepLOB)
        if obi > 0.2: score += 1
        elif obi < -0.2: score -= 1
        
        # Signal 2: Order Flow Imbalance (OFI)
        if ofi > 15: score += 1
        elif ofi < -15: score -= 1
        
        # Signal 3: Sentiment
        if sentiment > 0.25: score += 1
        elif sentiment < -0.25: score -= 1
        
        # Signal 4: Fair Value Gap (Stoikov)
        if micro_price > price * 1.0005: score += 1   # Undervalued
        elif micro_price < price * 0.9995: score -= 1 # Overvalued

        # Track Best Opportunity
        if abs(score) > abs(best_score):
            best_score = score
            best_sym = sym

    # 5. EXECUTION LOGIC
    # Threshold: Absolute Score >= 2 required for entry
    if best_sym and abs(best_score) >= 2:
        price = market_data[best_sym]['price']
        
        # Position Sizing: 20% of Cash
        # Ensure we don't divide by zero
        if price > 0:
            qty = (cash_balance * 0.20) / price
            
            _last_trade_tick = tick

            if best_score > 0:
                # Long Entry
                return ("BUY", best_sym, qty)
            else:
                # Short Entry (Sell to Open)
                return ("SELL", best_sym, qty)

    # Default: Hold
    return ("HOLD", None, 0)