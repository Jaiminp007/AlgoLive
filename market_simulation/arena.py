import time
import importlib
import importlib.util
import sys
import os
import threading
import numpy as np
import pandas as pd
from collections import deque
from queue import Queue
from datetime import datetime
from .data_feed import DataFeed
from .quant_features import SentimentSignalGenerator, calculate_multilevel_obi, calculate_weighted_microprice
from .market_metrics import CryptoMetrics
from .supervisor import Supervisor
from .attention_feed import AttentionFeed

# Analyst Engine imports
try:
    from analyst_engine.analyst import Analyst
    from analyst_engine.news_feed import NewsFeed
    ANALYST_AVAILABLE = True
except ImportError:
    ANALYST_AVAILABLE = False
    print("Warning: Analyst Engine not available. Structured market state disabled.")

class Arena:
    def __init__(self, socketio, db):
        self.socketio = socketio
        self.db = db
        self.data_feed = DataFeed()
        self.running = False
        self.agents = {} 
        # Agents are now in the 'agents' subdirectory of market_simulation
        self.agent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents")
        # Use symbols from DataFeed (supports both Crypto and Stocks)
        self.symbols = self.data_feed.symbols
        
        # O(1) deque for chart history (Equity Curve)
        self.chart_history = deque(maxlen=50000)
        
        # Market History per symbol for agents
        self.market_history = {sym: deque(maxlen=200) for sym in self.symbols}
        
        # QUANT SIGNALS INIT
        try:
            self.sentiment_engine = SentimentSignalGenerator()
        except:
            self.sentiment_engine = None
        
        # Async DB write queue
        self._db_queue = Queue()
        self._db_worker_running = True
        self._db_worker = threading.Thread(target=self._db_write_worker, daemon=True)
        self._db_worker.start()

        # SUPERVISOR INIT
        self.supervisor = Supervisor()
        
        # ANALYST ENGINE INIT
        if ANALYST_AVAILABLE:
            self.analyst = Analyst()
            self.news_feed_engine = NewsFeed() # Rename to avoid conflict
            print("Arena: Analyst Engine initialized.")
        else:
            self.analyst = None
            self.news_feed_engine = None
            
        self.ui_news = [] # Dedicated buffer for UI
        
        self.current_market_state = {}
        self.last_analyst_update = 0
        self.analyst_interval = 300  # 5 minutes
        
        # ATTENTION FEED INIT (Google Trends)
        self.attention_feed = AttentionFeed()
        self.attention_cache = {}  # Cached attention values
             
        # Warmup
        print("Arena: Fetching Market History for Warmup...")
        raw_history = self.data_feed.get_historical_data(limit=100, timeframe='1m')
        for sym, data in raw_history.items():
            if sym in self.market_history:
                # Normalize historical data to match live tick format
                # We approximate buy/sell vol as 50/50 for warmup since we don't have trade bits
                normalized_data = [{
                    'timestamp': d['timestamp'], 
                    'price': d['close'], 
                    'open': d['open'],
                    'high': d['high'],
                    'low': d['low'],
                    'volume': d['volume'],
                    'buy_volume': d['volume'] / 2, 
                    'sell_volume': d['volume'] / 2,
                    'funding_rate': 0.0001
                } for d in data]
                self.market_history[sym].extend(normalized_data)
        print(f"Arena: Loaded history for {list(raw_history.keys())}")
        
        # Restore state
        if self.db is not None:
            self._restore_state()
            self._restore_chart_history()
            
            # AUTO-CLEANUP: Clear chart history if it's stale (> 1 hour old)
            if self.chart_history:
                oldest_ts = self.chart_history[0].get('timestamp', 0)
                current_ts = datetime.now().timestamp() * 1000  # MS
                age_hours = (current_ts - oldest_ts) / (1000 * 60 * 60)
                if age_hours > 1:
                    print(f"Arena: Clearing stale chart history ({age_hours:.1f} hours old)")
                    self.chart_history.clear()
                    try:
                        self.db.chart_history.delete_many({})
                    except: pass

    def _db_write_worker(self):
        while self._db_worker_running:
            try:
                item = self._db_queue.get(timeout=1)
                if item is None: continue
                op_type, data = item
                if self.db is None: continue
                
                if op_type == 'chart':
                    self.db.chart_history.insert_one(data)
                elif op_type == 'agents_bulk':
                    from pymongo import UpdateOne
                    ops = [UpdateOne({'name': n}, {'$set': {'name': n, **s}}, upsert=True) 
                           for n, s in data.items()]
                    if ops: self.db.agents.bulk_write(ops, ordered=False)
            except Exception: pass

    def _restore_chart_history(self):
        try:
            history = list(self.db.chart_history.find({}, {'_id': 0}).sort('timestamp', 1).limit(50000))
            if history:
                self.chart_history = deque(history, maxlen=50000)
                print(f"Restored {len(history)} chart ticks.")
        except Exception as e:
            print(f"Failed to restore chart: {e}")

    def _restore_state(self):
        try:
            saved = self.db.agents.find()
            count = 0
            for doc in saved:
                name = doc['name']
                if self.load_agent(name):
                    self.agents[name]['equity'] = doc.get('equity', 100.0)
                    self.agents[name]['cash'] = doc.get('cash', 100.0)
                    self.agents[name]['total_fees'] = doc.get('total_fees', 0.0)
                    self.agents[name]['portfolio'] = doc.get('portfolio', {s: 0.0 for s in self.symbols})

                    # === FIX #1: Restore entry prices and custom state ===
                    self.agents[name]['entry_prices'] = doc.get('entry_prices', {})
                    self.agents[name]['custom_state'] = doc.get('custom_state', {})
                    self.agents[name]['trade_history'] = doc.get('trade_history', [])

                    # Restore Metrics
                    self.agents[name]['trades_count'] = doc.get('trades_count', 0)
                    self.agents[name]['wins'] = doc.get('wins', 0)
                    self.agents[name]['win_rate'] = doc.get('win_rate', 0.0)
                    self.agents[name]['returns_history'] = doc.get('returns_history', [])
                    self.agents[name]['sharpe'] = doc.get('sharpe', 0.0)
                    count += 1
                else:
                    self.db.agents.delete_one({'name': name})
            print(f"Restored {count} agents.")
        except Exception as e:
            print(f"Failed to restore state: {e}")

    def load_agent(self, name, restore=False, reload_module=False):
        filepath = os.path.join(self.agent_dir, f"{name}.py")
        if not os.path.exists(filepath): return False

        try:
            # Force reload if requested
            if reload_module and name in sys.modules:
                del sys.modules[name]

            spec = importlib.util.spec_from_file_location(name, filepath)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module # Register manually
            spec.loader.exec_module(module)
            
            if hasattr(module, 'execute_strategy'):
                print(f"Arena: Detected Strategy Agent '{name}'")
                instance = module
                
                # Init state
                if name not in self.agents:
                    self.agents[name] = {
                        'instance': instance,
                        'equity': 100.0,
                        'cash': 100.0,
                        'total_fees': 0.0,
                        'portfolio': {s: 0.0 for s in self.symbols},
                        'roi': 0.0,
                        'cashed_out': 0.0,
                        # === FIX #1: State persistence fields ===
                        'entry_prices': {},       # Track entry prices for positions
                        'custom_state': {},       # Agent's custom persistent state
                        'trade_history': [],      # Recent trade log
                        # --- METRICS ---
                        'trades_count': 0,
                        'wins': 0,
                        'win_rate': 0.0,
                        'returns_history': [],
                        'sharpe': 0.0
                    }
                    if not restore and self.db is not None: self._save_agent_state(name)
                else:
                    self.agents[name]['instance'] = instance
                
                return True
            else:
                print(f"Arena: Agent '{name}' missing execute_strategy (Legacy ignored)")
                return False
        except Exception as e:
            print(f"Failed to load {name}: {e}")
            return False

    def _save_agent_state(self, name):
        if self.db is None: return
        data = self.agents[name].copy()
        del data['instance']
        self.db.agents.update_one({'name': name}, {'$set': {'name': name, **data}}, upsert=True)

    def start_loop(self):
        if self.running: return
        self.running = True
        
        self.producer_thread = threading.Thread(target=self._data_producer, daemon=True)
        self.producer_thread.start()
        
        self.consumer_thread = threading.Thread(target=self._loop, daemon=True)
        self.consumer_thread.start()
        
        # Evolution Manager Thread
        self.evolution_thread = threading.Thread(target=self._evolution_manager, daemon=True)
        self.evolution_thread.start()
        
        # News Producer Thread
        self.news_thread = threading.Thread(target=self._news_producer, daemon=True)
        self.news_thread.start()
        
        print("Arena: Threads Started")

    def force_evolution(self):
        """Manually trigger evaluation and evolution for all agents."""
        print("Arena: MANUAL EVOLUTION TRIGGERED")
        from analyst_engine.brain import Brain
        brain = Brain()
        
        try:
            for name, agent_data in list(self.agents.items()):
                print(f"Arena: Evaluating agent {name}...")
                
                # 1. Read current code
                filepath = os.path.join(self.agent_dir, f"{name}.py")
                if not os.path.exists(filepath): continue
                with open(filepath, 'r') as f: code = f.read()
                
                # 2. Get Metrics
                roi = agent_data.get('roi', 0.0)
                portfolio = agent_data.get('portfolio', {})
                # simple logs summary
                logs_summary = f"Equity: {agent_data['equity']:.2f}, Cash: {agent_data['cash']:.2f}"
                
                # 3. Ask Brain to Evaluate
                decision, critique = brain.evaluate_agent(code, roi, portfolio, logs_summary)
                print(f"Arena: Eval Result for {name} -> {decision}")
                
                if decision == "REFINE":
                    # 4. Evolve
                    print(f"Arena: Evolving {name} due to: {critique}")
                    self.socketio.emit('agent_regenerating', {'name': name, 'critique': critique})
                    
                    result = brain.evolve_agent(name, critique, code)
                    
                    if result.get("success"):
                        print(f"Arena: Success! Hot-swapping {name}...")
                        # 5. Hot-Swap
                        self.load_agent(name, reload_module=True)
                        print(f"Arena: Hot-swap complete for {name}")
                        self.socketio.emit('agent_deployed', {'name': name})
        except Exception as e:
            print(f"Evolution Error: {e}")

    def _evolution_manager(self):
        """Background thread DISABLED. Use force_evolution() manually."""
        print("Arena: Auto-Evolution DISABLED. Waiting for manual trigger.")
        pass

    def stop_loop(self):
        self.running = False
        print("Arena: Stopping...")

    def reset(self, default_agents):
        self.running = False
        time.sleep(1)
        
        self.agents = {}
        self.chart_history = []
        if self.db is not None:
            try:
                self.db.agents.delete_many({})
                self.db.chart_history.delete_many({})
                self.db.trades.delete_many({})
            except: pass
            
        start_time = datetime.now().timestamp() * 1000
        initial = {'timestamp': start_time, 'price': 0, 'agents': {n: 100.0 for n in default_agents}}
        self.chart_history.append(initial)
        if self.db is not None: self.db.chart_history.insert_one(initial.copy())
        
        for name in default_agents: self.load_agent(name)
        
        self.start_loop()
        return True

    def soft_reset(self):
        """Resets arena state but KEEPS agents and their files."""
        self.running = False
        time.sleep(1)
        
        print("Arena: Soft Resetting...")
        
        # 1. Clear Histories
        self.chart_history.clear()
        for sym in self.symbols:
            self.market_history[sym].clear()
            
        # 2. Reset Agents
        for name in self.agents:
            self.agents[name].update({
                'equity': 100.0,
                'cash': 100.0,
                'total_fees': 0.0,
                'portfolio': {s: 0.0 for s in self.symbols},
                'roi': 0.0,
                'cashed_out': 0.0,
                # === FIX #1: Clear state on reset ===
                'entry_prices': {},
                'custom_state': {},
                'trade_history': []
            })
            
        # 3. DB Reset
        if self.db is not None:
            try:
                self.db.chart_history.delete_many({})
                self.db.trades.delete_many({})
                # Update agents in DB
                for name, data in self.agents.items():
                    self._save_agent_state(name)
            except Exception as e:
                print(f"Soft Reset DB Error: {e}")

        # 4. Re-init Chart
        start_time = datetime.now().timestamp() * 1000
        initial = {'timestamp': start_time, 'price': 0, 'agents': {n: 100.0 for n in self.agents.keys()}}
        self.chart_history.append(initial)
        if self.db is not None: self.db.chart_history.insert_one(initial.copy())
        
        # 5. Restart
        self.start_loop()
        return True

    def _data_producer(self):
        print("Producer: Started")
        while self.running:
            try:
                # Multi-ticker fetch
                # tickers = self.data_feed.get_multi_tickers()
                tickers = self.data_feed.get_market_snapshot()
                if tickers:
                    self.latest_tick = tickers
                time.sleep(1)
            except Exception as e:
                print(f"Producer Error: {e}")
                time.sleep(5)

    def _news_producer(self):
        print("News Producer: Started")
        while self.running:
            try:
                headlines = self.data_feed.get_news()
                if headlines:
                    # Append new unique headlines
                    for h in headlines:
                        if h['title'] not in [x['title'] for x in self.ui_news]:
                            self.ui_news.insert(0, h)
                            # Keep size manageable
                            if len(self.ui_news) > 50: self.ui_news.pop()
                            
                            # Emit Update
                            self.socketio.emit('news_update', h)
                            print(f"📰 News: {h['title']} ({h['sentiment']:.2f})")
                
                time.sleep(30) # Check every 30s
            except Exception as e:
                print(f"News Producer Error: {e}")
                time.sleep(60)

    def _loop(self):
        tick_counter = 0
        last_ts = 0
        last_analyst_log = 0
        
        while self.running:
          try:
            tickers = getattr(self, 'latest_tick', None)
            if not tickers:
                time.sleep(0.1)
                continue
            
            # Use Benchmark timestamp as reference (BTC or First available)
            benchmark_sym = 'BTC' if 'BTC' in tickers else list(tickers.keys())[0]
            ts = tickers.get(benchmark_sym, {}).get('timestamp', 0)
            
            if ts == last_ts:
                time.sleep(0.1)
                continue
            last_ts = ts
            
            # Update histories with extended data
            # Calc Tick Rule Volume Flow
            for sym, data in tickers.items():
                if sym in self.market_history:
                    # Tick Rule: Price > Prev ? Buy : Sell
                    prev_price = self.market_history[sym][-1]['price'] if self.market_history[sym] else data['price']
                    current_price = data['price']
                    vol = data['volume']
                    
                    buy_vol = 0.0
                    sell_vol = 0.0
                    
                    # Approximating incremental volume is hard with snapshot 'baseVolume' which is 24h rolling.
                    # Ideally we want 'volume change'. 
                    # For this demo, we assume 'volume' in snapshot is TOTAL 24h. We need delta.
                    # BUT `data_feed` snapshot `volume` IS usually 24h volume. 
                    # If we simply store that, we can't get flow. 
                    # So we calculate delta vol.
                    
                    last_vol = self.market_history[sym][-1]['volume_cum'] if (self.market_history[sym] and 'volume_cum' in self.market_history[sym][-1]) else vol
                    # Handle 24h reset or huge jump. If vol < last_vol, it reset.
                    if vol < last_vol: delta_vol = vol
                    else: delta_vol = vol - last_vol

                    # === FIX #3: Remove fake volume noise injection ===
                    # Old: Random noise when delta_vol == 0 gave agents fake signals
                    # New: Zero volume is real information - no activity = no signal
                    # delta_vol == 0 is legitimate and should stay 0

                    # Apply Tick Rule to DELTA volume
                    if current_price > prev_price:
                        buy_vol = delta_vol
                        sell_vol = 0
                    elif current_price < prev_price:
                        buy_vol = 0
                        sell_vol = delta_vol
                    else:
                        # === FIX #3: If price flat, split evenly (no random noise) ===
                        buy_vol = delta_vol * 0.5
                        sell_vol = delta_vol * 0.5

                    self.market_history[sym].append({
                        'timestamp': data['timestamp'],
                        'price': data['price'],
                        'high': data.get('high', data['price']),
                        'low': data.get('low', data['price']),
                        'open': data.get('open', data['price']),
                        'volume': delta_vol,     # Incremental volume for this tick
                        'volume_cum': vol,       # Store raw 24h vol for next delta calc
                        'buy_volume': buy_vol,
                        'sell_volume': sell_vol,
                        'funding_rate': 0.0001   # Default/Placeholder (will update periodically)
                    })
            
            # Periodically update funding rates (every 10 ticks ~ 10s)
            if tick_counter % 10 == 0:
                try:
                    f_rates = self.data_feed.get_funding_rates()
                    if f_rates:
                        for sym in self.symbols:
                            if sym in self.market_history and self.market_history[sym]:
                                # existing history items wont be updated, but new ones will use this
                                # Actually we just need to append it to the current "tick" but we already appended.
                                # Let's update the LAST item's funding rate
                                rate = f_rates.get(sym, 0.0001)
                                self.market_history[sym][-1]['funding_rate'] = rate
                except: pass

            # Prepare Market Data for Agents
            # === MODERATE FIX: Enable real sentiment analysis ===
            sentiment_score = 0.0
            try:
                if self.sentiment_engine and self.ui_news:
                    # Use the most recent news headline from UI buffer
                    latest_news = self.ui_news[0] if self.ui_news else None
                    if latest_news:
                        headline = latest_news.get('title', '')
                        if headline:
                            sentiment_score = self.sentiment_engine.get_sentiment_score(headline)
            except Exception as e:
                # Silently fall back to 0.0 on error
                sentiment_score = 0.0
            
            # 2. Update Attention (Google Trends) - cached hourly
            try:
                self.attention_cache = self.attention_feed.get_attention(['BTC', 'ETH', 'SOL'])
            except Exception:
                pass  # Keep existing cache on error

            market_data = {}
            for sym in self.symbols:
                hist = list(self.market_history[sym])
                history_prices = [h['price'] for h in hist]
                
                # Get Snapshot Data
                tick_data = tickers.get(sym, {})
                price = tick_data.get('price', 0)
                
                # --- CALC MICROSTRUCTURE SIGNALS ---
                # 1. Order Book Imbalance
                obi = calculate_multilevel_obi({
                    'bids': tick_data.get('bids', []),
                    'asks': tick_data.get('asks', [])
                })
                
                # 2. Micro Price
                best_bid = tick_data.get('bid', price)
                best_ask = tick_data.get('ask', price)
                # If no vol data in ticker, use 1.0/1.0 defaults or from OB
                # Mock volume for bid/ask if missing in ticker but present in OB
                best_bid_vol = 1.0
                best_ask_vol = 1.0
                
                if tick_data.get('bids') and len(tick_data['bids']) > 0:
                     best_bid_vol = tick_data['bids'][0][1]
                if tick_data.get('asks') and len(tick_data['asks']) > 0:
                     best_ask_vol = tick_data['asks'][0][1]
                     
                micro_price = calculate_weighted_microprice(best_bid, best_bid_vol, best_ask, best_ask_vol)
                
                
                # --- CALC HFT ALPHA SIGNALS ---
                # Convert deque to DF for Metrics
                df = pd.DataFrame(list(self.market_history[sym]))
                
                # Defaults
                parkinson_vol = 0.0
                cvd_score = 0.0
                taker_ratio = 1.0
                funding_vel = 0.0
                
                if not df.empty and len(df) > 15:
                    try:
                        # 1. Parkinson Vol
                        p_vol_series = CryptoMetrics.calculate_parkinson_volatility(df['high'], df['low'], window=14)
                        parkinson_vol = float(p_vol_series.iloc[-1])
                        
                        # 2. CVD Divergence
                        cvd_series = CryptoMetrics.calculate_cvd_divergence(df['price'], df['buy_volume'], df['sell_volume'], window=20)
                        cvd_score = float(cvd_series.iloc[-1])
                        
                        # 3. Taker Ratio (using our tick-rule volume)
                        taker_series = CryptoMetrics.calculate_taker_ratio(df['buy_volume'], df['sell_volume'], window=10)
                        taker_ratio = float(taker_series.iloc[-1])
                        
                        # 4. Funding Velocity
                        f_series = CryptoMetrics.calculate_funding_velocity(df['funding_rate'], window=5)
                        funding_vel = float(f_series.iloc[-1]) * 10000 # Scaling for readability
                        
                    except Exception as e:
                        # print(f"Calc Metrics Error {sym}: {e}")
                        pass

                market_data[sym] = {
                    'price': price,
                    'volume': tick_data.get('volume', 0),
                    'history': history_prices,
                    'prices': history_prices, 
                    'price_history': history_prices, 
                    'volumes': [h['volume'] for h in hist],
                    'timestamps': [h['timestamp'] for h in hist],
                    
                    # --- NEW ALPHA SIGNALS (INSTITUTIONAL GRADE) ---
                    'obi_weighted': obi,          # Renaming for consistency with brain
                    'micro_price': micro_price,   # Stoikov Fair Value
                    'sentiment': sentiment_score, # Sentiment
                    'ofi': (taker_ratio - 1.0) * 100, # Approx OFI from ratio
                    
                    'funding_rate_velocity': funding_vel,
                    'cvd_divergence': cvd_score,
                    'taker_ratio': taker_ratio,
                    'parkinson_vol': parkinson_vol,
                    'attention': self.attention_cache.get(sym, 0.0),  # Google Trends

                    'order_book': { 
                        'bids': tick_data.get('bids', []),
                        'asks': tick_data.get('asks', [])
                    }
                }
            
            # ===== ANALYST ENGINE UPDATE (Every 5 minutes) =====
            current_ts = time.time()
            if self.analyst and (current_ts - self.last_analyst_update) >= self.analyst_interval:
                try:
                    # Build order book snapshot for OBI calculation
                    order_book_snapshot = {sym: {
                        'bids': tickers.get(sym, {}).get('bids', []),
                        'asks': tickers.get(sym, {}).get('asks', [])
                    } for sym in self.symbols}
                    
                    self.current_market_state = self.analyst.compute_state(
                        market_history=self.market_history,
                        news_feed=self.news_feed_engine,
                        sentiment_engine=self.sentiment_engine,
                        order_book_snapshot=order_book_snapshot
                    )
                    self.last_analyst_update = current_ts
                    
                    # Emit to frontend
                    self.socketio.emit('analyst_update', self.current_market_state)
                    print(f"Arena: Analyst Update - Trend: {self.current_market_state.get('market_regime', {}).get('trend', 'N/A')}")
                    
                except Exception as e:
                    print(f"Arena: Analyst Engine error: {e}")
            
            # Broadcast
            # Determine Benchmark Price (BTC for Crypto, SPY or First for Stocks)
            benchmark_sym = 'BTC' if 'BTC' in self.symbols else ('SPY' if 'SPY' in self.symbols else self.symbols[0])
            benchmark_price = tickers.get(benchmark_sym, {}).get('price', 0)
            
            self.socketio.emit('market_tick', {'price': benchmark_price, 'timestamp': ts})
            
            # Chart update - SAFEGUARD against bad data
            if ts > 0 and benchmark_price > 0:
                chart_payload = {
                    'timestamp': ts,
                    'price': benchmark_price,
                    'agents': {n: d['equity'] for n, d in self.agents.items()}
                }
                self.chart_history.append(chart_payload)
                self._db_queue.put(('chart', chart_payload.copy()))
            
            updates = []
            
            # Agent Decisions
            agent_names = list(self.agents.keys())
            for name in agent_names:
                if name not in self.agents: continue
                data = self.agents[name]
                agent = data['instance']
                
                decision, symbol, quantity = "HOLD", None, 0
                
                try:
                    # === FIX #1: Build agent_state with entry prices and current PnL ===
                    agent_state = {
                        'entry_prices': data.get('entry_prices', {}),
                        'trade_history': data.get('trade_history', [])[-20:],  # Last 20 trades
                        'custom': data.get('custom_state', {}),
                        'current_pnl': {}  # Calculate PnL for each open position
                    }

                    # Calculate unrealized PnL for each open position
                    for asset, pos_qty in data['portfolio'].items():
                        if pos_qty != 0 and asset in data.get('entry_prices', {}):
                            entry = data['entry_prices'][asset]
                            current = tickers.get(asset, {}).get('price', 0)
                            if entry > 0 and current > 0:
                                if pos_qty > 0:  # Long position
                                    pnl_pct = ((current - entry) / entry) * 100
                                else:  # Short position
                                    pnl_pct = ((entry - current) / entry) * 100
                                agent_state['current_pnl'][asset] = {
                                    'pnl_percent': pnl_pct,
                                    'pnl_usd': (current - entry) * pos_qty if pos_qty > 0 else (entry - current) * abs(pos_qty),
                                    'entry_price': entry,
                                    'current_price': current
                                }

                    # execute_strategy(market_data, tick, cash, portfolio, market_state, agent_state)
                    # Pass market_state for agents that want enriched intelligence
                    try:
                        res = agent.execute_strategy(
                            market_data,
                            tick_counter,
                            data['cash'],
                            data['portfolio'],
                            market_state=self.current_market_state,
                            agent_state=agent_state  # NEW: Pass persistent state
                        )
                    except TypeError:
                        # Backward compatibility: try without agent_state
                        try:
                            res = agent.execute_strategy(
                                market_data,
                                tick_counter,
                                data['cash'],
                                data['portfolio'],
                                market_state=self.current_market_state
                            )
                        except TypeError:
                            # Backward compatibility: agent doesn't accept market_state
                            res = agent.execute_strategy(market_data, tick_counter, data['cash'], data['portfolio'])
                    
                    if isinstance(res, tuple) and len(res) == 3:
                        decision, symbol, quantity = res
                    else:
                        decision = "HOLD"
                    
                    # VALIDATION (Protect against "Degen" agents)
                    if decision in ["BUY", "SELL"]:
                         if not isinstance(quantity, (int, float)):
                             try:
                                 quantity = float(quantity)
                             except:
                                 decision = "HOLD" # Invalid quantity
                         
                         if symbol not in self.symbols:
                             decision = "HOLD" # Invalid symbol

                    # Execute (Safe now)
                    executed, fee = self._execute_order(name, data, decision, symbol, quantity, tickers)
                    
                    if executed and decision in ["BUY", "SELL"]:
                        self.socketio.emit('trade_log', {
                            'agent': name,
                            'action': decision,
                            'price': tickers.get(symbol, {}).get('price', 0),
                            'timestamp': ts,
                            'reason': f"{symbol} @ {quantity}",
                            'fee': fee
                        })
                        
                except Exception as e:
                    print(f"Agent {name} error: {e}")
                
                # Calc Equity
                equity = data['cash']
                for sym, qty in data['portfolio'].items():
                    price = tickers.get(sym, {}).get('price', 0)
                    equity += qty * price
                
                data['equity'] = equity
                data['roi'] = ((equity - 100) / 100) * 100
                
                # === FIX #2: Increased cash-out threshold to beat transaction costs ===
                # Old: 0.125% was less than fees (0.075% + slippage = ~0.15% round trip)
                # New: 0.50% ensures positive expectancy after costs
                CASHOUT_THRESHOLD = 0.50  # 0.50% ROI (Realistic Scalping Target)
                STARTING_EQUITY = 100.0
                
                if data['roi'] >= CASHOUT_THRESHOLD:
                    profit = equity - STARTING_EQUITY
                    data['cashed_out'] = data.get('cashed_out', 0.0) + profit
                    
                    # Close all positions by converting to cash at current prices
                    for sym, qty in data['portfolio'].items():
                        if qty != 0:
                            price = tickers.get(sym, {}).get('price', 0)
                            data['cash'] += qty * price  # Add position value to cash
                            data['portfolio'][sym] = 0.0  # Clear position
                    
                    # Reset to starting equity
                    data['cash'] = STARTING_EQUITY
                    data['equity'] = STARTING_EQUITY
                    data['roi'] = 0.0
                    
                    print(f"💰 CASH-OUT: {name} secured ${profit:.2f} profit! (Total: ${data['cashed_out']:.2f})")

                    # Clear entry prices on cashout
                    data['entry_prices'] = {}

                    # Emit cash-out event to frontend
                    self.socketio.emit('agent_cashout', {
                        'agent': name,
                        'profit': profit,
                        'total_cashed_out': data['cashed_out'],
                        'timestamp': ts
                    })

                # === FIX #4: Emergency Stop-Loss (Arena Safety Net) ===
                # If agent is losing badly (-2% from starting equity), force close all positions
                # This prevents catastrophic losses when agents fail to manage risk
                EMERGENCY_STOP_LOSS = -2.0  # -2% account drawdown triggers emergency exit
                if data['roi'] <= EMERGENCY_STOP_LOSS:
                    loss = STARTING_EQUITY - equity
                    print(f"🚨 EMERGENCY STOP: {name} hit -{abs(data['roi']):.2f}% drawdown. Closing all positions.")

                    # Close all positions
                    for sym, qty in data['portfolio'].items():
                        if qty != 0:
                            price = tickers.get(sym, {}).get('price', 0)
                            if qty > 0:
                                data['cash'] += qty * price
                            else:  # Short position
                                data['cash'] += qty * price  # qty is negative, so this subtracts
                            data['portfolio'][sym] = 0.0

                    # Clear entry prices
                    data['entry_prices'] = {}

                    # Recalculate equity
                    data['equity'] = data['cash']
                    data['roi'] = ((data['equity'] - STARTING_EQUITY) / STARTING_EQUITY) * 100

                    # Emit emergency stop event
                    self.socketio.emit('emergency_stop', {
                        'agent': name,
                        'loss': loss,
                        'final_equity': data['equity'],
                        'timestamp': ts
                    })

                updates.append({
                    'name': name,
                    'equity': data['equity'],
                    'roi': data['roi'],
                    'cash': data['cash'],
                    'total_fees': data.get('total_fees', 0.0),
                    'cashed_out': data.get('cashed_out', 0.0),
                    'portfolio': data['portfolio'],
                    'last_decision': f"{decision} {symbol if symbol else ''}",
                    # --- NEW METRICS ---
                    'trades': data.get('trades_count', 0),
                    'win_rate': round((data.get('wins', 0) / data.get('trades_count', 1)) * 100, 1) if data.get('trades_count', 0) > 0 else 0.0,
                    'sharpe': round(data.get('sharpe', 0.0), 2)
                })

            # Broadcast bundle
            updates.sort(key=lambda x: x['equity'], reverse=True)
            
            # Prepare multi-asset market payload
            market_payload = {
                'timestamp': ts,
                'prices': {s: tickers.get(s, {}).get('price', 0) for s in self.symbols}
            }
            
            self.socketio.emit('tick_bundle', {
                'market': market_payload,
                'chart': chart_payload,
                'leaderboard': updates
            })
            
            # DB Save
            if self.running:
                states = {n: {k: v for k, v in d.items() if k != 'instance'} for n, d in self.agents.items()}
                self._db_queue.put(('agents_bulk', states))
            
            # SUPERVISOR CHECK (Strategy Management) - DISABLED to prevent automatic regeneration
            # Uncomment below to re-enable automatic agent evolution based on market triggers
            # try:
            #     current_ts = time.time() # Seconds
            #     actions = self.supervisor.monitor(self.agents, self.market_history, current_ts)
            #     
            #     if actions:
            #         print(f"Arena: Supervisor triggered {len(actions)} actions.")
            #         from analyst_engine.brain import Brain
            #         brain = Brain() # Instantiate locally to avoid circular import issues if any
            #         
            #         for act in actions:
            #             if act['action'] == 'KILL':
            #                 name = act['agent']
            #                 reason = act['reason']
            #                 print(f"Arena: KILLING {name} due to: {reason}")
            #                 
            #                 # Notify Frontend
            #                 self.socketio.emit('agent_regenerating', {'name': name, 'critique': reason})
            #                 
            #                 # Trigger Evolution (Soft Kill / Refactor)
            #                 # We use existing code as base but force a major rethink via critique
            #                 if name in self.agents:
            #                     old_code = ""
            #                     filepath = os.path.join(self.agent_dir, f"{name}.py")
            #                     if os.path.exists(filepath):
            #                         with open(filepath, 'r') as f: old_code = f.read()
            #                     
            #                     result = brain.evolve_agent(name, reason, old_code)
            #                     
            #                     if result.get("success"):
            #                         print(f"Arena: Supervisor successfully revived {name}")
            #                         self.load_agent(name, reload_module=True)
            #                         self.socketio.emit('agent_deployed', {'name': name})
            # except Exception as e:
            #     print(f"Arena: Supervisor Check Error: {e}")

            tick_counter += 1
            time.sleep(1)
          except Exception as e:
            print(f"[LOOP ERROR] {e}", flush=True)
            import traceback
            traceback.print_exc()
            time.sleep(5)  # Wait before retrying

    def _execute_order(self, name, data, decision, symbol, quantity, tickers):
        if decision == "HOLD" or not symbol or quantity <= 0: return False, 0.0
        
        price = tickers.get(symbol, {}).get('price', 0)
        if price <= 0: return False, 0.0
        
        # === FIX #2: Realistic fee structure ===
        # Binance VIP0: 0.1% maker, 0.1% taker -> avg 0.075% with BNB discount
        # Old: 0.01% was unrealistically low
        fee_rate = 0.00075  # 0.075% fee (Realistic tier)
        
        # Simulate execution slippage (0.01% - 0.05% adverse price movement)
        slippage = np.random.uniform(0.0001, 0.0005)
        if decision == "BUY":
            price = price * (1 + slippage)  # Pay slightly more when buying
        else:
            price = price * (1 - slippage)  # Receive slightly less when selling
        
        # Calculate Equity for leverage check
        total_equity = data['cash']
        for s, q in data['portfolio'].items():
            total_equity += q * tickers.get(s, {}).get('price', 0)
            
        if decision == "BUY":
            cost = quantity * price
            fee = cost * fee_rate
            total_req = cost + fee
            
            # Check Max Buying Power (4x)
            current_long_value = sum([q * tickers.get(s, {}).get('price', 0) for s, q in data['portfolio'].items() if q > 0])
            max_long = total_equity * 4
            buying_power = max_long - current_long_value
            
            # LOGIC FIX: If we are covering a short (curr_qty < 0), we shouldn't be limited by "Buying Power" (Max Long Leverage).
            # We are reducing risk, not increasing it.
            curr_qty = data['portfolio'].get(symbol, 0)
            
            allowed = False
            if curr_qty < 0:
                # Covering Short: Only check if we have enough Cash (Liquidity)
                # We already received cash when we sold, so this should usually pass unless we lost too much.
                if data['cash'] >= total_req:
                    allowed = True
            else:
                # Opening/Increasing Long: Check Leverage
                if buying_power >= cost and data['cash'] >= total_req:
                    allowed = True
            
            if allowed:
                # --- METRICS & ENTRY PRICE UPDATE ---
                data['trades_count'] = data.get('trades_count', 0) + 1

                # Calculate new Weighted Average Entry Price
                prev_qty = data['portfolio'].get(symbol, 0)
                prev_entry = data.get('entry_prices', {}).get(symbol, 0.0)

                if 'entry_prices' not in data: data['entry_prices'] = {}
                if 'trade_history' not in data: data['trade_history'] = []

                # === FIX #1: Proper entry price handling for BUY ===
                if prev_qty < 0:
                    # Covering a short position
                    new_qty = prev_qty + quantity
                    if new_qty >= 0:
                        # Position fully closed or flipped to long
                        # Clear the short entry price
                        if symbol in data['entry_prices']:
                            del data['entry_prices'][symbol]
                        # If flipped to long, set new entry
                        if new_qty > 0:
                            data['entry_prices'][symbol] = price
                    # else: still short, keep existing entry
                else:
                    # Opening or adding to long
                    new_qty = prev_qty + quantity
                    if new_qty > 0:
                        if prev_qty > 0 and prev_entry > 0:
                            # Weighted average
                            total_cost = (prev_qty * prev_entry) + (quantity * price)
                            avg_entry = total_cost / new_qty
                            data['entry_prices'][symbol] = avg_entry
                        else:
                            # New position
                            data['entry_prices'][symbol] = price

                # Record trade in history
                data['trade_history'].append({
                    'action': 'BUY',
                    'symbol': symbol,
                    'quantity': quantity,
                    'price': price,
                    'fee': fee,
                    'timestamp': int(time.time() * 1000)
                })
                # Keep history bounded
                if len(data['trade_history']) > 100:
                    data['trade_history'] = data['trade_history'][-100:]

                data['cash'] -= total_req
                data['portfolio'][symbol] = data['portfolio'].get(symbol, 0) + quantity
                data['total_fees'] = data.get('total_fees', 0.0) + fee
                print(f"{name} BOUGHT {quantity} {symbol} @ {price} (Fee: {fee:.4f})")
                return True, fee

        elif decision == "SELL":
            curr_qty = data['portfolio'].get(symbol, 0)

            revenue = quantity * price
            fee = revenue * fee_rate
            proceeds = revenue - fee

            if 'entry_prices' not in data: data['entry_prices'] = {}
            if 'trade_history' not in data: data['trade_history'] = []

            # --- METRICS: Track Wins (Long Only for now) ---
            if curr_qty > 0:
                entry_price = data.get('entry_prices', {}).get(symbol, 0.0)
                if entry_price > 0 and price > entry_price:
                    data['wins'] = data.get('wins', 0) + 1

            data['trades_count'] = data.get('trades_count', 0) + 1

            # Safety checks for shorting leverage
            max_short = total_equity * 4
            current_short_value = sum([abs(q) * tickers.get(s, {}).get('price', 0) for s, q in data['portfolio'].items() if q < 0])

            if curr_qty <= 0:
                # Opening/Increasing Short
                if (max_short - current_short_value) >= revenue:
                    # === FIX #1: Track entry price for shorts ===
                    if curr_qty == 0:
                        # New short position
                        data['entry_prices'][symbol] = price
                    # else: already short, keep existing entry (could do weighted avg)

                    data['cash'] += proceeds
                    data['portfolio'][symbol] = curr_qty - quantity
                    data['total_fees'] = data.get('total_fees', 0.0) + fee

                    # Record trade
                    data['trade_history'].append({
                        'action': 'SELL',
                        'symbol': symbol,
                        'quantity': quantity,
                        'price': price,
                        'fee': fee,
                        'timestamp': int(time.time() * 1000)
                    })
                    if len(data['trade_history']) > 100:
                        data['trade_history'] = data['trade_history'][-100:]

                    print(f"{name} SHORTED {quantity} {symbol} @ {price} (Fee: {fee:.4f})")
                    return True, fee
            else:
                # Closing Long
                new_qty = curr_qty - quantity

                # === FIX #1: Clear entry price when fully closed ===
                if new_qty <= 0:
                    if symbol in data['entry_prices']:
                        del data['entry_prices'][symbol]
                    # If flipped to short, set new entry
                    if new_qty < 0:
                        data['entry_prices'][symbol] = price

                data['cash'] += proceeds
                data['portfolio'][symbol] = new_qty
                data['total_fees'] = data.get('total_fees', 0.0) + fee

                # Record trade
                data['trade_history'].append({
                    'action': 'SELL',
                    'symbol': symbol,
                    'quantity': quantity,
                    'price': price,
                    'fee': fee,
                    'timestamp': int(time.time() * 1000)
                })
                if len(data['trade_history']) > 100:
                    data['trade_history'] = data['trade_history'][-100:]

                print(f"{name} SOLD {quantity} {symbol} @ {price} (Fee: {fee:.4f})")
                return True, fee

        return False, 0.0
