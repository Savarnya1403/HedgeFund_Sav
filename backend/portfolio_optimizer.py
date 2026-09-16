"""
Indian Hedge Fund — Portfolio Optimizer v1.0
Modern Portfolio Theory + advanced extensions for Indian equities.
Dependencies: numpy, pandas, scipy, yfinance, sklearn
"""

from __future__ import annotations

import logging
import warnings
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf
from scipy import optimize, stats
from scipy.optimize import minimize, linprog

try:
    from sklearn.covariance import LedoitWolf, OAS
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logging.warning("sklearn not found — Ledoit-Wolf shrinkage will use manual implementation")

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RISK_FREE_RATE  = 0.065
MARKET_PREMIUM  = 0.060         # Indian equity risk premium
TRADING_DAYS    = 252
NIFTY_TICKER    = "^NSEI"
MAX_WEIGHT      = 0.30          # 30% cap per stock
MIN_WEIGHT      = 0.0           # Long-only

# Historical crisis scenarios (approximate peak-to-trough daily returns)
CRISIS_SCENARIOS: Dict[str, Dict[str, float]] = {
    "2008_global_crisis": {
        "description": "Lehman Brothers collapse — Nifty fell ~55%",
        "market_shock": -0.55, "period": "Oct 2007 – Mar 2009",
    },
    "2020_covid_crash": {
        "description": "COVID-19 pandemic — Nifty fell ~38% in 40 days",
        "market_shock": -0.38, "period": "Feb 2020 – Mar 2020",
    },
    "2013_taper_tantrum": {
        "description": "Fed taper tantrum — Nifty fell ~14%",
        "market_shock": -0.14, "period": "May 2013 – Aug 2013",
    },
    "2016_demonetization": {
        "description": "India demonetization shock — Nifty fell ~6%",
        "market_shock": -0.06, "period": "Nov 2016 – Dec 2016",
    },
    "2022_rate_hike_cycle": {
        "description": "Fed + RBI rate hike cycle — Nifty fell ~16%",
        "market_shock": -0.16, "period": "Jan 2022 – Jun 2022",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# RETURN DATA FETCHER
# ─────────────────────────────────────────────────────────────────────────────

class ReturnDataFetcher:
    """Fetches price data from yfinance and computes returns, expected returns,
    and covariance matrices for NSE-listed Indian stocks."""

    def _nse_ticker(self, symbol: str) -> str:
        if symbol.startswith("^") or symbol.endswith(".NS"):
            return symbol
        return f"{symbol}.NS"

    def fetch_returns(self, symbols: List[str], period: str = "2y") -> pd.DataFrame:
        """
        Download prices and compute daily log returns.
        Returns DataFrame: index=dates, columns=symbols.
        """
        tickers = [self._nse_ticker(s) for s in symbols]
        logger.info("Fetching %d tickers for period=%s", len(tickers), period)

        raw = yf.download(
            tickers,
            period=period,
            auto_adjust=True,
            progress=False,
            group_by="ticker",
            threads=True,
        )

        prices: Dict[str, pd.Series] = {}
        for sym, ticker in zip(symbols, tickers):
            try:
                if len(tickers) == 1:
                    col = raw["Close"] if "Close" in raw.columns else raw.iloc[:, 0]
                else:
                    col = raw[ticker]["Close"]
                col = col.dropna()
                if not col.empty:
                    prices[sym] = col
            except Exception as exc:
                logger.warning("  %s: %s", sym, exc)

        if not prices:
            raise ValueError("No price data could be fetched for given symbols")

        price_df = pd.DataFrame(prices).sort_index()
        price_df = price_df.ffill().bfill()
        price_df.dropna(how="all", inplace=True)

        # Log returns
        log_returns = np.log(price_df / price_df.shift(1)).dropna()
        log_returns.replace([np.inf, -np.inf], np.nan, inplace=True)
        log_returns.dropna(how="any", inplace=True)

        logger.info("Returns shape: %s", log_returns.shape)
        return log_returns

    def fetch_price_series(self, symbols: List[str], period: str = "2y") -> pd.DataFrame:
        """Return raw adjusted close prices (no return transformation)."""
        tickers = [self._nse_ticker(s) for s in symbols]
        raw     = yf.download(tickers, period=period, auto_adjust=True,
                              progress=False, group_by="ticker", threads=True)
        prices: Dict[str, pd.Series] = {}
        for sym, ticker in zip(symbols, tickers):
            try:
                if len(tickers) == 1:
                    col = raw["Close"]
                else:
                    col = raw[ticker]["Close"]
                prices[sym] = col.dropna()
            except Exception:
                pass
        df = pd.DataFrame(prices).ffill().bfill().dropna(how="all")
        return df

    def get_expected_returns(self, symbols: List[str],
                             method: str = "historical",
                             period: str = "3y") -> pd.Series:
        """
        Annualised expected returns.
        method: "historical" | "capm" | "shrinkage"
        """
        returns = self.fetch_returns(symbols, period=period)
        available = [s for s in symbols if s in returns.columns]

        if method == "historical":
            mu = returns[available].mean() * TRADING_DAYS
            return mu.rename("expected_return")

        elif method == "capm":
            # Fetch NIFTY50 as market proxy
            nifty_raw = yf.download(NIFTY_TICKER, period=period,
                                    auto_adjust=True, progress=False)
            if nifty_raw.empty:
                logger.warning("NIFTY data unavailable, falling back to historical")
                return self.get_expected_returns(symbols, "historical", period)

            market_ret = np.log(nifty_raw["Close"] / nifty_raw["Close"].shift(1)).dropna()
            market_ann = float(market_ret.mean() * TRADING_DAYS)

            expected: Dict[str, float] = {}
            for sym in available:
                sym_ret = returns[sym].dropna()
                idx     = sym_ret.index.intersection(market_ret.index)
                if len(idx) < 20:
                    expected[sym] = market_ann
                    continue
                s = sym_ret.reindex(idx)
                m = market_ret.reindex(idx)
                cov_mat = np.cov(s.values, m.values)
                beta    = cov_mat[0, 1] / cov_mat[1, 1] if cov_mat[1, 1] > 0 else 1.0
                expected[sym] = RISK_FREE_RATE + beta * MARKET_PREMIUM

            return pd.Series(expected, name="expected_return")

        elif method == "shrinkage":
            # James-Stein shrinkage toward grand mean
            hist   = returns[available].mean() * TRADING_DAYS
            n, p   = len(returns), len(available)
            grand  = hist.mean()
            # Shrinkage intensity (simplified)
            alpha  = min(1.0, (p + 2) / (n * ((hist - grand) ** 2).sum() + 1e-9))
            shrunk = (1 - alpha) * hist + alpha * grand
            return shrunk.rename("expected_return")

        else:
            raise ValueError(f"Unknown method '{method}'")

    def get_covariance_matrix(self, returns: pd.DataFrame,
                              method: str = "sample") -> pd.DataFrame:
        """
        Covariance matrix (annualised).
        method: "sample" | "ledoit_wolf" | "oracle"
        """
        clean = returns.dropna()

        if method == "sample":
            cov = clean.cov() * TRADING_DAYS
        elif method == "ledoit_wolf":
            if SKLEARN_AVAILABLE:
                lw  = LedoitWolf().fit(clean.values)
                cov = pd.DataFrame(lw.covariance_ * TRADING_DAYS,
                                   index=clean.columns, columns=clean.columns)
            else:
                cov = self._manual_ledoit_wolf(clean)
        elif method == "oracle":
            if SKLEARN_AVAILABLE:
                oas = OAS().fit(clean.values)
                cov = pd.DataFrame(oas.covariance_ * TRADING_DAYS,
                                   index=clean.columns, columns=clean.columns)
            else:
                cov = self._manual_ledoit_wolf(clean)
        else:
            raise ValueError(f"Unknown covariance method '{method}'")

        # Ensure positive semi-definite
        cov = self._make_psd(cov)
        return cov

    def _manual_ledoit_wolf(self, returns: pd.DataFrame) -> pd.DataFrame:
        """Oracle Approximating Shrinkage (simplified) when sklearn unavailable."""
        S   = returns.cov().values * TRADING_DAYS
        n   = len(returns)
        p   = S.shape[0]
        mu  = np.trace(S) / p
        F   = mu * np.eye(p)                    # shrinkage target: identity × mean variance
        # Ledoit-Wolf analytical shrinkage intensity
        alpha = min(1.0, ((n - 2) / n * np.trace(S @ S) + np.trace(S) ** 2) /
                    ((n + 2) * (np.trace(S @ S) - np.trace(S) ** 2 / p + 1e-12)))
        C = (1 - alpha) * S + alpha * F
        return pd.DataFrame(C, index=returns.columns, columns=returns.columns)

    @staticmethod
    def _make_psd(cov: pd.DataFrame, epsilon: float = 1e-8) -> pd.DataFrame:
        """Clip negative eigenvalues to ensure positive semi-definiteness."""
        arr   = cov.values.copy()
        vals, vecs = np.linalg.eigh(arr)
        vals  = np.maximum(vals, epsilon)
        psd   = vecs @ np.diag(vals) @ vecs.T
        return pd.DataFrame(psd, index=cov.index, columns=cov.columns)


# ─────────────────────────────────────────────────────────────────────────────
# MEAN-VARIANCE OPTIMIZER
# ─────────────────────────────────────────────────────────────────────────────

class MeanVarianceOptimizer:
    """Classical Markowitz mean-variance optimization via SLSQP."""

    def __init__(self, max_weight: float = MAX_WEIGHT):
        self.max_weight = max_weight

    def _portfolio_stats(self, weights: np.ndarray,
                         mu: np.ndarray, sigma: np.ndarray) -> Tuple[float, float, float]:
        ret = float(weights @ mu)
        vol = float(np.sqrt(weights @ sigma @ weights))
        sr  = (ret - RISK_FREE_RATE) / vol if vol > 1e-12 else 0.0
        return ret, vol, sr

    def _base_constraints(self, n: int) -> list:
        return [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

    def _base_bounds(self, n: int) -> list:
        return [(MIN_WEIGHT, self.max_weight)] * n

    def maximize_sharpe(self, expected_returns: pd.Series,
                        cov_matrix: pd.DataFrame,
                        risk_free_rate: float = RISK_FREE_RATE) -> dict:
        """Maximize Sharpe ratio portfolio."""
        symbols = list(expected_returns.index)
        mu      = expected_returns.values
        sigma   = cov_matrix.loc[symbols, symbols].values
        n       = len(symbols)

        def neg_sharpe(w):
            r, v, _ = self._portfolio_stats(w, mu, sigma)
            return -(r - risk_free_rate) / max(v, 1e-12)

        w0     = np.ones(n) / n
        result = minimize(neg_sharpe, w0,
                          method="SLSQP",
                          bounds=self._base_bounds(n),
                          constraints=self._base_constraints(n),
                          options={"ftol": 1e-9, "maxiter": 1000})

        w = result.x
        w = np.maximum(w, 0)
        w /= w.sum()
        ret, vol, sharpe = self._portfolio_stats(w, mu, sigma)

        return {
            "weights":  dict(zip(symbols, w.round(6).tolist())),
            "expected_return_pct": round(ret * 100, 2),
            "expected_vol_pct":    round(vol * 100, 2),
            "sharpe_ratio":        round(sharpe, 4),
            "method":              "max_sharpe",
        }

    def minimize_volatility(self, expected_returns: pd.Series,
                            cov_matrix: pd.DataFrame) -> dict:
        """Minimum variance portfolio."""
        symbols = list(expected_returns.index)
        mu      = expected_returns.values
        sigma   = cov_matrix.loc[symbols, symbols].values
        n       = len(symbols)

        def port_vol(w):
            return float(np.sqrt(w @ sigma @ w))

        w0     = np.ones(n) / n
        result = minimize(port_vol, w0,
                          method="SLSQP",
                          bounds=self._base_bounds(n),
                          constraints=self._base_constraints(n),
                          options={"ftol": 1e-9, "maxiter": 1000})

        w = result.x
        w = np.maximum(w, 0)
        w /= w.sum()
        ret, vol, sharpe = self._portfolio_stats(w, mu, sigma)

        return {
            "weights":             dict(zip(symbols, w.round(6).tolist())),
            "expected_return_pct": round(ret * 100, 2),
            "expected_vol_pct":    round(vol * 100, 2),
            "sharpe_ratio":        round(sharpe, 4),
            "method":              "min_vol",
        }

    def maximize_return(self, expected_returns: pd.Series,
                        cov_matrix: pd.DataFrame,
                        target_vol: float) -> dict:
        """Maximize return subject to a volatility cap."""
        symbols = list(expected_returns.index)
        mu      = expected_returns.values
        sigma   = cov_matrix.loc[symbols, symbols].values
        n       = len(symbols)

        def neg_return(w):
            return -float(w @ mu)

        constraints = self._base_constraints(n) + [
            {"type": "ineq",
             "fun": lambda w: target_vol - float(np.sqrt(w @ sigma @ w))}
        ]

        w0     = np.ones(n) / n
        result = minimize(neg_return, w0,
                          method="SLSQP",
                          bounds=self._base_bounds(n),
                          constraints=constraints,
                          options={"ftol": 1e-9, "maxiter": 1000})

        w = np.maximum(result.x, 0)
        w /= w.sum()
        ret, vol, sharpe = self._portfolio_stats(w, mu, sigma)

        return {
            "weights":             dict(zip(symbols, w.round(6).tolist())),
            "expected_return_pct": round(ret * 100, 2),
            "expected_vol_pct":    round(vol * 100, 2),
            "sharpe_ratio":        round(sharpe, 4),
            "method":              "max_return_constrained",
            "target_vol_pct":      round(target_vol * 100, 2),
        }

    def efficient_frontier(self, expected_returns: pd.Series,
                           cov_matrix: pd.DataFrame,
                           n_points: int = 50) -> list:
        """Generate efficient frontier points by sweeping target return."""
        symbols = list(expected_returns.index)
        mu      = expected_returns.values
        sigma   = cov_matrix.loc[symbols, symbols].values
        n       = len(symbols)

        min_ret = float(mu.min())
        max_ret = float(mu.max())
        targets = np.linspace(min_ret, max_ret, n_points)

        frontier = []
        for target in targets:
            constraints = self._base_constraints(n) + [
                {"type": "eq", "fun": lambda w, t=target: float(w @ mu) - t}
            ]

            def port_vol(w):
                return float(np.sqrt(w @ sigma @ w))

            w0     = np.ones(n) / n
            result = minimize(port_vol, w0,
                              method="SLSQP",
                              bounds=self._base_bounds(n),
                              constraints=constraints,
                              options={"ftol": 1e-9, "maxiter": 500})

            if result.success:
                w = np.maximum(result.x, 0)
                w /= w.sum()
                ret, vol, sharpe = self._portfolio_stats(w, mu, sigma)
                frontier.append({
                    "return_pct": round(ret * 100, 2),
                    "vol_pct":    round(vol * 100, 2),
                    "sharpe":     round(sharpe, 4),
                    "weights":    dict(zip(symbols, w.round(4).tolist())),
                })

        return frontier

    def monte_carlo_frontier(self, expected_returns: pd.Series,
                             cov_matrix: pd.DataFrame,
                             n_portfolios: int = 5000) -> dict:
        """Random portfolio simulation for visualisation."""
        symbols = list(expected_returns.index)
        mu      = expected_returns.values
        sigma   = cov_matrix.loc[symbols, symbols].values
        n       = len(symbols)

        np.random.seed(42)
        portfolios: List[dict] = []
        max_sharpe_idx  = 0
        max_sharpe_val  = -np.inf
        min_vol_idx     = 0
        min_vol_val     = np.inf

        for i in range(n_portfolios):
            raw = np.random.dirichlet(np.ones(n))
            # Clip to max_weight
            raw = np.minimum(raw, self.max_weight)
            raw /= raw.sum()

            ret, vol, sharpe = self._portfolio_stats(raw, mu, sigma)
            portfolios.append({
                "return_pct": round(ret * 100, 2),
                "vol_pct":    round(vol * 100, 2),
                "sharpe":     round(sharpe, 4),
                "weights":    dict(zip(symbols, raw.round(4).tolist())),
            })

            if sharpe > max_sharpe_val:
                max_sharpe_val = sharpe
                max_sharpe_idx = i
            if vol < min_vol_val:
                min_vol_val = vol
                min_vol_idx = i

        return {
            "portfolios":          portfolios,
            "n_portfolios":        n_portfolios,
            "max_sharpe_portfolio": portfolios[max_sharpe_idx],
            "min_vol_portfolio":   portfolios[min_vol_idx],
        }


# ─────────────────────────────────────────────────────────────────────────────
# RISK PARITY OPTIMIZER
# ─────────────────────────────────────────────────────────────────────────────

class RiskParityOptimizer:
    """
    Equal Risk Contribution (ERC) portfolio.
    Each asset contributes equally to total portfolio risk.
    Allows custom risk budget per asset.
    """

    def calculate_risk_contribution(self, weights: np.ndarray,
                                    cov_matrix: np.ndarray) -> np.ndarray:
        """Marginal risk contribution × weight = asset risk contribution."""
        port_vol = np.sqrt(weights @ cov_matrix @ weights)
        if port_vol < 1e-12:
            return np.zeros_like(weights)
        mrc = cov_matrix @ weights          # marginal risk contribution
        rc  = weights * mrc / port_vol      # component risk contribution
        return rc

    def optimize(self, cov_matrix: pd.DataFrame,
                 budget: Optional[List[float]] = None) -> dict:
        """
        Solve for equal-risk-contribution weights.
        budget: target fractional risk per asset (sums to 1). None → equal.
        """
        symbols = list(cov_matrix.index)
        sigma   = cov_matrix.values
        n       = len(symbols)

        target_rc = np.array(budget) if budget is not None else np.ones(n) / n
        target_rc = target_rc / target_rc.sum()    # normalise

        def objective(w):
            rc   = self.calculate_risk_contribution(w, sigma)
            port_vol = np.sqrt(w @ sigma @ w)
            target = target_rc * port_vol
            return float(np.sum((rc - target) ** 2))

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds      = [(0.001, 1.0)] * n    # small lower bound for stability
        w0          = np.ones(n) / n

        result = minimize(objective, w0,
                          method="SLSQP",
                          bounds=bounds,
                          constraints=constraints,
                          options={"ftol": 1e-12, "maxiter": 2000})

        w = np.maximum(result.x, 0)
        w /= w.sum()

        rc     = self.calculate_risk_contribution(w, sigma)
        port_v = float(np.sqrt(w @ sigma @ w))
        rc_pct = rc / port_v if port_v > 0 else np.zeros(n)

        return {
            "weights":                 dict(zip(symbols, w.round(6).tolist())),
            "risk_contributions":      dict(zip(symbols, rc.round(6).tolist())),
            "risk_contribution_pct":   dict(zip(symbols, rc_pct.round(4).tolist())),
            "portfolio_vol_pct":       round(port_v * 100, 2),
            "method":                  "risk_parity",
            "converged":               result.success,
        }


# ─────────────────────────────────────────────────────────────────────────────
# BLACK-LITTERMAN OPTIMIZER
# ─────────────────────────────────────────────────────────────────────────────

class BlackLittermanOptimizer:
    """
    Black-Litterman model for incorporating analyst views into portfolio
    construction. Uses market-cap equilibrium returns as prior.
    """

    def __init__(self, market_caps: Dict[str, float], symbols: List[str]):
        self.symbols     = symbols
        self.market_caps = market_caps
        total_cap        = sum(market_caps.get(s, 1.0) for s in symbols)
        self.market_weights = np.array([
            market_caps.get(s, 1.0) / total_cap for s in symbols
        ])

    def calculate_equilibrium_returns(self, cov_matrix: pd.DataFrame,
                                      market_weights: Optional[np.ndarray] = None,
                                      risk_aversion: float = 2.5) -> pd.Series:
        """
        Implied equilibrium returns from reverse optimization:
        Pi = lambda * Sigma * w_market
        """
        sigma = cov_matrix.loc[self.symbols, self.symbols].values
        w     = market_weights if market_weights is not None else self.market_weights
        pi    = risk_aversion * sigma @ w
        return pd.Series(pi, index=self.symbols, name="equilibrium_returns")

    def optimize(self, views: Dict[str, float],
                 confidences: Dict[str, float],
                 cov_matrix: pd.DataFrame,
                 tau: float = 0.05,
                 risk_aversion: float = 2.5) -> dict:
        """
        Black-Litterman posterior expected returns and optimal weights.
        views: {symbol: expected_annual_return}
        confidences: {symbol: confidence in [0, 1]}
        tau: uncertainty in prior (typically 0.01–0.05)
        """
        symbols = self.symbols
        sigma   = cov_matrix.loc[symbols, symbols].values
        n       = len(symbols)

        # Prior: equilibrium returns
        pi = self.calculate_equilibrium_returns(cov_matrix, risk_aversion=risk_aversion).values

        if not views:
            # No views — return market-cap weights
            ret, vol, sharpe = self._port_stats(self.market_weights, pi, sigma)
            return {
                "weights":             dict(zip(symbols, self.market_weights.round(6).tolist())),
                "bl_expected_returns": dict(zip(symbols, pi.round(4).tolist())),
                "expected_return_pct": round(ret * 100, 2),
                "expected_vol_pct":    round(vol * 100, 2),
                "sharpe_ratio":        round(sharpe, 4),
                "method":              "black_litterman",
                "note":                "No views provided, using equilibrium weights",
            }

        # Build views matrix P and view vector q
        view_syms  = [s for s in views if s in symbols]
        k          = len(view_syms)
        P          = np.zeros((k, n))
        q          = np.zeros(k)
        omega_diag = np.zeros(k)   # view uncertainty = (1 - confidence) * P * tau*Sigma * P^T

        sym_idx = {s: i for i, s in enumerate(symbols)}
        for j, sym in enumerate(view_syms):
            idx          = sym_idx[sym]
            P[j, idx]    = 1.0
            q[j]         = views[sym]
            conf         = np.clip(confidences.get(sym, 0.5), 0.01, 0.99)
            omega_diag[j] = (1 - conf) / conf  # higher confidence → lower uncertainty

        Omega = np.diag(omega_diag * (P @ (tau * sigma) @ P.T).diagonal())

        # BL posterior: combined expected returns
        tau_sigma      = tau * sigma
        tau_sigma_inv  = np.linalg.pinv(tau_sigma)
        Pt_Omega_inv   = P.T @ np.linalg.pinv(Omega)

        M              = tau_sigma_inv + Pt_Omega_inv @ P
        M_inv          = np.linalg.pinv(M)
        mu_bl          = M_inv @ (tau_sigma_inv @ pi + Pt_Omega_inv @ q)

        # BL posterior covariance
        sigma_bl       = sigma + M_inv

        # Optimal weights from BL posterior
        mu_series  = pd.Series(mu_bl, index=symbols)
        cov_bl     = pd.DataFrame(sigma_bl, index=symbols, columns=symbols)
        cov_bl     = ReturnDataFetcher._make_psd(cov_bl)

        mv = MeanVarianceOptimizer()
        opt = mv.maximize_sharpe(mu_series, cov_bl, RISK_FREE_RATE)

        return {
            "weights":              opt["weights"],
            "bl_expected_returns":  dict(zip(symbols, mu_bl.round(4).tolist())),
            "equilibrium_returns":  dict(zip(symbols, pi.round(4).tolist())),
            "expected_return_pct":  opt["expected_return_pct"],
            "expected_vol_pct":     opt["expected_vol_pct"],
            "sharpe_ratio":         opt["sharpe_ratio"],
            "views_incorporated":   view_syms,
            "method":               "black_litterman",
        }

    @staticmethod
    def _port_stats(w: np.ndarray, mu: np.ndarray,
                    sigma: np.ndarray) -> Tuple[float, float, float]:
        r   = float(w @ mu)
        vol = float(np.sqrt(w @ sigma @ w))
        sr  = (r - RISK_FREE_RATE) / max(vol, 1e-12)
        return r, vol, sr


# ─────────────────────────────────────────────────────────────────────────────
# CVAR OPTIMIZER
# ─────────────────────────────────────────────────────────────────────────────

class CVaROptimizer:
    """
    Minimize Conditional Value at Risk (CVaR / Expected Shortfall)
    using the Rockafellar-Uryasev (2000) linear programming formulation.
    """

    def optimize(self, returns: pd.DataFrame,
                 confidence: float = 0.95,
                 target_return: Optional[float] = None,
                 max_weight: float = MAX_WEIGHT) -> dict:
        """
        Minimize CVaR at given confidence level.
        Optionally constrain to minimum target_return (annualised).
        Returns weights that minimize tail risk.
        """
        R = returns.values          # T × N
        T, N = R.shape
        symbols = list(returns.columns)

        # Rockafellar-Uryasev LP:
        # Variables: [w (N), z (T), alpha (1)]
        # w = asset weights, z_t = VaR exceedances, alpha = VaR threshold
        # Minimize: alpha + 1/((1-c)*T) * sum(z_t)
        # s.t. z_t >= -R_t @ w - alpha,  z_t >= 0,  sum(w)=1, w>=0, w<=max_w

        alpha_idx = N + T       # index of VaR variable in x
        n_vars    = N + T + 1   # w (N) + z (T) + alpha (1)
        coeff     = 1.0 / ((1 - confidence) * T)

        # Objective: minimize alpha + coeff * sum(z_t)
        c_obj = np.zeros(n_vars)
        c_obj[N:N + T] = coeff
        c_obj[alpha_idx] = 1.0

        # Inequality constraints: -R_t @ w - alpha - z_t <= 0
        # i.e., z_t + R_t @ w + alpha >= 0
        # In standard LP form (A_ub @ x <= b_ub):
        # -z_t - R_t @ w - alpha <= 0 → A_ub, b_ub
        A_ub = np.zeros((T, n_vars))
        for t in range(T):
            A_ub[t, :N]          = -R[t, :]    # -w coeff
            A_ub[t, N + t]       = -1.0          # -z_t
            A_ub[t, alpha_idx]   = -1.0          # -alpha

        b_ub = np.zeros(T)

        # Equality: sum(w) = 1
        A_eq      = np.zeros((1, n_vars))
        A_eq[0, :N] = 1.0
        b_eq        = np.array([1.0])

        # Optional return constraint: sum(w * mu) >= target_return
        if target_return is not None:
            mu_hist = returns.mean().values * TRADING_DAYS
            ret_row = np.zeros(n_vars)
            ret_row[:N] = -mu_hist          # negate for <= form
            A_ub    = np.vstack([A_ub, ret_row[np.newaxis, :]])
            b_ub    = np.append(b_ub, -target_return)

        # Bounds: w in [0, max_weight], z >= 0, alpha unconstrained
        bounds = ([(0.0, max_weight)] * N +
                  [(0.0, None)] * T +
                  [(None, None)])            # alpha

        result = linprog(c_obj, A_ub=A_ub, b_ub=b_ub,
                         A_eq=A_eq, b_eq=b_eq,
                         bounds=bounds,
                         method="highs")

        if result.status not in (0, 1):
            logger.warning("CVaR LP did not converge: %s", result.message)
            # Fall back to equal weight
            w = np.ones(N) / N
        else:
            w = result.x[:N]
            w = np.maximum(w, 0)
            w /= w.sum()

        mu   = returns.mean().values * TRADING_DAYS
        sigma = returns.cov().values * TRADING_DAYS
        ret  = float(w @ mu)
        vol  = float(np.sqrt(w @ sigma @ w))
        sr   = (ret - RISK_FREE_RATE) / max(vol, 1e-12)

        # CVaR computation
        portfolio_returns = returns.values @ w
        var_val  = np.percentile(portfolio_returns, (1 - confidence) * 100)
        tail     = portfolio_returns[portfolio_returns <= var_val]
        cvar_val = float(tail.mean()) if len(tail) > 0 else var_val

        return {
            "weights":             dict(zip(symbols, w.round(6).tolist())),
            "expected_return_pct": round(ret * 100, 2),
            "expected_vol_pct":    round(vol * 100, 2),
            "sharpe_ratio":        round(sr, 4),
            "var_daily_pct":       round(var_val * 100, 3),
            "cvar_daily_pct":      round(cvar_val * 100, 3),
            "confidence":          confidence,
            "method":              "cvar",
            "converged":           result.status == 0,
        }


# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────

class PortfolioAnalytics:
    """Compute risk attribution, stress tests, and rebalancing signals."""

    def calculate_portfolio_metrics(self,
                                    weights: Dict[str, float],
                                    expected_returns: pd.Series,
                                    cov_matrix: pd.DataFrame,
                                    risk_free_rate: float = RISK_FREE_RATE) -> dict:
        symbols = list(weights.keys())
        w       = np.array([weights[s] for s in symbols])
        mu      = expected_returns.reindex(symbols).fillna(0).values
        sigma   = cov_matrix.loc[symbols, symbols].values

        port_ret = float(w @ mu)
        port_vol = float(np.sqrt(w @ sigma @ w))
        sharpe   = (port_ret - risk_free_rate) / max(port_vol, 1e-12)

        # Diversification ratio
        asset_vols = np.sqrt(np.diag(sigma))
        weighted_vol_sum = float(w @ asset_vols)
        div_ratio = weighted_vol_sum / max(port_vol, 1e-12)

        # HHI concentration
        hhi = float(np.sum(w ** 2))

        # Effective N
        eff_n = 1.0 / hhi if hhi > 0 else len(symbols)

        return {
            "expected_return_pct":   round(port_ret * 100, 2),
            "expected_vol_pct":      round(port_vol * 100, 2),
            "sharpe_ratio":          round(sharpe, 4),
            "diversification_ratio": round(div_ratio, 4),
            "hhi_concentration":     round(hhi, 4),
            "effective_n_stocks":    round(eff_n, 2),
            "n_holdings":            int(np.sum(w > 0.001)),
        }

    def calculate_risk_attribution(self, weights: Dict[str, float],
                                   cov_matrix: pd.DataFrame) -> dict:
        """Marginal and component risk contributions per asset."""
        symbols = [s for s in weights if s in cov_matrix.index]
        w       = np.array([weights[s] for s in symbols])
        sigma   = cov_matrix.loc[symbols, symbols].values

        port_vol = float(np.sqrt(w @ sigma @ w))
        if port_vol < 1e-12:
            return {}

        mrc      = sigma @ w / port_vol           # marginal risk contribution
        crc      = w * mrc                        # component risk contribution
        crc_pct  = crc / port_vol                 # as fraction of total risk

        return {
            "marginal_risk_contribution":   dict(zip(symbols, mrc.round(6).tolist())),
            "component_risk_contribution":  dict(zip(symbols, crc.round(6).tolist())),
            "risk_contribution_pct":        dict(zip(symbols, (crc_pct * 100).round(3).tolist())),
            "portfolio_vol_pct":            round(port_vol * 100, 2),
        }

    def stress_test(self, weights: Dict[str, float],
                    returns: pd.DataFrame,
                    scenarios: Optional[Dict[str, Dict[str, float]]] = None) -> dict:
        """
        Apply historical and custom stress scenarios to portfolio.
        Returns estimated P&L under each scenario.
        """
        symbols    = [s for s in weights if s in returns.columns]
        w          = np.array([weights[s] for s in symbols])
        ret_matrix = returns[symbols]

        results: Dict[str, dict] = {}

        # Historical scenarios using market beta proxy
        for sc_name, sc_info in CRISIS_SCENARIOS.items():
            mkt_shock = sc_info["market_shock"]
            # Estimate portfolio impact via beta to market
            # Use simplified: mean correlation × vol amplification
            port_ret_hist  = ret_matrix @ w
            port_std       = float(port_ret_hist.std() * np.sqrt(TRADING_DAYS))
            # Assume portfolio beta ≈ 0.85 (typical diversified Indian equity)
            # Conservative: scale by portfolio vol vs assumed 18% Nifty annual vol
            nifty_vol      = 0.18
            implied_beta   = port_std / nifty_vol * 0.85
            shock_pct      = mkt_shock * implied_beta * 100
            results[sc_name] = {
                "description":   sc_info["description"],
                "period":        sc_info["period"],
                "market_shock_pct":    round(mkt_shock * 100, 1),
                "portfolio_pnl_pct":   round(shock_pct, 2),
                "portfolio_pnl_method": "beta-scaled",
            }

        # Custom scenarios if provided
        if scenarios:
            for sc_name, sc_shocks in scenarios.items():
                pnl = 0.0
                for sym, shock in sc_shocks.items():
                    if sym in weights:
                        pnl += weights[sym] * shock
                results[sc_name] = {
                    "description":       "Custom scenario",
                    "portfolio_pnl_pct": round(pnl * 100, 2),
                    "shocks_applied":    sc_shocks,
                }

        # Historical worst periods from actual data
        port_returns_ts = ret_matrix @ w
        daily_pnl       = port_returns_ts
        worst_day       = float(daily_pnl.min())
        best_day        = float(daily_pnl.max())
        worst_week      = float(daily_pnl.rolling(5).sum().min())
        worst_month     = float(daily_pnl.rolling(21).sum().min())

        results["_historical_extremes"] = {
            "worst_single_day_pct":   round(worst_day * 100, 2),
            "best_single_day_pct":    round(best_day * 100, 2),
            "worst_week_pct":         round(worst_week * 100, 2),
            "worst_month_pct":        round(worst_month * 100, 2),
        }

        return results

    def rebalancing_signals(self, current_weights: Dict[str, float],
                            target_weights: Dict[str, float],
                            threshold: float = 0.05,
                            portfolio_value: float = 1_000_000.0) -> dict:
        """
        Detect drift and generate buy/sell signals.
        Only signals an asset if its weight has drifted > threshold from target.
        """
        all_syms = set(current_weights) | set(target_weights)
        signals: Dict[str, dict] = {}
        needs_rebal = False

        for sym in all_syms:
            curr  = current_weights.get(sym, 0.0)
            tgt   = target_weights.get(sym, 0.0)
            drift = curr - tgt

            if abs(drift) > threshold:
                action  = "SELL" if drift > 0 else "BUY"
                trade_v = abs(drift) * portfolio_value
                # Estimate cost: 0.122% round trip
                cost    = trade_v * 0.00122
                signals[sym] = {
                    "action":           action,
                    "current_weight":   round(curr, 4),
                    "target_weight":    round(tgt, 4),
                    "drift":            round(drift, 4),
                    "trade_value_inr":  round(trade_v, 2),
                    "estimated_cost_inr": round(cost, 2),
                }
                needs_rebal = True
            else:
                signals[sym] = {
                    "action":         "HOLD",
                    "current_weight": round(curr, 4),
                    "target_weight":  round(tgt, 4),
                    "drift":          round(drift, 4),
                }

        total_cost = sum(
            s["estimated_cost_inr"]
            for s in signals.values()
            if "estimated_cost_inr" in s
        )

        return {
            "needs_rebalancing":     needs_rebal,
            "threshold":             threshold,
            "signals":               signals,
            "total_estimated_cost_inr": round(total_cost, 2),
        }


# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────

class PortfolioOrchestrator:
    """
    Main API interface for portfolio optimisation and analysis.
    Wraps all optimisers into a unified interface.
    """

    def __init__(self):
        self.fetcher   = ReturnDataFetcher()
        self.mv        = MeanVarianceOptimizer()
        self.rp        = RiskParityOptimizer()
        self.cvar      = CVaROptimizer()
        self.analytics = PortfolioAnalytics()

    # ------------------------------------------------------------------
    def optimize_portfolio(self,
                           symbols: List[str],
                           method: str = "sharpe",
                           period: str = "3y",
                           constraints: Optional[Dict[str, Any]] = None,
                           views: Optional[Dict[str, float]] = None,
                           confidences: Optional[Dict[str, float]] = None,
                           market_caps: Optional[Dict[str, float]] = None,
                           cov_method: str = "ledoit_wolf",
                           return_method: str = "historical") -> dict:
        """
        Optimize portfolio using specified method.
        Methods: "sharpe" | "min_vol" | "risk_parity" | "black_litterman" | "cvar"
        """
        if not symbols:
            raise ValueError("symbols list cannot be empty")

        logger.info("Optimizing portfolio — %d symbols, method=%s", len(symbols), method)

        max_weight = (constraints or {}).get("max_weight", MAX_WEIGHT)
        self.mv.max_weight = max_weight

        # Fetch data
        returns  = self.fetcher.fetch_returns(symbols, period=period)
        avail    = [s for s in symbols if s in returns.columns]
        if not avail:
            raise ValueError("No return data available for provided symbols")

        returns  = returns[avail]
        cov_mat  = self.fetcher.get_covariance_matrix(returns, method=cov_method)
        mu       = self.fetcher.get_expected_returns(avail, method=return_method, period=period)

        if method == "sharpe":
            result = self.mv.maximize_sharpe(mu, cov_mat)
        elif method == "min_vol":
            result = self.mv.minimize_volatility(mu, cov_mat)
        elif method == "risk_parity":
            result = self.rp.optimize(cov_mat)
        elif method == "black_litterman":
            caps = market_caps or {s: 1.0 for s in avail}
            bl   = BlackLittermanOptimizer(caps, avail)
            result = bl.optimize(
                views=views or {},
                confidences=confidences or {},
                cov_matrix=cov_mat,
            )
        elif method == "cvar":
            target_ret = (constraints or {}).get("target_return")
            result = self.cvar.optimize(returns, target_return=target_ret,
                                        max_weight=max_weight)
        else:
            raise ValueError(f"Unknown method '{method}'")

        # Metrics
        weights = result["weights"]
        metrics = self.analytics.calculate_portfolio_metrics(weights, mu, cov_mat)
        risk_attr = self.analytics.calculate_risk_attribution(weights, cov_mat)

        # Efficient frontier for visualization
        frontier = self.mv.efficient_frontier(mu, cov_mat, n_points=30)

        # Monte Carlo cloud
        mc = self.mv.monte_carlo_frontier(mu, cov_mat, n_portfolios=2000)

        return {
            "method":           method,
            "symbols":          avail,
            "weights":          weights,
            "metrics":          metrics,
            "risk_attribution": risk_attr,
            "efficient_frontier": frontier,
            "monte_carlo":      {
                "max_sharpe":  mc["max_sharpe_portfolio"],
                "min_vol":     mc["min_vol_portfolio"],
                "n_simulated": mc["n_portfolios"],
            },
            "optimizer_output": {k: v for k, v in result.items() if k != "weights"},
        }

    # ------------------------------------------------------------------
    def analyze_existing_portfolio(self,
                                   holdings: Dict[str, int],
                                   period: str = "2y") -> dict:
        """
        Analyse an existing portfolio.
        holdings: {symbol: number_of_shares}
        Returns weights, risk metrics, correlation, rebalancing suggestions.
        """
        symbols = list(holdings.keys())
        if not symbols:
            raise ValueError("Holdings cannot be empty")

        prices_df = self.fetcher.fetch_price_series(symbols, period="5d")
        avail     = [s for s in symbols if s in prices_df.columns]
        if not avail:
            raise ValueError("Could not fetch price data for any holding")

        latest_prices = prices_df[avail].iloc[-1].to_dict()
        market_values = {s: holdings[s] * latest_prices[s] for s in avail}
        total_value   = sum(market_values.values())
        current_weights = {s: v / total_value for s, v in market_values.items()}

        # Returns and covariance
        returns  = self.fetcher.fetch_returns(avail, period=period)
        avail2   = [s for s in avail if s in returns.columns]
        returns  = returns[avail2]
        cov_mat  = self.fetcher.get_covariance_matrix(returns, "ledoit_wolf")
        mu       = self.fetcher.get_expected_returns(avail2, period=period)

        w_avail  = {s: current_weights.get(s, 0.0) for s in avail2}
        metrics  = self.analytics.calculate_portfolio_metrics(w_avail, mu, cov_mat)
        risk_attr = self.analytics.calculate_risk_attribution(w_avail, cov_mat)

        # Suggested optimal weights
        try:
            opt_result = self.mv.maximize_sharpe(mu, cov_mat)
            target_weights = opt_result["weights"]
        except Exception:
            target_weights = {s: 1.0 / len(avail2) for s in avail2}

        rebal = self.analytics.rebalancing_signals(
            current_weights=w_avail,
            target_weights=target_weights,
            portfolio_value=total_value,
        )

        stress = self.analytics.stress_test(w_avail, returns)

        corr_insights = self.get_correlation_insights(avail2, period=period)

        return {
            "holdings":           holdings,
            "current_prices":     {s: round(latest_prices.get(s, 0.0), 2) for s in avail},
            "market_values_inr":  {s: round(v, 2) for s, v in market_values.items()},
            "total_value_inr":    round(total_value, 2),
            "current_weights":    {s: round(v, 4) for s, v in current_weights.items()},
            "metrics":            metrics,
            "risk_attribution":   risk_attr,
            "optimal_weights":    target_weights,
            "rebalancing":        rebal,
            "stress_test":        stress,
            "correlation":        corr_insights,
        }

    # ------------------------------------------------------------------
    def get_correlation_insights(self, symbols: List[str],
                                 period: str = "2y") -> dict:
        """
        Correlation matrix analysis, highly-correlated pairs, and
        diversification score.
        """
        returns = self.fetcher.fetch_returns(symbols, period=period)
        avail   = [s for s in symbols if s in returns.columns]
        if not avail:
            return {"error": "No data available"}

        corr = returns[avail].corr()

        # Highly correlated pairs (|r| > 0.8)
        high_corr_pairs: List[dict] = []
        for i, s1 in enumerate(avail):
            for j, s2 in enumerate(avail):
                if i >= j:
                    continue
                r = corr.loc[s1, s2]
                if abs(r) > 0.8:
                    high_corr_pairs.append({
                        "symbol1": s1,
                        "symbol2": s2,
                        "correlation": round(float(r), 4),
                        "relationship": "strongly positive" if r > 0.8 else "strongly negative",
                    })

        # Diversification score (0-100)
        n  = len(avail)
        if n < 2:
            div_score = 0.0
        else:
            avg_corr  = corr.values[np.triu_indices(n, k=1)].mean()
            div_score = round((1 - avg_corr) * 100, 1)

        # Average pairwise correlation
        avg_pairwise = float(corr.values[np.triu_indices(n, k=1)].mean()) if n > 1 else 1.0

        # Cluster-like: most diversifying asset (lowest avg correlation to others)
        avg_corr_to_others = {
            s: float(corr[s].drop(s).abs().mean()) for s in avail
        }
        most_diversifying = min(avg_corr_to_others, key=avg_corr_to_others.get)
        least_diversifying = max(avg_corr_to_others, key=avg_corr_to_others.get)

        return {
            "correlation_matrix":    corr.round(4).to_dict(),
            "high_correlation_pairs": high_corr_pairs,
            "avg_pairwise_correlation": round(avg_pairwise, 4),
            "diversification_score_pct": div_score,
            "most_diversifying_asset":   most_diversifying,
            "least_diversifying_asset":  least_diversifying,
            "n_assets":                  n,
        }

    # ------------------------------------------------------------------
    def run_full_analysis(self,
                          symbols: List[str],
                          methods: Optional[List[str]] = None,
                          period: str = "3y") -> dict:
        """
        Run all optimization methods and return side-by-side comparison.
        """
        if methods is None:
            methods = ["sharpe", "min_vol", "risk_parity", "cvar"]

        results: Dict[str, dict] = {}
        for method in methods:
            try:
                r = self.optimize_portfolio(symbols, method=method, period=period)
                results[method] = {
                    "weights":  r["weights"],
                    "metrics":  r["metrics"],
                    "method_output": r.get("optimizer_output", {}),
                }
            except Exception as exc:
                logger.error("Method %s failed: %s", method, exc)
                results[method] = {"error": str(exc)}

        # Correlation insights once
        corr = self.get_correlation_insights(symbols, period=period)

        # Summary table
        summary = []
        for method, data in results.items():
            if "error" not in data:
                m = data.get("metrics", {})
                summary.append({
                    "method":              method,
                    "expected_return_pct": m.get("expected_return_pct"),
                    "expected_vol_pct":    m.get("expected_vol_pct"),
                    "sharpe_ratio":        m.get("sharpe_ratio"),
                    "hhi_concentration":   m.get("hhi_concentration"),
                })

        return {
            "symbols":     symbols,
            "period":      period,
            "methods":     results,
            "summary":     summary,
            "correlation": corr,
        }


# ─────────────────────────────────────────────────────────────────────────────
# CONVENIENCE ENTRY POINTS
# ─────────────────────────────────────────────────────────────────────────────

def optimize_portfolio(symbols: List[str],
                       method: str = "sharpe",
                       period: str = "3y",
                       **kwargs) -> dict:
    """Simple top-level function: optimize an Indian equity portfolio."""
    orch = PortfolioOrchestrator()
    return orch.optimize_portfolio(symbols, method=method, period=period, **kwargs)


def analyze_holdings(holdings: Dict[str, int], period: str = "2y") -> dict:
    """Analyse existing holdings by share count."""
    orch = PortfolioOrchestrator()
    return orch.analyze_existing_portfolio(holdings, period=period)


# ─────────────────────────────────────────────────────────────────────────────
# SMOKE TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    TEST_SYMBOLS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
                    "AXISBANK", "HINDUNILVR", "ITC", "WIPRO", "SBIN"]

    orch = PortfolioOrchestrator()

    print("Max-Sharpe optimization…")
    result = orch.optimize_portfolio(TEST_SYMBOLS, method="sharpe", period="2y")
    m = result["metrics"]
    print(f"  Expected Return : {m['expected_return_pct']}%")
    print(f"  Expected Vol    : {m['expected_vol_pct']}%")
    print(f"  Sharpe Ratio    : {m['sharpe_ratio']}")
    print(f"  Effective N     : {m['effective_n_stocks']}")
    print(f"  Top weights     : {sorted(result['weights'].items(), key=lambda x: -x[1])[:3]}")

    print("\nRisk Parity optimization…")
    result_rp = orch.optimize_portfolio(TEST_SYMBOLS, method="risk_parity", period="2y")
    print(f"  Portfolio Vol   : {result_rp['metrics']['expected_vol_pct']}%")

    print("\nCorrelation insights…")
    corr = orch.get_correlation_insights(TEST_SYMBOLS[:5], period="1y")
    print(f"  Diversification Score : {corr['diversification_score_pct']}%")
    print(f"  High-corr pairs       : {len(corr['high_correlation_pairs'])}")
    print("Done.")
