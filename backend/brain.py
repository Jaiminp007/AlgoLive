import os
import requests
import json
import ast
import re
from data_feed import DataFeed

class Brain:
    def __init__(self):
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.data_feed = DataFeed()

    def generate_agent_code(self, name, model="openai/gpt-4-turbo"):
        """
        Generates a Python trading agent using the specified LLM.
        """
        # 1. Gather Context
        historical_df = self.data_feed.get_historical_data(limit=390) # 1 full trading day
        news = self.data_feed.get_news()
        
        # Format context for prompt
        market_context = "Market Data Unavailable"
        if isinstance(historical_df, list) and len(historical_df) > 0:
            import pandas as pd
            df = pd.DataFrame(historical_df)
            market_context = f"""
            Recent Market Stats (Last 390 bars):
            - Current Price: {df.iloc[-1]['close']}
            - Daily Volatility: {df['close'].std()}
            - High: {df['high'].max()}
            - Low: {df['low'].min()}
            """
        
        pattern_context = "No specific chart patterns detected."
        
        # 2. Construct Prompt - FUNCTIONAL execute_trade STYLE with DEFENSIVE CODING
        system_prompt = f"""
You are an expert quantitative developer. Generate a robust Python trading algorithm using the functional style.

## CRITICAL: DEFENSIVE CODING REQUIREMENTS (MANDATORY)
You MUST follow these rules to prevent ALL runtime errors:

### DIVISION SAFETY - ALWAYS CHECK BEFORE DIVIDING:
```python
# WRONG - Will crash on zero:
rs = avg_gain / avg_loss

# CORRECT - Always guard divisions:
if avg_loss == 0:
    return 100  # or handle gracefully
rs = avg_gain / avg_loss
```

### DATA VALIDATION - CHECK LENGTH BEFORE COMPUTING:
```python
# WRONG - Assume data exists:
return sum(prices[-period:]) / period

# CORRECT - Validate first:
if len(prices) < period:
    return None
return sum(prices[-period:]) / period
```

{market_context}

## REQUIRED STRUCTURE (EXACT FORMAT):
```python
# --- Generated Algorithm Code Below ---

# Global scalping state variables
_prices = []
_entry_price = None
_entry_tick = None
_position_type = None
_trade_count = 0
_window_size = 100

def calculate_sma(prices, period):
    \"\"\"Simple Moving Average with safety check\"\"\"
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period

def calculate_ema(prices, period):
    \"\"\"Exponential Moving Average with safety check\"\"\"
    if len(prices) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    return ema

def calculate_rsi(prices, period=14):
    \"\"\"Relative Strength Index with division safety\"\"\"
    if len(prices) < period + 1:
        return 50  # Neutral default
    gains, losses = [], []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        gains.append(max(0, change))
        losses.append(max(0, -change))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100  # All gains, no losses
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    \"\"\"Bollinger Bands with safety check\"\"\"
    if len(prices) < period:
        return None, None, None
    sma = sum(prices[-period:]) / period
    variance = sum((p - sma) ** 2 for p in prices[-period:]) / period
    std = variance ** 0.5
    return sma - std_dev * std, sma, sma + std_dev * std

def execute_trade(ticker, price, tick, cash_balance, shares_held):
    \"\"\"
    Main trading function called on each tick.
    
    Args:
        ticker: Symbol being traded
        price: Current price
        tick: Current tick number (0-389 for a trading day)
        cash_balance: Available cash
        shares_held: Current position (positive=long, negative=short, 0=flat)
    
    Returns:
        \"HOLD\" or (\"BUY\"|\"SELL\", quantity)
    \"\"\"
    global _prices, _entry_price, _entry_tick, _position_type, _trade_count
    
    _prices.append(price)
    
    # Limit history to prevent memory leak
    if len(_prices) > _window_size:
        _prices.pop(0)
    
    # Wait for enough data
    if len(_prices) < 20:
        return \"HOLD\"
    
    # End-of-day liquidation (tick 375+)
    if tick >= 375:
        if shares_held != 0:
            return (\"BUY\", abs(shares_held)) if shares_held < 0 else (\"SELL\", abs(shares_held))
        return \"HOLD\"
    
    # YOUR STRATEGY LOGIC HERE:
    # - Calculate indicators using the helper functions
    # - Check for entry/exit signals
    # - Manage positions with stop-loss and take-profit
    
    return \"HOLD\"
```

## STRATEGY REQUIREMENTS:
1. Use at least 2-3 technical indicators (SMA, EMA, RSI, Bollinger Bands)
2. Include stop-loss (-0.3%) and take-profit (+0.5%) logic
3. Time-based exit (max 20-25 ticks per position)
4. Trade quantity: 200-400 shares with leverage

## FORBIDDEN PATTERNS:
1. ❌ Division without zero-check
2. ❌ Array access without length check
3. ❌ Missing `global` declaration for state variables
4. ❌ Using undefined functions or variables

## OUTPUT REQUIREMENTS:
1. Output ONLY valid Python code (NO markdown fences, NO explanations)
2. Include ALL helper functions (calculate_sma, calculate_ema, calculate_rsi, calculate_bollinger_bands)
3. Include the execute_trade function with EXACT signature
4. All divisions must have zero guards
5. Start with: # --- Generated Algorithm Code Below ---
"""

        user_prompt = f"Generate a complete scalping algorithm for {name} (BTC/USD) using the execute_trade function. Use multiple indicators and include aggressive entry/exit logic with proper risk management."
        
        if not self.api_key:
            return {"error": "No OpenRouter API Key set"}

        # 3. Call LLM with Fallback
        models_to_try = [
            model, 
            "google/gemini-2.0-flash-exp:free", 
            "meta-llama/llama-3.2-3b-instruct:free",
            "qwen/qwen-2.5-7b-instruct:free",
            "microsoft/phi-3-mini-128k-instruct:free"
        ]
        valid_code = None
        
        for current_model in models_to_try:
            if valid_code: break
            
            print(f"Brain: Attempting generation with {current_model}...")
            retries = 0
            max_retries = 2
            
            while not valid_code and retries <= max_retries:
                try:
                    response = requests.post(
                        self.base_url,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "http://localhost:3000",
                        },
                        json={
                            "model": current_model,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt}
                            ]
                        }
                    )
                    
                    if response.status_code != 200:
                        print(f"API Error ({current_model}): {response.text}")
                        if response.status_code in [429, 500, 502, 503]:
                            break
                        retries += 1
                        continue
                        
                    content = response.json()['choices'][0]['message']['content']
                
                    clean_code = self._clean_code(content)
                    
                    if self._validate_code(clean_code, name):
                        valid_code = clean_code
                    else:
                        print(f"Generated code failed validation. Retrying... ({retries})")
                        retries += 1
                except Exception as e:
                    print(f"Exception during generation: {e}")
                    if "429" in str(e):
                        break 
                    retries += 1
                    continue

        if valid_code:
            # 4. Save to file
            filename = f"agents/{name}.py"
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, 'w') as f:
                f.write(valid_code)
            return {"success": True, "filepath": filename, "code": valid_code, "name": name}
        else:
            return {"error": "Failed to generate valid code after retries."}

    def _clean_code(self, content):
        """Removes markdown code blocks if present."""
        pattern = r"```(?:python)?\s*(.*?)\s*```"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1)
        return content

    def _validate_code(self, code, class_name):
        """checks syntax and ensures safety."""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            print(f"Validation Failed: SyntaxError: {e}")
            return False
            
        # Check for forbidden imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in ['os', 'sys', 'subprocess', 'shutil', 'requests', 'urllib']:
                        print(f"Forbidden import: {alias.name}")
                        return False
        
        # Check for CLASS-BASED agent (preferred) or execute_trade (legacy)
        has_class_with_trade = False
        has_execute_trade = False
        
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                # Check if class has 'trade' method
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == 'trade':
                        has_class_with_trade = True
                        break
            if isinstance(node, ast.FunctionDef) and node.name == 'execute_trade':
                has_execute_trade = True
        
        if not has_class_with_trade and not has_execute_trade:
            print(f"Validation Failed: Code must contain class '{class_name}' with 'trade()' method OR 'execute_trade' function.")
            return False
            
        return True
