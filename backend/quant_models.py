"""
Quantitative Models Engine
Markov Chain regime detection, HMM proxy, factor model,
cross-asset arbitrage scanner, Kelly criterion, risk parity, pairs universe
"""
from __future__ import annotations

import logging
import math
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

_qm_cache: Dict[str, Any] = {}
_qm_ts: Dict[str, float] = {}


def _cached(key: str, ttl: float = 900) -> Optional[Any]:
    if key in _qm_cache and (time.time() - _qm_ts.get(key, 0)) < ttl:
        return _qm_cache[key]
    return None


def _store(key: str, val: Any):
    _qm_cache[key] = val
    _qm_ts[key] = time.time()


# ──────────────────────────────────────────────────────────────────
# MARKOV CHAIN MARKET REGIME DETECTION
# 3 States: BULL (0), SIDEWAYS (1), BEAR (2)
# Transition matrix estimated from Nifty50 rolling returns
# ──────────────────────────────────────────────────────────────────

class MarkovRegimeDetector:
    """
    Discrete Markov Chain with 3 states estimated from rolling returns.
    Uses 5-day rolling returns bucketed into 3 regimes.
    """

    STATES = {0: "BULL", 1: "SIDEWAYS", 2: "BEAR"}
    STATE_COLORS = {0: "#00d084", 1: "#f59e0b", 2: "#ff3b3b"}

    def __init__(self, returns: np.ndarray, n_states: int = 3, window: int = 5):
        self.returns = returns
        self.n_states = n_states
        self.window = window
        self.transition_matrix: Optional[np.ndarray] = None
        self.state_means: Optional[np.ndarray] = None
        self.state_sequence: List[int] = []
        self._fit()

    def _classify_return(self, r: float, thresholds: Tuple[float, float]) -> int:
        if r > thresholds[1]:
            return 0   # BULL
        elif r < thresholds[0]:
            return 2   # BEAR
        else:
            return 1   # SIDEWAYS

    def _fit(self):
        r = self.returns
        if len(r) < self.window * 5:
            return

        # Rolling window returns
        roll_rets = np.array([
            np.sum(r[i:i + self.window])
            for i in range(len(r) - self.window)
        ])

        # Adaptive thresholds: 33rd and 67th percentile
        p33 = np.percentile(roll_rets, 33)
        p67 = np.percentile(roll_rets, 67)

        # Classify each window return
        states = np.array([self._classify_return(rr, (p33, p67)) for rr in roll_rets])
        self.state_sequence = states.tolist()

        # Compute transition matrix
        T = np.ones((self.n_states, self.n_states)) * 0.01  # Laplace smoothing
        for t in range(len(states) - 1):
            T[states[t], states[t + 1]] += 1

        # Row-normalize
        row_sums = T.sum(axis=1, keepdims=True)
        self.transition_matrix = T / row_sums

        # State statistics
        self.state_means = np.array([
            roll_rets[states == s].mean() if np.any(states == s) else 0.0
            for s in range(self.n_states)
        ])
        self.state_stds = np.array([
            roll_rets[states == s].std() if np.any(states == s) else 0.01
            for s in range(self.n_states)
        ])
        self.thresholds = (p33, p67)

    @property
    def current_state(self) -> int:
        if not self.state_sequence:
            return 1
        return self.state_sequence[-1]

    def steady_state(self) -> np.ndarray:
        """Stationary distribution via eigendecomposition"""
        if self.transition_matrix is None:
            return np.array([1/3, 1/3, 1/3])
        eigenvalues, eigenvectors = np.linalg.eig(self.transition_matrix.T)
        stationary_idx = np.argmin(np.abs(eigenvalues - 1))
        ss = np.real(eigenvectors[:, stationary_idx])
        return ss / ss.sum()

    def n_step_probabilities(self, n: int = 20) -> np.ndarray:
        """Probability distribution after n steps from current state"""
        if self.transition_matrix is None:
            return np.array([1/3, 1/3, 1/3])
        p0 = np.zeros(self.n_states)
        p0[self.current_state] = 1.0
        Tn = np.linalg.matrix_power(self.transition_matrix, n)
        return p0 @ Tn

    def expected_duration(self) -> Dict[str, float]:
        """Expected number of periods in each state before transition"""
        if self.transition_matrix is None:
            return {}
        durations = {}
        for s in range(self.n_states):
            p_stay = self.transition_matrix[s, s]
            if p_stay < 1.0:
                durations[self.STATES[s]] = round(1 / (1 - p_stay), 1)
            else:
                durations[self.STATES[s]] = float("inf")
        return durations

    def to_dict(self) -> Dict:
        if self.transition_matrix is None:
            return {"error": "insufficient data"}
        current = self.current_state
        next_20d = self.n_step_probabilities(4)  # 4 * 5-day windows = 20 days
        next_63d = self.n_step_probabilities(12)
        ss = self.steady_state()

        return {
            "current_regime": self.STATES[current],
            "current_color": self.STATE_COLORS[current],
            "state_sequence": self.state_sequence[-60:],
            "transition_matrix": {
                self.STATES[i]: {self.STATES[j]: round(float(self.transition_matrix[i, j]), 3)
                                 for j in range(self.n_states)}
                for i in range(self.n_states)
            },
            "regime_probabilities_20d": {
                self.STATES[i]: round(float(next_20d[i]), 3)
                for i in range(self.n_states)
            },
            "regime_probabilities_63d": {
                self.STATES[i]: round(float(next_63d[i]), 3)
                for i in range(self.n_states)
            },
            "steady_state": {
                self.STATES[i]: round(float(ss[i]), 3)
                for i in range(self.n_states)
            },
            "expected_duration_periods": self.expected_duration(),
            "state_returns": {
                self.STATES[i]: {
                    "mean_pct": round(float(self.state_means[i]) * 100, 3),
                    "std_pct": round(float(self.state_stds[i]) * 100, 3),
                }
                for i in range(self.n_states)
            },
            "thresholds": {
                "bear_below": round(float(self.thresholds[0]) * 100, 2),
                "bull_above": round(float(self.thresholds[1]) * 100, 2),
            },
        }


