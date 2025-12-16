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

        # 2. Construct Prompt - MULTI-CURRENCY TRADING SYSTEM
        system_prompt = """
You are a Senior HFT Quant Strategist specializing in Market Microstructure.
Your goal is to build an INSTITUTIONAL-GRADE algo using DeepLOB, Stoikov, and NLP signals.

## MARKET DATA ARCHITECTURE (AVAILABLE GLOBALS)
The `market_data` dictionary passed to `execute_strategy` now contains predictive alpha signals:

market_data = {
    'price': 98000.0,
    'volume': 1500.0,
    'history': [...],       # Standard close prices
    
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
    'sentiment': 0.85,      # FinBERT News Sentiment (-1.0 to 1.0).
    'attention': 1.2,       # Google Trends Search Volume Delta. 
}

## YOUR MISSION
Create a strategy that fuses these signals using a "State-Based" logic:
1. **Regime Filter**: Check `sentiment` and `attention`.
2. **Setup Signal (Potential Energy)**: Use `obi_weighted`. Is there liquidity?
3. **Trigger Signal (Kinetic Energy)**: Use `ofi`. Are buyers stepping in?
4. **Fair Value Gap**: Calculate `(micro_price - price)`. Trade towards Micro-price.

## ===== CRITICAL TRADING RULES (MUST FOLLOW) =====

### 1. POSITION SIZING (5% Risk Per Trade)
- NEVER risk more than 5% of cash on a single trade.
- Formula: `qty = (cash_balance * 0.05) / price`
- This prevents catastrophic losses.

### 2. STOP-LOSS (-5% to -8%)
- Only exit when position is down -5% or more.
- Crypto is volatile. A -3% stop gets triggered by noise.
- Use: `if pnl_pct < -0.05: SELL`

### 3. PROFIT TARGET (+3% to +5%)
- Take profits when up +3% to +5%.
- Do NOT be greedy. Secure the bag.
- Use: `if pnl_pct > 0.03: SELL`

### 4. TRADE COOLDOWN (60 Ticks ~ 60 Seconds)
- After ANY trade (buy or sell), wait 60 ticks before next trade.
- Prevents overtrading and fee erosion.
- Track: `_last_trade_tick` global variable.

### 5. ENTRY THRESHOLD (Score >= 5)
- Lower your entry threshold to score >= 5 (not 10 or 15).
- This allows entries when signals are moderately aligned.

## TRADING CONSTRAINTS
- Starting capital: $10,000
- Trading fees: 0.1% per trade
- **HURDLE RATE**: You must beat the 0.2% round-trip fee.

## EXACT CODE TEMPLATE (USE THIS):
```python
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
    Institutional-grade algo with proper risk management.
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
    
    for sym, data in market_data.items():
        if not isinstance(data, dict) or 'price' not in data: continue
        
        # Skip if already holding
        if portfolio.get(sym, 0) != 0: continue
        
        price = data['price']
        
        # Extract Signals
        obi = data.get('obi_weighted', 0.0)
        ofi = data.get('ofi', 0.0)
        micro_price = data.get('micro_price', price)
        sentiment = data.get('sentiment', 0.0)
        
        # Calculate Score
        score = 0
        
        # Order Book Imbalance (Lowered threshold)
        if obi > 0.1:
            score += 5
        
        # Order Flow Imbalance
        if ofi > 30:
            score += 4
        elif ofi < -30:
            score -= 3
        
        # Fair Value Gap (Micro-price deviation)
        if price < micro_price * 0.995:  # Price below fair value
            score += 3
        
        # Sentiment
        if sentiment > 0.6:
            score += 2
        elif sentiment < 0.3:
            score -= 2
        
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
```

## MANDATORY RULES:
1. Function named `execute_strategy`.
2. 4 Arguments: `(market_data, tick, cash_balance, portfolio)`.
3. Returns `(ACTION, SYMBOL, QUANTITY)`.
4. MUST use `obi_weighted`, `micro_price`, `ofi` in logic.
5. NO markdown fences in output, just code.
6. MUST implement 5% position sizing.
7. MUST implement -5% stop loss and +3% profit target.
8. MUST implement 60-tick cooldown.
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
        models_to_try = [
            model, 
            "openai/gpt-oss-20b:free",
            "nvidia/nemotron-nano-9b-v2:free"
        ]
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
                if len(node.args.args) != 4:
                    print(f"Validation: execute_strategy needs 4 args, found {len(node.args.args)}")
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

## MARKET DATA ARCHITECTURE (AVAILABLE GLOBALS)
market_data = {{
    'price': 98000.0,
    'volume': 1500.0,
    # --- DEEP HFT SIGNALS ---
    'obi_weighted': 0.45,   # Multi-Level Order Book Imbalance (DeepLOB). >0.3 is Strong Support.
    'micro_price': 98005.2, # Stoikov Fair Value.
    'ofi': 150.0,           # Order Flow Imbalance. Leading indicator of immediate pressure.
    'sentiment': 0.85,      # Global News Sentiment.
}}

## YOUR MISSION
Rewrite the `execute_strategy` function to address the critique and IMPROVE performance using these signals.
- Keep the exact same function signature.
- Keep the same keys in `_entry_price`.
- IMPLEMENT HANDLING FOR EXISTING POSITIONS.

## EXACT CODE TEMPLATE (USE THIS):
```python
# --- Generated Algorithm Code Below ---
import numpy as np
import pandas as pd

# Global state
_entry_price = {{}}
_entry_tick = {{}}

def execute_strategy(market_data, tick, cash_balance, portfolio):
    '''
    See MARKET DATA ARCHITECTURE above.
    '''
    global _entry_price
    
    # 0. Hot-Swap Reconstruction
    for sym, qty in portfolio.items():
        if qty!= 0 and sym not in _entry_price:
             _entry_price[sym] = market_data.get(sym, {{}}).get('price', 0)

    best_opp = None
    best_score = -999
    
    if not market_data: return ("HOLD", None, 0)
    
    # scan for best asset
    for sym, data in market_data.items():
        if not data or 'price' not in data: continue
        
        price = data['price']
        
        # Signals
        obi = data.get('obi_weighted', 0.0)
        ofi = data.get('ofi', 0.0)
        micro_price = data.get('micro_price', price)
        sentiment = data.get('sentiment', 0.0)
        
        #... IMPROVED LOGIC BASED ON CRITIQUE...
        
        # Example HFT signal usage:
        # if ofi > 50 and obi > 0.3: score += 10
        
        #...
            
    # EXECUTION LOGIC...
    # Return ("ACTION", "SYMBOL", QTY)

    return ("HOLD", None, 0)
```

## MANDATORY RULES:
1. Function named `execute_strategy`.
2. 4 Arguments: `(market_data, tick, cash_balance, portfolio)`.
3. Returns `(ACTION, SYMBOL, QUANTITY)`.
4. Use `obi_weighted`, `micro_price`, `ofi` keys.
5. NO markdown fences in output, just code.
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
