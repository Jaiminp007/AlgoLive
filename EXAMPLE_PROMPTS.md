# Example Prompts for Sandbox Research Terminal

## Crypto HFT (High-Frequency Trading) Prompts

### 1. Basic Crypto HFT
```
/plan Create a high-frequency crypto trading algorithm that uses order book imbalance and microprice signals to trade BTC, ETH, and SOL with 0.3% profit targets
```

### 2. Order Flow Strategy
```
/plan Build a crypto HFT algorithm that trades based on order flow imbalance (OFI) and taker ratio, targeting quick 0.2% profits on BTC and ETH
```

### 3. Mean Reversion HFT
```
/plan Create a mean reversion crypto strategy that buys when price deviates from microprice by more than 0.1% and sells at 0.3% profit
```

### 4. Multi-Signal HFT
```
/plan Develop a crypto HFT algorithm combining order book imbalance, microprice deviation, and funding rate velocity to trade all crypto assets
```

### 5. Scalping Strategy
```
/plan Build a crypto scalping algorithm that takes many small trades (0.1-0.2% profit) using order book pressure signals on BTC, ETH, SOL, BNB
```

---

## Stock Fundamental Prompts

### 1. Insider Trading Strategy
```
/plan Find correlation between insider buying activity and stock price movements for tech stocks NVDA, AAPL, MSFT. Create an algorithm that trades based on insider sentiment
```

### 2. Institutional Flow Strategy
```
/plan Analyze institutional ownership changes from 13F filings for TSLA, NVDA, AAPL. Build an algorithm that follows institutional money flows
```

### 3. Earnings Momentum
```
/plan Create a stock trading algorithm that identifies companies with consistent earnings surprises and strong revenue growth among NVDA, MSFT, GOOGL, META
```

### 4. Multi-Factor Stock Strategy
```
/plan Build a stock algorithm combining insider sentiment, institutional ownership changes, and earnings momentum for all available stocks
```

### 5. News Sentiment Strategy
```
/plan Analyze news sentiment patterns for TSLA and create an algorithm that trades based on sentiment shifts before price moves
```

---

## Correlation/Event-Driven Prompts

### 1. Geopolitical Events
```
/plan Find correlation between defense sector stocks (e.g., Palantir PLTR) and geopolitical tensions. Create an algorithm that trades based on news events
```

### 2. Sector Rotation
```
/plan Analyze correlation between tech stocks NVDA, MSFT, AAPL and identify lead-lag relationships. Build an algorithm that trades based on sector momentum
```

### 3. Crypto-Stock Correlation
```
/plan Find correlations between crypto prices (BTC, ETH) and tech stock movements (NVDA, TSLA). Create a cross-asset arbitrage strategy
```

---

## What Makes a Good Prompt

### ✅ GOOD Prompts:

1. **Specific Asset Focus**
   - ✅ "Create HFT crypto algorithm for BTC, ETH, SOL"
   - ❌ "Create a trading algorithm"

2. **Clear Signal Type**
   - ✅ "using order book imbalance and microprice"
   - ❌ "using technical analysis"

3. **Profit Target**
   - ✅ "targeting 0.3% profits"
   - ❌ "maximize profits"

4. **Strategy Type**
   - ✅ "mean reversion" or "momentum" or "scalping"
   - ❌ "profitable strategy"

### Example: Bad vs Good Prompts

**❌ Bad Prompt:**
```
/plan make me money trading crypto
```
Why: Too vague, no specific signals or assets

**✅ Good Prompt:**
```
/plan Create a crypto HFT algorithm for BTC and ETH that uses order book imbalance (OBI > 0.3 = buy signal) with 0.3% profit targets and 0.1% stop-loss
```
Why: Specific assets, clear signals, defined risk/reward

---

## Prompt Template

Use this template for best results:

```
/plan Create a [STRATEGY_TYPE] algorithm for [ASSETS] that:
- Uses [SIGNAL_1] and [SIGNAL_2] 
- Targets [PROFIT_TARGET]% profit
- Uses [STOP_LOSS]% stop-loss
- Trades based on [CONDITION]
```

### Example Using Template:

```
/plan Create a high-frequency trading algorithm for BTC, ETH, SOL that:
- Uses order book imbalance and microprice deviation
- Targets 0.3% profit per trade
- Uses 0.1% stop-loss
- Trades when OBI > 0.3 AND price < microprice
```

---

## Quick Tips

1. **For Crypto HFT**: Focus on microstructure signals (OBI, microprice, OFI, taker ratio)
2. **For Stocks**: Focus on fundamentals (insider trades, institutional flows, earnings)
3. **Be Specific**: More details = better algorithm
4. **Set Targets**: Always include profit target and stop-loss
5. **Test First**: Use `/plan` then `/approve` before `/build`

---

## Workflow

```
Step 1: /plan <your detailed request>
   ↓
Step 2: Review the research plan
   ↓
Step 3: /approve (agent does research)
   ↓
Step 4: Review research findings
   ↓
Step 5: /build (agent creates algorithm)
   ↓
Step 6: /deploy (deploy to live arena)
```

---

## Common Issues and Solutions

### Issue: Validation fails with "Missing execute_strategy"

**Cause**: LLM returned wrong format

**Solution**: Use simpler, more specific prompt:
```
/build Create a simple crypto HFT algorithm for BTC that:
1. Buys when OBI > 0.3
2. Sells at 0.3% profit or 0.1% loss
3. Uses 20% position size
4. Returns (ACTION, SYMBOL, QUANTITY) tuple
```

### Issue: Agent keeps using moving averages for HFT

**Cause**: Prompt isn't specific enough about speed

**Solution**: Emphasize "high-frequency" and "order book signals":
```
/plan Create a HIGH-FREQUENCY crypto algorithm (NO moving averages) that uses ORDER BOOK signals only: OBI, microprice, OFI, taker ratio
```

### Issue: Algorithm trades stocks instead of crypto

**Cause**: Didn't specify crypto-only

**Solution**: Be explicit:
```
/plan Create crypto-only HFT algorithm for BTC, ETH, SOL, BNB. DO NOT trade stocks.
```

---

## Pro Tips

1. **Start Simple**: Get a basic strategy working, then iterate
2. **One Asset First**: Test with BTC only, then expand
3. **Check /code**: Use `/code` to review the algorithm before `/deploy`
4. **Use /explain**: If confused, use `/explain` to understand the logic
5. **Iterate**: If validation fails, try `/build` with a simpler request

---

Happy trading!
