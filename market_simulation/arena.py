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
        self.symbols = ["BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "ZEC", "TRX", "SUI", "LINK", "PEPE", "SHIB", "WIF", "ADA", "AVAX"]
        
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
            self.news_feed = NewsFeed()
            print("Arena: Analyst Engine initialized.")
        else:
            self.analyst = None
            self.news_feed = None
        
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
                    self.agents[name]['equity'] = doc.get('equity', 10000.0)
                    self.agents[name]['cash'] = doc.get('cash', 10000.0)
                    self.agents[name]['total_fees'] = doc.get('total_fees', 0.0)
                    self.agents[name]['portfolio'] = doc.get('portfolio', {s: 0.0 for s in self.symbols})
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
                        'equity': 10000.0,
                        'cash': 10000.0,
                        'total_fees': 0.0,
                        'portfolio': {s: 0.0 for s in self.symbols},
                        'roi': 0.0,
                        'cashed_out': 0.0  # Total profits secured via auto cash-out
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
        initial = {'timestamp': start_time, 'price': 0, 'agents': {n: 10000.0 for n in default_agents}}
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
                'equity': 10000.0,
                'cash': 10000.0,
                'total_fees': 0.0,
                'portfolio': {s: 0.0 for s in self.symbols},
                'roi': 0.0,
                'cashed_out': 0.0
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
        initial = {'timestamp': start_time, 'price': 0, 'agents': {n: 10000.0 for n in self.agents.keys()}}
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

    def _loop(self):
        tick_counter = 0
        last_ts = 0
        last_analyst_log = 0
        
        while self.running:
            tickers = getattr(self, 'latest_tick', None)
            if not tickers:
                time.sleep(0.1)
                continue
            
            # Use BTC timestamp as reference
            ts = tickers.get('BTC', {}).get('timestamp', 0)
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
                    
                    # Synthetic HFT Noise Injection (Simulation Fidelity)
                    # If data is stale (delta_vol=0), we simulate micro-transactions to keep signals alive
                    if delta_vol == 0:
                         delta_vol = np.random.uniform(0.01, 1.0) # Small noise
                    
                    # Apply Tick Rule to DELTA volume
                    if current_price > prev_price:
                        buy_vol = delta_vol
                        sell_vol = 0
                    elif current_price < prev_price:
                        buy_vol = 0
                        sell_vol = delta_vol
                    else:
                        # If price flat, random split (Noise)
                        split = np.random.random()
                        buy_vol = delta_vol * split
                        sell_vol = delta_vol * (1 - split)

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
            # 1. Calc Global Sentiment (Lightweight check: only revisit if news changed or periodically)
            # For this MVP, we just take the first headline from mock news
            sentiment_score = 0.0
            try:
                if self.sentiment_engine:
                    # In production, we'd only run this on new news.
                    # For demo, we just pick one random headline or the top one.
                    # Using a cache would be better to avoid 1s inference lag.
                    news_items = self.data_feed.get_news() 
                    headline = news_items[0] if news_items else ""
                    sentiment_score = self.sentiment_engine.get_sentiment_score(headline)
            except Exception:
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
                        news_feed=self.news_feed,
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
            btc_price = tickers.get('BTC', {}).get('price', 0)
            
            self.socketio.emit('market_tick', {'price': btc_price, 'timestamp': ts})
            
            # Chart update - SAFEGUARD against bad data
            if ts > 0 and btc_price > 0:
                chart_payload = {
                    'timestamp': ts,
                    'price': btc_price,
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
                    # execute_strategy(market_data, tick, cash, portfolio, market_state)
                    # Pass market_state for agents that want enriched intelligence
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
                data['roi'] = ((equity - 10000) / 10000) * 100
                
                # === AUTO CASH-OUT: When ROI >= 0.5%, secure profits and reset ===
                CASHOUT_THRESHOLD = 0.5  # 0.5% ROI
                STARTING_EQUITY = 10000.0
                
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
                    
                    # Emit cash-out event to frontend
                    self.socketio.emit('agent_cashout', {
                        'agent': name,
                        'profit': profit,
                        'total_cashed_out': data['cashed_out'],
                        'timestamp': ts
                    })
                
                updates.append({
                    'name': name,
                    'equity': data['equity'],
                    'roi': data['roi'],
                    'total_fees': data.get('total_fees', 0.0),
                    'cashed_out': data.get('cashed_out', 0.0),  # Include cashed out profits
                    'portfolio': data['portfolio'], # Send full portfolio
                    'last_decision': f"{decision} {symbol if symbol else ''}"
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
            
            # SUPERVISOR CHECK (Strategy Management)
            try:
                current_ts = time.time() # Seconds
                actions = self.supervisor.monitor(self.agents, self.market_history, current_ts)
                
                if actions:
                    print(f"Arena: Supervisor triggered {len(actions)} actions.")
                    from analyst_engine.brain import Brain
                    brain = Brain() # Instantiate locally to avoid circular import issues if any
                    
                    for act in actions:
                        if act['action'] == 'KILL':
                            name = act['agent']
                            reason = act['reason']
                            print(f"Arena: KILLING {name} due to: {reason}")
                            
                            # Notify Frontend
                            self.socketio.emit('agent_regenerating', {'name': name, 'critique': reason})
                            
                            # Trigger Evolution (Soft Kill / Refactor)
                            # We use existing code as base but force a major rethink via critique
                            if name in self.agents:
                                old_code = ""
                                filepath = os.path.join(self.agent_dir, f"{name}.py")
                                if os.path.exists(filepath):
                                    with open(filepath, 'r') as f: old_code = f.read()
                                
                                result = brain.evolve_agent(name, reason, old_code)
                                
                                if result.get("success"):
                                    print(f"Arena: Supervisor successfully revived {name}")
                                    self.load_agent(name, reload_module=True)
                                    self.socketio.emit('agent_deployed', {'name': name})
            except Exception as e:
                print(f"Arena: Supervisor Check Error: {e}")

            tick_counter += 1
            time.sleep(1)

    def _execute_order(self, name, data, decision, symbol, quantity, tickers):
        if decision == "HOLD" or not symbol or quantity <= 0: return False, 0.0
        
        price = tickers.get(symbol, {}).get('price', 0)
        if price <= 0: return False, 0.0
        
        # Realistic fee structure (Binance VIP0: 0.1% maker, 0.1% taker -> avg 0.075% with BNB discount)
        fee_rate = 0.00075  # 0.075% fee
        
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
            
            if buying_power >= cost:
                data['cash'] -= total_req
                data['portfolio'][symbol] = data['portfolio'].get(symbol, 0) + quantity
                data['total_fees'] = data.get('total_fees', 0.0) + fee
                print(f"{name} BOUGHT {quantity} {symbol} @ {price} (Fee: {fee:.4f})")
                return True, fee

        elif decision == "SELL":
            # Check shorting or closing?
            curr_qty = data['portfolio'].get(symbol, 0)
            
            # If we have positive holdings, selling reduces them (Close Long)
            # If we are flat/negative, selling increases short (Open Short)
            
            revenue = quantity * price
            fee = revenue * fee_rate
            proceeds = revenue - fee
            
            # Safety checks for shorting leverage could be added here
            max_short = total_equity * 4
            current_short_value = sum([abs(q) * tickers.get(s, {}).get('price', 0) for s, q in data['portfolio'].items() if q < 0])
            
            if curr_qty <= 0:
                # Opening/Increasing Short
                if (max_short - current_short_value) >= revenue:
                    data['cash'] += proceeds
                    data['portfolio'][symbol] = curr_qty - quantity
                    data['total_fees'] = data.get('total_fees', 0.0) + fee
                    print(f"{name} SHORTED {quantity} {symbol} @ {price} (Fee: {fee:.4f})")
                    return True, fee
            else:
                # Closing Long
                data['cash'] += proceeds
                data['portfolio'][symbol] = curr_qty - quantity
                data['total_fees'] = data.get('total_fees', 0.0) + fee
                print(f"{name} SOLD {quantity} {symbol} @ {price} (Fee: {fee:.4f})")
                return True, fee
                
        return False, 0.0
