# AlgoClash Live - AI Trading Arena

## Project Overview

AlgoClash is a real-time AI trading simulation platform where LLM-generated trading agents compete against each other using live market data from Binance (crypto) and Yahoo Finance (stocks).

## Architecture

```
AlgoLive/
├── backend/                    # Flask + Socket.IO API Server
│   └── app.py                  # Main API endpoints and WebSocket handlers
├── market_simulation/          # Core Trading Engine
│   ├── arena.py               # Main game loop, agent execution, order matching
│   ├── data_feed.py           # Hybrid data from Binance (crypto) + yfinance (stocks)
│   ├── supervisor.py          # Agent monitoring and evolution triggers
│   ├── quant_features.py      # Market microstructure signals (OBI, microprice)
│   ├── attention_feed.py      # Google Trends integration
│   ├── market_metrics.py      # Parkinson volatility, CVD, taker ratio
│   └── agents/                # Generated trading agent Python files
│       └── Agent_*.py         # Individual agent strategies
├── analyst_engine/             # LLM-powered Agent Generation
│   ├── brain.py               # Code generation via OpenRouter/GitHub AI
│   ├── analyst.py             # Market state computation
│   ├── news_feed.py           # News aggregation
│   └── ai_agents.json         # Available LLM models configuration
├── frontend/                   # React + Vite Dashboard
│   └── src/
│       ├── App.jsx            # Main router
│       ├── api.js             # Backend API client
│       ├── pages/             # Page components
│       │   ├── SelectionPage.jsx    # Agent selection/creation
│       │   ├── DashboardPage.jsx    # Live trading view
│       │   └── LeaderboardPage.jsx  # Rankings
│       └── components/        # UI components
│           ├── Dashboard.jsx       # Main dashboard layout
│           ├── Leaderboard.jsx     # Agent rankings
│           ├── LiveChart.jsx       # Equity curves
│           ├── AgentSelection.jsx  # Agent creation form
│           └── TradeLog.jsx        # Trade history
└── Dockerfile                 # Deployment configuration
```

## Core Components

### 1. Arena (`market_simulation/arena.py`)

The central trading engine that:
- Fetches live market data every second via DataFeed
- Executes agent strategies via `execute_strategy(market_data, tick, cash, portfolio)`
- Manages positions, calculates equity, and applies fees/slippage
- Broadcasts updates via Socket.IO

**Key Methods:**
- `start_loop()` - Starts the main trading loop
- `_loop()` - Main tick processing (line 396)
- `_execute_order()` - Order execution with fees/slippage (line 818)
- `load_agent()` - Dynamically loads agent Python modules (line 169)

**Current Issues:**
- Auto-cashout at 0.125% ROI (line 709) - too low vs transaction costs
- Fee rate 0.01% (line 825) - unrealistically low
- Volume delta uses random noise injection (line 443-444)
- Evolution manager disabled (line 284)

### 2. Data Feed (`market_simulation/data_feed.py`)

Hybrid data provider:
- **Crypto**: Binance via CCXT (`get_market_snapshot()`)
- **Stocks**: Yahoo Finance via yfinance

**Symbols**: BTC, ETH, SOL (crypto only by default)

### 3. Brain (`analyst_engine/brain.py`)

LLM-powered agent code generation:
- `generate_agent_code(name, model)` - Creates new trading agent
- `evaluate_agent(code, roi, portfolio, logs)` - Evaluates performance
- `evolve_agent(name, critique, old_code)` - Refines underperforming agents

### 4. Agent Strategy Interface (UPDATED)

Each agent must implement:
```python
def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):
    """
    Args:
        market_data: Dict[symbol, {price, volume, history, obi_weighted, micro_price, ofi, sentiment, ...}]
        tick: int - Current tick number
        cash_balance: float - Available cash
        portfolio: Dict[symbol, quantity] - Current positions
        market_state: Optional dict with analyst engine data
        agent_state: Dict with PERSISTENT state (use this instead of globals!):
            - 'entry_prices': {symbol: price} - Entry prices for open positions
            - 'current_pnl': {symbol: {pnl_percent, pnl_usd, entry_price, current_price}}
            - 'trade_history': [...] - Last 20 trades
            - 'custom': {} - Your own persistent variables

    Returns:
        Tuple[str, str, float]: (ACTION, SYMBOL, QUANTITY)
        - ACTION: "BUY" | "SELL" | "HOLD"
        - SYMBOL: "BTC" | "ETH" | "SOL"
        - QUANTITY: float
    """
```

**IMPORTANT**: Use `agent_state['current_pnl']` for PnL tracking instead of global variables!
Global variables like `_entry_price` RESET when the module reloads.

### 5. Available Market Signals

From `market_data[symbol]`:
| Signal | Description | Range |
|--------|-------------|-------|
| `price` | Current price | float |
| `volume` | 24h volume | float |
| `history` | Price history list | [float] |
| `obi_weighted` | Order Book Imbalance | -1.0 to 1.0 |
| `micro_price` | Stoikov fair value | float |
| `ofi` | Order Flow Imbalance | float |
| `sentiment` | News sentiment score | -1.0 to 1.0 |
| `attention` | Google Trends delta | float |
| `parkinson_vol` | Volatility estimate | float |
| `cvd_divergence` | CVD divergence score | float |
| `taker_ratio` | Buy/sell taker ratio | float |
| `funding_rate_velocity` | Funding rate change | float |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Arena status and active agents |
| `/health` | GET | Health check for keep-alive |
| `/generate_agent` | POST | Generate new agent with LLM |
| `/deploy_agent` | POST | Deploy agent to arena |
| `/stop_agent` | POST | Remove agent from arena |
| `/start_arena` | POST | Start trading loop |
| `/stop_arena` | POST | Stop trading loop |
| `/soft_reset_arena` | POST | Reset equity but keep agents |
| `/rebuild_algos` | POST | Trigger manual evolution |
| `/available_models` | GET | List available LLM models |

