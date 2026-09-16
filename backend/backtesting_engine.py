"""
Indian Hedge Fund — Backtesting Engine v1.0
Event-driven backtesting for Indian equity strategies (NSE).
Dependencies: numpy, pandas, scipy, yfinance, statsmodels
"""

from __future__ import annotations

import logging
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from itertools import product
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf
from scipy import stats

try:
    from statsmodels.tsa.stattools import coint, adfuller
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RISK_FREE_RATE = 0.065          # 6.5% — Indian 10Y G-Sec proxy
TRADING_DAYS   = 252
BROKERAGE_FEE  = 0.001          # 0.1%
STT_FEE        = 0.001          # 0.1% (delivery)
EXCHANGE_FEE   = 0.0002         # 0.02%
TOTAL_COST     = BROKERAGE_FEE + STT_FEE + EXCHANGE_FEE  # 0.122%


# ─────────────────────────────────────────────────────────────────────────────
# TECHNICAL INDICATOR HELPERS (pure numpy/pandas — no ta library)
# ─────────────────────────────────────────────────────────────────────────────

def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calc_macd(close: pd.Series,
              fast: int = 12, slow: int = 26, signal: int = 9
              ) -> Tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast   = close.ewm(span=fast,   adjust=False).mean()
    ema_slow   = close.ewm(span=slow,   adjust=False).mean()
    macd_line  = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram  = macd_line - signal_line
    return macd_line, signal_line, histogram


def calc_atr(high: pd.Series, low: pd.Series, close: pd.Series,
             period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, min_periods=period).mean()


def calc_bollinger(close: pd.Series, period: int = 20, std_dev: float = 2.0
                   ) -> Tuple[pd.Series, pd.Series, pd.Series]:
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return upper, mid, lower


def calc_donchian(high: pd.Series, low: pd.Series,
                  period: int = 20) -> Tuple[pd.Series, pd.Series]:
    upper = high.rolling(period).max()
    lower = low.rolling(period).min()
    return upper, lower


def calc_momentum(close: pd.Series, lookback: int = 252,
                  skip: int = 21) -> pd.Series:
    """12-1 month momentum (skip last month to avoid short-term reversal)."""
    return close.shift(skip) / close.shift(lookback) - 1


def calc_zscore(series: pd.Series, window: int = 20) -> pd.Series:
    mean = series.rolling(window).mean()
    std  = series.rolling(window).std()
    return (series - mean) / std.replace(0, np.nan)


def calc_ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


# ─────────────────────────────────────────────────────────────────────────────
# DATA HANDLER
# ─────────────────────────────────────────────────────────────────────────────

class DataHandler:
    """Downloads and serves OHLCV data for NSE stocks bar-by-bar."""

    def __init__(self, symbols: List[str], start_date: str, end_date: str):
        self.symbols    = symbols
        self.start_date = start_date
        self.end_date   = end_date
        self.data: Dict[str, pd.DataFrame] = {}
        self._bar_index: int = 0
        self._all_dates: pd.DatetimeIndex = pd.DatetimeIndex([])

        self._download_all()
        self._align_dates()

    # ------------------------------------------------------------------
    def _nse_ticker(self, symbol: str) -> str:
        if symbol.endswith(".NS") or symbol.startswith("^"):
            return symbol
        return f"{symbol}.NS"

    def _download_all(self):
        tickers = [self._nse_ticker(s) for s in self.symbols]
        logger.info("Downloading %d symbols from %s to %s", len(tickers),
                    self.start_date, self.end_date)
        raw = yf.download(
            tickers,
            start=self.start_date,
            end=self.end_date,
            auto_adjust=True,
            progress=False,
            group_by="ticker",
            threads=True,
        )
        for sym, ticker in zip(self.symbols, tickers):
            try:
                if len(tickers) == 1:
                    df = raw.copy()
                else:
                    df = raw[ticker].copy()
                df.dropna(how="all", inplace=True)
                df.columns = [c.lower() for c in df.columns]
                if not df.empty:
                    self.data[sym] = df
                    logger.info("  %s: %d bars", sym, len(df))
                else:
                    logger.warning("  %s: no data returned", sym)
            except Exception as exc:
                logger.warning("  %s: download failed — %s", sym, exc)

    def _align_dates(self):
        if not self.data:
            return
        date_sets = [set(df.index) for df in self.data.values()]
        common = sorted(date_sets[0].intersection(*date_sets[1:]))
        if not common:
            common = sorted(set().union(*date_sets))
        self._all_dates = pd.DatetimeIndex(common)
        for sym in list(self.data.keys()):
            self.data[sym] = self.data[sym].reindex(self._all_dates).ffill().bfill()

    # ------------------------------------------------------------------
    def get_bars(self, symbol: str, lookback: int = 0) -> pd.DataFrame:
        """Return bars up to (and including) the current bar."""
        if symbol not in self.data:
            return pd.DataFrame()
        idx = self._bar_index + 1
        df  = self.data[symbol].iloc[:idx]
        if lookback > 0:
            df = df.iloc[-lookback:]
        return df

    def get_latest_bar(self, symbol: str) -> dict:
        if symbol not in self.data or self._bar_index >= len(self._all_dates):
            return {}
        row = self.data[symbol].iloc[self._bar_index]
        return {
            "date":   self._all_dates[self._bar_index],
            "open":   float(row.get("open", np.nan)),
            "high":   float(row.get("high", np.nan)),
            "low":    float(row.get("low",  np.nan)),
            "close":  float(row.get("close", np.nan)),
            "volume": float(row.get("volume", 0)),
        }

    def update_bar(self):
        self._bar_index += 1

    @property
    def current_date(self) -> Optional[pd.Timestamp]:
        if self._bar_index < len(self._all_dates):
            return self._all_dates[self._bar_index]
        return None

    @property
    def is_finished(self) -> bool:
        return self._bar_index >= len(self._all_dates)

    @property
    def total_bars(self) -> int:
        return len(self._all_dates)


# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Trade:
    symbol:    str
    action:    str          # "BUY" | "SELL"
    quantity:  int
    price:     float
    date:      pd.Timestamp
    cost:      float        # transaction cost
    pnl:       float = 0.0  # filled on close