def run_markov_regime(close_prices: List[float], symbol: str = "NIFTY50") -> Dict:
    """Entry point: given list of closes, return regime analysis"""
    key = f"markov_{symbol}_{len(close_prices)}"
    cached = _cached(key, 1800)
    if cached is not None:
        return cached

    arr = np.array(close_prices, dtype=float)
    if len(arr) < 60:
        return {"error": "Need at least 60 data points"}

    rets = np.diff(arr) / arr[:-1]
    detector = MarkovRegimeDetector(rets, n_states=3, window=5)
    result = detector.to_dict()
    result["symbol"] = symbol
    result["data_points"] = len(arr)
    result["computed_at"] = datetime.now().isoformat()

    _store(key, result)
    return result


# ──────────────────────────────────────────────────────────────────
# VOLATILITY REGIME (GARCH-proxy via rolling vol)
# ──────────────────────────────────────────────────────────────────

def estimate_volatility_regime(returns: np.ndarray) -> Dict:
    """
    Simple GARCH(1,1) proxy: exponential weighted moving variance
    Classifies vol into Low/Normal/High/Crisis regimes
    """
    if len(returns) < 30:
        return {"error": "insufficient data"}

    r = returns
    alpha = 0.06    # GARCH weight on latest squared return
    beta  = 0.93    # persistence
    omega = 1e-6    # long-run variance component

    # Initialize with sample variance
    sigma2 = np.var(r[:20])
    sigma2_series = []

    for rt in r:
        sigma2 = omega + alpha * (rt ** 2) + beta * sigma2
        sigma2_series.append(sigma2)

    sigma2_arr = np.array(sigma2_series)
    vol_arr = np.sqrt(sigma2_arr) * np.sqrt(252)  # annualized

    current_vol = float(vol_arr[-1])
    long_run_vol = float(np.sqrt(omega / (1 - alpha - beta)) * np.sqrt(252)) if (alpha + beta) < 1 else float(np.mean(vol_arr))

    percentile_rank = float(np.mean(vol_arr[-252:] < current_vol)) * 100 if len(vol_arr) >= 252 else float(np.mean(vol_arr < current_vol)) * 100

    if current_vol < 12:
        regime = "LOW VOL"
        color = "#3b82f6"
        signal = "Complacency risk — consider protective puts; VIX likely to spike"
    elif current_vol < 20:
        regime = "NORMAL VOL"
        color = "#00d084"
        signal = "Healthy environment for trend-following strategies"
    elif current_vol < 30:
        regime = "HIGH VOL"
        color = "#f59e0b"
        signal = "Elevated uncertainty — reduce position sizes, favor defensive stocks"
    else:
        regime = "CRISIS VOL"
        color = "#ff3b3b"
        signal = "Crisis conditions — capital preservation mode; cash and gold"

    return {
        "current_vol_pct": round(current_vol, 2),
        "long_run_vol_pct": round(long_run_vol, 2),
        "vol_percentile": round(percentile_rank, 1),
        "regime": regime,
        "color": color,
        "signal": signal,
        "vol_series_daily": [round(float(v), 4) for v in vol_arr[-60:]],
        "is_rising": bool(vol_arr[-5:].mean() > vol_arr[-20:].mean()),
    }


