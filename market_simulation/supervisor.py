
import numpy as np
import time

class Supervisor:
    def __init__(self):
        self.last_check_time = 0
        self.check_interval = 300  # 5 minutes, as per spec
        self. atr_window = 60 # 1 hour if data is per minute (approx)
        self.vol_ma_window = 60 

    def monitor(self, agents, market_history, current_time):
        """
        Main entry point. Checks conditions and returns actions.
        Args:
            agents: Dict of agent objects/data
            market_history: Dict of deques containing price/volume history
            current_time: Current timestamp (seconds or ms)
        Returns:
            List of actions: [{'action': 'KILL', 'agent': 'name', 'reason': '...'}]
        """
        # Rate limit checks to every 5 mins (approx)
        # Assuming current_time is monotonic or unix timestamp in seconds
        if current_time - self.last_check_time < self.check_interval:
            return []

        self.last_check_time = current_time
        actions = []

        # 1. Global Market Checks (Volatility & Volume)
        # We check per symbol, but if ANY major symbol crashes, we might want to alert all.
        # For now, let's just check the agent's active positions or a major index like BTC.
        
        market_triggers = self._check_market_triggers(market_history)
        
        # 2. Agent Specific Checks (Stop-Loss)
        for name, agent_data in agents.items():
            # Check Stop-Loss
            sl_trigger = self._check_stop_loss(agent_data)
            if sl_trigger:
                actions.append({
                    'action': 'KILL',
                    'agent': name,
                    'reason': f"HARD TRIGGER: Stop-Loss Breach. {sl_trigger}"
                })
                continue # Priority to SL
            
            # If market trigger exists, apply to all agents? 
            # Or pass it as context? The spec says "HARD TRIGGER... strategy is nuked"
            # If Volatility Shock happens, we might want to kill ALL agents or just those exposed.
            # Implementation Plan says "If Hard Trigger met... strategy is nuked". 
            # Let's apply market triggers to active agents.
            if market_triggers:
                actions.append({
                    'action': 'KILL',
                    'agent': name,
                    'reason': f"HARD TRIGGER: Market Shock. {market_triggers}"
                })

        return actions

    def _check_stop_loss(self, agent_data):
        # Spec: ">3% Equity within a 5-minute window"
        # We need equity history. 
        # Assuming agent_data has some history or we track it.
        # Simple approach: Compare current equity to equity 5 mins ago? 
        # Arena doesn't pass agent history easily here, but it has `chart_history`.
        # For MVP, let's look at `roi` drop? Or simple max drawdown logic if available.
        
        # Alternative: We trust the arena to pass meaningful data. 
        # If we don't have history in `agent_data`, we can't strictly do "in 5 min window".
        # We will assume `agent_data` might have a `high_water_mark_5m` or similar if we modify Arena,
        # OR we rely on Arena to pass the full history. 
        
        # PROPOSAL: Use Total Drawdown for now as a proxy, or check if ROI dropped significantly.
        # Real implementation: Arena tracks snapshots.
        
        # Let's use a simpler heuristic for V1:
        # If ROI < -3.0% (Total) -> Kill (Safety Net)
        # Ideally we want "Drop of 3% in last 5 mins".
        current_roi = agent_data.get('roi', 0.0)
        if current_roi < -3.0:
            return f"ROI dropped below -3.0% ({current_roi:.2f}%)"
        return None

    def _check_market_triggers(self, market_history):
        # BTC is the bellwether
        btc_hist = market_history.get('BTC', [])
        if not btc_hist or len(btc_hist) < 20: return None
        
        # 1. Volatility Shock (ATR doubles)
        # Need "Current ATR" vs "1-hour avg ATR"
        # Approx: Calculate High-Low range for last few mins vs last hour
        try:
            prices = [h['price'] for h in btc_hist]
            highs = [h['high'] for h in btc_hist]
            lows = [h['low'] for h in btc_hist]
            
            if len(prices) < 60: return None
            
            # Current Volatility (Last 5 mins)
            recent_ranges = [h-l for h, l in zip(highs[-5:], lows[-5:])]
            current_atr = np.mean(recent_ranges) if recent_ranges else 0
            
            # Baseline Volatility (Last 60 mins)
            past_ranges = [h-l for h, l in zip(highs[-60:], lows[-60:])]
            baseline_atr = np.mean(past_ranges) if past_ranges else 1
            
            if current_atr > (baseline_atr * 2.0) and baseline_atr > 0:
                return f"Volatility Shock (ATR {current_atr:.2f} > 2x {baseline_atr:.2f})"
                
            # 2. Volume Explosion (>500% avg)
            volumes = [h['volume'] for h in btc_hist]
            current_vol = np.mean(volumes[-5:])
            baseline_vol = np.mean(volumes[-60:])
            
            if current_vol > (baseline_vol * 5.0) and baseline_vol > 0:
                return f"Volume Explosion (Vol {current_vol:.2f} > 5x {baseline_vol:.2f})"
                
        except Exception as e:
            print(f"Supervisor Check Error: {e}")
            
        return None