class Portfolio:
    """Tracks cash, holdings, equity curve, and trade log."""

    def __init__(self, initial_capital: float = 1_000_000.0):
        self.initial_capital = initial_capital
        self.cash             = initial_capital
        self.holdings: Dict[str, Dict[str, Any]] = {}  # sym → {qty, avg_price, cost_basis}
        self.trades:   List[Trade] = []
        self.equity_curve: List[Tuple[pd.Timestamp, float]] = []

    # ------------------------------------------------------------------
    def apply_transaction_costs(self, value: float) -> float:
        return value * TOTAL_COST

    def can_buy(self, symbol: str, quantity: int, price: float) -> bool:
        total = quantity * price
        cost  = self.apply_transaction_costs(total)
        return self.cash >= total + cost

    def update_holdings(self, symbol: str, quantity: int,
                        price: float, action: str,
                        date: Optional[pd.Timestamp] = None):
        if date is None:
            date = pd.Timestamp.now()
        trade_value = quantity * price
        cost        = self.apply_transaction_costs(trade_value)

        if action.upper() == "BUY":
            if not self.can_buy(symbol, quantity, price):
                logger.warning("Insufficient cash for %s BUY %d @ %.2f", symbol, quantity, price)
                return
            self.cash -= (trade_value + cost)
            if symbol not in self.holdings:
                self.holdings[symbol] = {"quantity": 0, "avg_price": 0.0, "cost_basis": 0.0}
            h = self.holdings[symbol]
            total_qty   = h["quantity"] + quantity
            h["cost_basis"] = h["cost_basis"] + trade_value + cost
            h["avg_price"]  = h["cost_basis"] / total_qty if total_qty else 0.0
            h["quantity"]   = total_qty
            self.trades.append(Trade(symbol, "BUY", quantity, price, date, cost))

        elif action.upper() == "SELL":
            if symbol not in self.holdings or self.holdings[symbol]["quantity"] < quantity:
                logger.warning("Cannot SELL %d of %s — insufficient position", quantity, symbol)
                return
            h = self.holdings[symbol]
            avg_cost  = h["avg_price"]
            pnl       = (price - avg_cost) * quantity - cost
            self.cash += (trade_value - cost)
            h["quantity"] -= quantity
            h["cost_basis"] = h["avg_price"] * h["quantity"]
            if h["quantity"] == 0:
                del self.holdings[symbol]
            self.trades.append(Trade(symbol, "SELL", quantity, price, date, cost, pnl))

    def calculate_equity(self, prices: Dict[str, float]) -> float:
        equity = self.cash
        for sym, h in self.holdings.items():
            px = prices.get(sym, h.get("avg_price", 0.0))
            equity += h["quantity"] * px
        return equity

    def get_position(self, symbol: str) -> dict:
        return self.holdings.get(symbol, {"quantity": 0, "avg_price": 0.0, "cost_basis": 0.0})

    def record_equity(self, date: pd.Timestamp, prices: Dict[str, float]):
        equity = self.calculate_equity(prices)
        self.equity_curve.append((date, equity))

    def equity_series(self) -> pd.Series:
        if not self.equity_curve:
            return pd.Series(dtype=float)
        dates, values = zip(*self.equity_curve)
        return pd.Series(values, index=pd.DatetimeIndex(dates), name="equity")


# ─────────────────────────────────────────────────────────────────────────────
# STRATEGY BASE
# ─────────────────────────────────────────────────────────────────────────────

class Strategy(ABC):
    """Abstract base class for all trading strategies."""

    def __init__(self, symbols: List[str], **params):
        self.symbols = symbols
        self.params  = params

    @abstractmethod
    def generate_signals(self, data_handler: DataHandler,
                         portfolio: Portfolio) -> Dict[str, str]:
        """Return dict of symbol → 'BUY'/'SELL'/'HOLD'."""
        ...

    def _get_close(self, data_handler: DataHandler,
                   symbol: str, lookback: int = 300) -> pd.Series:
        bars = data_handler.get_bars(symbol, lookback=lookback)
        if bars.empty or "close" not in bars.columns:
            return pd.Series(dtype=float)
        return bars["close"].dropna()


# ─────────────────────────────────────────────────────────────────────────────
# STRATEGY 1 — DUAL MOMENTUM
# ─────────────────────────────────────────────────────────────────────────────

class MomentumStrategy(Strategy):
    """
    Dual Momentum (Gary Antonacci style) adapted for Indian equities.
    - 12-1 month relative momentum across universe
    - Absolute momentum filter: beats risk-free rate
    - Monthly rebalancing, equal-weight top-N stocks
    """

    def __init__(self, symbols: List[str], top_n: int = 5,
                 lookback: int = 252, skip: int = 21, **params):
        super().__init__(symbols, **params)
        self.top_n      = top_n
        self.lookback   = lookback
        self.skip       = skip
        self._last_rebal: Optional[pd.Timestamp] = None
        self._signals: Dict[str, str] = {s: "HOLD" for s in symbols}

    def generate_signals(self, data_handler: DataHandler,
                         portfolio: Portfolio) -> Dict[str, str]:
        current = data_handler.current_date
        if current is None:
            return self._signals

        # Monthly rebalancing
        if (self._last_rebal is not None and
                current.month == self._last_rebal.month and
                current.year  == self._last_rebal.year):
            return self._signals

        moms: Dict[str, float] = {}
        for sym in self.symbols:
            close = self._get_close(data_handler, sym, self.lookback + self.skip + 10)
            if len(close) < self.lookback + self.skip:
                continue
            ret = close.iloc[-self.skip] / close.iloc[-(self.lookback)] - 1
            moms[sym] = ret

        if not moms:
            return self._signals

        # Absolute momentum: must beat annualised risk-free (approx 6.5%)
        monthly_rf = (1 + RISK_FREE_RATE) ** (1 / 12) - 1
        qualified  = {s: m for s, m in moms.items() if m > monthly_rf}

        # Relative momentum: rank and pick top-N
        ranked = sorted(qualified, key=lambda s: qualified[s], reverse=True)
        top    = set(ranked[:self.top_n])

        signals: Dict[str, str] = {}
        for sym in self.symbols:
            pos = portfolio.get_position(sym)
            if sym in top:
                signals[sym] = "BUY"
            elif pos["quantity"] > 0:
                signals[sym] = "SELL"
            else:
                signals[sym] = "HOLD"

        self._signals      = signals
        self._last_rebal   = current
        return signals


# ─────────────────────────────────────────────────────────────────────────────
# STRATEGY 2 — MEAN REVERSION
# ─────────────────────────────────────────────────────────────────────────────