# ──────────────────────────────────────────────────────────────────
# MULTI-FACTOR MODEL
# Factors: Momentum, Value, Quality, Low-Vol, Size
# ──────────────────────────────────────────────────────────────────

def score_factor_model(
    symbol: str,
    ret_1m: Optional[float],
    ret_3m: Optional[float],
    ret_12m: Optional[float],
    pe_ratio: Optional[float],
    roe: Optional[float],
    debt_equity: Optional[float],
    daily_vol_pct: Optional[float],
    market_cap: Optional[float],
    sector_avg_pe: Optional[float] = None,
) -> Dict:
    """
    Compute factor scores (0-100) for each factor.
    Score interpretation: 50 = median, 100 = best, 0 = worst.
    """
    scores: Dict[str, Optional[float]] = {}
    weights = {
        "momentum": 0.25,
        "value":    0.20,
        "quality":  0.25,
        "low_vol":  0.15,
        "size":     0.15,
    }

    # 1. MOMENTUM (12-1 month; avoid last month reversal)
    if ret_12m is not None and ret_1m is not None:
        mom = ret_12m - (ret_1m or 0)  # 12m minus last 1m
        scores["momentum"] = _sigmoid_score(mom, center=0, scale=30)
    elif ret_3m is not None:
        scores["momentum"] = _sigmoid_score(ret_3m, center=0, scale=20)
    else:
        scores["momentum"] = None

    # 2. VALUE (inverted P/E relative to sector)
    if pe_ratio is not None and pe_ratio > 0:
        benchmark = sector_avg_pe or 25
        relative_pe = pe_ratio / benchmark
        # Lower relative PE = higher value score
        scores["value"] = _sigmoid_score(-relative_pe, center=-1, scale=0.5)
    else:
        scores["value"] = None

    # 3. QUALITY (ROE + D/E)
    if roe is not None:
        roe_score = _sigmoid_score(roe, center=15, scale=20)
        if debt_equity is not None:
            de_score = _sigmoid_score(-debt_equity, center=-1, scale=1)
            scores["quality"] = (roe_score + de_score) / 2
        else:
            scores["quality"] = roe_score
    else:
        scores["quality"] = None

    # 4. LOW VOLATILITY (lower vol = higher score)
    if daily_vol_pct is not None:
        scores["low_vol"] = _sigmoid_score(-daily_vol_pct, center=-1.5, scale=1)
    else:
        scores["low_vol"] = None

    # 5. SIZE (small-mid cap premium, but with quality filter)
    if market_cap is not None:
        # Score peaks at mid-cap range (~₹10,000-₹50,000 Cr)
        mc_cr = market_cap / 1e7  # convert to Cr
        if mc_cr < 5000:     # small cap
            scores["size"] = 65
        elif mc_cr < 50000:  # mid cap
            scores["size"] = 75
        elif mc_cr < 200000: # large cap
            scores["size"] = 50
        else:                # mega cap
            scores["size"] = 40
    else:
        scores["size"] = None

    # Composite score
    valid = {k: v for k, v in scores.items() if v is not None}
    if valid:
        total_weight = sum(weights[k] for k in valid)
        composite = sum(scores[k] * weights[k] for k in valid) / total_weight
    else:
        composite = 50.0

    factor_interpretation = {
        "momentum": "Strong price trend" if (scores.get("momentum") or 0) > 65 else "Weak trend" if (scores.get("momentum") or 0) < 35 else "Neutral trend",
        "value": "Undervalued vs sector" if (scores.get("value") or 0) > 65 else "Overvalued" if (scores.get("value") or 0) < 35 else "Fairly valued",
        "quality": "High quality (ROE + balance sheet)" if (scores.get("quality") or 0) > 65 else "Quality concerns" if (scores.get("quality") or 0) < 35 else "Average quality",
        "low_vol": "Low volatility (defensible)" if (scores.get("low_vol") or 0) > 65 else "High volatility" if (scores.get("low_vol") or 0) < 35 else "Normal volatility",
        "size": "Mid-cap sweet spot" if (scores.get("size") or 0) >= 70 else "Large-cap stability" if (scores.get("size") or 0) >= 50 else "Mega-cap constraints",
    }

    return {
        "symbol": symbol,
        "factor_scores": {k: round(v, 1) if v is not None else None for k, v in scores.items()},
        "composite_score": round(composite, 1),
        "factor_interpretation": factor_interpretation,
        "composite_label": "Strong Buy" if composite > 70 else "Buy" if composite > 60 else "Sell" if composite < 30 else "Avoid" if composite < 40 else "Hold",
        "composite_color": "#00d084" if composite > 65 else "#ff3b3b" if composite < 35 else "#f59e0b",
    }