## Socket.IO Events

| Event | Direction | Description |
|-------|-----------|-------------|
| `market_tick` | Server→Client | Price updates |
| `tick_bundle` | Server→Client | Full tick data bundle |
| `trade_log` | Server→Client | Trade execution logs |
| `agent_cashout` | Server→Client | Agent profit secured |
| `news_update` | Server→Client | News headline |
| `analyst_update` | Server→Client | Market state update |
| `request_history` | Client→Server | Request chart history |
| `chart_history_response` | Server→Client | Chart history data |

## Implemented Fixes (January 2026)

### Fix 1: State Persistence (COMPLETED)
- **Problem**: Agents used Python globals that reset on module reload
- **Solution**: Arena now passes `agent_state` dict with:
  - `entry_prices`: Persistent entry prices tracked by Arena
  - `current_pnl`: Pre-calculated PnL for each position
  - `trade_history`: Last 20 trades
  - `custom`: Agent's custom persistent state
- **Files Modified**: `arena.py` (lines 653-676, 919-946, 974-1042)

### Fix 2: Realistic Transaction Costs (COMPLETED)
- **Problem**: CASHOUT_THRESHOLD was 0.125% (less than costs)
- **Solution**:
  - CASHOUT_THRESHOLD increased to 0.50%
  - Fee rate changed from 0.01% to 0.075% (realistic Binance rate)
- **Files Modified**: `arena.py` (lines 755-758, 873-876)

### Fix 3: Removed Fake Volume Noise (COMPLETED)
- **Problem**: Random noise injection when delta_vol == 0
- **Solution**: Zero volume is now treated as legitimate data (no fake signals)
- **Files Modified**: `arena.py` (lines 452-467)

### Fix 4: Emergency Stop-Loss (COMPLETED)
- **Problem**: No safety net for catastrophic losses
- **Solution**: Arena now enforces -2% emergency stop-loss on all agents
- **Files Modified**: `arena.py` (lines 789-820)

### Moderate Fixes (COMPLETED)
- **Sentiment Analysis**: Now uses real news headlines (lines 496-509)
- **Brain Prompts**: Updated to teach agents about `agent_state` and new thresholds
- **Files Modified**: `brain.py` (lines 42-227, 462-545)

## Trading Parameters

| Parameter | Old Value | New Value |
|-----------|-----------|-----------|
| Cashout Threshold | 0.125% | 0.50% |
| Fee Rate | 0.01% | 0.075% |
| Emergency Stop | None | -2.0% |
| Agent Stop-Loss | -2.0% | -0.30% (suggested) |
| Entry Score | >= 3 | >= 2 |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGO_URI` | MongoDB connection string | None (no persistence) |
| `OPENROUTER_API_KEY` | OpenRouter API key | Required for agent generation |
| `GITHUB_TOKEN` | GitHub AI inference token | Optional |
| `ASSET_CLASS` | "STOCK" or "CRYPTO" | CRYPTO |
| `ENABLE_SEMANTIC_ALPHA` | Enable sentiment analysis | true |
| `RENDER_EXTERNAL_URL` | Self-ping URL for Render | None |
| `PORT` | Server port | 5000 |

## Development Commands

```bash
# Backend
cd backend
pip install -r requirements.txt
python app.py

# Frontend
cd frontend
npm install
npm run dev
```

## Deployment

### Render Deployment

Currently deployed on Render (free tier). Uses threading mode for Socket.IO.

**Service Configuration:**
```
Name: algoclash-backend
Runtime: Python 3
Root Directory: backend
Build Command: pip install -r requirements.txt
Start Command: python app.py
Instance Type: Free
```

**Environment Variables Required:**
- `MONGO_URI` - MongoDB connection string
- `OPENROUTER_API_KEY` - For LLM agent generation
- `GITHUB_TOKEN` - For GitHub AI models (optional)
- `RENDER_EXTERNAL_URL` - Your Render service URL (for internal keep-alive)

### GitHub Actions Keep-Alive

The `.github/workflows/keep-alive.yml` workflow pings the `/health` endpoint every 14 minutes to prevent Render's free tier from sleeping.

**Setup:**
1. Push code to GitHub with the workflow file
2. Go to repo Settings → Secrets → Actions
3. Add `RENDER_URL` secret with your Render URL (e.g., `https://algoclash-backend.onrender.com`)
4. Or update the workflow file with your actual URL
5. Enable Actions in the Actions tab

**Monitoring:**
- Check Actions tab for ping history
- Each run shows uptime, active agents, trades, and ROI

## File Modification Guide

When implementing fixes:
1. **arena.py** - Main trading logic, order execution, state management
2. **brain.py** - Agent generation prompts and validation
3. **data_feed.py** - Market data fetching
4. **supervisor.py** - Agent monitoring and evolution triggers
