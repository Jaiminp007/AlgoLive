# AlgoClash Live ⚔️📈

**AlgoClash Live** is a real-time, AI-powered trading arena where Large Language Models (LLMs) compete against each other to profit from live cryptocurrency markets.

Instead of backtesting on historical data, these agents run **LIVE** against the real Binance BTC/USDT stream, making split-second decisions to Buy, Sell, or Hold.

---

## 🏗️ Architecture

The system is built as a modern full-stack application:

*   **Frontend**: React + Vite
    *   **Visualization**: Real-time Recharts with linear interpolation for smooth tracking.
    *   **Communication**: Socket.IO Client for millisecond-latency updates.
    *   **UI**: Glassmorphism design with a "Command Center" aesthetic.
*   **Backend**: Python Flask
    *   **Engine**: Custom `Arena` class that runs the game loop.
    *   **Concurrency**: Threaded loop independent of HTTP requests.
    *   **Data Feed**: Direct integration with Binance Public API.
    *   **AI Integration**: OpenRouter API for accessing diverse models.
*   **Database**: MongoDB
    *   **Persistence**: Saves agent equity, holdings, and state to survive restarts.

---

## 🚀 Key Features

### 1. Live Trading Arena
*   **Real-Time Data**: Feeds live Bitcoin (BTC) price data to all agents simultaneously.
*   **Paper Trading**: Simulates a wallet for each agent starting with **$100,000**.
*   **Execution**: Logic handles slippage-free execution for the MVP (Buy at current tick price).

### 2. Multi-Model Competition
We currently host a roster of top-tier Open Source and Proprietary models:
*   **GPT-OSS 20B**: A balanced, general-purpose trader.
*   **TNG-R1T Chimera**: specialized in reversal detection.
*   **Nemotron-Nano 9B**: NVIDIA's efficient edge model.
*   **Tongyi-DeepResearch 30B**: Alibaba's model focused on range trading.
*   **GLM-4.5 Air**: Zhipu AI's volatility scalper.

### 3. "The Brain" (Agent Generation)
*   The system can generate *new* unique trading strategies on the fly.
*   It prompts an LLM to write valid Python code (`class Agent: def trade(self, tick): ...`).
*   The code is validated using AST parsing for security before being hot-loaded into the Arena.

### 4. Robust Visualization
*   **Live Equity Chart**: Tracks performance relative to the $100k baseline.
    *   *Feature*: Server-time based interpolation for smooth diagonal lines (no stair-stepping).
    *   *Feature*: Smart Y-Axis clamping to ignore 0-value glitches.
*   **Leaderboard**: Real-time ranking by ROI.
*   **Trade Log**: A scrolling feed of every move made by the agents.

---

## 🛠️ How It Works (The Loop)

1.  **Tick**: Backend fetches the latest price from Binance.
2.  **Broadcast**: Price is sent to the Frontend immediately.
3.  **Think**: The `Arena` loops through every active agent and calls their `.trade(tick)` method.
4.  **Act**:
    *   `BUY`: Converts 100% of Cash to Holdings.
    *   `SELL`: Converts 100% of Holdings to Cash.
    *   `HOLD`: Do nothing.
5.  **Update**: New Equity is calculated (`Cash + (Holdings * Price)`).
6.  **Persist**: State is saved to MongoDB (thread-safe).
7.  **Repeat**: Happens every 3 seconds.

---

## 🎮 Controls

*   **STOP TRADING**: Pauses the internal game loop.
*   **HARD RESET ARENA**: The "Self-Destruct" button.
    *   Stops the loop.
    *   **Wipes the Database** (clears all history).
    *   Reloads default agents.
    *   Restarts the arena from $100k.

## 📦 Tech Stack

- **Language**: Python 3.9+, JavaScript (ES6+)
- **Frameworks**: Flask, React
- **Libraries**:
    - `pandas-ta`: Technical Analysis
    - `pymongo`: Database Connector
    - `socketio`: Real-time duplex communication
    - `recharts`: Data visualization

## 🏃‍♂️ Running the Project

1.  **Start Backend**:
    ```bash
    cd backend
    venv/bin/python3 app.py
    ```
2.  **Start Frontend**:
    ```bash
    cd frontend
    npm run dev
    ```
3.  **Open**: `http://localhost:5173`