class MeanReversionStrategy(Strategy):
    """
    Statistical mean reversion using z-score + Bollinger + RSI filter.
    - Buy z-score < -2, confirmed by BB lower touch and RSI < 40
    - Sell when z-score > 2 or RSI > 70
    """

    def __init__(self, symbols: List[str],
                 z_window: int = 20, z_buy: float = -2.0, z_sell: float = 2.0,
                 rsi_period: int = 14, rsi_buy: float = 40, **params):
        super().__init__(symbols, **params)
        self.z_window  = z_window
        self.z_buy     = z_buy
        self.z_sell    = z_sell
        self.rsi_period = rsi_period
        self.rsi_buy   = rsi_buy

    def generate_signals(self, data_handler: DataHandler,
                         portfolio: Portfolio) -> Dict[str, str]:
        signals: Dict[str, str] = {}
        for sym in self.symbols:
            close = self._get_close(data_handler, sym, lookback=100)
            if len(close) < self.z_window + self.rsi_period + 5:
                signals[sym] = "HOLD"
                continue

            z   = calc_zscore(close, self.z_window).iloc[-1]
            rsi = calc_rsi(close, self.rsi_period).iloc[-1]
            _, _, bb_lower = calc_bollinger(close, self.z_window)
            price = close.iloc[-1]
            pos   = portfolio.get_position(sym)

            if z < self.z_buy and rsi < self.rsi_buy and price <= bb_lower.iloc[-1] * 1.01:
                signals[sym] = "BUY"
            elif pos["quantity"] > 0 and (z > self.z_sell or rsi > 70):
                signals[sym] = "SELL"
            else:
                signals[sym] = "HOLD"
        return signals


# ─────────────────────────────────────────────────────────────────────────────
# STRATEGY 3 — TREND FOLLOWING (TURTLE)
# ─────────────────────────────────────────────────────────────────────────────

class TrendFollowingStrategy(Strategy):
    """
    Turtle Trading System adapted for NSE:
    - Entry: 20-day Donchian channel breakout
    - Exit:  10-day Donchian channel
    - ATR-based position sizing (1% risk per trade)
    - Trailing stop: 2x ATR from entry high
    """

    def __init__(self, symbols: List[str],
                 entry_period: int = 20, exit_period: int = 10,
                 atr_period: int = 14, risk_pct: float = 0.01,
                 atr_multiplier: float = 2.0, **params):
        super().__init__(symbols, **params)
        self.entry_period    = entry_period
        self.exit_period     = exit_period
        self.atr_period      = atr_period
        self.risk_pct        = risk_pct
        self.atr_multiplier  = atr_multiplier
        self._entry_prices: Dict[str, float] = {}
        self._highest_high:  Dict[str, float] = {}

    def generate_signals(self, data_handler: DataHandler,
                         portfolio: Portfolio) -> Dict[str, str]:
        signals: Dict[str, str] = {}
        for sym in self.symbols:
            bars = data_handler.get_bars(sym, lookback=self.entry_period + self.atr_period + 5)
            if bars.empty or len(bars) < self.entry_period + 2:
                signals[sym] = "HOLD"
                continue

            high  = bars["high"]
            low   = bars["low"]
            close = bars["close"]

            dc_upper_entry, dc_lower_entry = calc_donchian(high, low, self.entry_period)
            dc_upper_exit,  dc_lower_exit  = calc_donchian(high, low, self.exit_period)
            atr   = calc_atr(high, low, close, self.atr_period)

            current_close = close.iloc[-1]
            dc_hi_entry   = dc_upper_entry.iloc[-2]   # previous bar breakout
            dc_lo_exit    = dc_lower_exit.iloc[-2]
            current_atr   = atr.iloc[-1]

            pos = portfolio.get_position(sym)

            if pos["quantity"] == 0:
                # Entry: close breaks above 20-day high
                if current_close > dc_hi_entry:
                    signals[sym] = "BUY"
                    self._entry_prices[sym] = current_close
                    self._highest_high[sym] = current_close
                else:
                    signals[sym] = "HOLD"
            else:
                # Update trailing stop
                self._highest_high[sym] = max(
                    self._highest_high.get(sym, current_close),
                    current_close
                )
                trailing_stop = self._highest_high[sym] - self.atr_multiplier * current_atr
                # Exit: 10-day low OR trailing stop hit
                if current_close < dc_lo_exit or current_close < trailing_stop:
                    signals[sym] = "SELL"
                    self._entry_prices.pop(sym, None)
                    self._highest_high.pop(sym, None)
                else:
                    signals[sym] = "HOLD"

        return signals


# ─────────────────────────────────────────────────────────────────────────────
# STRATEGY 4 — PAIRS TRADING
# ─────────────────────────────────────────────────────────────────────────────

