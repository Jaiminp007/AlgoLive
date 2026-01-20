# AlgoClash Live

> The AI Trading Arena - Where LLM-powered agents compete in real-time against live market data

AlgoClash Live is a real-time AI trading simulation platform where Large Language Model (LLM) generated trading agents compete against each other using live cryptocurrency and stock market data. Watch as AI agents analyze market microstructure, execute trades, and evolve their strategies in real-time.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
  - [AlgoClash Cortex (Analyst Engine)](#algoclash-cortex-analyst-engine)
  - [Multi-Loop Design](#multi-loop-design)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Environment Variables](#environment-variables)
  - [Running the Project](#running-the-project)
- [Sandbox Research Terminal](#sandbox-research-terminal)
  - [Command-Based Workflow](#command-based-workflow)
  - [Available Commands](#available-commands)
  - [Research Workflow Example](#research-workflow-example)
  - [Agent Validation and Auto-Repair](#agent-validation-and-auto-repair)
- [Trading System](#trading-system)
  - [Multi-Asset Trading](#multi-asset-trading)
  - [Market Hours Detection](#market-hours-detection)
  - [Trading Parameters](#trading-parameters)
  - [Market Signals](#market-signals)
  - [Order Execution](#order-execution)
- [Creating Trading Agents](#creating-trading-agents)
  - [Agent Interface](#agent-interface)
  - [Agent State Management](#agent-state-management)
  - [Signal Scoring](#signal-scoring)
  - [Example Strategies](#example-strategies)
- [API Reference](#api-reference)
  - [REST Endpoints](#rest-endpoints)
  - [WebSocket Events](#websocket-events)
- [Data Sources](#data-sources)
  - [Cryptocurrency Data](#cryptocurrency-data)
  - [Stock Market Data](#stock-market-data)
  - [FinancialDatasets.ai Integration](#financialdatasetsai-integration)
- [Deployment](#deployment)
  - [Render Deployment](#render-deployment)
  - [Docker Deployment](#docker-deployment)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

AlgoClash Live enables you to:

- **Generate AI Trading Agents** using various LLM models (GPT-4o, Claude, DeepSeek, Llama, etc.)
- **Research Strategies** using an interactive terminal with Python execution sandbox
- **Watch Live Competition** as agents trade crypto and stocks in real-time
- **Analyze Performance** with live equity curves, trade logs, and leaderboards
- **Deploy Custom Algorithms** directly to the arena

The platform fetches live market data every second from **Binance via CCXT** (crypto) and **FinancialDatasets.ai / Yahoo Finance** (stocks when markets are open, cached otherwise), enriches it with market microstructure and sentiment signals, and executes agent strategies in a simulated trading environment with realistic transaction costs.

---

## Key Features

### Multi-Asset Live Trading

Trade across multiple asset classes simultaneously:

| Asset Class | Symbols | Data Source | Update Frequency |
|-------------|---------|-------------|------------------|
| **Cryptocurrency** | BTC, ETH, SOL, BNB | Binance via CCXT | Every 1 second |
| **Stocks** | AAPL, TSLA, NVDA, MSFT, GOOGL, AMZN, META | FinancialDatasets.ai / Yahoo Finance | Every 5 minutes when market open |

**Market Hours Intelligence:**
- Stock market hours: 9:30 AM - 4:30 PM Eastern Time, Monday-Friday
- Automatic detection of market hours with timezone support
- API throttling: Stock APIs polled every 5 minutes during market hours only
- After-hours: Returns cached prices to avoid unnecessary API calls
- Crypto: 24/7 real-time updates

### Command-Based Sandbox Research Terminal

The revolutionary **Sandbox Research Terminal** allows you to develop trading algorithms through natural language commands:

| Command | Purpose | Example |
|---------|---------|---------|
| `/plan` | Create research plan | `/plan Find correlation between PLTR and US-Venezuela tensions` |
| `/approve` | Execute the research plan | `/approve` |
| `/research` | Deep research on a topic | `/research insider trading patterns in tech stocks` |
| `/build` | Build algorithm from findings | `/build` |
| `/backtest` | Backtest algorithm | `/backtest --period 6m --initial 10000` |
| `/deploy` | Deploy to live arena | `/deploy` |

**Key Benefits:**
- **Natural Language Interface**: Describe what you want in plain English
- **Structured Workflow**: Plan -> Research -> Build -> Deploy
- **Code Execution**: Live Python sandbox with E2B for safe execution
- **Auto-Validation**: Algorithms validated before deployment with auto-repair
- **Multi-Turn Research**: Iterative exploration of financial data

### LLM-Powered Agent Generation

Create trading agents using state-of-the-art language models:

| Provider | Models |
|----------|--------|
| **OpenAI** | GPT-4o, GPT-4o-mini |
| **Anthropic** | Claude 3.5 Sonnet, Claude 3 Opus |
| **DeepSeek** | DeepSeek V3, DeepSeek R1 |
| **Meta** | Llama 3.3 70B |
| **Mistral AI** | Mistral Large |
| **Google** | Gemini 2.0 Flash |
| **GitHub Models** | Access via GitHub AI Inference API |

### Real-Time Market Signals

Agents receive rich market data including:

**Technical Signals (All Assets):**
- **Order Book Imbalance (OBI)** - Buy/sell pressure indicator
- **Microprice** - Stoikov fair value estimate
- **Order Flow Imbalance (OFI)** - Net order flow direction
- **Parkinson Volatility** - High-low volatility estimate
- **CVD Divergence** - Cumulative volume delta divergence
- **Taker Ratio** - Aggressive buy/sell ratio
- **Funding Rate Velocity** - Funding rate change speed (crypto only)

**Fundamental Signals (Stocks Only - via FinancialDatasets.ai):**
- **Insider Sentiment** - Net insider buying/selling score
- **Institutional Change** - Quarter-over-quarter institutional ownership change
- **Revenue Growth** - Year-over-year revenue growth rate
- **Profit Margin** - Net profit margin
- **P/E Ratio** - Price-to-earnings ratio
- **Earnings Surprise** - Actual vs. estimated earnings delta
- **News Sentiment** - Aggregated news sentiment score

**News & Sentiment:**
- Real-time news feed with sentiment analysis
- Google Trends attention metrics
- Social sentiment indicators

---

## Architecture

### AlgoClash Cortex (Analyst Engine)

AlgoClash Cortex is the high-frequency intelligence layer that powers the trading arena using a **Multi-Loop, Event-Driven Architecture**:

```
┌───────────────────────────────────────────────────────────────┐
│                     Data Aggregation Layer                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐    │
│  │   Binance    │  │ FinDatasets  │  │  News API        │    │
│  │   WebSocket  │  │  REST API    │  │  Google Trends   │    │
│  └──────┬───────┘  └──────┬───────┘  └─────────┬────────┘    │
└─────────┼──────────────────┼────────────────────┼─────────────┘
          │                  │                    │
          └──────────────────┴────────────────────┘
                             │
          ┌──────────────────▼────────────────────┐
          │        Arena (market_simulation/)      │
          │  ┌────────────────────────────────┐   │
          │  │   Signal Enrichment Layer      │   │
          │  │   - OBI, Microprice, OFI       │   │
          │  │   - Volatility, CVD, Funding   │   │
          │  │   - Fundamental Data Cache     │   │
          │  └────────────┬───────────────────┘   │
          │               │                        │
          │  ┌────────────▼───────────────────┐   │
          │  │   Agent Execution Loop         │   │
          │  │   execute_strategy() called    │   │
          │  │   every 1 second               │   │
          │  └────────────┬───────────────────┘   │
          │               │                        │
          │  ┌────────────▼───────────────────┐   │
          │  │   Order Matching Engine        │   │
          │  │   - Fees (0.05%)               │   │
          │  │   - Slippage simulation        │   │
          │  │   - Position tracking          │   │
          │  └────────────┬───────────────────┘   │
          └───────────────┼────────────────────────┘
                          │
          ┌───────────────▼────────────────────┐
          │       Socket.IO Real-time          │
          │       - Chart updates              │
          │       - Trade notifications        │
          │       - News feed                  │
          │       - Leaderboard updates        │
          └───────────────┬────────────────────┘
                          │
          ┌───────────────▼────────────────────┐
          │       React Frontend               │
          │   - Dashboard                      │
          │   - Live Charts                    │
          │   - Sandbox Terminal               │
          │   - Leaderboard                    │
          └────────────────────────────────────┘
```

### Multi-Loop Design

The platform follows a decoupled "manager/worker" architecture with multiple time loops:

| Loop | Function | Frequency | Description |
|------|----------|-----------|-------------|
| **Worker Loop** | Strategy Execution | ~1 second | Runs `execute_strategy()` for all active agents |
| **News Loop** | News Polling | ~30 seconds | Fetches news and emits updates via Socket.IO |
| **Analyst Loop** | Market State | 5 minutes | Computes structured market state with technical indicators |
| **Fundamentals Loop** | Stock Data | 1 hour | Refreshes fundamental data from FinancialDatasets.ai (market hours only) |
| **Stock Price Loop** | Price Updates | 5 minutes | Polls stock prices when market is open |
| **Supervisor Loop** | Risk Management | 5 minutes | Checks stop-losses and monitors performance (currently disabled) |

---

## Getting Started

### Prerequisites

- **Python 3.9+** - Backend runtime
- **Node.js 18+** - Frontend build tool
- **npm or yarn** - Package manager

### Installation

1. **Clone the repository**

```bash
git clone https://github.com/yourusername/algoclash-live.git
cd algoclash-live/AlgoLive
```

2. **Set up the backend**

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. **Set up the frontend**

```bash
cd ../frontend
npm install
```

### Environment Variables

Create a `.env` file in the `backend/` directory:

```bash
# Required - LLM Agent Generation
OPENROUTER_API_KEY=sk-or-v1-...

# Optional - GitHub AI Models
GITHUB_TOKEN=github_pat_...

# Optional - Premium Stock Data
FINANCIAL_DATASETS_API_KEY=...

# Required - Sandbox Python Execution
E2B_API_KEY=e2b_...

# Optional - Data Persistence
MONGO_URI=mongodb://localhost:27017/algoclash

# Configuration
ASSET_CLASS=CRYPTO          # CRYPTO or STOCK
ENABLE_SEMANTIC_ALPHA=true  # Enable sentiment analysis
PORT=5000                   # Backend port
```

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key for LLM agent generation |
| `E2B_API_KEY` | Yes | E2B API key for Python sandbox execution in research terminal |
| `GITHUB_TOKEN` | No | GitHub AI inference token for GitHub models |
| `FINANCIAL_DATASETS_API_KEY` | No | Enables premium fundamental data for stocks |
| `MONGO_URI` | No | MongoDB for persistence (runs in-memory without) |
| `ASSET_CLASS` | No | Default: `CRYPTO`. Set to `STOCK` for stock mode |
| `ENABLE_SEMANTIC_ALPHA` | No | Default: `true`. Enable news sentiment analysis |
| `PORT` | No | Default: `5000`. Backend server port |
| `RENDER_EXTERNAL_URL` | No | Your Render URL for internal keep-alive |

### Running the Project

**Terminal 1 - Backend:**

```bash
cd backend
source venv/bin/activate
python app.py
```

**Terminal 2 - Frontend:**

```bash
cd frontend
npm run dev
```

**Access the dashboard:**

Open `http://localhost:5173` in your browser.

---

## Sandbox Research Terminal

The **Sandbox Research Terminal** is a revolutionary feature that lets you develop trading algorithms through natural language commands. Instead of writing code directly, you describe what you want to research, and an LLM agent explores financial data, discovers patterns, and builds algorithms for you.

### Command-Based Workflow

The terminal operates in a structured workflow:

```
/plan → /approve → /build → /backtest → /deploy
```

1. **Planning Phase (`/plan`)** - Describe your research goal
2. **Approval Phase (`/approve`)** - Agent executes the plan and shows findings
3. **Build Phase (`/build`)** - Agent creates algorithm based on research
4. **Backtest Phase (`/backtest`)** - Test algorithm on historical data
5. **Deploy Phase (`/deploy`)** - Deploy to live arena

### Available Commands

#### Core Modes

| Command | Description | Example |
|---------|-------------|---------|
| `/plan <request>` | Create research plan without executing code | `/plan Find correlation between PLTR and US defense spending` |
| `/approve` | Execute the research plan and show findings | `/approve` |
| `/build` | Build algorithm based on research findings | `/build` |
| `/backtest` | Backtest algorithm against historical data | `/backtest --period 6m --initial 10000` |

#### Research Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/research <topic>` | Deep research on a specific topic | `/research insider trading patterns in NVDA` |
| `/analyze <ticker>` | Full analysis of a ticker | `/analyze AAPL` |
| `/compare <ticker1> <ticker2>` | Compare two assets | `/compare NVDA PLTR` |
| `/sentiment <ticker>` | News sentiment analysis | `/sentiment TSLA` |

#### Data Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/insider <ticker>` | Show recent insider trades | `/insider NVDA` |
| `/institutional <ticker>` | Institutional ownership changes | `/institutional AAPL` |
| `/financials <ticker>` | Financial statements | `/financials MSFT` |
| `/news <ticker>` | Recent news with sentiment | `/news TSLA` |

#### Algorithm Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/deploy` | Deploy algorithm to arena | `/deploy` |
| `/optimize` | Optimize algorithm parameters | `/optimize` |
| `/explain` | Explain current algorithm logic | `/explain` |
| `/code` | Show full algorithm code | `/code` |

#### Session Commands

| Command | Description |
|---------|-------------|
| `/clear` | Clear conversation history |
| `/model <name>` | Switch AI model |
| `/status` | Show session status |
| `/help` | Show all commands |
| `/exit` | End session |

### Research Workflow Example

Let's walk through a complete research workflow to find correlations between Palantir (PLTR) and US-Venezuela tensions:

```bash
# Step 1: Create a research plan
$ /plan Find correlation between PLTR and tensions between US and Venezuela

# Agent creates a structured plan:
📋 Research Plan:
1. Fetch historical price data for PLTR (2022-2026)
2. Fetch news data for Venezuela-related events
3. Fetch insider trading data for PLTR
4. Analyze correlation between news events and price movements
5. Identify trading signals based on geopolitical tension indicators

# Step 2: Execute the plan
$ /approve

# Agent executes research:
🧠 Executing research plan...
✓ Fetched 1,460 price data points for PLTR
✓ Analyzed 127 news articles mentioning Venezuela
✓ Found 43 insider trades in the period
✓ Computed correlations and event impacts

📊 Research Findings:
- PLTR price shows 0.64 correlation with defense sector during geopolitical events
- Significant price movement (+3.2% avg) within 48 hours of Venezuela-US tension news
- Insider buying activity increases 2 weeks before major defense contracts
- Strong correlation (0.78) between PLTR and defense ETF (ITA) movements

# Step 3: Build the algorithm
$ /build

# Agent generates algorithm:
🧠 Building algorithm based on research findings...

✓ Algorithm created: Agent_sandbox_pltr_defense_correlation
Strategy: Momentum + News Sentiment + Defense Sector Correlation
- Buy when: PLTR > defense sector momentum AND positive news sentiment
- Sell when: Stop-loss (-0.3%) OR take-profit (+0.5%)
- Position size: 20% of cash balance

# Step 4: Backtest the algorithm
$ /backtest --period 6m --initial 10000

# Results displayed:
📈 Backtest Results (6 months):
ROI: +18.3%
Win Rate: 64.2%
Sharpe Ratio: 1.82
Max Drawdown: -2.1%
Total Trades: 47

# Step 5: Deploy to arena
$ /deploy

✓ Algorithm deployed to arena as: Agent_sandbox_pltr_defense_correlation
✓ Now competing with 6 other agents
→ View performance at http://localhost:5173/dashboard
```

### Agent Validation and Auto-Repair

Before deployment, all algorithms undergo a rigorous validation process:

#### Validation Pipeline

1. **Static Validation**
   - Syntax check with Python AST parser
   - Verify `execute_strategy` function exists
   - Validate function signature (4-6 arguments)
   - Check for dangerous imports (`os`, `sys`, `subprocess`)

2. **Runtime Validation**
   - Execute against "dirty" mock data with None values
   - Test defensive programming (handles missing/None fields)
   - Verify no NoneType errors or crashes
   - Check state persistence across multiple ticks

3. **Auto-Repair Loop**
   - If validation fails, LLM attempts to fix the code
   - Maximum 3 repair attempts
   - Common fixes:
     - Add `.get(key, 0) or 0` for None protection
     - Handle missing dictionary keys
     - Fix division by zero errors
     - Correct variable type mismatches

#### Validation Example

```python
# Original code (fails validation):
def execute_strategy(market_data, tick, cash_balance, portfolio, ...):
    btc = market_data.get('BTC', {})
    obi = btc.get('obi_weighted')  # Can be None!
    score = obi * 2  # ERROR: NoneType * int
    
# Auto-repaired code:
def execute_strategy(market_data, tick, cash_balance, portfolio, ...):
    btc = market_data.get('BTC', {})
    obi = btc.get('obi_weighted', 0) or 0  # Safe default
    score = obi * 2  # No error
```

The validation system ensures that only production-ready algorithms are deployed to the arena, preventing crashes and maintaining system stability.

---

## Trading System

### Multi-Asset Trading

AlgoClash Live supports simultaneous trading of cryptocurrencies and stocks:

**Cryptocurrency Trading:**
- **Symbols**: BTC, ETH, SOL, BNB
- **Source**: Binance via CCXT library
- **Update Frequency**: Real-time (every 1 second)
- **Trading Hours**: 24/7
- **Order Types**: Market orders with simulated slippage

**Stock Trading:**
- **Symbols**: AAPL, TSLA, NVDA, MSFT, GOOGL, AMZN, META
- **Source**: FinancialDatasets.ai (primary), Yahoo Finance (fallback)
- **Update Frequency**: Every 5 minutes when market is open
- **Trading Hours**: 9:30 AM - 4:30 PM ET, Monday-Friday
- **After-Hours**: Returns cached prices, no new trades
- **Order Types**: Market orders with simulated slippage

### Market Hours Detection

The system includes intelligent market hours detection:

```python
# Automatic detection of US stock market hours
is_open = is_stock_market_open()  # True during 9:30 AM - 4:30 PM ET

# Timezone-aware with pytz
# Falls back to UTC-5 if pytz unavailable

# Weekend detection
# Returns False on Saturday and Sunday
```

**API Throttling:**
- Stock APIs only polled during market hours
- 5-minute intervals to respect API limits
- Cached prices used when market closed
- Fundamental data refreshed hourly (market hours only)

### Trading Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| Starting Capital | $10,000 | Initial cash balance per agent |
| Cashout Threshold | 0.50% ROI | Auto-secure profits above this |
| Emergency Stop-Loss | -2.00% | Arena enforces this limit |
| Transaction Fee | 0.05% | Per-trade fee |
| Slippage | 0.02-0.10% | Simulated market impact |
| Max Position Size | 100% | Agents can use all capital |
| Cooldown | Agent-defined | Minimum ticks between trades |

### Market Signals

Agents receive comprehensive market data through the `market_data` parameter:

```python
market_data = {
    'BTC': {
        # Price Data
        'price': 50000.0,           # Current price
        'open': 49800.0,            # Session open price
        'high': 50200.0,            # Session high
        'low': 49700.0,             # Session low
        'volume': 1500000.0,        # 24h volume
        'history': [49800, ...],    # Recent price history
        
        # Technical Signals (All Assets)
        'obi_weighted': 0.23,       # Order Book Imbalance (-1 to 1)
        'micro_price': 50010.0,     # Fair value estimate
        'ofi': 0.15,                # Order Flow Imbalance
        'sentiment': 0.42,          # News sentiment (-1 to 1)
        'parkinson_vol': 0.035,     # Volatility estimate
        'cvd_divergence': 0.08,     # Volume divergence
        'taker_ratio': 0.58,        # Buy/sell ratio
        'funding_rate_velocity': 0.0001,  # Crypto only
        
        # Fundamental Signals (Stocks Only)
        'insider_sentiment': None,      # Not available for crypto
        'institutional_change': None,   # Not available for crypto
        'revenue_growth': None,
        'profit_margin': None,
        'pe_ratio': None,
    },
    'AAPL': {
        # Price Data
        'price': 185.50,
        'open': 184.20,
        'high': 186.10,
        'low': 183.90,
        'volume': 52400000.0,
        
        # Technical Signals
        'obi_weighted': 0.15,
        'micro_price': 185.65,
        'sentiment': 0.28,
        
        # Fundamental Signals (Stocks Only)
        'insider_sentiment': 0.34,          # -1 to 1
        'institutional_change': 2.3,        # % QoQ change
        'revenue_growth': 11.2,             # % YoY
        'profit_margin': 0.265,             # 26.5%
        'pe_ratio': 28.4,
        'earnings_surprise': 3.2,           # % vs estimate
        'news_sentiment_score': 0.42,       # -1 to 1
    }
}
```

### Order Execution

Agents return trade signals in this format:

```python
def execute_strategy(market_data, tick, cash_balance, portfolio, ...):
    # Your strategy logic here
    
    # Return format: (ACTION, SYMBOL, QUANTITY)
    return ("BUY", "BTC", 0.5)      # Buy 0.5 BTC
    return ("SELL", "AAPL", 100)    # Sell 100 shares of AAPL
    return ("HOLD", None, 0)        # Do nothing
```

**Order Processing:**
1. Validate sufficient cash (for BUY) or position (for SELL)
2. Calculate transaction fee (0.05%)
3. Apply slippage simulation
4. Update portfolio and cash balance
5. Emit trade notification via Socket.IO
6. Update agent's entry prices and PnL tracking

---

## Creating Trading Agents

### Agent Interface

All trading agents must implement the `execute_strategy` function:

```python
def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    """
    Trading strategy function for AlgoClash arena.
    
    Args:
        market_data: Dict[symbol -> market data dict]
            See Market Signals section for full structure
            
        tick: int
            Current tick number (increments every second)
            
        cash_balance: float
            Available cash to trade
            
        portfolio: Dict[symbol -> quantity]
            Current positions
            Example: {'BTC': 0.5, 'ETH': 0, 'AAPL': 100}
            
        market_state: Optional[dict]
            Structured market analysis from Analyst Engine
            Contains trend, volatility, regime information
            
        agent_state: Dict
            Persistent state across ticks:
            - 'entry_prices': {symbol: price} - Your entry prices
            - 'current_pnl': {symbol: pnl_data} - Current PnL per position
            - 'trade_history': List of recent trades
            - 'custom': {} - Your custom persistent variables
            
    Returns:
        Tuple[str, str, float]: (ACTION, SYMBOL, QUANTITY)
        - ACTION: "BUY" | "SELL" | "HOLD"
        - SYMBOL: "BTC", "ETH", "SOL", "AAPL", "TSLA", etc.
        - QUANTITY: float (fractional quantities allowed)
    """
    # Your strategy here
    return ("HOLD", None, 0)
```

### Agent State Management

**IMPORTANT**: Do NOT use Python globals for state. Use `agent_state['custom']`:

```python
# WRONG - Global state (not persistent across restarts)
entry_price = 50000.0

# CORRECT - Persistent state
def execute_strategy(..., agent_state=None):
    if agent_state is None:
        agent_state = {'custom': {}}
    
    custom = agent_state.get('custom', {})
    
    # Initialize state
    if 'entry_price' not in custom:
        custom['entry_price'] = 50000.0
    
    # Use state
    entry_price = custom['entry_price']
    
    # Update state
    custom['entry_price'] = 51000.0
```

### Signal Scoring

Example multi-signal scoring system:

```python
import numpy as np

def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    SYMBOLS = ['BTC', 'ETH', 'AAPL', 'NVDA']
    POSITION_SIZE = 0.20  # 20% of cash
    
    best_score = 0
    best_symbol = None
    
    for sym in SYMBOLS:
        data = market_data.get(sym, {})
        if not data:
            continue
            
        score = 0
        
        # Signal 1: Order Book Imbalance
        obi = data.get('obi_weighted', 0) or 0
        if obi > 0.2:
            score += 1
        elif obi < -0.2:
            score -= 1
            
        # Signal 2: News Sentiment
        sentiment = data.get('sentiment', 0) or 0
        if sentiment > 0.3:
            score += 1
        elif sentiment < -0.3:
            score -= 1
            
        # Signal 3: Insider Sentiment (stocks only)
        insider = data.get('insider_sentiment')
        if insider is not None:
            if insider > 0.3:
                score += 2  # Strong bullish signal
            elif insider < -0.3:
                score -= 2
                
        # Signal 4: Microprice vs Price
        micro = data.get('micro_price', 0) or 0
        price = data.get('price', 0) or 0
        if micro and price:
            deviation = (micro - price) / price
            if deviation > 0.001:
                score += 1
                
        if abs(score) > abs(best_score):
            best_score = score
            best_symbol = sym
    
    # Execute if threshold met
    if best_symbol and abs(best_score) >= 3:
        price = market_data[best_symbol]['price']
        quantity = (cash_balance * POSITION_SIZE) / price
        
        if best_score > 0:
            return ("BUY", best_symbol, quantity)
        else:
            return ("SELL", best_symbol, quantity)
    
    return ("HOLD", None, 0)
```

### Example Strategies

**1. Momentum + Insider Trading Strategy (Stocks)**

```python
def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    """
    Buys stocks with positive insider sentiment and price momentum.
    Sells on stop-loss or take-profit.
    """
    if agent_state is None:
        agent_state = {'custom': {}, 'current_pnl': {}}
    
    custom = agent_state.get('custom', {})
    current_pnl = agent_state.get('current_pnl', {})
    
    STOCKS = ['AAPL', 'NVDA', 'TSLA', 'MSFT']
    TAKE_PROFIT = 0.005  # 0.5%
    STOP_LOSS = -0.003   # -0.3%
    
    # Exit logic
    for sym in STOCKS:
        qty = portfolio.get(sym, 0)
        if qty > 0:
            pnl_info = current_pnl.get(sym, {})
            pnl_pct = pnl_info.get('pnl_percent', 0) / 100.0
            
            if pnl_pct >= TAKE_PROFIT or pnl_pct <= STOP_LOSS:
                return ("SELL", sym, qty)
    
    # Entry logic
    for sym in STOCKS:
        if portfolio.get(sym, 0) > 0:
            continue
            
        data = market_data.get(sym, {})
        if not data:
            continue
        
        # Check insider sentiment
        insider = data.get('insider_sentiment', 0) or 0
        if insider < 0.3:
            continue
        
        # Check price momentum
        price = data.get('price', 0) or 0
        open_price = data.get('open', 0) or 0
        if price <= open_price:
            continue
        
        # Buy signal
        quantity = (cash_balance * 0.25) / price
        return ("BUY", sym, quantity)
    
    return ("HOLD", None, 0)
```

**2. Order Book Imbalance Strategy (Crypto)**

```python
def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    """
    Trades based on order book imbalance and microprice deviation.
    """
    CRYPTO = ['BTC', 'ETH', 'SOL']
    
    for sym in CRYPTO:
        data = market_data.get(sym, {})
        if not data:
            continue
        
        obi = data.get('obi_weighted', 0) or 0
        micro = data.get('micro_price', 0) or 0
        price = data.get('price', 0) or 0
        
        if not price:
            continue
        
        # Strong buy signal
        if obi > 0.3 and micro > price * 1.001:
            quantity = (cash_balance * 0.33) / price
            return ("BUY", sym, quantity)
        
        # Strong sell signal
        if obi < -0.3 and micro < price * 0.999:
            qty = portfolio.get(sym, 0)
            if qty > 0:
                return ("SELL", sym, qty)
    
    return ("HOLD", None, 0)
```

---

## API Reference

### REST Endpoints

#### Health & Status

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with detailed metrics |
| `/status` | GET | Arena status (running, agent count) |
| `/` | GET | API info and available endpoints |

#### Agent Management

| Endpoint | Method | Body | Description |
|----------|--------|------|-------------|
| `/generate_agent` | POST | `{name, model}` | Generate agent code using LLM |
| `/deploy_agent` | POST | `{name}` | Deploy agent to arena |
| `/stop_agent` | POST | `{name}` | Remove agent from arena |
| `/agent_code/<name>` | GET | - | Get agent source code |
| `/leaderboard` | GET | - | Get sorted leaderboard |
| `/available_models` | GET | - | List available LLM models |

#### Arena Control

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/start_arena` | POST | Start arena execution loop |
| `/stop_arena` | POST | Stop arena execution loop |
| `/reset_arena` | POST | Hard reset (reload default agents) |
| `/soft_reset_arena` | POST | Soft reset (keep agents, reset balances) |
| `/rebuild_algos` | POST | Force evolution of agents |
| `/clear_all_data` | POST | Clear all data and agents |

#### Sandbox Research Terminal

| Endpoint | Method | Body | Description |
|----------|--------|------|-------------|
| `/sandbox/create` | POST | `{model}` | Create research session |
| `/sandbox/message` | POST | `{session_id, message}` | Send message to agent |
| `/sandbox/execute` | POST | `{session_id, code}` | Execute code manually |
| `/sandbox/finalize` | POST | `{session_id, agent_name, code?}` | Deploy strategy to arena |
| `/sandbox/status/<id>` | GET | - | Get session status |
| `/sandbox/history/<id>` | GET | - | Get full session history |
| `/sandbox/close` | POST | `{session_id}` | Close session |

### WebSocket Events

#### Server -> Client

| Event | Data | Description |
|-------|------|-------------|
| `chart_update` | `{timestamp, agents: [{name, equity, roi, ...}]}` | Live equity curve update |
| `trade_executed` | `{agent_name, action, symbol, quantity, price, ...}` | Trade notification |
| `news_update` | `{articles: [{title, sentiment, ticker, ...}]}` | News feed update |
| `analyst_update` | `{market_state: {...}}` | Market analysis from Analyst Engine |
| `sandbox_execution` | `{session_id, code, result, error}` | Sandbox code execution result |
| `sandbox_log` | `{session_id, type, message}` | Sandbox agent thinking/logs |

#### Client -> Server

| Event | Data | Description |
|-------|------|-------------|
| `request_history` | - | Request chart history on connect |
| `sandbox_subscribe` | `{session_id}` | Subscribe to sandbox session updates |

---

## Data Sources

### Cryptocurrency Data

**Primary Source: Binance via CCXT**

```python
# Real-time crypto prices
exchange = ccxt.binance()
ticker = exchange.fetch_ticker('BTC/USDT')

# Symbols supported:
- BTC/USDT
- ETH/USDT
- SOL/USDT
- BNB/USDT
```

**Features:**
- Real-time WebSocket data (1-second updates)
- Order book data for OBI calculation
- Funding rate data
- 24/7 availability
- No API key required for public data

### Stock Market Data

**Primary Source: FinancialDatasets.ai**

Premium stock data with fundamental information:

```python
# Real-time stock prices
GET /prices/snapshot?ticker=AAPL

# Historical prices
GET /prices?ticker=AAPL&interval=daily&start_date=2024-01-01&end_date=2024-12-31

# Insider trades
GET /insider-trades?ticker=AAPL&limit=50

# Institutional ownership
GET /institutional-ownership?ticker=AAPL

# Financial statements
GET /financials/income-statements?ticker=AAPL&period=quarterly&limit=8

# News with sentiment
GET /news?ticker=AAPL&limit=20
```

**Fallback Source: Yahoo Finance**

Used when FinancialDatasets.ai is unavailable:

```python
import yfinance as yf

ticker = yf.Ticker("AAPL")
data = ticker.history(period="1d", interval="1m")
```

**Market Hours Handling:**
- Polls stock APIs every 5 minutes when market is open
- Returns cached prices when market is closed
- Respects API rate limits
- Automatic weekend detection

### FinancialDatasets.ai Integration

The platform integrates with FinancialDatasets.ai for comprehensive fundamental data:

**Available Data:**
1. **Price Data**: Real-time and historical prices
2. **Insider Trades**: Officer and director transactions
3. **Institutional Ownership**: 13F filings from major institutions
4. **Financial Statements**: Income, balance sheet, cash flow
5. **SEC Filings**: 10-K, 10-Q, 8-K filings
6. **News**: Real-time news with sentiment analysis
7. **Segmented Financials**: Business and geographic segments

**Authentication:**
```python
headers = {
    'X-API-KEY': os.getenv('FINANCIAL_DATASETS_API_KEY')
}
```

**Caching Strategy:**
- Fundamental data cached for 1 hour
- Price data cached for 5 minutes
- News updated every 30 seconds
- Minimizes API calls to respect rate limits

---

## Deployment

### Render Deployment

AlgoClash Live is optimized for deployment on Render:

**backend/render.yaml:**
```yaml
services:
  - type: web
    name: algoclash-backend
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn --worker-class gevent --bind 0.0.0.0:$PORT backend.app:app
    envVars:
      - key: PYTHON_VERSION
        value: 3.9.0
      - key: OPENROUTER_API_KEY
        sync: false
      - key: FINANCIAL_DATASETS_API_KEY
        sync: false
      - key: E2B_API_KEY
        sync: false
      - key: MONGO_URI
        sync: false
```

**Keep-Alive Feature:**
Render free tier sleeps after inactivity. The backend includes automatic keep-alive:

```python
def keep_alive():
    """Pings the server every 10 minutes to prevent Render from sleeping"""
    render_url = os.getenv('RENDER_EXTERNAL_URL')
    while True:
        time.sleep(600)  # 10 minutes
        requests.get(f"{render_url}/health")
```

### Docker Deployment

**Dockerfile:**
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

# Copy application
COPY . .

EXPOSE 5000

CMD ["python", "backend/app.py"]
```

**Docker Compose:**
```yaml
version: '3.8'

services:
  backend:
    build: .
    ports:
      - "5000:5000"
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - E2B_API_KEY=${E2B_API_KEY}
      - FINANCIAL_DATASETS_API_KEY=${FINANCIAL_DATASETS_API_KEY}
      - MONGO_URI=${MONGO_URI}
    depends_on:
      - mongo

  mongo:
    image: mongo:6
    ports:
      - "27017:27017"
    volumes:
      - mongo-data:/data/db

  frontend:
    image: node:18
    working_dir: /app
    volumes:
      - ./frontend:/app
    command: npm run dev
    ports:
      - "5173:5173"

volumes:
  mongo-data:
```

---

## Tech Stack

### Backend
- **Python 3.9+** - Core runtime
- **Flask** - Web framework
- **Flask-SocketIO** - WebSocket server
- **MongoDB** - Data persistence (optional)
- **CCXT** - Cryptocurrency exchange integration
- **yfinance** - Stock market data (fallback)
- **pandas/numpy** - Data processing
- **TextBlob** - Sentiment analysis
- **E2B Code Interpreter** - Python sandbox execution
- **Azure AI Inference** - GitHub AI models SDK

### Frontend
- **React 18** - UI framework
- **Vite** - Build tool and dev server
- **React Router** - Client-side routing
- **Socket.IO Client** - WebSocket client
- **Recharts** - Chart visualization
- **Axios** - HTTP client

### LLM Integration
- **OpenRouter** - Multi-model LLM access
- **GitHub AI Inference** - GitHub models API
- **Anthropic Claude** - Via OpenRouter
- **OpenAI GPT-4** - Via OpenRouter
- **DeepSeek** - Via OpenRouter

### Data Sources
- **Binance API** - Crypto price data
- **FinancialDatasets.ai** - Stock fundamental data
- **Yahoo Finance** - Stock price fallback
- **Google Trends** - Attention metrics

---

## Project Structure

```
AlgoLive/
├── backend/
│   ├── app.py                    # Flask application & API routes
│   ├── requirements.txt          # Python dependencies
│   ├── .env                      # Environment variables
│   └── render.yaml               # Render deployment config
│
├── analyst_engine/
│   ├── analyst.py                # Market state analyzer (5-min loop)
│   ├── brain.py                  # LLM agent code generator
│   ├── sandbox_agent.py          # Sandbox research terminal
│   ├── news_feed.py              # News polling (30s loop)
│   └── ai_agents.json            # Available LLM models config
│
├── market_simulation/
│   ├── arena.py                  # Core trading arena (1s loop)
│   ├── data_feed.py              # Market data fetching (crypto + stocks)
│   ├── financial_datasets_provider.py  # FinancialDatasets.ai integration
│   ├── quant_features.py         # Signal calculation (OBI, microprice, etc.)
│   ├── market_metrics.py         # Advanced metrics (Parkinson vol, CVD, etc.)
│   ├── supervisor.py             # Risk management (currently disabled)
│   ├── attention_feed.py         # Google Trends integration
│   └── agents/                   # Generated agent files
│       ├── Agent_momentum_breakout.py
│       └── Agent_sandbox_*.py
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx               # Main application component
│   │   ├── api.js                # API client & Socket.IO setup
│   │   ├── pages/
│   │   │   ├── SelectionPage.jsx      # Agent generation page
│   │   │   ├── DashboardPage.jsx      # Live trading dashboard
│   │   │   ├── LeaderboardPage.jsx    # Agent rankings
│   │   │   └── SandboxResearchPage.jsx # Research terminal
│   │   └── components/
│   │       ├── AgentSelection.jsx     # Agent selection UI
│   │       ├── Dashboard.jsx          # Main dashboard
│   │       ├── LiveChart.jsx          # Equity curve chart
│   │       ├── TradeLog.jsx           # Trade history
│   │       ├── Leaderboard.jsx        # Rankings table
│   │       ├── NewsFeed.jsx           # News display
│   │       └── ControlPanel.jsx       # Arena controls
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
│
├── SANDBOX_AGENT_PROMPT.md      # System prompt for research agent
├── README.md                     # This file
└── Dockerfile                    # Docker configuration
```

---

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

**Development Guidelines:**
- Follow PEP 8 for Python code
- Use ESLint configuration for JavaScript/React
- Add docstrings to all functions
- Write tests for new features
- Update README with new features

---

## License

This project is licensed under the MIT License. See LICENSE file for details.

---

## Acknowledgments

- **CCXT** - Cryptocurrency exchange integration
- **FinancialDatasets.ai** - Premium stock market data
- **E2B** - Secure Python sandbox execution
- **OpenRouter** - Multi-model LLM access
- **GitHub AI** - AI model inference platform

---

## Support

For issues, questions, or contributions:
- GitHub Issues: https://github.com/yourusername/algoclash-live/issues
- Documentation: https://github.com/yourusername/algoclash-live/wiki

---

Built with Python, React, and AI. Trade responsibly.
