import os
import requests
import json
import ast
import re
from market_simulation.data_feed import DataFeed

# GitHub AI Inference SDK
try:
    from azure.ai.inference import ChatCompletionsClient
    from azure.ai.inference.models import SystemMessage, UserMessage
    from azure.core.credentials import AzureKeyCredential
    GITHUB_AI_AVAILABLE = True
except ImportError:
    GITHUB_AI_AVAILABLE = False
    print("Warning: azure-ai-inference not installed. GitHub AI inference disabled.")

class Brain:
    def __init__(self):
        # OpenRouter config
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        
        # GitHub AI config
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.github_endpoint = "https://models.github.ai/inference"
        
        self.data_feed = DataFeed()

    def generate_agent_code(self, name, model="openai/gpt-4-turbo"):
        """Generates a Python trading agent using the specified LLM."""
        
        # 1. Gather Context
        tickers = self.data_feed.get_multi_tickers()
        market_stats = ""
        for sym, data in tickers.items():
            market_stats += f"- {sym}: ${data['price']} (Vol: {data['volume']})\n"
        
        if not market_stats:
            market_stats = "Market Offline (Simulated Environment)"

        # 2. Construct Prompt - MULTI-CURRENCY TRADING SYSTEM (UPDATED WITH STATE PERSISTENCE)
        system_prompt = """
You are a Senior HFT Quant Strategist specializing in Market Microstructure.
Your goal is to build an INSTITUTIONAL-GRADE algo using DeepLOB, Stoikov, and NLP signals.

## MARKET DATA ARCHITECTURE
The `market_data` dictionary passed to `execute_strategy` contains predictive alpha signals:

market_data[symbol] = {
    'price': 98000.0,
    'volume': 1500.0,
    'history': [...],       # Standard close prices (list of floats)
    'volumes': [...],       # Historical volumes (list of floats)

    # --- MICROSTRUCTURE ALPHA (Physics of the Order Book) ---
    'obi_weighted': 0.45,   # Multi-Level Order Book Imbalance (DeepLOB).
                            # Range -1.0 to 1.0. High > 0.1 means Bid support.

    'micro_price': 98005.2, # Stoikov Fair Value.
                            # If micro_price > price: Market is undervalued.

    'ofi': 120.5,           # Order Flow Imbalance.
                            # Net aggressive buying volume vs selling volume.

    # --- ADVANCED MARKET INTERNALS (Institutional Grade) ---
    'funding_rate_velocity': 0.01,
    'cvd_divergence': -0.5,
    'taker_ratio': 1.1,
    'parkinson_vol': 0.02,

    # --- SEMANTIC & ATTENTION ALPHA ---
    'sentiment': 0.85,      # News Sentiment (-1.0 to 1.0).
    'attention': 1.2,       # Google Trends Search Volume Delta.
}

## AGENT STATE (PERSISTENT - USE THIS INSTEAD OF GLOBALS!)
The `agent_state` dictionary is provided by the Arena and persists across module reloads:

agent_state = {
    'entry_prices': {'BTC': 50000.0, 'ETH': 3000.0},  # Your entry price for each position
    'trade_history': [...],  # Last 20 trades
    'custom': {},  # Store your own state variables here (persists!)
    'current_pnl': {
        'BTC': {
            'pnl_percent': 0.35,   # Current profit/loss %
            'pnl_usd': 123.45,     # Dollar P&L
            'entry_price': 50000,  # Your entry
            'current_price': 50175 # Current market price
        }
    }
}

CRITICAL: DO NOT use global variables like `_entry_price` - they RESET when the module reloads!
ALWAYS use `agent_state['entry_prices']` and `agent_state['current_pnl']` instead.

## YOUR MISSION
Create a strategy that fuses these signals using a "State-Based" logic:
1. **Focus on BTC, ETH, SOL ONLY** — These have best liquidity and signal quality.
2. **Volume Spike Filter**: Only enter when volume > 1.5x rolling average.
3. **Trailing Stop**: Track peak price and exit if price drops 2% from peak.
4. **Fair Value Gap**: Calculate `(micro_price - price)`. Trade towards Micro-price.
5. **SHORT SELLING**: If signals are negative (e.g., negative Sentiment + negative OBI), SELL to open a short.

## ===== CRITICAL TRADING RULES (MUST FOLLOW) =====

### 1. FOCUS ON TOP 3 COINS ONLY
- ONLY trade BTC, ETH, SOL. Ignore all other symbols.
- `symbols = ['BTC', 'ETH', 'SOL']`

### 2. POSITION SIZING (20% Risk Per Trade)
- Risk up to 20% of CASH on a single trade.
- Use FLOAT quantity: `qty = (cash_balance * 0.20) / price`
- DO NOT use int() or floor(). Fractional quantities like 0.0023 are valid.

### 3. MINIMUM PROFIT TARGET (Fees Coverage)
- Trading fees are ~0.075% per side (0.15% round trip).
- Slippage is ~0.025% per side (0.05% round trip).
- Total cost: ~0.20% per round trip.
- **You MUST NOT take profit until PnL > 0.50% (0.005).**
- `if pnl_pct > 0.005: SELL` (Secure profit after costs)

### 4. ENTRY LOGIC (Long & Short)
- Long Entry: Score >= 2
- Short Entry: Score <= -2 (SELL to Open)
- **Cooldown**: Wait 60 ticks after any trade.

### 5. STOP-LOSS (-0.30%)
- Tight stop: -0.30% from entry (to limit losses).
- Use: `if agent_state['current_pnl'].get(sym, {}).get('pnl_percent', 0) < -0.30:`
- Emergency Arena stop at -2% exists as backup.

## EXACT CODE TEMPLATE (USE THIS):
```python
# --- Generated Algorithm Code Below ---
import numpy as np
import pandas as pd

# Use agent_state for persistence - NO global variables!
_last_trade_tick = 0  # Only this is safe as a global (just a counter)

def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    '''
    Institutional-grade algo with State Persistence and Fee Awareness.
    agent_state provides entry_prices and current_pnl - USE THESE!
    '''
    global _last_trade_tick

    # Handle backward compatibility
    if agent_state is None:
        agent_state = {'entry_prices': {}, 'current_pnl': {}, 'custom': {}}

    symbols = ['BTC', 'ETH', 'SOL']

    # Cooldown
    if tick - _last_trade_tick < 60:
        return ("HOLD", None, 0)

    # 1. EXIT LOGIC - Use agent_state['current_pnl'] for reliable PnL tracking
    for sym in symbols:
        qty = portfolio.get(sym, 0)
        if qty == 0: continue

        pnl_info = agent_state.get('current_pnl', {}).get(sym, {})
        pnl_pct = pnl_info.get('pnl_percent', 0) / 100.0  # Convert from % to decimal

        # TAKE PROFIT (0.50% target to beat 0.20% costs)
        if pnl_pct > 0.005:
            _last_trade_tick = tick
            action = "SELL" if qty > 0 else "BUY"
            return (action, sym, abs(qty))

        # STOP LOSS (-0.30%)
        if pnl_pct < -0.003:
            _last_trade_tick = tick
            action = "SELL" if qty > 0 else "BUY"
            return (action, sym, abs(qty))

    # 2. ENTRY LOGIC - Find best opportunity
    best_sym = None
    best_score = 0

    for sym in symbols:
        if portfolio.get(sym, 0) != 0: continue  # Already in position

        data = market_data.get(sym, {})
        if not data: continue

        obi = data.get('obi_weighted', 0)
        ofi = data.get('ofi', 0)
        sentiment = data.get('sentiment', 0)

        score = 0
        if obi > 0.1: score += 1
        if obi < -0.1: score -= 1
        if ofi > 10: score += 1
        if ofi < -10: score -= 1
        if sentiment > 0.2: score += 1
        if sentiment < -0.2: score -= 1

        if abs(score) > abs(best_score):
            best_score = score
            best_sym = sym

    if best_sym and abs(best_score) >= 2:
        price = market_data[best_sym]['price']
        qty = (cash_balance * 0.20) / price

        _last_trade_tick = tick

        if best_score > 0:
            return ("BUY", best_sym, qty)
        else:
            return ("SELL", best_sym, qty)  # Short Sell

    return ("HOLD", None, 0)
```

## MANDATORY RULES:
1. `execute_strategy` must accept `(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None)`.
2. Return `(ACTION, SYMBOL, QUANTITY)`.
3. `ACTION` must be "BUY", "SELL", or "HOLD".
4. **USE `agent_state['current_pnl']` for PnL tracking - NOT global variables!**
5. **PROFIT TARGET > 0.50% is NON-NEGOTIABLE (to beat 0.20% costs).**
6. Use `obi_weighted` and `ofi` for signals.
7. Support **SHORT SELLING** (Return "SELL" when you have 0 quantity to open short).
"""

        user_prompt = f"Generate a multi-currency strategy for {name}. Focus on finding the best momentum asset among BTC, ETH, SOL."
        
        # Determine if using GitHub or OpenRouter based on model prefix
        is_github_model = model.startswith('github:')
        
        if is_github_model:
            if not GITHUB_AI_AVAILABLE:
                return {"error": "GitHub AI SDK not installed. Run: pip install azure-ai-inference"}
            if not self.github_token:
                return {"error": "No GITHUB_TOKEN set in environment"}
        else:
            if not self.api_key:
                return {"error": "No OpenRouter API Key set"}

        # 3. Call LLM with Fallback
        models_to_try = [model] # No fallback as per user request
        valid_code = None
        
        for current_model in models_to_try:
            if valid_code: break
            
            current_is_github = current_model.startswith('github:')
            actual_model = current_model.replace('github:', '') if current_is_github else current_model
            
            print(f"Brain: Generating with {current_model}...")
            retries = 0
            max_retries = 2
            
            while not valid_code and retries <= max_retries:
                try:
                    content = ""
                    if current_is_github and GITHUB_AI_AVAILABLE and self.github_token:
                        content = self._call_github_api(actual_model, system_prompt, user_prompt)
                    else:
                        response = requests.post(
                            self.base_url,
                            headers={
                                "Authorization": f"Bearer {self.api_key}",
                                "Content-Type": "application/json",
                                "HTTP-Referer": "http://localhost:3000",
                            },
                            json={
                                "model": actual_model,
                                "messages": [
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": user_prompt}
                                ]
                            }
                        )
                        if response.status_code != 200:
                            print(f"API Error ({current_model}): {response.text}")
                            if response.status_code in [429, 500, 502, 503]: break
                            retries += 1
                            continue
                        content = response.json()['choices'][0]['message']['content']
                
                    clean_code = self._clean_code(content)
                    if self._validate_code(clean_code, name):
                        valid_code = clean_code
                    else:
                        print(f"Validation failed (retry {retries})")
                        retries += 1
                except Exception as e:
                    print(f"Generation error: {e}")
                    retries += 1
                    continue

        if valid_code:
            # Save to market_simulation/agents/
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            filename = os.path.join(base_dir, "market_simulation", "agents", f"{name}.py")
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, 'w') as f:
                f.write(valid_code)
            return {"success": True, "filepath": filename, "code": valid_code, "name": name}
        else:
            return {"error": "Failed to generate valid code."}

    def _call_github_api(self, model, system_prompt, user_prompt):
        client = ChatCompletionsClient(
            endpoint=self.github_endpoint,
            credential=AzureKeyCredential(self.github_token),
        )
        response = client.complete(
            messages=[
                SystemMessage(content=system_prompt),
                UserMessage(content=user_prompt),
            ],
            model=model
        )
        return response.choices[0].message.content

    def _clean_code(self, content):
        pattern = r"```(?:python)?\s*(.*?)\s*```"
        match = re.search(pattern, content, re.DOTALL)
        if match: return match.group(1)
        return content

    def _validate_code(self, code, class_name):
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            print(f"Syntax Error: {e}")
            return False
            
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in ['os', 'sys', 'subprocess', 'requests']:
                        return False

        has_strategy = False
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == 'execute_strategy':
                has_strategy = True
                # Allow 4-6 args: (market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None)
                num_args = len(node.args.args)
                if num_args < 4 or num_args > 6:
                    print(f"Validation: execute_strategy needs 4-6 args, found {num_args}")
                    return False

        if not has_strategy:
            print("Validation: Missing execute_strategy function")
            return False

        return True

    def evaluate_agent(self, code, roi, portfolio, logs):
        """
        Evaluates an agent's performance and code quality.
        Returns: (decision, critique)
        decision: "KEEP" or "REFINE"
        critique: String explanation
        """
        system_prompt = """
You are a Senior Algorithmic Trading Auditor. Your job is to strictly evaluate a trading bot's performance and code logic.

DECISION CRITERIA:
1. ROI Analysis:
   - If ROI > 1.0% (in short term) -> KEEP (unless logic is dangerous).
   - If ROI is negative (< -1.0%) -> REFINE.
   - If ROI is flat (approx 0%) but trading is active -> KEEP (give it time).
   - If ROI is flat and NO trades -> REFINE (it's stuck).

2. Logic Analysis:
   - Look for "hardcoded" logic that fails in dynamic markets.
   - Look for unsafe math (though system prompt prevents most).
   - Look for logic that ignores trends.

OUTPUT FORMAT:
First line: DECISION: [KEEP | REFINE]
Subsequent lines: CRITIQUE: [Detailed explanation of why, and what to improve]
"""
        
        user_prompt = f"""
EVALUATE THIS AGENT:

PERFORMANCE:
- ROI: {roi}%
- Portfolio: {portfolio}
- Recent Logs: {logs}

CURRENT CODE:
```python
{code}
```
"""
        # Quick evaluation call (use a cheaper model if possible, or same model)
        # Using a fast model for evaluation is usually sufficient
        model = "nvidia/nemotron-nano-9b-v2:free" 
        
        response_content = ""
        try:
             # Re-use logic or straightforward call. For simplicity, reusing same structure logic minimally
            if not self.api_key: return "KEEP", "No API Key"

            response = requests.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:3000",
                },
                json={
                    "model": model,
                    "max_tokens": 1000,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                }
            )
            if response.status_code == 200:
                response_content = response.json()['choices'][0]['message']['content']
            else:
                print(f"Eval Error: {response.text}")
                return "KEEP", "API Error"
                
        except Exception as e:
            print(f"Eval Exception: {e}")
            return "KEEP", f"Exception: {e}"

        # Parse response
        decision = "KEEP"
        critique = "No critique"
        
        lines = response_content.split('\n')
        for line in lines:
            if line.startswith("DECISION:"):
                if "REFINE" in line: decision = "REFINE"
            elif line.startswith("CRITIQUE:"):
                critique = line.replace("CRITIQUE:", "").strip()
                # Capture rest of lines as critique too if multiline? 
                # For now simple parsing
                
        # Capture full critique if multiline
        if "CRITIQUE:" in response_content:
            parts = response_content.split("CRITIQUE:")
            if len(parts) > 1:
                critique = parts[1].strip()

        return decision, critique

    def evolve_agent(self, name, critique, old_code, model="openai/gpt-4-turbo"):
        """Regenerates agent code based on critique."""
        print(f"Brain: Evolving {name} with critique: {critique[:50]}...")
        
        # 1. Gather Context (Same as generate)
        tickers = self.data_feed.get_multi_tickers()
        market_stats = ""
        for sym, data in tickers.items():
            market_stats += f"- {sym}: ${data['price']} (Vol: {data['volume']})\n"
            
        # 2. Construct Prompt (Modified for Evolution)
        system_prompt = f"""
You are an elite crypto hedge fund algo developer. You are FIXING and IMPROVING an existing strategy.

## CRITIQUE OF OLD STRATEGY
{critique}

## MARKET DATA ARCHITECTURE
market_data[symbol] = {{
    'price': 98000.0,
    'volume': 1500.0,
    'obi_weighted': 0.45,   # Multi-Level Order Book Imbalance (DeepLOB). >0.3 is Strong Support.
    'micro_price': 98005.2, # Stoikov Fair Value.
    'ofi': 150.0,           # Order Flow Imbalance. Leading indicator of immediate pressure.
    'sentiment': 0.85,      # Global News Sentiment.
}}

## AGENT STATE (PERSISTENT - USE THIS!)
agent_state = {{
    'entry_prices': {{'BTC': 50000.0}},  # Your entry prices (persists across reloads!)
    'current_pnl': {{
        'BTC': {{'pnl_percent': 0.35, 'entry_price': 50000, 'current_price': 50175}}
    }}
}}

CRITICAL: Use `agent_state['current_pnl']` for PnL - NOT global variables!

## YOUR MISSION
Rewrite the `execute_strategy` function to address the critique and IMPROVE performance.
- Use agent_state for state persistence (NO global _entry_price!)
- Profit target: 0.50% (to beat 0.20% transaction costs)
- Stop-loss: -0.30%

## EXACT CODE TEMPLATE (USE THIS):
```python
# --- Generated Algorithm Code Below ---
import numpy as np
import pandas as pd

_last_trade_tick = 0  # Only counters are safe as globals

def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    '''
    Use agent_state for persistent state - NOT globals!
    '''
    global _last_trade_tick

    if agent_state is None:
        agent_state = {{'entry_prices': {{}}, 'current_pnl': {{}}}}

    symbols = ['BTC', 'ETH', 'SOL']

    # Cooldown
    if tick - _last_trade_tick < 60:
        return ("HOLD", None, 0)

    # EXIT LOGIC - Use agent_state['current_pnl']
    for sym in symbols:
        qty = portfolio.get(sym, 0)
        if qty == 0: continue

        pnl_info = agent_state.get('current_pnl', {{}}).get(sym, {{}})
        pnl_pct = pnl_info.get('pnl_percent', 0) / 100.0

        if pnl_pct > 0.005:  # Take profit at 0.50%
            _last_trade_tick = tick
            return ("SELL" if qty > 0 else "BUY", sym, abs(qty))

        if pnl_pct < -0.003:  # Stop loss at -0.30%
            _last_trade_tick = tick
            return ("SELL" if qty > 0 else "BUY", sym, abs(qty))

    # ENTRY LOGIC - Your improved signals here
    # ...

    return ("HOLD", None, 0)
```

## MANDATORY RULES:
1. Function signature: `execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None)`.
2. Returns `(ACTION, SYMBOL, QUANTITY)`.
3. USE `agent_state['current_pnl']` - NOT global variables!
4. Profit target > 0.50%, Stop loss at -0.30%.
"""
        
        user_prompt = f"Refactor {name} to fix: {critique}. Improve profitability."
        
        # Reuse generation logic (copy-paste-adapt from generate_agent_code loop)
        # For brevity, I will call the internal logic if refactored, but here I'll just duplicate the loop structure for safety
        
        models_to_try = [model, "openai/gpt-oss-20b:free"]
        valid_code = None
        
        for current_model in models_to_try:
            if valid_code: break
            
            # ... (Simulate same call logic as generate_agent_code) ...
            try:
                response = requests.post(
                    self.base_url,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json", "HTTP-Referer": "http://localhost:3000"},
                    json={"model": current_model, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]}
                )
                if response.status_code!= 200: continue
                content = response.json()['choices'][0]['message']['content']
                clean_code = self._clean_code(content)
                if self._validate_code(clean_code, name):
                    valid_code = clean_code
            except Exception as e:
                print(f"Evolve error: {e}")
                continue

        if valid_code:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            filename = os.path.join(base_dir, "market_simulation", "agents", f"{name}.py")
            # Backup old?
            # os.rename(filename, filename + ".bak") 
            with open(filename, 'w') as f:
                f.write(valid_code)
            return {"success": True, "filepath": filename, "code": valid_code}
        else:
            return {"error": "Failed to evolve code."}