class PairsTrading(Strategy):
    """
    Statistical pairs trading using Engle-Granger cointegration.
    Trades a list of pairs: [(sym1, sym2), ...]
    - OLS regression for hedge ratio
    - Trade when spread z-score > ±2.0
    - Half-life mean reversion for position duration
    """

    def __init__(self, symbols: List[str], pairs: Optional[List[Tuple[str, str]]] = None,
                 z_entry: float = 2.0, z_exit: float = 0.5,
                 lookback: int = 60, z_window: int = 20, **params):
        super().__init__(symbols, **params)
        self.pairs    = pairs or self._make_pairs(symbols)
        self.z_entry  = z_entry
        self.z_exit   = z_exit
        self.lookback = lookback
        self.z_window = z_window
        self._pair_state: Dict[Tuple[str, str], str] = {}  # "long_s1", "short_s1", "flat"

    @staticmethod
    def _make_pairs(symbols: List[str]) -> List[Tuple[str, str]]:
        """Return all unique symbol pairs."""
        pairs = []
        for i, s1 in enumerate(symbols):
            for s2 in symbols[i + 1:]:
                pairs.append((s1, s2))
        return pairs

    def _compute_spread(self, close1: pd.Series, close2: pd.Series
                        ) -> Tuple[pd.Series, float]:
        """OLS hedge ratio and spread."""
        n     = min(len(close1), len(close2))
        y     = close1.iloc[-n:].values
        x     = close2.iloc[-n:].values
        beta, alpha = np.polyfit(x, y, 1)
        spread = pd.Series(y - beta * x - alpha, index=close1.index[-n:])
        return spread, beta

    def _half_life(self, spread: pd.Series) -> float:
        """Ornstein-Uhlenbeck half-life of mean reversion."""
        lag    = spread.shift(1).dropna()
        delta  = spread.diff().dropna()
        n      = min(len(lag), len(delta))
        beta   = np.polyfit(lag.values[-n:], delta.values[-n:], 1)[0]
        if beta >= 0:
            return np.inf
        return -np.log(2) / beta

    def generate_signals(self, data_handler: DataHandler,
                         portfolio: Portfolio) -> Dict[str, str]:
        signals = {sym: "HOLD" for sym in self.symbols}

        for pair in self.pairs:
            s1, s2 = pair
            if s1 not in data_handler.data or s2 not in data_handler.data:
                continue

            c1 = self._get_close(data_handler, s1, self.lookback + self.z_window + 5)
            c2 = self._get_close(data_handler, s2, self.lookback + self.z_window + 5)
            if len(c1) < self.lookback or len(c2) < self.lookback:
                continue

            spread, hedge = self._compute_spread(c1, c2)
            z_series      = calc_zscore(spread, self.z_window)
            if z_series.empty or z_series.isna().iloc[-1]:
                continue
            z = z_series.iloc[-1]

            state = self._pair_state.get(pair, "flat")
            p1    = portfolio.get_position(s1)
            p2    = portfolio.get_position(s2)

            if state == "flat":
                if z > self.z_entry:
                    # Short s1, long s2
                    signals[s1] = "SELL"
                    signals[s2] = "BUY"
                    self._pair_state[pair] = "short_s1"
                elif z < -self.z_entry:
                    # Long s1, short s2
                    signals[s1] = "BUY"
                    signals[s2] = "SELL"
                    self._pair_state[pair] = "long_s1"

            elif state == "short_s1":
                if abs(z) < self.z_exit:
                    # Unwind
                    if p1["quantity"] > 0:
                        signals[s1] = "SELL"
                    if p2["quantity"] > 0:
                        signals[s2] = "SELL"
                    self._pair_state[pair] = "flat"

            elif state == "long_s1":
                if abs(z) < self.z_exit:
                    if p1["quantity"] > 0:
                        signals[s1] = "SELL"
                    if p2["quantity"] > 0:
                        signals[s2] = "SELL"
                    self._pair_state[pair] = "flat"

        return signals


# ─────────────────────────────────────────────────────────────────────────────
# STRATEGY 5 — MULTI-FACTOR
# ─────────────────────────────────────────────────────────────────────────────

class FactorStrategy(Strategy):
    """
    Multi-factor strategy: value + momentum + quality + low-vol.
    Uses price-based proxies for value/quality since we won't have
    real-time fundamental data. Monthly rebalancing.
    - Momentum: 12-1 month return
    - Low-vol:  1Y realized volatility (lower is better)
    - Mean-reversion proxy: 1M z-score (lower score → potential value)
    - Trend proxy: price vs 200-day MA
    """

    def __init__(self, symbols: List[str], top_pct: float = 0.25,
                 lookback_mom: int = 252, lookback_vol: int = 252, **params):
        super().__init__(symbols, **params)
        self.top_pct      = top_pct
        self.lookback_mom = lookback_mom
        self.lookback_vol = lookback_vol
        self._last_rebal: Optional[pd.Timestamp] = None
        self._signals: Dict[str, str] = {s: "HOLD" for s in symbols}

    def _compute_scores(self, data_handler: DataHandler) -> Dict[str, float]:
        scores: Dict[str, float] = {}
        raw: Dict[str, Dict[str, float]] = {}

        for sym in self.symbols:
            close = self._get_close(data_handler, sym,
                                    self.lookback_mom + 30)
            if len(close) < self.lookback_mom:
                continue

            # Factor 1: Momentum (12-1 month)
            mom = close.iloc[-21] / close.iloc[-self.lookback_mom] - 1

            # Factor 2: Low volatility (negative — low vol = good)
            ret_1y = close.iloc[-self.lookback_vol:].pct_change().dropna()
            vol    = ret_1y.std() * np.sqrt(TRADING_DAYS)

            # Factor 3: Trend (price vs 200d MA)
            ma200  = close.rolling(200).mean().iloc[-1]
            trend  = (close.iloc[-1] / ma200 - 1) if ma200 > 0 else 0.0

            # Factor 4: Short-term reversion signal (z-score, inverted)
            z = calc_zscore(close, 20).iloc[-1]

            raw[sym] = {"momentum": mom, "low_vol": -vol,
                         "trend": trend, "reversion": -z}

        if not raw:
            return scores

        # Z-score each factor cross-sectionally, then sum
        factor_names = ["momentum", "low_vol", "trend", "reversion"]
        factor_vals: Dict[str, List[float]] = {f: [] for f in factor_names}
        sym_order = list(raw.keys())

        for sym in sym_order:
            for f in factor_names:
                factor_vals[f].append(raw[sym][f])

        factor_z: Dict[str, np.ndarray] = {}
        for f in factor_names:
            arr  = np.array(factor_vals[f], dtype=float)
            std  = arr.std()
            mean = arr.mean()
            factor_z[f] = (arr - mean) / std if std > 0 else np.zeros_like(arr)

        weights = {"momentum": 0.35, "low_vol": 0.25, "trend": 0.25, "reversion": 0.15}
        for i, sym in enumerate(sym_order):
            composite = sum(weights[f] * factor_z[f][i] for f in factor_names)
            scores[sym] = composite

        return scores

    def generate_signals(self, data_handler: DataHandler,
                         portfolio: Portfolio) -> Dict[str, str]:
        current = data_handler.current_date
        if current is None:
            return self._signals

        if (self._last_rebal is not None and
                current.month == self._last_rebal.month and
                current.year  == self._last_rebal.year):
            return self._signals

        scores = self._compute_scores(data_handler)
        if not scores:
            return self._signals

        n_top    = max(1, int(len(scores) * self.top_pct))
        ranked   = sorted(scores, key=lambda s: scores[s], reverse=True)
        top      = set(ranked[:n_top])

        signals: Dict[str, str] = {}
        for sym in self.symbols:
            pos = portfolio.get_position(sym)
            if sym in top:
                signals[sym] = "BUY"
            elif pos["quantity"] > 0:
                signals[sym] = "SELL"
            else:
                signals[sym] = "HOLD"

        self._signals    = signals
        self._last_rebal = current
        return signals


# ─────────────────────────────────────────────────────────────────────────────
# STRATEGY 6 — RSI + MACD
# ─────────────────────────────────────────────────────────────────────────────