def _sigmoid_score(x: float, center: float, scale: float) -> float:
    """Maps any real number to 0-100 via sigmoid centered at center"""
    z = (x - center) / scale
    return round(100 / (1 + math.exp(-z)), 2)


# ──────────────────────────────────────────────────────────────────
# CROSS-ASSET ARBITRAGE SCANNER
# Detects price dislocations between correlated assets
# ──────────────────────────────────────────────────────────────────

ARBI_PAIRS = [
    # Cash-Future basis
    ("NSE Spot vs Future", "^NSEI", "nifty_fut_proxy", "index_future"),
    # ETF-Index arbitrage proxies
    ("Nifty Bees vs Nifty", "NIFTYBEES.NS", "^NSEI", "etf_arb"),
    # Cross-listing
    ("Infosys vs Infosys ADR", "INFY.NS", "INFY", "cross_listing"),
    ("Wipro vs Wipro ADR", "WIPRO.NS", "WIT", "cross_listing"),
    ("HDFC Bank vs HDFC ADR", "HDFCBANK.NS", "HDB", "cross_listing"),
    # Sector pairs
    ("HDFC Bank vs ICICI Bank", "HDFCBANK.NS", "ICICIBANK.NS", "sector_pair"),
    ("TCS vs Infosys", "TCS.NS", "INFY.NS", "sector_pair"),
    ("ONGC vs Oil India", "ONGC.NS", "OIL.NS", "sector_pair"),
    ("Nifty50 vs S&P500", "^NSEI", "^GSPC", "global_arb"),
    ("Gold ETF vs Gold Futures", "GOLDBEES.NS", "GC=F", "commodity_etf"),
]


