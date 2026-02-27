# --- Oracle Insider: Fundamental Alpha Hunter ---
# Trades stocks based on insider activity, institutional flows, and earnings
# OPTIMIZED: Wider targets, reduced position size, better cooldowns
import numpy as np
import pandas as pd

_last_trade_tick = 0
_conviction_trades = {}  # Track high-conviction positions

def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    '''
    Oracle Insider: Exploits fundamental signals from FinancialDatasets.ai.
    Focuses on stocks with insider buying, institutional accumulation, and earnings beats.
    '''
    global _last_trade_tick, _conviction_trades
    
    if agent_state is None:
        agent_state = {'entry_prices': {}, 'current_pnl': {}, 'custom': {}}
    
    # Stock focus - these have fundamental data
    stock_symbols = ['AAPL', 'TSLA', 'NVDA', 'MSFT', 'GOOGL', 'AMZN', 'META']
    # Also trade crypto for diversification
    crypto_symbols = ['BTC', 'ETH']
    all_symbols = stock_symbols + crypto_symbols
    
    # INCREASED COOLDOWN: 300 ticks (5 minutes, was 90)
    if tick - _last_trade_tick < 300:
        return ("HOLD", None, 0)
    
    # === EXIT LOGIC ===
    for sym in all_symbols:
        qty = portfolio.get(sym, 0)
        if qty == 0:
            continue
        
        pnl_info = agent_state.get('current_pnl', {}).get(sym, {})
        pnl_pct = pnl_info.get('pnl_percent', 0) / 100.0
        
        # WIDER PROFIT TARGET: 1.5% (was 0.75%)
        # Fundamentals need time to play out
        if pnl_pct > 0.015:
            _last_trade_tick = tick
            if sym in _conviction_trades:
                del _conviction_trades[sym]
            action = "SELL" if qty > 0 else "BUY"
            return (action, sym, abs(qty))
        
        # WIDER STOP LOSS: -1.0% (was -0.45%)
        if pnl_pct < -0.01:
            _last_trade_tick = tick
            if sym in _conviction_trades:
                del _conviction_trades[sym]
            action = "SELL" if qty > 0 else "BUY"
            return (action, sym, abs(qty))
        
        # Check if fundamental thesis has broken
        data = market_data.get(sym, {})
        if sym in stock_symbols:
            insider = data.get('insider_sentiment')
            inst_change = data.get('institutional_change')
            
            # Exit if insiders start selling (thesis broken)
            if insider is not None and insider < -0.3 and qty > 0:
                _last_trade_tick = tick
                if sym in _conviction_trades:
                    del _conviction_trades[sym]
                return ("SELL", sym, abs(qty))
    
    # === ENTRY LOGIC: Fundamental Score ===
    best_sym = None
    best_score = 0
    best_is_stock = False
    
    # Scan stocks first (primary focus)
    for sym in stock_symbols:
        if portfolio.get(sym, 0) != 0:
            continue
        
        data = market_data.get(sym, {})
        if not data:
            continue
        
        price = data.get('price', 0)
        if price <= 0:
            continue
        
        # Fundamental signals
        insider = data.get('insider_sentiment')
        inst_change = data.get('institutional_change')
        rev_growth = data.get('revenue_growth')
        profit_margin = data.get('profit_margin')
        pe_ratio = data.get('pe_ratio')
        earnings_surprise = data.get('earnings_surprise')
        news_sentiment = data.get('news_sentiment_score')
        
        # Technical confirmation
        obi = data.get('obi_weighted', 0) or 0
        
        score = 0
        signals_found = 0
        
        # === BULLISH FUNDAMENTAL SIGNALS ===
        
        # Insider buying is the strongest signal
        if insider is not None:
            signals_found += 1
            if insider > 0.6:
                score += 2.5  # Heavy insider buying = very bullish
            elif insider > 0.3:
                score += 1.5
            elif insider < -0.5:
                score -= 2  # Insider selling = bearish
        
        # Institutional accumulation
        if inst_change is not None:
            signals_found += 1
            if inst_change > 3.0:
                score += 2  # Strong accumulation
            elif inst_change > 1.5:
                score += 1
            elif inst_change < -2.0:
                score -= 1.5  # Distribution
        
        # Revenue growth
        if rev_growth is not None:
            signals_found += 1
            if rev_growth > 25:
                score += 1.5  # High growth
            elif rev_growth > 15:
                score += 1
            elif rev_growth < 0:
                score -= 1  # Declining
        
        # Profit margin health
        if profit_margin is not None:
            signals_found += 1
            if profit_margin > 0.25:
                score += 0.5  # Healthy margins
            elif profit_margin < 0.05:
                score -= 0.5  # Thin margins
        
        # Earnings surprise
        if earnings_surprise is not None:
            signals_found += 1
            if earnings_surprise > 0.1:
                score += 1.5  # Beat estimates by >10%
            elif earnings_surprise > 0.05:
                score += 0.75
            elif earnings_surprise < -0.05:
                score -= 1  # Missed estimates
        
        # News sentiment
        if news_sentiment is not None:
            signals_found += 1
            if news_sentiment > 0.5:
                score += 0.5
            elif news_sentiment < -0.5:
                score -= 0.5
        
        # Technical confirmation (order book)
        if obi > 0.2:
            score += 0.5
        elif obi < -0.2:
            score -= 0.5
        
        # Only trade if we have enough fundamental data
        if signals_found >= 2 and abs(score) > abs(best_score):
            best_score = score
            best_sym = sym
            best_is_stock = True
    
    # Also scan crypto with technical-only approach
    for sym in crypto_symbols:
        if portfolio.get(sym, 0) != 0:
            continue
        
        data = market_data.get(sym, {})
        if not data:
            continue
        
        price = data.get('price', 0)
        if price <= 0:
            continue
        
        obi = data.get('obi_weighted', 0) or 0
        ofi = data.get('ofi', 0) or 0
        sentiment = data.get('sentiment', 0) or 0
        attention = data.get('attention', 0) or 0
        
        score = 0
        
        if obi > 0.2:
            score += 1
        elif obi < -0.2:
            score -= 1
        
        if ofi > 15:
            score += 1
        elif ofi < -15:
            score -= 1
        
        if sentiment > 0.4:
            score += 1
        elif sentiment < -0.4:
            score -= 1
        
        # Attention surge from Google Trends
        if attention > 1.5:
            score += 0.5
        
        # Only override stocks if crypto signal is very strong
        if abs(score) >= 3 and abs(score) > abs(best_score):
            best_score = score
            best_sym = sym
            best_is_stock = False
    
    # INCREASED Entry threshold: 3.5 for stocks, 4 for crypto (was 2.5/3)
    threshold = 3.5 if best_is_stock else 4
    
    if best_sym and abs(best_score) >= threshold:
        price = market_data[best_sym]['price']
        
        # REDUCED POSITION SIZE: 8% for stocks, 5% for crypto (was 25%/18%)
        position_pct = 0.08 if best_is_stock else 0.05
        qty = (cash_balance * position_pct) / price
        
        _last_trade_tick = tick
        _conviction_trades[best_sym] = best_score
        
        if best_score > 0:
            return ("BUY", best_sym, qty)
        else:
            return ("SELL", best_sym, qty)
    
    return ("HOLD", None, 0)