class RSI_MACDStrategy(Strategy):
    """
    Classic technical: RSI oversold + MACD bullish cross → BUY
    RSI overbought + MACD bearish cross → SELL
    Fixed stop-loss 5%, target 15%
    """

    def __init__(self, symbols: List[str],
                 rsi_period: int = 14, rsi_buy: float = 30, rsi_sell: float = 70,
                 macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9,
                 stop_loss: float = 0.05, target: float = 0.15, **params):
        super().__init__(symbols, **params)
        self.rsi_period  = rsi_period
        self.rsi_buy     = rsi_buy
        self.rsi_sell    = rsi_sell
        self.macd_fast   = macd_fast
        self.macd_slow   = macd_slow
        self.macd_signal = macd_signal
        self.stop_loss   = stop_loss
        self.target      = target
        self._entry_prices: Dict[str, float] = {}

    def generate_signals(self, data_handler: DataHandler,
                         portfolio: Portfolio) -> Dict[str, str]:
        signals: Dict[str, str] = {}
        for sym in self.symbols:
            close = self._get_close(data_handler, sym, lookback=100)
            if len(close) < self.macd_slow + self.macd_signal + 5:
                signals[sym] = "HOLD"
                continue

            rsi  = calc_rsi(close, self.rsi_period)
            macd_line, signal_line, _ = calc_macd(
                close, self.macd_fast, self.macd_slow, self.macd_signal)

            rsi_now  = rsi.iloc[-1]
            rsi_prev = rsi.iloc[-2]
            macd_now  = macd_line.iloc[-1]
            macd_prev = macd_line.iloc[-2]
            sig_now   = signal_line.iloc[-1]
            sig_prev  = signal_line.iloc[-2]
            price     = close.iloc[-1]
            pos       = portfolio.get_position(sym)

            # MACD crossover detection
            bullish_cross = (macd_prev < sig_prev) and (macd_now > sig_now)
            bearish_cross = (macd_prev > sig_prev) and (macd_now < sig_now)

            if pos["quantity"] == 0:
                if rsi_now < self.rsi_buy and bullish_cross:
                    signals[sym] = "BUY"
                    self._entry_prices[sym] = price
                else:
                    signals[sym] = "HOLD"
            else:
                entry = self._entry_prices.get(sym, pos.get("avg_price", price))
                stop  = entry * (1 - self.stop_loss)
                tgt   = entry * (1 + self.target)
                if price <= stop or price >= tgt or (rsi_now > self.rsi_sell and bearish_cross):
                    signals[sym] = "SELL"
                    self._entry_prices.pop(sym, None)
                else:
                    signals[sym] = "HOLD"

        return signals


# ─────────────────────────────────────────────────────────────────────────────
# BACKTEST ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class BacktestEngine:
    """Connects DataHandler, Strategy, and Portfolio into an event loop."""

    def __init__(self, strategy: Strategy, data_handler: DataHandler,
                 portfolio: Portfolio):
        self.strategy      = strategy
        self.data_handler  = data_handler
        self.portfolio     = portfolio

    def run(self) -> dict:
        logger.info("Starting backtest — %d bars", self.data_handler.total_bars)

        # Need warm-up period
        warmup = 270
        for _ in range(min(warmup, self.data_handler.total_bars - 1)):
            self.data_handler.update_bar()

        bar_count = 0
        while not self.data_handler.is_finished:
            current_date = self.data_handler.current_date
            prices = {sym: self.data_handler.get_latest_bar(sym).get("close", 0.0)
                      for sym in self.data_handler.symbols}

            signals = self._generate_signals()
            self._execute_orders(signals, current_date, prices)
            self.portfolio.record_equity(current_date, prices)
            self.data_handler.update_bar()
            bar_count += 1

        logger.info("Backtest complete — %d trading bars processed", bar_count)

        equity   = self.portfolio.equity_series()
        trades   = self.portfolio.trades
        return {
            "equity_curve": equity,
            "trades":       trades,
            "final_equity": equity.iloc[-1] if not equity.empty else self.portfolio.initial_capital,
            "cash":         self.portfolio.cash,
            "holdings":     dict(self.portfolio.holdings),
        }

    def _generate_signals(self) -> Dict[str, str]:
        try:
            return self.strategy.generate_signals(self.data_handler, self.portfolio)
        except Exception as exc:
            logger.error("Signal generation error: %s", exc)
            return {}

    def _execute_orders(self, signals: Dict[str, str],
                        date: pd.Timestamp, prices: Dict[str, float]):
        for sym, signal in signals.items():
            price = prices.get(sym, 0.0)
            if price <= 0:
                continue

            pos = self.portfolio.get_position(sym)

            if signal == "BUY" and pos["quantity"] == 0:
                # Size: allocate up to 10% of portfolio equity per position
                equity   = self.portfolio.calculate_equity(prices)
                alloc    = min(equity * 0.10, self.portfolio.cash * 0.95)
                quantity = int(alloc / price)
                if quantity > 0:
                    self.portfolio.update_holdings(sym, quantity, price, "BUY", date)

            elif signal == "SELL" and pos["quantity"] > 0:
                self.portfolio.update_holdings(sym, pos["quantity"], price, "SELL", date)


# ─────────────────────────────────────────────────────────────────────────────
# PERFORMANCE ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────