def scan_arbitrage(histories: Dict[str, List[float]]) -> Dict:
    """
    Given a dict of symbol->close_prices, detect spread dislocations.
    Uses 2-std-dev bands on log ratio.
    """
    key = f"arb_scan_{sum(len(v) for v in histories.values())}"
    cached = _cached(key, 300)
    if cached is not None:
        return cached

    opportunities = []

    for name, sym1, sym2, arb_type in ARBI_PAIRS:
        h1 = histories.get(sym1)
        h2 = histories.get(sym2)
        if not h1 or not h2 or len(h1) < 30 or len(h2) < 30:
            continue

        n = min(len(h1), len(h2))
        a1 = np.array(h1[-n:], dtype=float)
        a2 = np.array(h2[-n:], dtype=float)

        if np.any(a2 == 0):
            continue

        # Log ratio
        log_ratio = np.log(a1 / a2)
        mean_ratio = np.mean(log_ratio[:-5])   # exclude very recent for robustness
        std_ratio  = np.std(log_ratio[:-5])

        if std_ratio < 1e-8:
            continue

        current_ratio = log_ratio[-1]
        zscore = (current_ratio - mean_ratio) / std_ratio

        if abs(zscore) < 1.5:
            signal = "NEUTRAL"
            color = "#555"
            action = "No actionable spread"
        elif zscore > 2.5:
            signal = "SELL SPREAD"
            color = "#ff3b3b"
            action = f"{sym1} overpriced vs {sym2} — consider long {sym2}/short {sym1}"
        elif zscore < -2.5:
            signal = "BUY SPREAD"
            color = "#00d084"
            action = f"{sym1} underpriced vs {sym2} — consider long {sym1}/short {sym2}"
        elif zscore > 1.5:
            signal = "WATCH SELL"
            color = "#f59e0b"
            action = f"Spread widening — monitor for entry"
        else:
            signal = "WATCH BUY"
            color = "#3b82f6"
            action = "Spread compressing — monitor for entry"

        half_life = _compute_half_life(log_ratio - mean_ratio)
        opportunities.append({
            "name": name,
            "sym1": sym1,
            "sym2": sym2,
            "type": arb_type,
            "zscore": round(float(zscore), 3),
            "mean_ratio": round(float(mean_ratio), 4),
            "current_ratio": round(float(current_ratio), 4),
            "std_ratio": round(float(std_ratio), 4),
            "signal": signal,
            "color": color,
            "action": action,
            "half_life_days": half_life,
            "data_points": n,
        })

    opportunities.sort(key=lambda x: abs(x["zscore"]), reverse=True)
    active = [o for o in opportunities if o["signal"] not in ("NEUTRAL",)]

    result = {
        "opportunities": opportunities,
        "active_signals": active,
        "summary": {
            "total_scanned": len(ARBI_PAIRS),
            "active_signals": len(active),
            "buy_spread": sum(1 for o in active if "BUY" in o["signal"]),
            "sell_spread": sum(1 for o in active if "SELL" in o["signal"]),
        },
        "computed_at": datetime.now().isoformat(),
    }
    _store(key, result)
    return result


def _compute_half_life(spread: np.ndarray) -> Optional[float]:
    """Ornstein-Uhlenbeck half-life via OLS regression"""
    try:
        if len(spread) < 10:
            return None
        y = np.diff(spread)
        x = spread[:-1]
        # OLS: y = a + b*x
        x_mean = np.mean(x)
        cov = np.mean((x - x_mean) * y)
        var_x = np.var(x)
        if var_x < 1e-12:
            return None
        b = cov / var_x
        if b >= 0 or b <= -1:
            return None
        half_life = -np.log(2) / b
        return round(float(half_life), 1)
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────
# KELLY CRITERION
# ──────────────────────────────────────────────────────────────────

def compute_kelly(
    win_rate: float,
    avg_win_pct: float,
    avg_loss_pct: float,
    max_kelly_fraction: float = 0.25,
) -> Dict:
    """
    Full Kelly and fractional Kelly position sizing.
    win_rate: probability of positive outcome (0-1)
    avg_win_pct: average winning trade return (positive number)
    avg_loss_pct: average losing trade return (positive number = loss)
    """
    if avg_loss_pct <= 0 or avg_win_pct <= 0:
        return {"error": "Invalid inputs"}

    b = avg_win_pct / avg_loss_pct   # odds ratio
    p = win_rate
    q = 1 - p

    full_kelly = (p * b - q) / b
    half_kelly = full_kelly / 2
    quarter_kelly = full_kelly / 4

    # Capped kelly for practical use
    practical_kelly = max(0.0, min(max_kelly_fraction, full_kelly))

    # Expected value and edge
    edge = p * avg_win_pct - q * avg_loss_pct
    ev_per_trade = edge

    return {
        "full_kelly_pct": round(full_kelly * 100, 2),
        "half_kelly_pct": round(half_kelly * 100, 2),
        "quarter_kelly_pct": round(quarter_kelly * 100, 2),
        "practical_kelly_pct": round(practical_kelly * 100, 2),
        "edge_per_trade_pct": round(ev_per_trade, 3),
        "win_rate": round(p, 3),
        "odds_ratio": round(b, 3),
        "interpretation": (
            "Positive edge — Kelly suggests meaningful position size"
            if full_kelly > 0.05 else
            "Marginal edge — small position size recommended"
            if full_kelly > 0 else
            "Negative edge — no position recommended"
        ),
        "risk_warning": "Full Kelly maximizes long-run growth but allows large drawdowns. Use 25-50% Kelly in practice.",
    }


