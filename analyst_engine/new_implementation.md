# 🧠 AlgoClash Cortex (The Analyst Engine)

**AlgoClash Cortex** is the high-frequency intelligence layer that powers the AlgoClash live trading arena.

Unlike standard "Chat-with-PDF" trading bots, Cortex uses a **Multi-Loop, Event-Driven Architecture**. It separates data processing, strategy generation, and execution into distinct lifecycles to solve latency issues and prevent hallucinations.

---

## 🏗️ Architecture: The "Manager-Worker" Model

The system operates on three decoupled time loops to balance **responsiveness** with **inference costs**.

| Component | Role | Frequency | Function |
| :--- | :--- | :--- | :--- |
| **The Worker** | ⚡ Execution | **3 Seconds** (Tick) | Runs the active Python strategy against live prices. |
| **The Supervisor** | 🛡️ Risk/News | **5 Minutes** | Checks news, volatility, and stop-losses. Decides to *Update* or *Kill* the worker. |
| **The Manager** | 🧠 Strategy Gen | **On Trigger** | Uses LLMs (Claude/GPT-4) to write *new* Python code based on deep analysis. |

### System Flow
1.  **Aggregator:** Ingests raw Binance WebSockets + News API.
2.  **Analyst:** Formalizes data into a "Market State" (Calculates RSI, MACD, Order Flow Imbalance).
3.  **Sandbox:** Safely executes the current `ActiveAgent` code.
4.  **Evaluator:** Triggers a "Regime Change" (Re-generation) if the market shifts unexpectedly.

---

## 🚨 The Trigger System (Event-Driven)

We do **not** blindly regenerate code every 15 minutes. We use an **Event-Driven Trigger System** to save tokens and react instantly to crashes.

The **Supervisor** runs every 5 minutes and evaluates the following conditions. If a **Hard Trigger** is met, the current strategy is nuked and a new one is generated immediately.

### 1. Hard Triggers (Instant Kill)
*Logic that overrides the AI immediately for safety.*

* **🛑 Stop-Loss Breach:** If the active agent loses **>3% Equity** within a 5-minute window.
* **📉 Volatility Shock:** If `ATR` (Average True Range) doubles (2x) compared to the 1-hour average.
* **🔊 Volume Explosion:** If volume spikes **>500%** above the moving average (indicates a pump/dump or flash crash).

### 2. Soft Triggers (Context Updates)
*Logic that adapts the strategy without rewriting code.*

* **📰 News Event:** If a news item is significant but not catastrophic (e.g., "CPI Data Released"), the Supervisor calls `agent.update_context(news_summary)`. The Python code adjusts its internal variables (e.g., `self.sentiment = 'BEARISH'`) without needing a restart.

---

## 🛡️ The Sandbox (Safety Layer)

We do not simply `exec()` code from an LLM. All strategies are loaded into a restricted **`StrategySandbox`**.

### Security Measures
1.  **Restricted Globals:** Agents have no access to `os`, `sys`, or file I/O. They cannot delete files or access the internet.
2.  **Order Throttling:** The wrapper limits agents to **max 5 orders per minute** to prevent infinite loop wash-trading.
3.  **Error Handling:** If an agent throws a syntax error or runtime exception, the Sandbox catches it and switches to a default `HOLD` state.

---

## 🔌 API & Data Pipeline

### Input: The "Formalized" Data
The Cortex feeds the LLM a highly structured JSON payload, not raw noise.

```json
{
  "market_regime": {
    "trend": "STRONG_UPTREND",
    "volatility": "LOW",
    "order_book_imbalance": "BID_HEAVY"
  },
  "technical_signals": {
    "rsi_14": 82.5,
    "ema_cross": "GOLDEN_CROSS",
    "support_level": 97500.00
  },
  "risk_metrics": {
    "current_drawdown": -0.5,
    "sharpe_est": 1.2
  }
}