class PerformanceAnalytics:
    """Comprehensive performance metrics for backtested strategies."""

    def calculate_metrics(self,
                          equity_curve: pd.Series,
                          trades: List[Trade],
                          benchmark: Optional[pd.Series] = None) -> dict:
        if equity_curve.empty or len(equity_curve) < 2:
            return {"error": "Insufficient equity curve data"}

        equity_curve = equity_curve.sort_index().dropna()
        daily_returns = equity_curve.pct_change().dropna()

        initial = equity_curve.iloc[0]
        final   = equity_curve.iloc[-1]
        n_years = len(equity_curve) / TRADING_DAYS

        total_return = (final / initial - 1) * 100
        cagr = ((final / initial) ** (1 / max(n_years, 0.01)) - 1) * 100 if n_years > 0 else 0.0

        vol_annual = daily_returns.std() * np.sqrt(TRADING_DAYS) * 100

        # Drawdown
        rolling_max = equity_curve.cummax()
        drawdown    = (equity_curve - rolling_max) / rolling_max
        max_dd      = drawdown.min() * 100

        # Drawdown duration
        in_dd    = drawdown < 0
        dd_dur   = 0
        current_dur = 0
        for v in in_dd:
            if v:
                current_dur += 1
                dd_dur = max(dd_dur, current_dur)
            else:
                current_dur = 0

        # Risk-adjusted
        excess = daily_returns - RISK_FREE_RATE / TRADING_DAYS
        sharpe = (excess.mean() / daily_returns.std() * np.sqrt(TRADING_DAYS)
                  if daily_returns.std() > 0 else 0.0)

        downside = daily_returns[daily_returns < 0].std()
        sortino  = (excess.mean() / downside * np.sqrt(TRADING_DAYS)
                    if downside > 0 else 0.0)

        calmar   = (cagr / abs(max_dd)) if max_dd != 0 else 0.0

        # Trade statistics
        trade_stats = self._trade_statistics(trades)

        # Monthly returns
        monthly_returns = self.calculate_monthly_returns(equity_curve)

        # Benchmark metrics
        bench_metrics: dict = {}
        if benchmark is not None and not benchmark.empty:
            bench_metrics = self._benchmark_metrics(daily_returns, benchmark)

        # Rolling metrics
        roll = self.calculate_rolling_metrics(equity_curve)

        # Top 5 drawdowns
        top_dds = self._top_drawdowns(equity_curve, n=5)

        return {
            "returns": {
                "total_return_pct":  round(total_return, 2),
                "cagr_pct":          round(cagr, 2),
                "monthly_returns":   monthly_returns.to_dict() if not monthly_returns.empty else {},
            },
            "risk": {
                "annualized_vol_pct":       round(vol_annual, 2),
                "max_drawdown_pct":         round(max_dd, 2),
                "max_drawdown_duration_days": int(dd_dur),
                "calmar_ratio":             round(calmar, 3),
            },
            "risk_adjusted": {
                "sharpe_ratio":   round(sharpe, 3),
                "sortino_ratio":  round(sortino, 3),
                "information_ratio": round(bench_metrics.get("information_ratio", 0.0), 3),
            },
            "trade_statistics": trade_stats,
            "rolling_metrics":  roll,
            "benchmark":        bench_metrics,
            "drawdown_analysis": top_dds,
        }

    # ------------------------------------------------------------------
    def _trade_statistics(self, trades: List[Trade]) -> dict:
        sells = [t for t in trades if t.action == "SELL"]
        if not sells:
            return {
                "total_trades": 0, "win_rate_pct": 0.0,
                "avg_win_pct": 0.0, "avg_loss_pct": 0.0,
                "profit_factor": 0.0, "avg_holding_days": 0,
            }

        pnls     = [t.pnl for t in sells]
        winners  = [p for p in pnls if p > 0]
        losers   = [p for p in pnls if p <= 0]

        win_rate   = len(winners) / len(pnls) * 100
        avg_win    = np.mean(winners) if winners else 0.0
        avg_loss   = np.mean(losers)  if losers  else 0.0
        gross_win  = sum(winners)
        gross_loss = abs(sum(losers))
        pf         = gross_win / gross_loss if gross_loss > 0 else np.inf

        # Average holding days (approx: match buys to sells by symbol)
        buys_by_sym: Dict[str, List[Trade]] = {}
        for t in trades:
            if t.action == "BUY":
                buys_by_sym.setdefault(t.symbol, []).append(t)

        holding_days: List[int] = []
        for t in sells:
            buys = buys_by_sym.get(t.symbol, [])
            if buys:
                buy_t = buys.pop(0)
                delta = (t.date - buy_t.date).days
                holding_days.append(delta)

        avg_hold = int(np.mean(holding_days)) if holding_days else 0

        return {
            "total_trades":      len(sells),
            "win_rate_pct":      round(win_rate, 2),
            "avg_win_inr":       round(avg_win, 2),
            "avg_loss_inr":      round(avg_loss, 2),
            "profit_factor":     round(pf, 3) if pf != np.inf else 999.0,
            "avg_holding_days":  avg_hold,
            "total_pnl_inr":     round(sum(pnls), 2),
        }

    def _benchmark_metrics(self, strategy_returns: pd.Series,
                           benchmark_prices: pd.Series) -> dict:
        bench_ret = benchmark_prices.pct_change().dropna()
        # Align
        idx       = strategy_returns.index.intersection(bench_ret.index)
        if len(idx) < 10:
            return {}
        s = strategy_returns.reindex(idx).dropna()
        b = bench_ret.reindex(idx).dropna()
        idx = s.index.intersection(b.index)
        s, b = s.reindex(idx), b.reindex(idx)

        slope, intercept, r, _, _ = stats.linregress(b.values, s.values)
        beta    = slope
        alpha   = intercept * TRADING_DAYS * 100   # annualised %
        r2      = r ** 2
        te      = (s - b).std() * np.sqrt(TRADING_DAYS) * 100
        ir      = ((s - b).mean() / (s - b).std() * np.sqrt(TRADING_DAYS)
                   if (s - b).std() > 0 else 0.0)

        return {
            "alpha_pct":        round(alpha, 2),
            "beta":             round(beta, 3),
            "r_squared":        round(r2, 3),
            "tracking_error_pct": round(te, 2),
            "information_ratio": round(ir, 3),
        }

    # ------------------------------------------------------------------
    def calculate_monthly_returns(self, equity_curve: pd.Series) -> pd.DataFrame:
        if equity_curve.empty:
            return pd.DataFrame()
        monthly_eq = equity_curve.resample("ME").last()
        monthly_ret = monthly_eq.pct_change().dropna() * 100
        df = pd.DataFrame({
            "year":  monthly_ret.index.year,
            "month": monthly_ret.index.month,
            "ret":   monthly_ret.values,
        })
        if df.empty:
            return pd.DataFrame()
        table = df.pivot(index="year", columns="month", values="ret")
        table.columns = ["Jan","Feb","Mar","Apr","May","Jun",
                         "Jul","Aug","Sep","Oct","Nov","Dec"][:len(table.columns)]
        # Add annual column
        annual_eq  = equity_curve.resample("YE").last()
        annual_ret = annual_eq.pct_change().dropna() * 100
        ann_dict   = {y: r for y, r in zip(annual_ret.index.year, annual_ret.values)}
        table["Annual"] = table.index.map(lambda y: ann_dict.get(y, np.nan))
        return table.round(2)

    def calculate_rolling_metrics(self, equity_curve: pd.Series,
                                  window: int = 252) -> dict:
        if len(equity_curve) < window + 2:
            return {}
        dr   = equity_curve.pct_change().dropna()
        rf_d = RISK_FREE_RATE / TRADING_DAYS

        roll_ret    = dr.rolling(window).mean() * TRADING_DAYS * 100
        roll_vol    = dr.rolling(window).std()  * np.sqrt(TRADING_DAYS) * 100
        excess      = dr - rf_d
        roll_sharpe = (excess.rolling(window).mean() /
                       dr.rolling(window).std() * np.sqrt(TRADING_DAYS))

        return {
            "rolling_12m_return":  roll_ret.dropna().round(2).to_dict(),
            "rolling_12m_vol":     roll_vol.dropna().round(2).to_dict(),
            "rolling_12m_sharpe":  roll_sharpe.dropna().round(3).to_dict(),
        }

    def plot_equity_curve_data(self, equity_curve: pd.Series) -> list:
        if equity_curve.empty:
            return []
        normalised = equity_curve / equity_curve.iloc[0] * 100
        drawdown   = ((equity_curve - equity_curve.cummax()) /
                       equity_curve.cummax() * 100)
        result = []
        for date, eq, norm, dd in zip(equity_curve.index,
                                       equity_curve.values,
                                       normalised.values,
                                       drawdown.values):
            result.append({
                "date":        date.strftime("%Y-%m-%d"),
                "equity":      round(float(eq), 2),
                "normalised":  round(float(norm), 2),
                "drawdown_pct": round(float(dd), 2),
            })
        return result

    def _top_drawdowns(self, equity_curve: pd.Series, n: int = 5) -> list:
        """Find top-N drawdown periods."""
        rolling_max = equity_curve.cummax()
        drawdown    = (equity_curve - rolling_max) / rolling_max

        results = []
        visited  = set()
        temp     = drawdown.copy()

        for _ in range(n):
            if temp.empty:
                break
            trough_date = temp.idxmin()
            trough_val  = temp[trough_date]
            if trough_val >= 0 or trough_date in visited:
                break
            visited.add(trough_date)

            # Find start (peak before trough)
            pre_trough = equity_curve[:trough_date]
            peak_date  = pre_trough.idxmax()

            # Find recovery (equity returns to peak level after trough)
            peak_val     = equity_curve[peak_date]
            post_trough  = equity_curve[trough_date:]
            recovered    = post_trough[post_trough >= peak_val]
            recovery_date = recovered.index[0] if not recovered.empty else None

            duration = (trough_date - peak_date).days
            recovery_days = ((recovery_date - trough_date).days
                             if recovery_date else None)

            results.append({
                "peak_date":      peak_date.strftime("%Y-%m-%d"),
                "trough_date":    trough_date.strftime("%Y-%m-%d"),
                "recovery_date":  recovery_date.strftime("%Y-%m-%d") if recovery_date else "Ongoing",
                "drawdown_pct":   round(trough_val * 100, 2),
                "duration_days":  duration,
                "recovery_days":  recovery_days,
            })

            # Zero out this drawdown period and continue
            mask = (temp.index >= peak_date) & (temp.index <= (recovery_date or temp.index[-1]))
            temp = temp[~mask]

        return results