def compute_kelly_from_history(returns: List[float]) -> Dict:
    """Compute Kelly from historical trade returns"""
    r = np.array(returns)
    wins  = r[r > 0]
    losses = r[r < 0]
    if len(wins) == 0 or len(losses) == 0:
        return {"error": "Need both wins and losses"}

    win_rate = len(wins) / len(r)
    avg_win  = float(np.mean(wins))
    avg_loss = float(np.abs(np.mean(losses)))

    return compute_kelly(win_rate, avg_win, avg_loss)


# ──────────────────────────────────────────────────────────────────
# RISK PARITY ALLOCATION
# ──────────────────────────────────────────────────────────────────

def compute_risk_parity(
    symbols: List[str],
    return_matrix: np.ndarray,
    target_vol_pct: float = 10.0,
) -> Dict:
    """
    Risk parity: allocate so each asset contributes equally to portfolio risk.
    return_matrix: (T, N) matrix of daily returns
    """
    if return_matrix.shape[0] < 20 or return_matrix.shape[1] < 2:
        return {"error": "Insufficient data"}

    n = return_matrix.shape[1]
    cov = np.cov(return_matrix.T) * 252   # annualized covariance

    # Inverse volatility weighting (approximation of risk parity)
    vols = np.sqrt(np.diag(cov))
    if np.any(vols == 0):
        return {"error": "Zero volatility detected"}

    inv_vol = 1 / vols
    weights_inv_vol = inv_vol / inv_vol.sum()

    # Iterative risk parity (50 iterations)
    weights = weights_inv_vol.copy()
    for _ in range(50):
        portfolio_vol = np.sqrt(weights @ cov @ weights)
        marginal_risk = (cov @ weights) / portfolio_vol
        risk_contrib  = weights * marginal_risk
        weights = weights / risk_contrib
        weights = weights / weights.sum()

    # Portfolio stats
    port_vol  = float(np.sqrt(weights @ cov @ weights))
    port_mean = float(np.mean(return_matrix, axis=0) @ weights) * 252

    # Scale to target vol
    scale = target_vol_pct / 100 / port_vol
    scaled_weights = weights * scale
    scaled_weights = np.clip(scaled_weights, 0, 1)

    # Risk contributions
    port_vol_final = float(np.sqrt(weights @ cov @ weights))
    marginal_risk = (cov @ weights) / port_vol_final
    risk_contribs = weights * marginal_risk / port_vol_final

    return {
        "symbols": symbols,
        "weights_pct": {symbols[i]: round(float(weights[i]) * 100, 2) for i in range(n)},
        "scaled_weights_pct": {symbols[i]: round(float(scaled_weights[i]) * 100, 2) for i in range(n)},
        "risk_contributions_pct": {symbols[i]: round(float(risk_contribs[i]) * 100, 2) for i in range(n)},
        "individual_vols_pct": {symbols[i]: round(float(vols[i]) * 100, 2) for i in range(n)},
        "portfolio_vol_pct": round(port_vol * 100, 2),
        "expected_return_pct": round(port_mean * 100, 2),
        "sharpe_estimate": round(port_mean / port_vol, 3) if port_vol > 0 else None,
        "target_vol_pct": target_vol_pct,
        "leverage": round(float(scale), 3),
        "note": "Risk parity: equal risk contribution per asset; no return forecasts used",
        "computed_at": datetime.now().isoformat(),
    }


# ──────────────────────────────────────────────────────────────────
# MOMENTUM + MEAN-REVERSION BLEND
# ──────────────────────────────────────────────────────────────────

