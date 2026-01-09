"""
INSTITUTIONAL-GRADE HFT ALGORITHM
==================================
Strategy: Multi-Signal Microstructure Fusion
Signals: DeepLOB OBI, Stoikov Microprice, Order Flow Imbalance, NLP Sentiment
Risk Management: Fee-aware profit targets, tight stops, position sizing

Author: Senior Quant Strategist
Version: 1.0
"""

import numpy as np
import pandas as pd
from typing import Tuple, Dict, Any, Optional

# Global cooldown tracker (safe to use as simple counter)
_last_trade_tick = 0

def execute_strategy(
    market_data: Dict[str, Dict[str, Any]],
    tick: int,
    cash_balance: float,
    portfolio: Dict[str, float],
    market_state: Optional[Dict] = None,
    agent_state: Optional[Dict] = None
) -> Tuple[str, Optional[str], float]:
    """
    Institutional-Grade Market Microstructure Algorithm
    
    Parameters:
    -----------
    market_data : Dict with keys like 'BTC', 'ETH', 'SOL'
        Contains price, volume, obi_weighted, micro_price, ofi, sentiment, etc.
    tick : int
        Current simulation tick
    cash_balance : float
        Available cash for trading
    portfolio : Dict[str, float]
        Current holdings {symbol: quantity}
    market_state : Optional[Dict]
        Market regime information (unused)
    agent_state : Optional[Dict]
        Persistent state with entry_prices, current_pnl, custom data
    
    Returns:
    --------
    Tuple[str, Optional[str], float]
        (ACTION, SYMBOL, QUANTITY) where ACTION in ["BUY", "SELL", "HOLD"]
    """
    global _last_trade_tick
    
    # Initialize agent_state if not provided (backward compatibility)
    if agent_state is None:
        agent_state = {
            'entry_prices': {},
            'current_pnl': {},
            'trade_history': [],
            'custom': {}
        }
    
    # Focus on top 3 liquid coins only
    SYMBOLS = ['BTC', 'ETH', 'SOL']
    
    # Trading parameters
    POSITION_SIZE_PCT = 0.20        # Risk 20% per trade
    PROFIT_TARGET_PCT = 0.005       # 0.50% profit target (beats 0.20% costs)
    STOP_LOSS_PCT = -0.003          # -0.30% stop loss
    COOLDOWN_TICKS = 60             # Wait 60 ticks between trades
    ENTRY_THRESHOLD = 2             # Score must be >= |2| to enter
    
    # ========================================
    # STEP 1: COOLDOWN CHECK
    # ========================================
    if tick - _last_trade_tick < COOLDOWN_TICKS:
        return ("HOLD", None, 0)
    
    # ========================================
    # STEP 2: EXIT LOGIC (Priority: Close existing positions)
    # ========================================
    for sym in SYMBOLS:
        qty = portfolio.get(sym, 0)
        if qty == 0:
            continue  # No position to exit
        
        # Get PnL from agent_state (reliable tracking)
        pnl_info = agent_state.get('current_pnl', {}).get(sym, {})
        pnl_percent = pnl_info.get('pnl_percent', 0)  # Already in percentage
        pnl_decimal = pnl_percent / 100.0  # Convert to decimal for comparison
        
        # PROFIT TAKE: Exit when profit > 0.50% (covers 0.20% costs + buffer)
        if pnl_decimal > PROFIT_TARGET_PCT:
            _last_trade_tick = tick
            action = "SELL" if qty > 0 else "BUY"  # Close long or short
            return (action, sym, abs(qty))
        
        # STOP LOSS: Exit when loss < -0.30% (tight risk control)
        if pnl_decimal < STOP_LOSS_PCT:
            _last_trade_tick = tick
            action = "SELL" if qty > 0 else "BUY"  # Close long or short
            return (action, sym, abs(qty))
    
    # ========================================
    # STEP 3: ENTRY LOGIC (Find best opportunity)
    # ========================================
    best_symbol = None
    best_score = 0
    best_data = None
    
    for sym in SYMBOLS:
        # Skip if already in position
        if portfolio.get(sym, 0) != 0:
            continue
        
        data = market_data.get(sym, {})
        if not data or 'price' not in data:
            continue
        
        # Extract microstructure signals
        obi = data.get('obi_weighted', 0)          # Order Book Imbalance
        ofi = data.get('ofi', 0)                   # Order Flow Imbalance
        sentiment = data.get('sentiment', 0)       # NLP Sentiment
        micro_price = data.get('micro_price', 0)   # Stoikov Fair Value
        price = data.get('price', 0)
        
        # Volume filter: Check if volume is elevated
        volume = data.get('volume', 0)
        volumes_hist = data.get('volumes', [])
        if len(volumes_hist) >= 20:
            avg_volume = np.mean(volumes_hist[-20:])
            if volume < avg_volume * 1.5:
                continue  # Skip low-volume periods
        
        # ========================================
        # SCORING SYSTEM (Institutional Signals)
        # ========================================
        score = 0
        
        # Signal 1: Order Book Imbalance (DeepLOB)
        if obi > 0.1:      # Strong bid support
            score += 1
        elif obi < -0.1:   # Strong ask pressure
            score -= 1
        
        # Signal 2: Order Flow Imbalance
        if ofi > 10:       # Net aggressive buying
            score += 1
        elif ofi < -10:    # Net aggressive selling
            score -= 1
        
        # Signal 3: NLP Sentiment
        if sentiment > 0.2:    # Positive news sentiment
            score += 1
        elif sentiment < -0.2: # Negative news sentiment
            score -= 1
        
        # Signal 4: Microprice vs Market Price (Stoikov)
        if micro_price > 0:
            price_gap = (micro_price - price) / price
            if price_gap > 0.001:      # Market undervalued by >0.1%
                score += 1
            elif price_gap < -0.001:   # Market overvalued by >0.1%
                score -= 1
        
        # Update best candidate
        if abs(score) > abs(best_score):
            best_score = score
            best_symbol = sym
            best_data = data
    
    # ========================================
    # STEP 4: EXECUTE ENTRY
    # ========================================
    if best_symbol and abs(best_score) >= ENTRY_THRESHOLD:
        price = best_data['price']
        
        # Position sizing: 20% of cash balance
        quantity = (cash_balance * POSITION_SIZE_PCT) / price
        
        # Minimum quantity check (avoid dust trades)
        if quantity * price < 1.0:
            return ("HOLD", None, 0)
        
        _last_trade_tick = tick
        
        if best_score > 0:
            # LONG ENTRY: Bullish signals
            return ("BUY", best_symbol, quantity)
        else:
            # SHORT ENTRY: Bearish signals (SELL to open short)
            return ("SELL", best_symbol, quantity)
    
    # No action
    return ("HOLD", None, 0)


def get_strategy_info() -> Dict[str, Any]:
    """
    Returns strategy metadata for logging and monitoring
    """
    return {
        "name": "Institutional Microstructure Fusion",
        "version": "1.0",
        "symbols": ["BTC", "ETH", "SOL"],
        "signals": [
            "Order Book Imbalance (DeepLOB)",
            "Order Flow Imbalance", 
            "NLP Sentiment",
            "Stoikov Microprice"
        ],
        "risk_per_trade": "20%",
        "profit_target": "0.50%",
        "stop_loss": "-0.30%",
        "features": [
            "Volume spike filtering",
            "Fee-aware exits",
            "Short selling support",
            "State-based persistence"
        ]
    }