# ─────────────────────────────────────────────────────────────────────────────
# BACKTEST ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────

STRATEGY_REGISTRY = {
    "momentum":       MomentumStrategy,
    "mean_reversion": MeanReversionStrategy,
    "trend":          TrendFollowingStrategy,
    "pairs":          PairsTrading,
    "factor":         FactorStrategy,
    "rsi_macd":       RSI_MACDStrategy,
}


class BacktestOrchestrator:
    """High-level API for running, comparing, and optimising strategies."""

    def __init__(self):
        self.analytics = PerformanceAnalytics()

    # ------------------------------------------------------------------
    def run_strategy(self,
                     strategy_name: str,
                     symbols: List[str],
                     start_date: str,
                     end_date:   str,
                     initial_capital: float = 1_000_000.0,
                     benchmark_symbol: Optional[str] = None,
                     **params) -> dict:
        """Validate, run and return full backtest results."""
        if strategy_name not in STRATEGY_REGISTRY:
            raise ValueError(f"Unknown strategy '{strategy_name}'. "
                             f"Choose from: {list(STRATEGY_REGISTRY)}")

        if not symbols:
            raise ValueError("symbols list cannot be empty")

        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt   = datetime.strptime(end_date,   "%Y-%m-%d")
        except ValueError:
            raise ValueError("Dates must be in YYYY-MM-DD format")

        if end_dt <= start_dt:
            raise ValueError("end_date must be after start_date")

        logger.info("Running strategy '%s' on %d symbols [%s → %s]",
                    strategy_name, len(symbols), start_date, end_date)

        # Fetch benchmark
        benchmark_series: Optional[pd.Series] = None
        if benchmark_symbol:
            bench_sym = benchmark_symbol if benchmark_symbol.startswith("^") \
                else f"{benchmark_symbol}.NS"
            raw = yf.download(bench_sym, start=start_date, end=end_date,
                              auto_adjust=True, progress=False)
            if not raw.empty:
                benchmark_series = raw["Close"].squeeze()

        # Build components
        data_handler = DataHandler(symbols, start_date, end_date)
        strategy     = STRATEGY_REGISTRY[strategy_name](symbols, **params)
        portfolio    = Portfolio(initial_capital)
        engine       = BacktestEngine(strategy, data_handler, portfolio)

        result       = engine.run()

        metrics = self.analytics.calculate_metrics(
            result["equity_curve"],
            result["trades"],
            benchmark=benchmark_series
        )

        plot_data = self.analytics.plot_equity_curve_data(result["equity_curve"])

        return {
            "strategy":        strategy_name,
            "symbols":         symbols,
            "start_date":      start_date,
            "end_date":        end_date,
            "initial_capital": initial_capital,
            "final_equity":    round(result["final_equity"], 2),
            "metrics":         metrics,
            "equity_curve":    plot_data,
            "n_trades":        len(result["trades"]),
        }

    # ------------------------------------------------------------------
    def walk_forward_optimization(self,
                                  strategy_name: str,
                                  symbols: List[str],
                                  start_date: str,
                                  end_date: str,
                                  param_grid: dict,
                                  n_splits: int = 5,
                                  initial_capital: float = 1_000_000.0) -> dict:
        """
        Walk-forward optimisation via time-series splits.
        param_grid: e.g. {"top_n": [3,5,7], "lookback": [126, 252]}
        Returns best params per fold + out-of-sample cumulative performance.
        """
        start_dt = pd.Timestamp(start_date)
        end_dt   = pd.Timestamp(end_date)
        total_days = (end_dt - start_dt).days
        fold_days  = total_days // n_splits

        param_combinations = [dict(zip(param_grid.keys(), vals))
                              for vals in product(*param_grid.values())]

        folds_results = []
        oos_equity_all: List[pd.Series] = []

        for fold in range(n_splits - 1):
            is_start = start_dt + timedelta(days=fold * fold_days)
            is_end   = start_dt + timedelta(days=(fold + 1) * fold_days)
            oos_end  = start_dt + timedelta(days=(fold + 2) * fold_days)

            is_start_str  = is_start.strftime("%Y-%m-%d")
            is_end_str    = is_end.strftime("%Y-%m-%d")
            oos_start_str = is_end.strftime("%Y-%m-%d")
            oos_end_str   = min(oos_end, end_dt).strftime("%Y-%m-%d")

            logger.info("Fold %d/%d — IS: %s→%s | OOS: %s→%s",
                        fold + 1, n_splits - 1,
                        is_start_str, is_end_str,
                        oos_start_str, oos_end_str)

            best_sharpe = -np.inf
            best_params = {}

            for params in param_combinations:
                try:
                    res = self.run_strategy(
                        strategy_name, symbols,
                        is_start_str, is_end_str,
                        initial_capital=initial_capital,
                        **params
                    )
                    sharpe = res["metrics"].get("risk_adjusted", {}).get("sharpe_ratio", 0.0)
                    if sharpe > best_sharpe:
                        best_sharpe = sharpe
                        best_params = params
                except Exception as exc:
                    logger.warning("Param combo %s failed: %s", params, exc)

            # Out-of-sample with best params
            oos_result: dict = {}
            try:
                oos_result = self.run_strategy(
                    strategy_name, symbols,
                    oos_start_str, oos_end_str,
                    initial_capital=initial_capital,
                    **best_params
                )
                oos_sharpe = oos_result["metrics"].get("risk_adjusted", {}).get("sharpe_ratio", 0.0)
            except Exception as exc:
                logger.warning("OOS run failed fold %d: %s", fold + 1, exc)
                oos_sharpe = np.nan

            folds_results.append({
                "fold":       fold + 1,
                "is_period":  f"{is_start_str} → {is_end_str}",
                "oos_period": f"{oos_start_str} → {oos_end_str}",
                "best_params":   best_params,
                "is_sharpe":     round(best_sharpe, 3),
                "oos_sharpe":    round(oos_sharpe, 3) if not np.isnan(oos_sharpe) else None,
            })

        return {
            "strategy":    strategy_name,
            "n_splits":    n_splits,
            "param_grid":  param_grid,
            "folds":       folds_results,
            "avg_oos_sharpe": round(
                np.nanmean([f["oos_sharpe"] for f in folds_results
                            if f["oos_sharpe"] is not None]), 3
            ),
        }

    # ------------------------------------------------------------------
    def compare_strategies(self,
                           symbols: List[str],
                           start_date: str,
                           end_date: str,
                           initial_capital: float = 1_000_000.0) -> dict:
        """Run all 6 strategies on the same universe and compare metrics."""
        comparison: Dict[str, dict] = {}

        for name in STRATEGY_REGISTRY:
            logger.info("Comparing strategy: %s", name)
            try:
                result = self.run_strategy(
                    name, symbols, start_date, end_date,
                    initial_capital=initial_capital
                )
                m = result.get("metrics", {})
                comparison[name] = {
                    "total_return_pct": m.get("returns", {}).get("total_return_pct", None),
                    "cagr_pct":         m.get("returns", {}).get("cagr_pct", None),
                    "sharpe_ratio":     m.get("risk_adjusted", {}).get("sharpe_ratio", None),
                    "sortino_ratio":    m.get("risk_adjusted", {}).get("sortino_ratio", None),
                    "max_drawdown_pct": m.get("risk", {}).get("max_drawdown_pct", None),
                    "calmar_ratio":     m.get("risk", {}).get("calmar_ratio", None),
                    "total_trades":     m.get("trade_statistics", {}).get("total_trades", 0),
                    "win_rate_pct":     m.get("trade_statistics", {}).get("win_rate_pct", None),
                    "profit_factor":    m.get("trade_statistics", {}).get("profit_factor", None),
                    "final_equity":     result.get("final_equity", initial_capital),
                }
            except Exception as exc:
                logger.error("Strategy %s failed: %s", name, exc)
                comparison[name] = {"error": str(exc)}

        # Rank by Sharpe
        ranked = sorted(
            [k for k in comparison if "sharpe_ratio" in comparison[k]
             and comparison[k]["sharpe_ratio"] is not None],
            key=lambda k: comparison[k]["sharpe_ratio"],
            reverse=True
        )

        return {
            "strategies":    comparison,
            "ranking_sharpe": ranked,
            "symbols":       symbols,
            "period":        f"{start_date} → {end_date}",
        }