def compute_adaptive_strategy(returns: np.ndarray, lookback: int = 63) -> Dict:
    """
    Detects whether momentum or mean-reversion is working in current regime.
    Uses variance ratio test to detect serial correlation.
    """
    if len(returns) < lookback * 2:
        return {"regime": "UNKNOWN", "strategy": "HOLD"}

    r = returns[-lookback * 2:]

    # Variance ratio test: VR = Var(k-period) / (k * Var(1-period))
    def variance_ratio(k: int) -> float:
        n = len(r)
        mu = np.mean(r)
        var_1 = np.mean((r - mu) ** 2)
        # k-period returns
        k_rets = np.array([np.sum(r[i:i + k]) for i in range(n - k)])
        var_k = np.mean((k_rets - k * mu) ** 2) / k
        if var_1 < 1e-10:
            return 1.0
        return var_k / var_1

    vr5  = variance_ratio(5)
    vr10 = variance_ratio(10)
    vr20 = variance_ratio(20)
    avg_vr = (vr5 + vr10 + vr20) / 3

    if avg_vr > 1.1:
        regime = "TRENDING"
        strategy = "MOMENTUM"
        desc = f"Variance ratio {avg_vr:.2f} > 1 → positive serial correlation → trend-following works"
        signal_color = "#00d084"
    elif avg_vr < 0.9:
        regime = "MEAN-REVERTING"
        strategy = "MEAN REVERSION"
        desc = f"Variance ratio {avg_vr:.2f} < 1 → negative serial correlation → buy dips, sell rallies"
        signal_color = "#3b82f6"
    else:
        regime = "RANDOM"
        strategy = "AVOID / NEUTRAL"
        desc = f"Variance ratio {avg_vr:.2f} ≈ 1 → random walk → neither strategy has edge"
        signal_color = "#555"

    return {
        "regime": regime,
        "strategy": strategy,
        "description": desc,
        "color": signal_color,
        "variance_ratios": {"vr5": round(vr5, 4), "vr10": round(vr10, 4), "vr20": round(vr20, 4), "avg": round(avg_vr, 4)},
        "lookback_days": lookback,
        "computed_at": datetime.now().isoformat(),
    }


# ──────────────────────────────────────────────────────────────────
# PORTFOLIO RISK METRICS
# ──────────────────────────────────────────────────────────────────

def compute_portfolio_risk(
    positions: List[Dict],   # [{symbol, weight, returns_series}]
    rf_annual: float = 0.07,
) -> Dict:
    """
    Given a list of positions with weights and return series,
    compute portfolio-level risk metrics.
    """
    if not positions:
        return {"error": "No positions"}

    rf_daily = rf_annual / 252

    # Align all return series
    min_len = min(len(p["returns"]) for p in positions if p.get("returns"))
    if min_len < 20:
        return {"error": "Insufficient history"}

    weights = np.array([p["weight"] for p in positions])
    weights = weights / weights.sum()

    ret_matrix = np.column_stack([
        np.array(p["returns"][-min_len:])
        for p in positions if p.get("returns")
    ])

    portfolio_returns = ret_matrix @ weights
    cum_rets = np.cumprod(1 + portfolio_returns)

    # Max drawdown
    peak = np.maximum.accumulate(cum_rets)
    drawdowns = (cum_rets - peak) / peak
    max_dd = float(np.min(drawdowns))

    # Annualized metrics
    ann_ret = float(np.mean(portfolio_returns)) * 252
    ann_vol = float(np.std(portfolio_returns)) * np.sqrt(252)
    sharpe = (ann_ret - rf_annual) / ann_vol if ann_vol > 0 else 0

    # Sortino (downside deviation)
    neg_rets = portfolio_returns[portfolio_returns < rf_daily]
    down_dev = float(np.std(neg_rets)) * np.sqrt(252) if len(neg_rets) > 5 else ann_vol
    sortino = (ann_ret - rf_annual) / down_dev if down_dev > 0 else 0

    # Calmar
    calmar = ann_ret / abs(max_dd) if max_dd != 0 else 0

    # Beta to Nifty50 (placeholder: assume first position is index benchmark)
    # In production, use actual Nifty returns
    cov_matrix = np.cov(ret_matrix.T) * 252

    return {
        "ann_return_pct": round(ann_ret * 100, 2),
        "ann_vol_pct": round(ann_vol * 100, 2),
        "sharpe": round(sharpe, 3),
        "sortino": round(sortino, 3),
        "calmar": round(calmar, 3),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "var_95_pct": round(float(np.percentile(portfolio_returns, 5)) * 100, 3),
        "cvar_95_pct": round(float(np.mean(portfolio_returns[portfolio_returns < np.percentile(portfolio_returns, 5)])) * 100, 3),
        "covariance_matrix": {
            positions[i]["symbol"]: {
                positions[j]["symbol"]: round(float(cov_matrix[i, j]), 6)
                for j in range(len(positions))
            }
            for i in range(len(positions))
        },
        "data_points": min_len,
        "computed_at": datetime.now().isoformat(),
    }


