import time
import importlib.util
import os
import threading
import numpy as np
import pandas as pd
from datetime import datetime
from data_feed import DataFeed

# Global state access (circular import avoidance usually handled by passing socketio/db to init)

class Arena:
    def __init__(self, socketio, db):
        self.socketio = socketio
        self.db = db
        self.data_feed = DataFeed()
        self.running = False
        self.agents = {} # {name: {'instance': obj, 'equity': 1000000, 'cash': 1000000, 'holdings': 0}}
        self.agent_dir = "agents"
        
        if not hasattr(self, 'chart_history') or not self.chart_history:
             self.chart_history = [] # In-memory history of chart ticks
             
        # Fetch Market History for Agent Warmup (390 minutes of 1m candles for full day context)
        # MUST BE DONE BEFORE RESTORE STATE
        print("Arena: Fetching Market History for Warmup...")
        self.market_history_snapshot = self.data_feed.get_historical_data(limit=390, timeframe='1m')
        print(f"Arena: Loaded {len(self.market_history_snapshot)} history points.")
        
        # Restore state on startup
        if self.db is not None:
            self._restore_state()
            self._restore_chart_history()

    def _restore_chart_history(self):
        """Loads chart history from MongoDB."""
        try:
            # Sort by timestamp ascending
            history = list(self.db.chart_history.find({}, {'_id': 0}).sort('timestamp', 1))
            if history:
                self.chart_history = history
                print(f"Restored {len(history)} chart ticks from DB.")
        except Exception as e:
            print(f"Failed to restore chart history: {e}")
            self.chart_history = []

    def _restore_state(self):
        """Restores agents from MongoDB."""
        try:
            saved_agents = self.db.agents.find()
            count = 0
            for doc in saved_agents:
                name = doc['name']
                # Load the code
                if self.load_agent(name, restore=True):
                    # Restore values
                    self.agents[name]['equity'] = doc.get('equity', 100.0)
                    self.agents[name]['cash'] = doc.get('cash', 100.0)
                    self.agents[name]['holdings'] = doc.get('holdings', 0.0)
                    count += 1
            print(f"Restored {count} agents from DB.")
            if count > 0:
                self.start_loop()
        except Exception as e:
            print(f"Failed to restore state: {e}")

    def load_agent(self, name, restore=False):
        """Loads a single agent by name (filename must be name.py)."""
        filepath = os.path.join(self.agent_dir, f"{name}.py")
        if not os.path.exists(filepath):
            print(f"Agent file not found: {filepath}")
            return False

        try:
            spec = importlib.util.spec_from_file_location(name, filepath)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Check for Functional Agent (execute_trade)
            if hasattr(module, 'execute_trade'):
                print(f"Arena: Detected Functional Agent '{name}'")
                instance = module # The module acts as the instance
                
                # INJECT GLOBAL DATA (Numpy Arrays)
                if self.market_history_snapshot:
                    df = pd.DataFrame(self.market_history_snapshot)
                    setattr(module, 'opens', df['open'].values)
                    setattr(module, 'highs', df['high'].values)
                    setattr(module, 'lows', df['low'].values)
                    setattr(module, 'closes', df['close'].values)
                    setattr(module, 'volumes', df['volume'].values)
                    # Helper for appending later
                    module._history_df = df
            
            else:
                # Legacy Class-based Agent
                print(f"Arena: Detected Class Agent '{name}'")
                AgentClass = getattr(module, name)
                instance = AgentClass()
                
                # INJECT HISTORY (Warm Up)
                if hasattr(instance, 'history') and isinstance(instance.history, list):
                    if not instance.history and self.market_history_snapshot:
                        instance.history = self.market_history_snapshot.copy()
                        # Pad volume_history if it exists
                        if hasattr(instance, 'volume_history') and isinstance(instance.volume_history, list):
                            if not instance.volume_history:
                                instance.volume_history = [0] * len(instance.history)
            
            # Initialize state if not exists
            if name not in self.agents:
                self.agents[name] = {
                    'instance': instance,
                    'type': 'functional' if hasattr(module, 'execute_trade') else 'class',
                    'equity': 100.0,
                    'cash': 100.0,
                    'holdings': 0.0,
                    'roi': 0.0
                }
                # Save initial state to DB if this is a fresh load (not restore)
                if not restore and self.db is not None:
                    self._save_agent_state(name)
            else:
                # Update instance but keep state
                self.agents[name]['instance'] = instance
                self.agents[name]['type'] = 'functional' if hasattr(module, 'execute_trade') else 'class'
                
            print(f"Loaded agent: {name}")
            return True
        except Exception as e:
            print(f"Failed to load agent {name}: {e}")
            return False
            
    def _save_agent_state(self, name):
        """Upsert agent state to DB."""
        if self.db is None: return
        data = self.agents[name].copy()
        del data['instance'] # Cannot serialize object
        self.db.agents.update_one(
            {'name': name},
            {'$set': {'name': name, **data}},
            upsert=True
        )

    def start_loop(self):
        if self.running:
            return
        self.running = True
        
        # Start Data Producer (Fetches from Binance)
        self.producer_thread = threading.Thread(target=self._data_producer)
        self.producer_thread.daemon = True
        self.producer_thread.start()
        
        # Start Agent Consumer (Runs Simulation)
        self.consumer_thread = threading.Thread(target=self._loop)
        self.consumer_thread.daemon = True
        self.consumer_thread.start()
        
        print("Arena: Producer & Consumer Threads Started")

    def stop_loop(self):
        self.running = False
        print("Arena Loop Stopped (Requested)")

    def reset(self, default_agents):
        """Thread-safe reset of the arena."""
        print("RESET: Stopping Loop...")
        self.running = False
        time.sleep(1) # Give loop time to exit
        
        print("RESET: Clearing Memory & DB...")
        self.agents = {} # Clear memory
        self.chart_history = [] # Clear history
        
        if self.db is not None:
            try:
                self.db.agents.delete_many({}) # Clear DB
                self.db.chart_history.delete_many({}) # Clear Chart History
                print("RESET: DB Cleared.")
            except Exception as e:
                print(f"RESET: DB Clear Failed: {e}")
        
        # Initialize Chart History with Starting Point
        start_time = datetime.now().timestamp() * 1000
        initial_payload = {
            'timestamp': start_time,
            'price': 0, # Irrelevant for agent lines
            'agents': {name: 100.0 for name in default_agents}
        }
        self.chart_history.append(initial_payload)
        
        # Save initial point to DB
        if self.db is not None:
            self.db.chart_history.insert_one(initial_payload.copy())
        
        print(f"RESET: Reloading defaults: {default_agents}")
        for agent_name in default_agents:
            self.load_agent(agent_name)
            
        print("RESET: Restarting Loop...")
        self.start_loop()
        return True

    def _data_producer(self):
        """
        Background thread that purely fetches data.
        Does NOT block the simulation loop.
        """
        tick_count = 0
        last_depth = {'bids': [], 'asks': []}
        
        print("Arena: Data Producer Started")
        
        while self.running:
            try:
                # print(f"Producer: Fetching Ticker... {tick_count}")
                # 1. Fetch Ticker (Fast)
                ticker = self.data_feed.get_ticker()
                # print(f"Producer: Got Ticker {ticker['price'] if ticker else 'None'}")
                
                # 2. Fetch Order Book (Slow - every 10 ticks)
                if tick_count % 10 == 0:
                    try:
                        # print("Producer: Fetching Depth...")
                        last_depth = self.data_feed.get_order_book(limit=5)
                        # print("Producer: Got Depth")
                    except Exception as e:
                        print(f"Producer: Depth fetch failed: {e}")
                
                if ticker:
                    # Enrich and Cache
                    ticker['depth'] = last_depth
                    self.latest_tick = ticker # Atomic update (Python dict)
                    # print(f"Producer: Updated latest_tick to {ticker['price']}")
                
                tick_count += 1
                time.sleep(1) # Poll every 1s
                
            except Exception as e:
                print(f"Producer Error: {e}")
                time.sleep(5) # Backoff

    def _loop(self):
        """
        Consumer thread that runs agents.
        Reads from self.latest_tick (Non-Blocking).
        """
        last_processed_time = None
        tick_counter = 0 # For 'tick' argument in execute_trade
        
        while self.running:
            # Read cached data
            tick = getattr(self, 'latest_tick', None)
            
            if not tick:
                time.sleep(0.1)
                continue
                
            # Dedup: Don't process the same tick twice
            if tick['timestamp'] == last_processed_time:
                time.sleep(0.1)
                continue
            
            last_processed_time = tick['timestamp']
            
            price = tick['price']
            timestamp = tick['timestamp']
            
            # Broadcast to frontend immediately
            self.socketio.emit('market_tick', tick)
            
            # Broadcast unified chart tick
            current_time_ms = datetime.now().timestamp() * 1000
            
            chart_payload = {
                'timestamp': current_time_ms,
                'price': price,
                'agents': {name: d['equity'] for name, d in self.agents.items()}
            }
            self.chart_history.append(chart_payload)
            
            if self.db is not None:
                try:
                    self.db.chart_history.insert_one(chart_payload.copy())
                except Exception as e:
                    pass # Ignore db errors in loop

            if len(self.chart_history) > 50000:
                self.chart_history.pop(0)

            self.socketio.emit('chart_tick', chart_payload)
            
            updates = []
            
            # Create a snapshot of keys to iterate safely
            current_agent_names = list(self.agents.keys())
            
            for name in current_agent_names:
                # Double check existence in case reset cleared it mid-loop
                if name not in self.agents: continue
                agent_data = self.agents[name]
                if 'instance' not in agent_data: continue

                agent = agent_data['instance']
                agent_type = agent_data.get('type', 'class')
                
                # Execute Strategy
                decision = "HOLD"
                reason = ""
                quantity = 0
                
                try:
                    if agent_type == 'functional':
                        # Update Agent's Internal Data Arrays with NEW tick info
                        # We append the new price to the numpy arrays so indicators can calculate on latest data
                        if hasattr(agent, '_history_df'):
                            # Create new row
                            new_row = pd.DataFrame([{
                                'timestamp': timestamp, 
                                'open': price, 'high': price, 'low': price, 'close': price, 
                                'volume': 0 # Volume not really available live tick-by-tick easily without aggregation
                            }])
                            # Inefficiencies here (appending efficiently is hard), but for 1s loop it's OK-ish
                            # Better: Rolling buffer. For now, concat.
                            # Limit growth to prevent memory leak? Keep last 1000?
                            agent._history_df = pd.concat([agent._history_df, new_row], ignore_index=True).tail(500)
                            
                            # Update injected arrays
                            setattr(agent, 'opens', agent._history_df['open'].values)
                            setattr(agent, 'highs', agent._history_df['high'].values)
                            setattr(agent, 'lows', agent._history_df['low'].values)
                            setattr(agent, 'closes', agent._history_df['close'].values)
                            setattr(agent, 'volumes', agent._history_df['volume'].values)

                        # Call execute_trade
                        # def execute_trade(ticker, price, tick, cash_balance, shares_held):
                        result = agent.execute_trade(name, price, tick_counter, agent_data['cash'], agent_data['holdings'])
                        
                        if isinstance(result, dict):
                            decision = result.get('action', 'HOLD')
                            quantity = result.get('quantity', 0)
                        else:
                            decision = "HOLD" # Invalid return
                            
                    else:
                        # Legacy Class Agent
                        # Update history manualy
                        if hasattr(agent, 'history'):
                            agent.history.append({
                                'timestamp': timestamp,
                                'open': price, 'high': price, 'low': price, 'close': price,
                                'volume': 0
                            })
                            if len(agent.history) > 100: agent.history.pop(0)
                            
                        trade_result = agent.trade(tick)
                        if isinstance(trade_result, dict):
                            decision = trade_result.get('action', 'HOLD')
                            reason = trade_result.get('reason', '')
                        else:
                            decision = trade_result
                            
                except Exception as e:
                    print(f"Agent {name} crashed: {e}")
                    decision = "HOLD"
                    reason = f"Error: {e}"

                # Execute Order
                self._execute_order(name, agent_data, decision, price, quantity)
                
                # Update Equity (Cash + Holdings * Price)
                equity = agent_data['cash'] + (agent_data['holdings'] * price)
                agent_data['equity'] = equity
                roi = ((equity - 100) / 100) * 100
                agent_data['roi'] = roi
                
                # Periodic Save (could optimize to only save on change)
                if self.running: 
                    self._save_agent_state(name)
                
                updates.append({
                    'name': name,
                    'equity': equity,
                    'roi': roi,
                    'holdings': agent_data['holdings'],
                    'last_decision': decision
                })
                
                # Log trade if acted
                if decision in ["BUY", "SELL"]:
                    trade_log = {
                        'agent': name,
                        'action': decision,
                        'price': price,
                        'timestamp': timestamp,
                        'reason': reason
                    }
                    self.socketio.emit('trade_log', trade_log)

            # Broadcast Leaderboard Update
            updates.sort(key=lambda x: x['equity'], reverse=True)
            # print(f"Emitting Leaderboard Update for {len(updates)} agents")
            self.socketio.emit('leaderboard_update', updates)
            
            tick_counter += 1
            if tick_counter > 390: tick_counter = 0 # Daily cycle reset
            
            time.sleep(1) # Tick every 1 second

    def _execute_order(self, name, data, decision, price, quantity=0):
        # Realism Mode: Spot (1x) + Short (0.4x) + 0.025% Fees (Institutional)
        fee_rate = 0.00025
        
        # Calculate current equity
        equity = data['cash'] + (data['holdings'] * price)
        
        if decision == "BUY":
            # Scenario A: COVER SHORT (Negative Holdings)
            if data['holdings'] < 0:
                amount_to_cover = abs(data['holdings'])
                
                # If quantity specified, partial cover? 
                # For simplicity, if functional agent says BUY, we check quantity.
                # If quantity is 0 or not passed (legacy), we assume "close short or buy max".
                # Let's enforce the quantity if provided > 0.
                if quantity > 0:
                    amount_to_cover = min(amount_to_cover, quantity)
                    
                cost = amount_to_cover * price
                fee = cost * fee_rate
                
                total_cost = cost + fee
                
                if data['cash'] >= total_cost:
                    data['cash'] -= total_cost
                    data['holdings'] += amount_to_cover # Becomes less negative or zero
                    print(f"{name} COVERED SHORT {amount_to_cover:.6f} BTC @ {price} | Cost: ${total_cost:.2f}")

            # Scenario B: OPEN LONG (Flat or Positive)
            elif data['holdings'] >= 0:
                # Buy with available CASH
                if data['cash'] > 1.0:
                    # Leverage 4x check? Prompt says "4x leverage".
                    # Arena implementation: Standard "Cash" account for buying?
                    # If we want 4x leverage, we should allow buying up to 4x Equity.
                    # Current logic: Buy up to Cash. 
                    # REQUIRED CHANGE: Allow buying on margin (negative cash?) OR just pretend cash is 4x?
                    # The user prompt: "can trade up to $40,000 with $10,000 capital".
                    # So we should allow `data['cash']` to go negative? 
                    # Simplest way: Allow purchasing provided Margin Ratio is safe.
                    # Check Max Buying Power = Equity * 4
                    # Current Holding Value = Holdings * Price
                    # Buying Power Remaining = (Equity * 4) - Current Position Value
                    
                    max_position_value = equity * 4.0
                    current_position_value = data['holdings'] * price
                    available_buying_power = max_position_value - current_position_value
                    
                    if available_buying_power > 10.0:
                        amount_to_buy = available_buying_power / price
                        
                        if quantity > 0:
                            amount_to_buy = min(amount_to_buy, quantity)
                        
                        cost = amount_to_buy * price
                        fee = cost * fee_rate
                        
                        # We reduce cash (can go negative - margin loan)
                        data['cash'] -= (cost + fee)
                        data['holdings'] += amount_to_buy
                        print(f"{name} BOUGHT {amount_to_buy:.6f} BTC @ {price} | Fee: ${fee:.4f}")

        elif decision == "SELL":
            # Scenario A: CLOSE LONG (Positive Holdings)
            if data['holdings'] > 0:
                amount_to_sell = data['holdings']
                if quantity > 0:
                    amount_to_sell = min(amount_to_sell, quantity)
                    
                revenue = amount_to_sell * price
                fee = revenue * fee_rate
                proceeds = revenue - fee
                
                data['cash'] += proceeds
                data['holdings'] -= amount_to_sell
                print(f"{name} SOLD LONG {amount_to_sell:.6f} BTC @ {price} | Fee: ${fee:.4f}")

            # Scenario B: OPEN SHORT (Flat or Negative)
            elif data['holdings'] <= 0:
                # Check Max Short Power = Equity * 4 ?
                # Prompt says "4x LEVERAGE... SHORT SELLING".
                # Standard margin: Margin Requirement usually 50%. 2x leverage? 
                # Prompt says 4x.
                
                max_short_value = equity * 4.0
                current_short_value = abs(data['holdings']) * price
                available_short_power = max_short_value - current_short_value
                
                if available_short_power > 10.0:
                    amount_to_short = available_short_power / price
                    
                    if quantity > 0:
                        amount_to_short = min(amount_to_short, quantity)
                        
                    revenue = amount_to_short * price
                    fee = revenue * fee_rate
                    proceeds = revenue - fee
                    
                    # Shorting CREDITS cash
                    data['cash'] += proceeds
                    data['holdings'] -= amount_to_short
                    print(f"{name} SHORTED {amount_to_short:.6f} BTC @ {price} | Credit: ${proceeds:.2f}")