# ─────────────────────────────────────────────────────────────────────────────
# CONVENIENCE ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def run_backtest(strategy_name: str,
                 symbols: List[str],
                 start_date: str = "2020-01-01",
                 end_date: str   = "2024-12-31",
                 initial_capital: float = 1_000_000.0,
                 **params) -> dict:
    """Simple top-level function to run a single backtest."""
    orch = BacktestOrchestrator()
    return orch.run_strategy(
        strategy_name, symbols, start_date, end_date,
        initial_capital=initial_capital, **params
    )


if __name__ == "__main__":
    # Quick smoke test
    TEST_SYMBOLS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]
    orch = BacktestOrchestrator()
    print("Running RSI+MACD strategy smoke test…")
    result = run_backtest(
        "rsi_macd",
        TEST_SYMBOLS,
        start_date="2021-01-01",
        end_date="2023-12-31",
    )
    m = result.get("metrics", {})
    print(f"  Total Return : {m.get('returns',{}).get('total_return_pct')}%")
    print(f"  CAGR         : {m.get('returns',{}).get('cagr_pct')}%")
    print(f"  Sharpe       : {m.get('risk_adjusted',{}).get('sharpe_ratio')}")
    print(f"  Max DD       : {m.get('risk',{}).get('max_drawdown_pct')}%")
    print(f"  Trades       : {result.get('n_trades')}")
    print("Done.")