# ──────────────────────────────────────────────────────────────────
# MEAN-REVERSION Z-SCORE + BOLLINGER BANDS ENHANCED
# ──────────────────────────────────────────────────────────────────

def compute_mean_reversion_signals(prices: List[float], symbol: str) -> Dict:
    arr = np.array(prices, dtype=float)
    n = len(arr)
    if n < 50:
        return {"symbol": symbol, "error": "insufficient data"}

    # Multiple lookback z-scores
    def zscore(lookback: int) -> Optional[float]:
        if n < lookback:
            return None
        subset = arr[-lookback:]
        m, s = np.mean(subset), np.std(subset)
        if s < 1e-8:
            return None
        return round(float((arr[-1] - m) / s), 3)

    z20 = zscore(20)
    z50 = zscore(50)
    z200 = zscore(200) if n >= 200 else None

    # Bollinger bands (20-day, 2-std)
    if n >= 20:
        sma20 = float(np.mean(arr[-20:]))
        std20 = float(np.std(arr[-20:]))
        bb_upper = sma20 + 2 * std20
        bb_lower = sma20 - 2 * std20
        bb_pct = (arr[-1] - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5
    else:
        sma20 = bb_upper = bb_lower = bb_pct = None

    # Mean reversion strength
    z_composite = np.mean([z for z in [z20, z50] if z is not None])

    if z_composite < -2:
        signal = "STRONG BUY (oversold)"
        color = "#00d084"
    elif z_composite < -1:
        signal = "BUY (mild oversold)"
        color = "#22c55e"
    elif z_composite > 2:
        signal = "STRONG SELL (overbought)"
        color = "#ff3b3b"
    elif z_composite > 1:
        signal = "SELL (mild overbought)"
        color = "#ef4444"
    else:
        signal = "HOLD"
        color = "#555"

    return {
        "symbol": symbol,
        "current_price": round(float(arr[-1]), 2),
        "zscore_20d": z20,
        "zscore_50d": z50,
        "zscore_200d": z200,
        "bb_upper": round(bb_upper, 2) if bb_upper else None,
        "bb_mid": round(sma20, 2) if sma20 else None,
        "bb_lower": round(bb_lower, 2) if bb_lower else None,
        "bb_pct": round(float(bb_pct), 3) if bb_pct is not None else None,
        "signal": signal,
        "color": color,
        "computed_at": datetime.now().isoformat(),
    }


# ──────────────────────────────────────────────────────────────────
# PAIRS TRADING UNIVERSE SCANNER
# Extended beyond analytics.py — 50+ pairs across sectors
# ──────────────────────────────────────────────────────────────────

EXTENDED_PAIRS = [
    # Banking
    ("HDFCBANK", "ICICIBANK"),
    ("HDFCBANK", "KOTAKBANK"),
    ("ICICIBANK", "AXISBANK"),
    ("SBIN", "BANKBARODA"),
    ("KOTAKBANK", "INDUSINDBK"),
    # IT
    ("TCS", "INFY"),
    ("TCS", "WIPRO"),
    ("INFY", "HCLTECH"),
    ("WIPRO", "TECHM"),
    # Oil & Gas
    ("ONGC", "OIL"),
    ("BPCL", "IOC"),
    ("RELIANCE", "ONGC"),
    # Auto
    ("MARUTI", "M%26M"),
    ("TATAMOTORS", "BAJAJ-AUTO"),
    # Pharma
    ("SUNPHARMA", "CIPLA"),
    ("DRREDDY", "LUPIN"),
    # FMCG
    ("HINDUNILVR", "ITC"),
    ("NESTLEIND", "BRITANNIA"),
    # Metals
    ("TATASTEEL", "JSWSTEEL"),
    ("HINDALCO", "VEDL"),
    # Cement
    ("ULTRACEMCO", "GRASIM"),
    ("SHREECEM", "AMBUJA"),
    # Power
    ("NTPC", "POWERGRID"),
    ("ADANIGREEN", "TATAPOWER"),
    # Telecom
    ("BHARTIARTL", "IDEA"),
]


def rank_pairs_by_cointegration(pair_zscores: List[Dict]) -> List[Dict]:
    """Rank pairs by absolute z-score for trade opportunity"""
    return sorted(pair_zscores, key=lambda x: abs(x.get("current_zscore", 0)), reverse=True)
