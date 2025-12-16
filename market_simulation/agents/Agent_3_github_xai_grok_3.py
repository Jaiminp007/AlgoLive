# --- Generated Algorithm Code Below ---
import numpy as np
import pandas as pd

# Global state
_entry_price = {}
_entry_tick = {}
_last_trade_tick = 0  # COOLDOWN TRACKER

def calculate_ema(prices, period):
    if not prices or len(prices) < period: return None
    clean_prices = [p for p in prices if isinstance(p, (int, float))]
    if len(clean_prices) < period: return None
    multiplier = 2 / (period + 1)
    ema = sum(clean_prices[:period]) / period
    for p in clean_prices[period:]:
        ema = (p - ema) * multiplier + ema
    return ema

def execute_strategy(market_data, tick, cash_balance, portfolio):
    '''
    Institutional-grade multi-currency momentum algo for BTC, ETH, SOL with proper risk management.
    '''
    global _entry_price, _last_trade_tick
    
    # ===== COOLDOWN CHECK =====
    # Wait 60 ticks (~ 60 seconds) between trades
    if tick - _last_trade_tick < 60:
        return ("HOLD", None, 0)
    
    # 0. Hot-Swap Reconstruction
    for sym, qty in portfolio.items():
        if qty != 0 and sym not in _entry_price:
            current_p = market_data.get(sym, {}).get('price', 0)
            if current_p: _entry_price[sym] = current_p

    # ===== EXIT LOGIC (Check Existing Positions First) =====
    for sym, qty in portfolio.items():
        if qty == 0: continue
        data = market_data.get(sym, {})
        if not data or 'price' not in data: continue
        
        price = data['price']
        entry = _entry_price.get(sym, price)
        if entry == 0: continue
        
        pnl_pct = (price / entry) - 1.0
        
        # PROFIT TARGET: +3% to +5%
        if pnl_pct > 0.03:
            _entry_price.pop(sym, None)
            _last_trade_tick = tick  # COOLDOWN
            return ("SELL", sym, qty)
        
        # STOP-LOSS: -5%
        if pnl_pct < -0.05:
            _entry_price.pop(sym, None)
            _last_trade_tick = tick  # COOLDOWN
            return ("SELL", sym, qty)
    
    # ===== ENTRY LOGIC =====
    if not market_data: return ("HOLD", None, 0)
    
    best_sym = None
    best_score = -999
    
    # Focus on BTC, ETH, SOL for momentum trading
    target_assets = ['BTC', 'ETH', 'SOL']
    
    for sym in target_assets:
        data = market_data.get(sym, {})
        if not isinstance(data, dict) or 'price' not in data: continue
        
        # Skip if already holding
        if portfolio.get(sym, 0) != 0: continue
        
        price = data['price']
        
        # Extract Microstructure Signals for momentum
        obi = data.get('obi_weighted', 0.0)  # Order Book Imbalance for liquidity support
        ofi = data.get('ofi', 0.0)  # Order Flow Imbalance for aggressive buying
        micro_price = data.get('micro_price', price)  # Stoikov Fair Value
        sentiment = data.get('sentiment', 0.0)  # News Sentiment
        attention = data.get('attention', 0.0)  # Search Volume Delta
        
        # Calculate Momentum Score
        score = 0
        
        # Order Book Imbalance (Liquidity Support - Lowered threshold for entry)
        if obi > 0.1:
            score += 5
        
        # Order Flow Imbalance (Aggressive Buying Momentum)
        if ofi > 30:
            score += 4
        elif ofi < -30:
            score -= 3
        
        # Fair Value Gap (Undervaluation based on Micro-price)
        if price < micro_price * 0.995:  # Price below fair value by 0.5%
            score += 3
        
        # Sentiment Boost (Positive News)
        if sentiment > 0.6:
            score += 2
        elif sentiment < 0.3:
            score -= 2
        
        # Attention Boost (Rising Public Interest)
        if attention > 1.0:
            score += 1
        
        if score > best_score:
            best_score = score
            best_sym = sym
    
    # ===== EXECUTION (Score >= 5) =====
    if best_sym and best_score >= 5:
        data = market_data[best_sym]
        price = data['price']
        
        # POSITION SIZING: Risk only 5% of cash
        qty = (cash_balance * 0.05) / price
        
        # Ensure minimum viable qty
        if qty > 0 and cash_balance >= price * qty:
            _entry_price[best_sym] = price
            _last_trade_tick = tick  # COOLDOWN
            return ("BUY", best_sym, qty)
    
    return ("HOLD", None, 0)