"""
BacktestEngine - Historical strategy backtesting for AlgoClash.

Replays historical market data through trading strategies and calculates
performance metrics including Sharpe ratio, max drawdown, win rate, and total return.
"""

import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Callable
import importlib.util
import sys
import os
import requests


class BacktestEngine:
    """
    Backtests trading strategies against historical market data.

    Matches Arena execution logic: fees, slippage, position management.
    """

    # Match Arena's fee/slippage parameters
    FEE_RATE = 0.00075  # 0.075% per trade (Binance-like)
    SLIPPAGE_RATE = 0.00025  # 0.025% per trade

    # Supported symbols
    CRYPTO_SYMBOLS = ['BTC', 'ETH', 'SOL', 'BNB']
    STOCK_SYMBOLS = ['AAPL', 'TSLA', 'NVDA', 'MSFT', 'GOOGL', 'AMZN', 'META']

    # Yahoo Finance ticker mappings
    YAHOO_TICKERS = {
        'BTC': 'BTC-USD',
        'ETH': 'ETH-USD',
        'SOL': 'SOL-USD',
        'BNB': 'BNB-USD',
        'AAPL': 'AAPL',
        'TSLA': 'TSLA',
        'NVDA': 'NVDA',
        'MSFT': 'MSFT',
        'GOOGL': 'GOOGL',
        'AMZN': 'AMZN',
        'META': 'META'
    }

    def __init__(self):
        self.historical_data = {}
        self.results = None

    def fetch_historical_data(
        self,
        symbols: List[str],
        period: str = '3m',
        interval: str = '1h'
    ) -> Dict[str, List[dict]]:
        """
        Fetch historical OHLCV data from Yahoo Finance.

        Args:
            symbols: List of symbols to fetch (e.g., ['BTC', 'ETH', 'AAPL'])
            period: Time period - '1m', '3m', '6m', '1y', '2y'
            interval: Data interval - '1m', '5m', '15m', '1h', '1d'

        Returns:
            Dict mapping symbol to list of OHLCV candles
        """
        # Map period to yfinance format
        yf_period_map = {
            '1m': '1mo',
            '3m': '3mo',
            '6m': '6mo',
            '1y': '1y',
            '2y': '2y'
        }
        yf_period = yf_period_map.get(period, '3mo')

        # Adjust interval based on period (yfinance limits)
        # For longer periods, we need larger intervals
        if period in ['6m', '1y', '2y']:
            interval = '1d'  # Daily for longer periods
        elif period == '3m':
            interval = '1h'  # Hourly for 3 months
        else:
            interval = '1h'  # Hourly for 1 month

        historical_data = {}

        for symbol in symbols:
            yahoo_ticker = self.YAHOO_TICKERS.get(symbol, symbol)

            try:
                ticker = yf.Ticker(yahoo_ticker)
                df = ticker.history(period=yf_period, interval=interval)

                if df.empty:
                    print(f"BacktestEngine: No data for {symbol}")
                    continue

                # Convert to list of candles
                candles = []
                for idx, row in df.iterrows():
                    candles.append({
                        'timestamp': int(idx.timestamp() * 1000),
                        'open': float(row['Open']),
                        'high': float(row['High']),
                        'low': float(row['Low']),
                        'close': float(row['Close']),
                        'volume': float(row['Volume'])
                    })

                historical_data[symbol] = candles
                print(f"BacktestEngine: Fetched {len(candles)} candles for {symbol}")

            except Exception as e:
                print(f"BacktestEngine: Error fetching {symbol} from Yahoo: {e}")

        # If Yahoo Finance failed for crypto, try Binance as fallback
        if not historical_data:
            print("BacktestEngine: Yahoo Finance failed, trying Binance fallback...")
            historical_data = self._fetch_from_binance(symbols, period)

        self.historical_data = historical_data
        return historical_data

    def _fetch_from_binance(self, symbols: List[str], period: str) -> Dict[str, List[dict]]:
        """Fallback: Fetch crypto data from Binance API."""
        historical_data = {}

        # Map period to Binance interval and limit
        period_config = {
            '1m': ('1h', 720),      # 30 days of hourly
            '3m': ('4h', 540),      # 90 days of 4-hour
            '6m': ('1d', 180),      # 180 days of daily
            '1y': ('1d', 365),      # 365 days of daily
        }
        interval, limit = period_config.get(period, ('4h', 540))

        binance_symbols = {
            'BTC': 'BTCUSDT',
            'ETH': 'ETHUSDT',
            'SOL': 'SOLUSDT',
            'BNB': 'BNBUSDT'
        }

        for symbol in symbols:
            binance_symbol = binance_symbols.get(symbol)
            if not binance_symbol:
                continue  # Skip non-crypto symbols

            try:
                url = f"https://api.binance.com/api/v3/klines"
                response = requests.get(url, params={
                    'symbol': binance_symbol,
                    'interval': interval,
                    'limit': limit
                }, timeout=10)

                if response.status_code != 200:
                    print(f"BacktestEngine: Binance error for {symbol}: {response.status_code}")
                    continue

                klines = response.json()
                candles = []

                for k in klines:
                    candles.append({
                        'timestamp': int(k[0]),
                        'open': float(k[1]),
                        'high': float(k[2]),
                        'low': float(k[3]),
                        'close': float(k[4]),
                        'volume': float(k[5])
                    })

                historical_data[symbol] = candles
                print(f"BacktestEngine: Fetched {len(candles)} candles for {symbol} from Binance")

            except Exception as e:
                print(f"BacktestEngine: Binance error for {symbol}: {e}")

        return historical_data

    def load_strategy_from_code(self, code: str) -> Optional[Callable]:
        """
        Dynamically load execute_strategy function from code string.

        Args:
            code: Python source code containing execute_strategy function

        Returns:
            The execute_strategy function, or None if loading fails
        """
        try:
            # Create a temporary module
            spec = importlib.util.spec_from_loader("backtest_strategy", loader=None)
            module = importlib.util.module_from_spec(spec)

            # Add numpy to the module's namespace
            module.__dict__['np'] = np
            module.__dict__['numpy'] = np

            # Execute the code in the module's namespace
            exec(code, module.__dict__)

            # Get the execute_strategy function
            if hasattr(module, 'execute_strategy'):
                return module.execute_strategy
            else:
                print("BacktestEngine: No execute_strategy function found in code")
                return None

        except Exception as e:
            print(f"BacktestEngine: Error loading strategy: {e}")
            return None

    def run_backtest(
        self,
        strategy_code: str,
        symbols: List[str] = None,
        period: str = '3m',
        initial_capital: float = 10000.0
    ) -> Dict:
        """
        Run a full backtest of the strategy.

        Args:
            strategy_code: Python code containing execute_strategy function
            symbols: List of symbols to trade (default: all crypto)
            period: Backtest period - '1m', '3m', '6m', '1y'
            initial_capital: Starting cash balance

        Returns:
            Dict with metrics, trades, and equity curve
        """
        # Default to crypto symbols
        if symbols is None:
            symbols = self.CRYPTO_SYMBOLS

        # Load strategy
        strategy_fn = self.load_strategy_from_code(strategy_code)
        if strategy_fn is None:
            return {
                'error': 'Failed to load strategy code',
                'metrics': {},
                'trades': [],
                'equity_curve': []
            }

        # Fetch historical data if not already loaded
        if not self.historical_data or not all(s in self.historical_data for s in symbols):
            self.fetch_historical_data(symbols, period)

        if not self.historical_data:
            return {
                'error': 'Failed to fetch historical data',
                'metrics': {},
                'trades': [],
                'equity_curve': []
            }

        # Find common timestamps across all symbols
        all_timestamps = None
        for symbol in symbols:
            if symbol not in self.historical_data:
                continue
            timestamps = set(c['timestamp'] for c in self.historical_data[symbol])
            if all_timestamps is None:
                all_timestamps = timestamps
            else:
                all_timestamps = all_timestamps.intersection(timestamps)

        if not all_timestamps:
            return {
                'error': 'No overlapping data across symbols',
                'metrics': {},
                'trades': [],
                'equity_curve': []
            }

        sorted_timestamps = sorted(all_timestamps)

        # Build timestamp-indexed data
        indexed_data = {symbol: {} for symbol in symbols}
        for symbol in symbols:
            if symbol not in self.historical_data:
                continue
            for candle in self.historical_data[symbol]:
                indexed_data[symbol][candle['timestamp']] = candle

        # Initialize backtest state
        cash = initial_capital
        portfolio = {s: 0.0 for s in symbols}
        entry_prices = {}
        trades = []
        equity_curve = []
        agent_state = {
            'entry_prices': entry_prices,
            'current_pnl': {},
            'trade_history': [],
            'custom': {}
        }

        # Price history for signals
        price_history = {s: [] for s in symbols}

        # Run through each tick
        for tick_idx, ts in enumerate(sorted_timestamps):
            # Build market_data dict (matching Arena format)
            market_data = {}

            for symbol in symbols:
                if symbol not in indexed_data or ts not in indexed_data[symbol]:
                    continue

                candle = indexed_data[symbol][ts]
                price = candle['close']

                # Update price history
                price_history[symbol].append(price)
                if len(price_history[symbol]) > 100:
                    price_history[symbol] = price_history[symbol][-100:]

                # Calculate simple signals (can't replicate all Arena signals)
                history = price_history[symbol]

                # Simple OBI approximation from price movement
                obi = 0
                if len(history) >= 2:
                    price_change = (history[-1] - history[-2]) / history[-2] if history[-2] != 0 else 0
                    obi = min(1, max(-1, price_change * 100))  # Scale to -1 to 1

                # Parkinson volatility
                parkinson_vol = 0
                if candle['high'] > 0 and candle['low'] > 0:
                    parkinson_vol = np.sqrt(
                        (1 / (4 * np.log(2))) *
                        (np.log(candle['high'] / candle['low']) ** 2)
                    )

                market_data[symbol] = {
                    'price': price,
                    'volume': candle['volume'],
                    'high': candle['high'],
                    'low': candle['low'],
                    'open': candle['open'],
                    'history': list(history),
                    'obi_weighted': obi,
                    'micro_price': price,  # Approximate
                    'sentiment': 0,
                    'ofi': 0,
                    'parkinson_vol': parkinson_vol,
                    'cvd_divergence': 0,
                    'taker_ratio': 0.5,
                    'funding_rate_velocity': 0,
                    'attention': 0,
                    # Stock signals (set to None for crypto)
                    'insider_sentiment': None if symbol in self.CRYPTO_SYMBOLS else 0,
                    'institutional_change': None if symbol in self.CRYPTO_SYMBOLS else 0,
                    'revenue_growth': None,
                    'profit_margin': None,
                    'pe_ratio': None,
                    'data_source': 'backtest'
                }

            if not market_data:
                continue

            # Update agent_state with current PnL
            agent_state['current_pnl'] = {}
            for symbol in symbols:
                qty = portfolio.get(symbol, 0)
                if qty != 0 and symbol in entry_prices and symbol in market_data:
                    entry = entry_prices[symbol]
                    current = market_data[symbol]['price']
                    if qty > 0:  # Long
                        pnl_pct = ((current - entry) / entry) * 100
                    else:  # Short
                        pnl_pct = ((entry - current) / entry) * 100
                    pnl_usd = qty * (current - entry) if qty > 0 else abs(qty) * (entry - current)

                    agent_state['current_pnl'][symbol] = {
                        'pnl_percent': pnl_pct,
                        'pnl_usd': pnl_usd,
                        'entry_price': entry,
                        'current_price': current
                    }

            agent_state['entry_prices'] = entry_prices.copy()

            # Execute strategy
            try:
                result = strategy_fn(
                    market_data,
                    tick_idx,
                    cash,
                    portfolio.copy(),
                    None,  # market_state
                    agent_state
                )

                # Handle result
                if result is None:
                    action, symbol, quantity = "HOLD", None, 0
                elif isinstance(result, tuple) and len(result) >= 3:
                    action, symbol, quantity = result[0], result[1], result[2]
                else:
                    action, symbol, quantity = "HOLD", None, 0

            except Exception as e:
                print(f"BacktestEngine: Strategy error at tick {tick_idx}: {e}")
                action, symbol, quantity = "HOLD", None, 0

            # Execute trade
            if action in ["BUY", "SELL"] and symbol and quantity > 0 and symbol in market_data:
                price = market_data[symbol]['price']

                # Calculate costs
                trade_value = price * quantity
                fee = trade_value * self.FEE_RATE
                slippage = trade_value * self.SLIPPAGE_RATE
                total_cost = fee + slippage

                if action == "BUY":
                    required_cash = trade_value + total_cost
                    if cash >= required_cash:
                        cash -= required_cash
                        portfolio[symbol] = portfolio.get(symbol, 0) + quantity

                        # Track entry price (average if adding to position)
                        if symbol not in entry_prices or portfolio[symbol] == quantity:
                            entry_prices[symbol] = price
                        else:
                            # Average entry
                            old_qty = portfolio[symbol] - quantity
                            entry_prices[symbol] = (
                                (entry_prices[symbol] * old_qty + price * quantity) /
                                portfolio[symbol]
                            )

                        trades.append({
                            'tick': tick_idx,
                            'timestamp': ts,
                            'action': 'BUY',
                            'symbol': symbol,
                            'price': price,
                            'quantity': quantity,
                            'fee': fee,
                            'value': trade_value
                        })

                elif action == "SELL":
                    current_qty = portfolio.get(symbol, 0)
                    sell_qty = min(quantity, abs(current_qty)) if current_qty > 0 else quantity

                    if current_qty > 0:
                        # Closing long position
                        cash += trade_value - total_cost
                        portfolio[symbol] = current_qty - sell_qty

                        # Calculate PnL
                        entry = entry_prices.get(symbol, price)
                        pnl = (price - entry) * sell_qty - total_cost
                        pnl_pct = ((price - entry) / entry * 100) if entry > 0 else 0

                        trades.append({
                            'tick': tick_idx,
                            'timestamp': ts,
                            'action': 'SELL',
                            'symbol': symbol,
                            'price': price,
                            'quantity': sell_qty,
                            'fee': fee,
                            'value': trade_value,
                            'pnl': pnl,
                            'pnl_pct': pnl_pct
                        })

                        if portfolio[symbol] == 0:
                            del entry_prices[symbol]

                    else:
                        # Opening short (simplified - just track as negative)
                        cash += trade_value - total_cost
                        portfolio[symbol] = portfolio.get(symbol, 0) - sell_qty
                        entry_prices[symbol] = price

                        trades.append({
                            'tick': tick_idx,
                            'timestamp': ts,
                            'action': 'SELL',
                            'symbol': symbol,
                            'price': price,
                            'quantity': sell_qty,
                            'fee': fee,
                            'value': trade_value
                        })

            # Calculate equity
            equity = cash
            for sym in symbols:
                qty = portfolio.get(sym, 0)
                if qty != 0 and sym in market_data:
                    equity += qty * market_data[sym]['price']

            equity_curve.append({
                'tick': tick_idx,
                'timestamp': ts,
                'equity': equity,
                'cash': cash
            })

        # Calculate metrics
        metrics = self._calculate_metrics(equity_curve, trades, initial_capital)

        self.results = {
            'metrics': metrics,
            'trades': trades[-50:],  # Last 50 trades
            'equity_curve': equity_curve[::max(1, len(equity_curve)//100)]  # Downsample to ~100 points
        }

        return self.results

    def _calculate_metrics(
        self,
        equity_curve: List[dict],
        trades: List[dict],
        initial_capital: float
    ) -> Dict:
        """Calculate performance metrics from backtest results."""

        if not equity_curve:
            return {
                'total_return': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'win_rate': 0,
                'total_trades': 0,
                'profit_factor': 0,
                'avg_trade_pnl': 0
            }

        # Total return
        final_equity = equity_curve[-1]['equity']
        total_return = ((final_equity - initial_capital) / initial_capital) * 100

        # Sharpe ratio (annualized, assuming hourly data)
        returns = []
        for i in range(1, len(equity_curve)):
            prev_eq = equity_curve[i-1]['equity']
            curr_eq = equity_curve[i]['equity']
            if prev_eq > 0:
                returns.append((curr_eq - prev_eq) / prev_eq)

        if returns:
            returns_arr = np.array(returns)
            mean_return = np.mean(returns_arr)
            std_return = np.std(returns_arr)

            # Annualize (assuming ~24 * 365 hourly observations per year)
            annualization_factor = np.sqrt(24 * 365)
            sharpe_ratio = (mean_return / std_return * annualization_factor) if std_return > 0 else 0
        else:
            sharpe_ratio = 0

        # Max drawdown
        peak = initial_capital
        max_drawdown = 0
        for point in equity_curve:
            if point['equity'] > peak:
                peak = point['equity']
            drawdown = (peak - point['equity']) / peak * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # Win rate and profit factor
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in trades if t.get('pnl', 0) < 0]

        total_trades = len([t for t in trades if 'pnl' in t])  # Only count closed trades
        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0

        gross_profit = sum(t.get('pnl', 0) for t in winning_trades)
        gross_loss = abs(sum(t.get('pnl', 0) for t in losing_trades))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0)

        # Average trade PnL
        all_pnl = [t.get('pnl', 0) for t in trades if 'pnl' in t]
        avg_trade_pnl = np.mean(all_pnl) if all_pnl else 0

        return {
            'total_return': round(total_return, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'max_drawdown': round(max_drawdown, 2),
            'win_rate': round(win_rate, 1),
            'total_trades': len(trades),
            'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else 999.99,
            'avg_trade_pnl': round(avg_trade_pnl, 2)
        }


# Singleton instance
_backtest_engine = None

def get_backtest_engine() -> BacktestEngine:
    """Get the singleton BacktestEngine instance."""
    global _backtest_engine
    if _backtest_engine is None:
        _backtest_engine = BacktestEngine()
    return _backtest_engine
