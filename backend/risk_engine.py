"""
Risk Management & Portfolio Risk Analytics Engine
Indian Hedge Fund Intelligence System
GARCH, VaR, Stress Testing, Factor Decomposition, Tail Risk.
All implemented from scratch using NumPy/Pandas/SciPy.
"""

import warnings
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf
from scipy import stats
from scipy.optimize import minimize
from scipy.stats import norm, t as student_t, jarque_bera, genextreme

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS FOR INDIAN MARKETS
# ─────────────────────────────────────────────────────────────────────────────

RISK_FREE_RATE_ANNUAL = 0.065   # ~6.5% RBI repo rate proxy
TRADING_DAYS_ANNUAL = 252
INDIA_VIX_SYMBOL = "^INDIAVIX"
NIFTY50_SYMBOL = "^NSEI"
NIFTY_BANK_SYMBOL = "^NSEBANK"
NIFTY_IT_SYMBOL = "^CNXIT"
NIFTY_PHARMA_SYMBOL = "^CNXPHARMA"
NIFTY_METAL_SYMBOL = "^CNXMETAL"
NIFTY_SMALLCAP_SYMBOL = "^CNXSC"
USDINR_SYMBOL = "USDINR=X"
CRUDE_SYMBOL = "CL=F"


def _annualize_vol(daily_vol: float) -> float:
    return daily_vol * np.sqrt(TRADING_DAYS_ANNUAL)


def _daily_rfr() -> float:
    return RISK_FREE_RATE_ANNUAL / TRADING_DAYS_ANNUAL


def _fetch_returns(symbols: list, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """Fetch adjusted close prices and compute log returns."""
    prices = {}
    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period=period, interval=interval)
            if not hist.empty:
                prices[sym] = hist["Close"]
        except Exception:
            pass

    if not prices:
        return pd.DataFrame()

    price_df = pd.DataFrame(prices).dropna(how="all")
    returns = np.log(price_df / price_df.shift(1)).dropna()
    return returns


# ─────────────────────────────────────────────────────────────────────────────
# GARCH VOLATILITY
# ─────────────────────────────────────────────────────────────────────────────

class GARCHVolatility:
    """GARCH(1,1) and EGARCH(1,1) models via Maximum Likelihood."""

    def _garch_log_likelihood(self, params: np.ndarray, returns: np.ndarray) -> float:
        """Negative log-likelihood for GARCH(1,1)."""
        omega, alpha, beta = params
        n = len(returns)

        if omega <= 0 or alpha < 0 or beta < 0 or alpha + beta >= 1:
            return 1e10

        sigma2 = np.zeros(n)
        sigma2[0] = np.var(returns)

        for t in range(1, n):
            sigma2[t] = omega + alpha * returns[t - 1] ** 2 + beta * sigma2[t - 1]
            if sigma2[t] <= 0:
                return 1e10

        llh = -0.5 * np.sum(np.log(2 * np.pi) + np.log(sigma2) + returns ** 2 / sigma2)
        return -llh  # minimize negative log-likelihood

    def fit_garch(self, returns: np.ndarray, p: int = 1, q: int = 1) -> dict:
        """Fit GARCH(1,1) via maximum likelihood."""
        returns = np.asarray(returns, dtype=float)
        returns = returns[np.isfinite(returns)]

        if len(returns) < 30:
            return {"error": "Insufficient data for GARCH fitting"}

        # Initial parameters
        var0 = np.var(returns)
        x0 = np.array([var0 * 0.05, 0.10, 0.85])
        bounds = [(1e-8, None), (0, 0.999), (0, 0.999)]
        constraints = [{"type": "ineq", "fun": lambda x: 0.999 - x[1] - x[2]}]

        try:
            result = minimize(
                self._garch_log_likelihood,
                x0,
                args=(returns,),
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
                options={"maxiter": 500, "ftol": 1e-9},
            )
            omega, alpha, beta = result.x
        except Exception as e:
            return {"error": f"Optimization failed: {str(e)}"}

        persistence = alpha + beta
        unconditional_var = omega / (1 - persistence) if persistence < 1 else var0

        # Current conditional variance
        n = len(returns)
        sigma2 = np.zeros(n)
        sigma2[0] = var0
        for t in range(1, n):
            sigma2[t] = omega + alpha * returns[t - 1] ** 2 + beta * sigma2[t - 1]

        current_sigma2 = sigma2[-1]

        # Forecast volatility: sigma^2_{t+h} = omega*(1+pers+...+pers^{h-1}) + pers^h * sigma^2_t
        forecasts = {}
        for h in [1, 5, 10, 21]:
            if persistence < 1:
                fwd_var = (omega * (1 - persistence ** h) / (1 - persistence) +
                           persistence ** h * current_sigma2)
            else:
                fwd_var = current_sigma2
            forecasts[f"{h}d_vol_annualized"] = round(_annualize_vol(np.sqrt(fwd_var)) * 100, 2)

        return {
            "omega": round(float(omega), 8),
            "alpha": round(float(alpha), 6),
            "beta": round(float(beta), 6),
            "persistence": round(float(persistence), 6),
            "unconditional_vol_annualized": round(_annualize_vol(np.sqrt(unconditional_var)) * 100, 2),
            "current_conditional_vol_annualized": round(_annualize_vol(np.sqrt(current_sigma2)) * 100, 2),
            "vol_forecasts": forecasts,
            "long_run_vol": round(_annualize_vol(np.sqrt(unconditional_var)) * 100, 2),
            "converged": result.success if hasattr(result, 'success') else True,
            "log_likelihood": round(float(-result.fun), 4),
        }

    def _egarch_log_likelihood(self, params: np.ndarray, returns: np.ndarray) -> float:
        """EGARCH(1,1) negative log-likelihood."""
        omega, alpha, gamma, beta = params
        n = len(returns)

        log_sigma2 = np.zeros(n)
        log_sigma2[0] = np.log(np.var(returns))

        for t in range(1, n):
            eps_prev = returns[t - 1] / np.exp(log_sigma2[t - 1] / 2 + 1e-8)
            log_sigma2[t] = (omega + alpha * abs(eps_prev) + gamma * eps_prev +
                             beta * log_sigma2[t - 1])

        sigma2 = np.exp(log_sigma2)
        if np.any(sigma2 <= 0) or not np.all(np.isfinite(sigma2)):
            return 1e10

        llh = -0.5 * np.sum(np.log(2 * np.pi) + log_sigma2 + returns ** 2 / sigma2)
        return -llh

    def fit_egarch(self, returns: np.ndarray) -> dict:
        """Fit EGARCH(1,1) — captures leverage effect (negative returns → higher vol)."""
        returns = np.asarray(returns, dtype=float)
        returns = returns[np.isfinite(returns)]

        if len(returns) < 30:
            return {"error": "Insufficient data for EGARCH fitting"}

        x0 = np.array([-0.1, 0.15, -0.1, 0.80])
        bounds = [(-1, 1), (0, 1), (-1, 0), (0, 0.999)]

        try:
            result = minimize(
                self._egarch_log_likelihood,
                x0,
                args=(returns,),
                method="L-BFGS-B",
                bounds=bounds,
                options={"maxiter": 500},
            )
            omega, alpha, gamma, beta = result.x
        except Exception as e:
            return {"error": f"EGARCH optimization failed: {str(e)}"}

        # gamma < 0 confirms leverage effect (negative shocks → larger vol)
        leverage_effect = gamma < 0

        return {
            "omega": round(float(omega), 8),
            "alpha": round(float(alpha), 6),
            "gamma": round(float(gamma), 6),
            "beta": round(float(beta), 6),
            "leverage_effect_present": bool(leverage_effect),
            "leverage_asymmetry": round(float(gamma), 6),
            "note": "Negative gamma confirms leverage effect (bad news amplifies volatility more than good news)",
            "converged": bool(result.success),
        }

    def calculate_realized_vol(self, returns: np.ndarray, window: int = 21) -> dict:
        """Rolling realized volatility."""
        returns = np.asarray(returns, dtype=float)
        returns = returns[np.isfinite(returns)]
        if len(returns) < window:
            return {"error": "Insufficient data"}

        rolling_vol = pd.Series(returns).rolling(window).std().dropna()
        current_vol = rolling_vol.iloc[-1]
        annualized = _annualize_vol(current_vol)

        # Percentile rank of current vol in historical distribution
        vol_percentile = stats.percentileofscore(rolling_vol.values, current_vol)

        return {
            "current_realized_vol_daily": round(float(current_vol) * 100, 4),
            "current_realized_vol_annualized": round(float(annualized) * 100, 2),
            "vol_percentile_rank": round(float(vol_percentile), 1),
            "vol_regime": (
                "VERY_HIGH" if vol_percentile > 80 else
                "HIGH" if vol_percentile > 60 else
                "MODERATE" if vol_percentile > 40 else
                "LOW" if vol_percentile > 20 else
                "VERY_LOW"
            ),
            "1m_avg_vol_annualized": round(_annualize_vol(rolling_vol.tail(21).mean()) * 100, 2),
            "3m_avg_vol_annualized": round(_annualize_vol(rolling_vol.tail(63).mean()) * 100, 2) if len(rolling_vol) >= 63 else None,
            "max_vol_1y_annualized": round(_annualize_vol(rolling_vol.max()) * 100, 2),
            "min_vol_1y_annualized": round(_annualize_vol(rolling_vol.min()) * 100, 2),
        }


# ─────────────────────────────────────────────────────────────────────────────
# VAR CALCULATOR
# ─────────────────────────────────────────────────────────────────────────────

class VaRCalculator:
    """Value at Risk and Expected Shortfall via Parametric, Historical, Monte Carlo."""

    def parametric_var(self, returns: np.ndarray, confidence: float = 0.99, horizon: int = 1) -> dict:
        """Parametric VaR assuming normal distribution."""
        returns = np.asarray(returns, dtype=float)
        returns = returns[np.isfinite(returns)]

        mu = np.mean(returns)
        sigma = np.std(returns, ddof=1)
        z = norm.ppf(1 - confidence)

        # 1-day VaR
        var_1d = -(mu + z * sigma)

        # Scale to horizon
        var_h = var_1d * np.sqrt(horizon)

        # CVaR (Expected Shortfall): expected loss given loss > VaR
        cvar_1d = -(mu - sigma * norm.pdf(norm.ppf(1 - confidence)) / (1 - confidence))
        cvar_h = cvar_1d * np.sqrt(horizon)

        return {
            "method": "parametric_normal",
            "confidence": confidence,
            "horizon_days": horizon,
            "var_1d_pct": round(var_1d * 100, 4),
            "var_horizon_pct": round(var_h * 100, 4),
            "cvar_1d_pct": round(cvar_1d * 100, 4),
            "cvar_horizon_pct": round(cvar_h * 100, 4),
            "daily_mean_return": round(mu * 100, 6),
            "daily_vol": round(sigma * 100, 4),
            "z_score": round(abs(z), 4),
        }

    def historical_var(self, returns: np.ndarray, confidence: float = 0.99, horizon: int = 1) -> dict:
        """Historical simulation VaR from empirical distribution."""
        returns = np.asarray(returns, dtype=float)
        returns = returns[np.isfinite(returns)]

        if len(returns) == 0:
            return {"error": "No returns data"}

        # Scale to horizon (square root of time approximation)
        horizon_returns = returns * np.sqrt(horizon)
        sorted_returns = np.sort(horizon_returns)

        # VaR
        var_level = np.percentile(sorted_returns, (1 - confidence) * 100)
        var = -var_level

        # CVaR: average of losses beyond VaR
        tail_losses = sorted_returns[sorted_returns <= var_level]
        cvar = -np.mean(tail_losses) if len(tail_losses) > 0 else var

        # Cornish-Fisher adjustment for fat tails
        mu = np.mean(returns)
        sigma = np.std(returns, ddof=1)
        skew = stats.skew(returns)
        kurt = stats.kurtosis(returns)
        z = norm.ppf(1 - confidence)
        z_cf = (z + (z ** 2 - 1) * skew / 6 +
                (z ** 3 - 3 * z) * kurt / 24 -
                (2 * z ** 3 - 5 * z) * skew ** 2 / 36)
        var_cf = -(mu + z_cf * sigma) * np.sqrt(horizon)

        return {
            "method": "historical_simulation",
            "confidence": confidence,
            "horizon_days": horizon,
            "observations": len(returns),
            "var_pct": round(var * 100, 4),
            "cvar_pct": round(cvar * 100, 4),
            "tail_observations": len(tail_losses),
            "worst_loss_pct": round(-sorted_returns[0] * 100, 4),
            "cornish_fisher_var_pct": round(var_cf * 100, 4),
        }

    def monte_carlo_var(self, returns: np.ndarray, confidence: float = 0.99,
                        n_sims: int = 10000, horizon: int = 1) -> dict:
        """Monte Carlo VaR using GARCH-estimated parameters."""
        returns = np.asarray(returns, dtype=float)
        returns = returns[np.isfinite(returns)]

        garch = GARCHVolatility()
        garch_params = garch.fit_garch(returns)

        if "error" in garch_params:
            # Fall back to normal simulation
            mu = np.mean(returns)
            sigma = np.std(returns, ddof=1)
            sims = np.random.normal(mu * horizon, sigma * np.sqrt(horizon), n_sims)
        else:
            omega = garch_params["omega"]
            alpha = garch_params["alpha"]
            beta = garch_params["beta"]
            current_var = (garch_params["current_conditional_vol_annualized"] / 100 / np.sqrt(TRADING_DAYS_ANNUAL)) ** 2
            mu = np.mean(returns)

            # Simulate horizon-day path returns
            np.random.seed(42)
            sims = np.zeros(n_sims)
            for sim in range(n_sims):
                sigma2_t = current_var
                path_return = 0
                for day in range(horizon):
                    eps = np.random.normal(0, np.sqrt(sigma2_t))
                    path_return += mu + eps
                    sigma2_t = omega + alpha * eps ** 2 + beta * sigma2_t
                sims[sim] = path_return

        var_level = np.percentile(sims, (1 - confidence) * 100)
        var = -var_level
        tail = sims[sims <= var_level]
        cvar = -np.mean(tail) if len(tail) > 0 else var

        return {
            "method": "monte_carlo_garch",
            "confidence": confidence,
            "horizon_days": horizon,
            "n_simulations": n_sims,
            "var_pct": round(var * 100, 4),
            "cvar_pct": round(cvar * 100, 4),
            "simulated_mean_pct": round(np.mean(sims) * 100, 4),
            "simulated_5th_pct": round(np.percentile(sims, 5) * 100, 4),
            "simulated_1st_pct": round(np.percentile(sims, 1) * 100, 4),
        }

    def portfolio_var(self, weights: dict, returns_df: pd.DataFrame,
                      confidence: float = 0.99, method: str = "historical") -> dict:
        """Multi-asset portfolio VaR with component and marginal VaR."""
        symbols = list(weights.keys())
        w = np.array([weights[s] for s in symbols])

        # Align
        avail = [s for s in symbols if s in returns_df.columns]
        if not avail:
            return {"error": "No matching symbols in returns_df"}

        ret_matrix = returns_df[avail].dropna()
        w_avail = np.array([weights[s] for s in avail])
        w_avail /= w_avail.sum()  # renormalize

        # Portfolio returns
        port_returns = (ret_matrix * w_avail).sum(axis=1).values

        if method == "historical":
            var_info = VaRCalculator().historical_var(port_returns, confidence)
        elif method == "parametric":
            var_info = VaRCalculator().parametric_var(port_returns, confidence)
        else:
            var_info = VaRCalculator().monte_carlo_var(port_returns, confidence)

        # Covariance matrix
        cov = ret_matrix.cov().values
        port_var_daily = w_avail @ cov @ w_avail
        port_vol_daily = np.sqrt(port_var_daily)

        # Component VaR
        z = norm.ppf(1 - confidence)
        marginal_var = cov @ w_avail / port_vol_daily * abs(z)
        component_var = w_avail * marginal_var

        total_undiversified_var = np.sum([
            abs(z) * np.sqrt(cov[i, i]) * w_avail[i]
            for i in range(len(avail))
        ])
        diversification_benefit = total_undiversified_var - port_vol_daily * abs(z)

        component_var_dict = {}
        for i, sym in enumerate(avail):
            component_var_dict[sym] = {
                "weight": round(float(w_avail[i]), 4),
                "component_var_pct": round(float(component_var[i]) * 100, 4),
                "marginal_var_pct": round(float(marginal_var[i]) * 100, 4),
                "risk_contribution_pct": round(float(component_var[i]) / (port_vol_daily * abs(z)) * 100, 2) if port_vol_daily > 0 else 0,
            }

        return {
            "portfolio_var": var_info,
            "component_var": component_var_dict,
            "portfolio_vol_daily_pct": round(port_vol_daily * 100, 4),
            "portfolio_vol_annualized_pct": round(_annualize_vol(port_vol_daily) * 100, 2),
            "diversification_benefit_pct": round(diversification_benefit * 100, 4),
            "concentration_hhi": round(float(np.sum(w_avail ** 2)), 4),
        }


# ─────────────────────────────────────────────────────────────────────────────
# STRESS TESTER
# ─────────────────────────────────────────────────────────────────────────────

class StressTester:
    """Historical and hypothetical scenario stress testing for Indian portfolios."""

    # Approximate historical market shocks (factor-based)
    HISTORICAL_SCENARIOS = {
        "COVID_2020_March": {
            "description": "COVID-19 crash - March 2020 (NIFTY -38%)",
            "nifty_shock": -0.38,
            "bank_shock": -0.45,
            "it_shock": -0.25,
            "pharma_shock": +0.05,
            "metal_shock": -0.42,
            "fmcg_shock": -0.20,
            "sector_map": {"HDFCBANK": -0.45, "ICICIBANK": -0.50, "AXISBANK": -0.55,
                           "TCS": -0.25, "INFY": -0.22, "WIPRO": -0.28,
                           "SUNPHARMA": +0.03, "DRREDDY": +0.08,
                           "RELIANCE": -0.35, "TATASTEEL": -0.48}
        },
        "NBFC_CRISIS_2018": {
            "description": "IL&FS / NBFC crisis - Sep-Oct 2018",
            "nifty_shock": -0.15,
            "bank_shock": -0.22,
            "it_shock": -0.08,
            "pharma_shock": -0.05,
            "metal_shock": -0.18,
            "fmcg_shock": -0.10,
            "sector_map": {"BAJFINANCE": -0.40, "HDFC": -0.20, "LICHSGFIN": -0.38,
                           "TCS": -0.08, "INFY": -0.07}
        },
        "DEMONETIZATION_2016": {
            "description": "Demonetization shock - Nov-Dec 2016",
            "nifty_shock": -0.08,
            "bank_shock": +0.05,
            "it_shock": -0.05,
            "pharma_shock": -0.06,
            "metal_shock": -0.12,
            "fmcg_shock": -0.15,
            "sector_map": {"SBIN": +0.12, "HDFCBANK": +0.03,
                           "HINDUNILVR": -0.15, "ITC": -0.12}
        },
        "LEHMAN_2008": {
            "description": "Global financial crisis - Oct 2008",
            "nifty_shock": -0.55,
            "bank_shock": -0.58,
            "it_shock": -0.40,
            "pharma_shock": -0.25,
            "metal_shock": -0.65,
            "fmcg_shock": -0.30,
            "sector_map": {}
        },
        "DOT_COM_2001": {
            "description": "Dot-com bust + 9/11 - 2001",
            "nifty_shock": -0.25,
            "bank_shock": -0.20,
            "it_shock": -0.60,
            "pharma_shock": +0.05,
            "metal_shock": -0.15,
            "fmcg_shock": -0.10,
            "sector_map": {}
        },
        "KARGIL_1999": {
            "description": "Kargil War crisis - 1999",
            "nifty_shock": -0.12,
            "bank_shock": -0.15,
            "it_shock": -0.10,
            "pharma_shock": -0.08,
            "metal_shock": -0.10,
            "fmcg_shock": -0.05,
            "sector_map": {}
        },
    }

    HYPOTHETICAL_SCENARIOS = {
        "RATE_HIKE_200BPS": {
            "description": "RBI emergency rate hike of 200bps",
            "sector_shocks": {
                "IT": -0.20, "BANK": -0.25, "REALTY": -0.30, "AUTO": -0.15,
                "FMCG": -0.08, "PHARMA": -0.03, "INFRA": -0.20, "NBFC": -0.35,
            }
        },
        "INR_DEPRECIATION_10PCT": {
            "description": "USD/INR moves from ~84 to ~92 (INR -10%)",
            "sector_shocks": {
                "IT": +0.15, "PHARMA": +0.12, "TEXTILE": +0.10, "METAL_EXPORTS": +0.08,
                "AUTO": -0.12, "PAINT": -0.15, "AVIATION": -0.20, "OIL_IMPORTS": -0.18,
            }
        },
        "CRUDE_SPIKE_50PCT": {
            "description": "Brent crude spikes from $80 to $120",
            "sector_shocks": {
                "OIL_GAS": +0.25, "ONGC": +0.30,
                "AUTO": -0.18, "AVIATION": -0.25, "PAINT": -0.20, "TYRE": -0.15,
                "SHIPPING": -0.12, "LOGISTICS": -0.10,
            }
        },
        "CHINA_CONFLICT": {
            "description": "India-China border conflict escalation",
            "sector_shocks": {
                "DEFENSE": +0.20, "BORDER_INFRA": +0.15,
                "IMPORT_DEPENDENT": -0.20, "ELECTRONICS": -0.25, "CHEMICAL": -0.15,
                "IT": -0.10, "METAL": -0.12,
            }
        },
        "MONSOON_FAILURE": {
            "description": "Below-normal monsoon, drought conditions",
            "sector_shocks": {
                "AGRI": -0.20, "FMCG_RURAL": -0.15, "MICRO_FINANCE": -0.25,
                "TRACTOR": -0.20, "FERTILIZER": +0.10, "IRRIGATION": +0.08,
                "CONSUMER_STAPLES": -0.08,
            }
        },
        "US_RECESSION": {
            "description": "US enters deep recession",
            "sector_shocks": {
                "IT": -0.30, "TCS": -0.28, "INFY": -0.32, "WIPRO": -0.35,
                "METALS": -0.25, "PHARMA_US_EXPOSED": -0.15,
                "DOMESTIC_CONSUMPTION": -0.05, "NIFTY_OVERALL": -0.20,
            }
        },
    }

    def _apply_beta_adjusted_shock(self, weights: dict, sector_shock: float,
                                   betas: dict, default_beta: float = 1.0) -> float:
        """Apply a market-level shock to a portfolio using beta-adjusted returns."""
        pnl = 0.0
        for sym, wt in weights.items():
            beta = betas.get(sym, default_beta)
            pnl += wt * beta * sector_shock
        return pnl

    def historical_scenarios(self, returns_df: pd.DataFrame, weights: dict) -> dict:
        """Apply pre-defined Indian market historical stress scenarios."""
        symbols = list(weights.keys())
        results = {}

        # Calculate betas against NIFTY from returns
        betas = {}
        if "^NSEI" in returns_df.columns:
            nifty_ret = returns_df["^NSEI"]
            nifty_var = nifty_ret.var()
            for sym in symbols:
                if sym in returns_df.columns and nifty_var > 0:
                    cov = returns_df[sym].cov(nifty_ret)
                    betas[sym] = cov / nifty_var
                else:
                    betas[sym] = 1.0
        else:
            betas = {s: 1.0 for s in symbols}

        for scenario_name, scenario in self.HISTORICAL_SCENARIOS.items():
            nifty_shock = scenario["nifty_shock"]
            sector_map = scenario.get("sector_map", {})

            portfolio_pnl = 0.0
            stock_pnl = {}

            for sym, wt in weights.items():
                # Use specific shock if available, else use beta-adjusted NIFTY shock
                if sym in sector_map:
                    shock = sector_map[sym]
                else:
                    beta = betas.get(sym, 1.0)
                    shock = nifty_shock * beta

                stock_pnl[sym] = round(shock * wt * 100, 2)
                portfolio_pnl += wt * shock

            results[scenario_name] = {
                "description": scenario["description"],
                "nifty_shock_pct": round(nifty_shock * 100, 1),
                "portfolio_pnl_pct": round(portfolio_pnl * 100, 2),
                "stock_contributions_pct": stock_pnl,
                "severity": (
                    "EXTREME" if portfolio_pnl < -0.30 else
                    "SEVERE" if portfolio_pnl < -0.20 else
                    "MODERATE" if portfolio_pnl < -0.10 else
                    "MILD"
                ),
            }

        # Sort by severity (most severe first)
        sorted_results = dict(sorted(results.items(),
                                     key=lambda x: x[1]["portfolio_pnl_pct"]))
        return {
            "scenarios": sorted_results,
            "worst_case": list(sorted_results.keys())[0] if sorted_results else None,
            "best_case_among_bad": list(sorted_results.keys())[-1] if sorted_results else None,
        }

    def hypothetical_scenarios(self, returns_df: pd.DataFrame, weights: dict) -> dict:
        """Forward-looking hypothetical stress scenarios."""
        results = {}

        # Sector classification (simplified mapping)
        IT_STOCKS = {"TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM", "OFSS"}
        BANK_STOCKS = {"HDFCBANK", "ICICIBANK", "AXISBANK", "SBIN", "KOTAKBANK", "INDUSINDBK", "BANKBARODA"}
        PHARMA_STOCKS = {"SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "APOLLOHOSP"}
        AUTO_STOCKS = {"MARUTI", "TATAMOTORS", "EICHERMOT", "HEROMOTOCO", "MM", "TVSMOTOR"}
        METAL_STOCKS = {"TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "SAIL", "COALINDIA"}

        def _get_sector_shock(sym: str, scenario: dict) -> float:
            sector_shocks = scenario.get("sector_shocks", {})
            if sym in IT_STOCKS and "IT" in sector_shocks:
                return sector_shocks["IT"]
            if sym in BANK_STOCKS and "BANK" in sector_shocks:
                return sector_shocks["BANK"]
            if sym in PHARMA_STOCKS and "PHARMA" in sector_shocks:
                return sector_shocks.get("PHARMA", sector_shocks.get("PHARMA_US_EXPOSED", 0))
            if sym in AUTO_STOCKS and "AUTO" in sector_shocks:
                return sector_shocks["AUTO"]
            if sym in METAL_STOCKS and "METALS" in sector_shocks:
                return sector_shocks["METALS"]
            return sector_shocks.get("NIFTY_OVERALL", -0.05)

        for scenario_name, scenario in self.HYPOTHETICAL_SCENARIOS.items():
            portfolio_pnl = 0.0
            stock_pnl = {}

            for sym, wt in weights.items():
                shock = _get_sector_shock(sym, scenario)
                stock_pnl[sym] = round(shock * wt * 100, 2)
                portfolio_pnl += wt * shock

            results[scenario_name] = {
                "description": scenario["description"],
                "portfolio_pnl_pct": round(portfolio_pnl * 100, 2),
                "stock_contributions_pct": stock_pnl,
                "severity": (
                    "EXTREME" if portfolio_pnl < -0.30 else
                    "SEVERE" if portfolio_pnl < -0.20 else
                    "MODERATE" if portfolio_pnl < -0.10 else
                    "MILD" if portfolio_pnl < 0 else
                    "POSITIVE"
                ),
            }

        return {
            "scenarios": results,
            "worst_case": min(results.keys(), key=lambda x: results[x]["portfolio_pnl_pct"]) if results else None,
        }

    def sensitivity_analysis(self, portfolio_weights: dict, returns_df: pd.DataFrame) -> dict:
        """Sensitivity of portfolio to key market factors."""
        symbols = list(portfolio_weights.keys())
        w = np.array([portfolio_weights[s] for s in symbols if s in returns_df.columns])
        syms_avail = [s for s in symbols if s in returns_df.columns]

        if not syms_avail:
            return {"error": "No matching symbols"}

        ret_matrix = returns_df[syms_avail].dropna()
        port_returns = (ret_matrix * (w / w.sum())).sum(axis=1)

        sensitivities = {}

        factor_map = {
            "NIFTY50": "^NSEI",
            "USD_INR": "USDINR=X",
            "CRUDE_OIL": "CL=F",
        }

        for factor_name, factor_sym in factor_map.items():
            if factor_sym in returns_df.columns:
                factor_ret = returns_df[factor_sym].reindex(port_returns.index).dropna()
                aligned_port = port_returns.reindex(factor_ret.index).dropna()
                if len(factor_ret) > 10 and len(aligned_port) > 10:
                    common = factor_ret.index.intersection(aligned_port.index)
                    if len(common) > 10:
                        slope, intercept, r, p, se = stats.linregress(
                            factor_ret.loc[common].values,
                            aligned_port.loc[common].values
                        )
                        sensitivities[factor_name] = {
                            "beta": round(float(slope), 4),
                            "alpha_daily": round(float(intercept) * 100, 6),
                            "r_squared": round(float(r ** 2), 4),
                            "p_value": round(float(p), 4),
                            "1pct_move_impact_pct": round(float(slope) * 1.0, 4),
                        }

        # NIFTY50 sensitivity
        if "^NSEI" in returns_df.columns:
            nifty = returns_df["^NSEI"].reindex(port_returns.index).dropna()
            common = nifty.index.intersection(port_returns.index)
            if len(common) > 10:
                s, i, r, p, se = stats.linregress(nifty.loc[common].values, port_returns.loc[common].values)
                sensitivities["NIFTY50_SENSITIVITY"] = {
                    "portfolio_beta": round(float(s), 4),
                    "for_1pct_nifty_move_portfolio_moves_pct": round(float(s), 4),
                }

        return {
            "factor_sensitivities": sensitivities,
            "interpretation": "Beta > 1 means portfolio amplifies factor moves; < 1 means dampens",
        }


# ─────────────────────────────────────────────────────────────────────────────
# FACTOR RISK DECOMPOSITION
# ─────────────────────────────────────────────────────────────────────────────

class FactorRiskDecomposition:
    """OLS factor decomposition and Fama-French factor analysis."""

    def decompose(self, returns: pd.DataFrame, factor_returns: pd.DataFrame) -> dict:
        """Regress each stock against market factors."""
        stock_symbols = returns.columns.tolist()
        factor_symbols = factor_returns.columns.tolist()

        # Align dates
        common_idx = returns.index.intersection(factor_returns.index)
        if len(common_idx) < 30:
            return {"error": "Insufficient overlapping data"}

        stock_ret = returns.loc[common_idx]
        factor_ret = factor_returns.loc[common_idx]

        results = {}
        for sym in stock_symbols:
            if sym not in stock_ret.columns:
                continue
            y = stock_ret[sym].values
            mask = np.isfinite(y)
            y = y[mask]
            X_raw = factor_ret.values[mask]

            # Add intercept
            X = np.column_stack([np.ones(len(y)), X_raw])
            if len(y) < 30 or X.shape[1] > len(y):
                continue

            try:
                # OLS: (X'X)^-1 X'y
                XtX = X.T @ X
                Xty = X.T @ y
                betas = np.linalg.lstsq(XtX, Xty, rcond=None)[0]

                y_hat = X @ betas
                residuals = y - y_hat
                ss_res = np.sum(residuals ** 2)
                ss_tot = np.sum((y - y.mean()) ** 2)
                r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0

                total_var = np.var(y)
                idio_var = np.var(residuals)
                systematic_var = total_var - idio_var

                factor_betas = {}
                for j, fname in enumerate(factor_symbols):
                    factor_betas[fname] = round(float(betas[j + 1]), 4)

                results[sym] = {
                    "alpha_daily": round(float(betas[0]) * 100, 6),
                    "factor_betas": factor_betas,
                    "r_squared": round(float(r_squared), 4),
                    "idiosyncratic_var_pct": round(float(idio_var / total_var * 100) if total_var > 0 else 0, 2),
                    "systematic_var_pct": round(float(systematic_var / total_var * 100) if total_var > 0 else 0, 2),
                    "annualized_idio_vol": round(_annualize_vol(np.sqrt(idio_var)) * 100, 2),
                }
            except Exception as e:
                results[sym] = {"error": str(e)}

        return {
            "stock_factor_exposures": results,
            "factors_used": factor_symbols,
            "observations": len(common_idx),
        }

    def calculate_fama_french_factors(self, returns_df: pd.DataFrame) -> dict:
        """Approximate Fama-French 3-factor model for Indian markets."""
        try:
            # Download factor proxies
            nifty = yf.Ticker("^NSEI").history(period="1y")["Close"].pct_change().dropna()
            smallcap = yf.Ticker("^CNXSC").history(period="1y")["Close"].pct_change().dropna()
            nifty50 = yf.Ticker("^NSEI").history(period="1y")["Close"].pct_change().dropna()
            next50 = yf.Ticker("^NSMIDCP").history(period="1y")["Close"].pct_change().dropna()

            rfr_daily = _daily_rfr()

            # Market factor
            mkt_rf = nifty - rfr_daily

            # SMB proxy: small cap minus large cap
            common = smallcap.index.intersection(nifty50.index)
            smb = (smallcap.reindex(common) - nifty50.reindex(common))

            # HML proxy: value factor (hard to compute exactly without B/P ratios)
            # Use NiftyNext50 - Nifty50 as a rough value/mid proxy
            if len(next50) > 10:
                common2 = next50.index.intersection(nifty50.index)
                hml_proxy = next50.reindex(common2) - nifty50.reindex(common2)
            else:
                hml_proxy = pd.Series(dtype=float)

            # Run 3-factor regression for each stock
            stock_factor_loadings = {}
            for sym in returns_df.columns:
                y = returns_df[sym]
                common_all = y.index.intersection(mkt_rf.index)
                if len(common_all) < 30:
                    continue

                y_aligned = y.reindex(common_all).values
                mkt_aligned = mkt_rf.reindex(common_all).values

                # 2-factor: market + SMB if available
                smb_common = smb.index.intersection(common_all)
                if len(smb_common) > 30:
                    smb_aligned = smb.reindex(common_all).fillna(0).values
                    X = np.column_stack([np.ones(len(y_aligned)), mkt_aligned, smb_aligned])
                else:
                    X = np.column_stack([np.ones(len(y_aligned)), mkt_aligned])

                mask = np.isfinite(y_aligned) & np.all(np.isfinite(X), axis=1)
                if mask.sum() < 20:
                    continue

                try:
                    betas = np.linalg.lstsq(X[mask], y_aligned[mask], rcond=None)[0]
                    stock_factor_loadings[sym] = {
                        "alpha": round(float(betas[0]) * 252 * 100, 2),
                        "market_beta": round(float(betas[1]), 4),
                        "smb_loading": round(float(betas[2]), 4) if len(betas) > 2 else None,
                        "interpretation": {
                            "market_beta": "Market sensitivity",
                            "smb_loading": "Positive = small-cap tilt, Negative = large-cap tilt",
                        }
                    }
                except Exception:
                    pass

            return {
                "model": "Approximate Fama-French for Indian Markets",
                "factors": {
                    "MKT_RF": "NIFTY50 excess return over risk-free rate",
                    "SMB": "NIFTY Smallcap - NIFTY50 return",
                    "HML_PROXY": "NIFTY Next50 - NIFTY50 return",
                },
                "stock_loadings": stock_factor_loadings,
            }

        except Exception as e:
            return {"error": f"Fama-French calculation failed: {str(e)}"}


# ─────────────────────────────────────────────────────────────────────────────
# DRAWDOWN ANALYZER
# ─────────────────────────────────────────────────────────────────────────────

class DrawdownAnalyzer:
    """Comprehensive drawdown analytics."""

    def calculate(self, equity_curve: pd.Series) -> dict:
        """All drawdown periods with depth, duration, recovery."""
        equity = equity_curve.dropna()
        if len(equity) == 0:
            return {"error": "Empty equity curve"}

        running_max = equity.cummax()
        underwater = (equity - running_max) / running_max

        # Find drawdown periods
        drawdown_periods = []
        in_drawdown = False
        dd_start = None
        dd_trough_val = 0
        dd_trough_date = None

        for i in range(len(equity)):
            uw = underwater.iloc[i]
            if uw < 0 and not in_drawdown:
                in_drawdown = True
                dd_start = equity.index[i]
                dd_trough_val = uw
                dd_trough_date = equity.index[i]
            elif in_drawdown:
                if uw < dd_trough_val:
                    dd_trough_val = uw
                    dd_trough_date = equity.index[i]
                if uw == 0:
                    # Recovered
                    recovery_date = equity.index[i]
                    start_idx = equity.index.get_loc(dd_start)
                    trough_idx = equity.index.get_loc(dd_trough_date)
                    end_idx = i
                    drawdown_periods.append({
                        "start": str(dd_start.date()) if hasattr(dd_start, 'date') else str(dd_start),
                        "trough": str(dd_trough_date.date()) if hasattr(dd_trough_date, 'date') else str(dd_trough_date),
                        "recovery": str(recovery_date.date()) if hasattr(recovery_date, 'date') else str(recovery_date),
                        "max_depth_pct": round(dd_trough_val * 100, 2),
                        "duration_to_trough_days": trough_idx - start_idx,
                        "recovery_days": end_idx - trough_idx,
                        "total_duration_days": end_idx - start_idx,
                    })
                    in_drawdown = False
                    dd_start = None

        # If still in drawdown at end
        if in_drawdown and dd_start is not None:
            start_idx = equity.index.get_loc(dd_start)
            trough_idx = equity.index.get_loc(dd_trough_date)
            drawdown_periods.append({
                "start": str(dd_start.date()) if hasattr(dd_start, 'date') else str(dd_start),
                "trough": str(dd_trough_date.date()) if hasattr(dd_trough_date, 'date') else str(dd_trough_date),
                "recovery": "ONGOING",
                "max_depth_pct": round(dd_trough_val * 100, 2),
                "duration_to_trough_days": trough_idx - start_idx,
                "recovery_days": None,
                "total_duration_days": len(equity) - 1 - start_idx,
            })

        max_dd = underwater.min()
        avg_dd = underwater[underwater < 0].mean() if (underwater < 0).any() else 0

        # Calmar ratio
        annual_return = (equity.iloc[-1] / equity.iloc[0]) ** (252 / len(equity)) - 1
        calmar = annual_return / abs(max_dd) if max_dd != 0 else 0

        completed = [d for d in drawdown_periods if d["recovery"] != "ONGOING"]
        avg_recovery = np.mean([d["recovery_days"] for d in completed if d["recovery_days"] is not None]) if completed else None

        return {
            "max_drawdown_pct": round(float(max_dd) * 100, 2),
            "avg_drawdown_pct": round(float(avg_dd) * 100, 2),
            "calmar_ratio": round(float(calmar), 4),
            "total_drawdown_periods": len(drawdown_periods),
            "avg_recovery_days": round(avg_recovery, 1) if avg_recovery else None,
            "currently_in_drawdown": in_drawdown,
            "current_drawdown_pct": round(float(underwater.iloc[-1]) * 100, 2),
            "drawdown_periods": drawdown_periods[-10:],
        }

    def underwater_curve(self, equity_curve: pd.Series) -> list:
        """Percentage below all-time-high at each date."""
        equity = equity_curve.dropna()
        running_max = equity.cummax()
        underwater = (equity - running_max) / running_max * 100
        return [
            {"date": str(equity.index[i].date()) if hasattr(equity.index[i], 'date') else str(equity.index[i]),
             "underwater_pct": round(float(underwater.iloc[i]), 3)}
            for i in range(len(equity))
        ]

    def calculate_pain_index(self, equity_curve: pd.Series) -> float:
        """Pain index = average of all underwater values (sum of underwater / n)."""
        equity = equity_curve.dropna()
        running_max = equity.cummax()
        underwater = (equity - running_max) / running_max
        pain = abs(underwater.mean())
        return round(float(pain) * 100, 4)


# ─────────────────────────────────────────────────────────────────────────────
# TAIL RISK ANALYZER
# ─────────────────────────────────────────────────────────────────────────────

class TailRiskAnalyzer:
    """Higher-moment risk, EVT, and copula-based tail dependence."""

    def calculate_tail_risk(self, returns: np.ndarray) -> dict:
        """Skewness, kurtosis, Jarque-Bera, tail percentiles, tail ratio."""
        returns = np.asarray(returns, dtype=float)
        returns = returns[np.isfinite(returns)]

        if len(returns) < 20:
            return {"error": "Insufficient data"}

        skew = float(stats.skew(returns))
        kurt = float(stats.kurtosis(returns))  # excess kurtosis
        jb_stat, jb_pvalue = jarque_bera(returns)

        p1 = np.percentile(returns, 1)
        p5 = np.percentile(returns, 5)
        p95 = np.percentile(returns, 95)
        p99 = np.percentile(returns, 99)

        tail_ratio = abs(p95) / abs(p5) if p5 != 0 else None

        return {
            "skewness": round(skew, 4),
            "excess_kurtosis": round(kurt, 4),
            "skewness_interpretation": "Negative skew (more large losses than gains)" if skew < 0 else "Positive skew",
            "kurtosis_interpretation": "Fat-tailed (leptokurtic)" if kurt > 0 else "Thin-tailed",
            "jarque_bera_stat": round(float(jb_stat), 4),
            "jarque_bera_pvalue": round(float(jb_pvalue), 6),
            "normality_rejected": jb_pvalue < 0.05,
            "1st_percentile_loss_pct": round(abs(p1) * 100, 4),
            "5th_percentile_loss_pct": round(abs(p5) * 100, 4),
            "95th_percentile_gain_pct": round(p95 * 100, 4),
            "99th_percentile_loss_pct": round(abs(p1) * 100, 4),
            "tail_ratio": round(tail_ratio, 4) if tail_ratio else None,
            "tail_ratio_interpretation": "< 1 means losses exceed gains in tail (typical for stocks)",
        }

    def extreme_value_theory(self, returns: np.ndarray) -> dict:
        """Generalized Extreme Value distribution for tail estimation."""
        returns = np.asarray(returns, dtype=float)
        returns = returns[np.isfinite(returns)]

        if len(returns) < 50:
            return {"error": "Need at least 50 observations for EVT"}

        losses = -returns  # flip to positive losses

        # Block maxima: use monthly (21-day) maxima
        block_size = 21
        n_blocks = len(losses) // block_size
        if n_blocks < 10:
            return {"error": "Insufficient blocks for GEV fitting"}

        block_maxima = np.array([
            losses[i * block_size:(i + 1) * block_size].max()
            for i in range(n_blocks)
        ])

        try:
            # Fit GEV distribution
            shape, loc, scale = genextreme.fit(block_maxima)

            # 99.9% VaR from GEV
            var_999 = float(genextreme.ppf(0.999, shape, loc=loc, scale=scale))

            # Return period calculation
            return_period_100d = float(genextreme.ppf(1 - 1 / 100, shape, loc=loc, scale=scale))

            return {
                "gev_shape_xi": round(float(shape), 6),
                "gev_location_mu": round(float(loc), 6),
                "gev_scale_sigma": round(float(scale), 6),
                "tail_index": round(float(shape), 6),
                "tail_type": (
                    "Frechet (fat tails)" if shape > 0 else
                    "Gumbel (exponential tails)" if abs(shape) < 0.01 else
                    "Weibull (thin tails)"
                ),
                "evt_var_999_pct": round(var_999 * 100, 4),
                "100d_return_level_pct": round(return_period_100d * 100, 4),
                "blocks_used": n_blocks,
                "block_size_days": block_size,
            }
        except Exception as e:
            return {"error": f"GEV fitting failed: {str(e)}"}

    def copula_analysis(self, returns_df: pd.DataFrame) -> dict:
        """Tail dependence between assets — how correlated are they in crashes."""
        symbols = returns_df.columns.tolist()
        n = len(symbols)

        if n < 2:
            return {"error": "Need at least 2 assets for copula analysis"}

        returns_clean = returns_df.dropna()

        # Transform to uniform marginals (empirical CDF)
        uniform_margins = pd.DataFrame(index=returns_clean.index)
        for sym in symbols:
            u = returns_clean[sym].rank() / (len(returns_clean) + 1)
            uniform_margins[sym] = u

        # Lower tail dependence coefficient (crashes): P(U < q | V < q) as q→0
        q_low = 0.10   # 10th percentile threshold
        q_high = 0.90  # 90th percentile threshold

        tail_dep = {}
        for i in range(n):
            for j in range(i + 1, n):
                s1, s2 = symbols[i], symbols[j]
                u1 = uniform_margins[s1].values
                u2 = uniform_margins[s2].values

                # Lower tail: both below q
                joint_low = np.mean((u1 < q_low) & (u2 < q_low))
                lambda_lower = joint_low / q_low if q_low > 0 else 0

                # Upper tail: both above 1-q
                joint_high = np.mean((u1 > q_high) & (u2 > q_high))
                lambda_upper = joint_high / (1 - q_high) if (1 - q_high) > 0 else 0

                # Normal correlation for comparison
                normal_corr = float(returns_clean[s1].corr(returns_clean[s2]))

                pair_key = f"{s1}_{s2}"
                tail_dep[pair_key] = {
                    "lower_tail_dependence": round(float(lambda_lower), 4),
                    "upper_tail_dependence": round(float(lambda_upper), 4),
                    "normal_correlation": round(normal_corr, 4),
                    "crash_amplification": round(float(lambda_lower) / abs(normal_corr) if normal_corr != 0 else 0, 3),
                    "interpretation": (
                        "HIGH crash correlation (diversification fails in crashes)"
                        if lambda_lower > 0.5 else
                        "MODERATE tail dependence"
                        if lambda_lower > 0.25 else
                        "LOW tail dependence (good diversification in crashes)"
                    ),
                }

        # Overall portfolio tail risk summary
        all_lower = [v["lower_tail_dependence"] for v in tail_dep.values()]
        avg_lower_tail = np.mean(all_lower) if all_lower else 0

        return {
            "pairwise_tail_dependence": tail_dep,
            "avg_lower_tail_dependence": round(float(avg_lower_tail), 4),
            "portfolio_tail_risk": (
                "HIGH — Stocks likely to crash together" if avg_lower_tail > 0.5 else
                "MODERATE — Some diversification in crashes" if avg_lower_tail > 0.25 else
                "LOW — Good diversification even in extreme events"
            ),
        }


# ─────────────────────────────────────────────────────────────────────────────
# RISK BUDGET OPTIMIZER
# ─────────────────────────────────────────────────────────────────────────────

class RiskBudgetOptimizer:
    """Risk parity and risk budget allocation."""

    def calculate_risk_budget(self, current_weights: dict, cov_matrix: pd.DataFrame) -> dict:
        """Current risk contribution % per asset."""
        symbols = [s for s in current_weights.keys() if s in cov_matrix.columns]
        if not symbols:
            return {"error": "No matching symbols in covariance matrix"}

        w = np.array([current_weights[s] for s in symbols])
        w = w / w.sum()

        cov = cov_matrix.loc[symbols, symbols].values
        port_var = w @ cov @ w
        port_vol = np.sqrt(port_var)

        # Marginal contribution to risk
        mcr = cov @ w / port_vol if port_vol > 0 else np.zeros(len(w))
        # Component contribution to risk
        ccr = w * mcr
        # Risk contribution %
        risk_contrib_pct = ccr / port_vol * 100 if port_vol > 0 else np.zeros(len(w))

        result = {}
        for i, sym in enumerate(symbols):
            result[sym] = {
                "weight_pct": round(float(w[i]) * 100, 2),
                "risk_contribution_pct": round(float(risk_contrib_pct[i]), 2),
                "marginal_contribution": round(float(mcr[i]) * 100, 6),
                "risk_vs_weight_ratio": round(float(risk_contrib_pct[i]) / (w[i] * 100) if w[i] > 0 else 0, 3),
            }

        # HHI of risk concentration
        rc_fracs = np.array([v["risk_contribution_pct"] / 100 for v in result.values()])
        hhi = float(np.sum(rc_fracs ** 2))

        return {
            "risk_contributions": result,
            "portfolio_vol_daily_pct": round(port_vol * 100, 4),
            "portfolio_vol_annual_pct": round(_annualize_vol(port_vol) * 100, 2),
            "risk_concentration_hhi": round(hhi, 4),
            "equal_risk_budget_hhi": round(1 / len(symbols), 4),
            "concentration_vs_equal_risk": "CONCENTRATED" if hhi > 2 / len(symbols) else "DIVERSIFIED",
        }

    def suggest_risk_budget_rebalancing(self, current_weights: dict,
                                         target_risk_budget: dict,
                                         cov_matrix: pd.DataFrame) -> dict:
        """Calculate weight adjustments needed to hit target risk budget."""
        symbols = [s for s in current_weights.keys() if s in cov_matrix.columns]
        if not symbols:
            return {"error": "No matching symbols"}

        current_rb = self.calculate_risk_budget(current_weights, cov_matrix)
        if "error" in current_rb:
            return current_rb

        # Normalize target budget
        target_total = sum(target_risk_budget.get(s, 1 / len(symbols)) for s in symbols)
        target_normalized = {s: target_risk_budget.get(s, 1 / len(symbols)) / target_total
                             for s in symbols}

        suggestions = {}
        for sym in symbols:
            current_rc = current_rb["risk_contributions"].get(sym, {}).get("risk_contribution_pct", 0) / 100
            target_rc = target_normalized.get(sym, 1 / len(symbols))
            current_wt = current_weights.get(sym, 0)

            # Simple heuristic: if over-budget in risk, reduce weight proportionally
            if current_rc > 0:
                suggested_wt = current_wt * (target_rc / current_rc)
            else:
                suggested_wt = current_wt

            suggestions[sym] = {
                "current_weight_pct": round(current_wt * 100, 2),
                "current_risk_contrib_pct": round(current_rc * 100, 2),
                "target_risk_budget_pct": round(target_rc * 100, 2),
                "suggested_weight_pct": round(suggested_wt * 100, 2),
                "weight_change_pct": round((suggested_wt - current_wt) * 100, 2),
                "action": "REDUCE" if suggested_wt < current_wt else "INCREASE",
            }

        return {
            "rebalancing_suggestions": suggestions,
            "note": "Suggestions are heuristic approximations. True risk parity requires iterative optimization.",
        }


# ─────────────────────────────────────────────────────────────────────────────
# RISK DASHBOARD (MAIN API INTERFACE)
# ─────────────────────────────────────────────────────────────────────────────

class RiskDashboard:
    """Main entry point for portfolio and individual stock risk analytics."""

    def __init__(self):
        self.garch = GARCHVolatility()
        self.var_calc = VaRCalculator()
        self.stress_tester = StressTester()
        self.factor_risk = FactorRiskDecomposition()
        self.drawdown = DrawdownAnalyzer()
        self.tail_risk = TailRiskAnalyzer()
        self.risk_budget = RiskBudgetOptimizer()

    def get_portfolio_risk(self, symbols: list, weights: dict = None) -> dict:
        """
        Comprehensive portfolio risk report.
        symbols: list of NSE symbols (without .NS)
        weights: dict {symbol: weight} (equal weight if None)
        """
        if not symbols:
            return {"error": "No symbols provided"}

        # Normalize weights
        if weights is None:
            weights = {s: 1 / len(symbols) for s in symbols}
        else:
            total = sum(weights.values())
            weights = {k: v / total for k, v in weights.items()}

        # Fetch data
        ns_symbols = [f"{s}.NS" for s in symbols]
        all_symbols_to_fetch = ns_symbols + [NIFTY50_SYMBOL, NIFTY_BANK_SYMBOL,
                                              NIFTY_IT_SYMBOL, CRUDE_SYMBOL, USDINR_SYMBOL]

        returns_df = _fetch_returns(all_symbols_to_fetch, period="1y")

        # Map NS symbols to original
        rename_map = {f"{s}.NS": s for s in symbols}
        returns_df = returns_df.rename(columns=rename_map)

        if returns_df.empty:
            return {"error": "Failed to fetch returns data"}

        # Portfolio returns
        avail_symbols = [s for s in symbols if s in returns_df.columns]
        if not avail_symbols:
            return {"error": "No data for any symbol"}

        w_avail = {s: weights[s] for s in avail_symbols}
        total_w = sum(w_avail.values())
        w_avail = {s: v / total_w for s, v in w_avail.items()}

        w_array = np.array([w_avail[s] for s in avail_symbols])
        port_returns = (returns_df[avail_symbols] * w_array).sum(axis=1).dropna().values

        result = {
            "symbols": avail_symbols,
            "weights": {s: round(w_avail[s], 4) for s in avail_symbols},
            "timestamp": datetime.now().isoformat(),
            "period": "1 year",
        }

        # 1. VaR (3 methods)
        try:
            result["var_parametric"] = self.var_calc.parametric_var(port_returns, 0.99)
            result["var_historical"] = self.var_calc.historical_var(port_returns, 0.99)
            result["var_monte_carlo"] = self.var_calc.monte_carlo_var(port_returns, 0.99, n_sims=5000)
            result["portfolio_var_full"] = self.var_calc.portfolio_var(w_avail, returns_df, 0.99)
        except Exception as e:
            result["var_error"] = str(e)

        # 2. GARCH volatility forecast
        try:
            result["garch_volatility"] = self.garch.fit_garch(port_returns)
            result["realized_volatility"] = self.garch.calculate_realized_vol(port_returns)
        except Exception as e:
            result["garch_error"] = str(e)

        # 3. Risk-adjusted ratios
        try:
            mu = np.mean(port_returns)
            sigma = np.std(port_returns, ddof=1)
            rfr = _daily_rfr()

            # Sharpe
            sharpe = (mu - rfr) / sigma * np.sqrt(TRADING_DAYS_ANNUAL) if sigma > 0 else 0

            # Sortino (downside deviation)
            downside = port_returns[port_returns < rfr] - rfr
            downside_std = np.sqrt(np.mean(downside ** 2)) if len(downside) > 0 else sigma
            sortino = (mu - rfr) / downside_std * np.sqrt(TRADING_DAYS_ANNUAL) if downside_std > 0 else 0

            # Information ratio vs NIFTY
            ir = None
            if "^NSEI" in returns_df.columns:
                nifty_ret = returns_df["^NSEI"].reindex(returns_df[avail_symbols].dropna().index).dropna()
                port_series = (returns_df[avail_symbols] * w_array).sum(axis=1)
                common = nifty_ret.index.intersection(port_series.index)
                if len(common) > 10:
                    active_return = port_series.loc[common].values - nifty_ret.loc[common].values
                    tracking_error = np.std(active_return) * np.sqrt(TRADING_DAYS_ANNUAL)
                    ir = np.mean(active_return) * TRADING_DAYS_ANNUAL / tracking_error if tracking_error > 0 else 0

            result["risk_adjusted_ratios"] = {
                "sharpe_ratio": round(float(sharpe), 4),
                "sortino_ratio": round(float(sortino), 4),
                "information_ratio_vs_nifty": round(float(ir), 4) if ir is not None else None,
                "annual_return_pct": round(float(mu * TRADING_DAYS_ANNUAL * 100), 2),
                "annual_vol_pct": round(float(sigma * np.sqrt(TRADING_DAYS_ANNUAL) * 100), 2),
            }
        except Exception as e:
            result["ratio_error"] = str(e)

        # 4. Drawdown
        try:
            equity_curve = pd.Series((1 + pd.Series(port_returns)).cumprod().values)
            result["drawdown_analysis"] = self.drawdown.calculate(equity_curve)
            result["pain_index"] = self.drawdown.calculate_pain_index(equity_curve)
        except Exception as e:
            result["drawdown_error"] = str(e)

        # 5. Stress tests
        try:
            result["stress_tests_historical"] = self.stress_tester.historical_scenarios(returns_df, w_avail)
            result["stress_tests_hypothetical"] = self.stress_tester.hypothetical_scenarios(returns_df, w_avail)
            result["sensitivity"] = self.stress_tester.sensitivity_analysis(w_avail, returns_df)
        except Exception as e:
            result["stress_test_error"] = str(e)

        # 6. Factor decomposition
        try:
            factor_cols = [NIFTY50_SYMBOL, NIFTY_BANK_SYMBOL, NIFTY_IT_SYMBOL]
            factor_data = returns_df[[c for c in factor_cols if c in returns_df.columns]]
            stock_data = returns_df[[s for s in avail_symbols if s in returns_df.columns]]
            if not factor_data.empty and not stock_data.empty:
                result["factor_decomposition"] = self.factor_risk.decompose(stock_data, factor_data)
        except Exception as e:
            result["factor_error"] = str(e)

        # 7. Tail risk
        try:
            result["tail_risk"] = self.tail_risk.calculate_tail_risk(port_returns)
            result["extreme_value_theory"] = self.tail_risk.extreme_value_theory(port_returns)
            stock_data_for_copula = returns_df[[s for s in avail_symbols if s in returns_df.columns]].dropna()
            if stock_data_for_copula.shape[1] >= 2:
                result["copula_tail_dependence"] = self.tail_risk.copula_analysis(stock_data_for_copula)
        except Exception as e:
            result["tail_risk_error"] = str(e)

        # 8. Risk budget
        try:
            cov_matrix = returns_df[[s for s in avail_symbols if s in returns_df.columns]].cov()
            result["risk_budget"] = self.risk_budget.calculate_risk_budget(w_avail, cov_matrix)
        except Exception as e:
            result["risk_budget_error"] = str(e)

        # 9. Concentration risk (HHI of weights)
        hhi_weight = sum(v ** 2 for v in w_avail.values())
        n_eff = 1 / hhi_weight if hhi_weight > 0 else len(avail_symbols)
        result["concentration_risk"] = {
            "hhi_weights": round(hhi_weight, 4),
            "effective_n_positions": round(n_eff, 2),
            "max_weight_pct": round(max(w_avail.values()) * 100, 2),
            "concentration_level": (
                "HIGHLY_CONCENTRATED" if hhi_weight > 0.25 else
                "CONCENTRATED" if hhi_weight > 0.15 else
                "MODERATELY_DIVERSIFIED" if hhi_weight > 0.10 else
                "WELL_DIVERSIFIED"
            ),
        }

        return result

    def get_stock_risk(self, symbol: str) -> dict:
        """Individual stock risk metrics."""
        ns_sym = f"{symbol}.NS"

        try:
            ticker = yf.Ticker(ns_sym)
            hist = ticker.history(period="2y")
        except Exception as e:
            return {"error": f"Failed to fetch data for {symbol}: {str(e)}"}

        if hist.empty or len(hist) < 30:
            return {"error": f"Insufficient data for {symbol}"}

        close = hist["Close"]
        returns = np.log(close / close.shift(1)).dropna().values

        # Fetch NIFTY for beta
        nifty_hist = yf.Ticker(NIFTY50_SYMBOL).history(period="2y")
        nifty_returns = np.log(nifty_hist["Close"] / nifty_hist["Close"].shift(1)).dropna()

        result = {"symbol": symbol, "timestamp": datetime.now().isoformat()}

        # Beta
        try:
            nifty_series = pd.Series(nifty_returns.values, index=nifty_returns.index)
            stock_series = pd.Series(returns, index=close.index[1:])
            common_idx = stock_series.index.intersection(nifty_series.index)
            if len(common_idx) > 20:
                s_ret = stock_series.loc[common_idx].values
                n_ret = nifty_series.loc[common_idx].values
                beta, alpha, r, p, se = stats.linregress(n_ret, s_ret)
                result["beta"] = {
                    "beta": round(float(beta), 4),
                    "alpha_annual_pct": round(float(alpha) * TRADING_DAYS_ANNUAL * 100, 2),
                    "r_squared": round(float(r ** 2), 4),
                    "interpretation": (
                        "Defensive (low beta)" if beta < 0.75 else
                        "Market-like" if beta < 1.25 else
                        "Aggressive (high beta)"
                    ),
                }
        except Exception as e:
            result["beta_error"] = str(e)

        # Historical vol percentile
        try:
            result["volatility"] = self.garch.calculate_realized_vol(returns)
            result["garch"] = self.garch.fit_garch(returns)
        except Exception as e:
            result["volatility_error"] = str(e)

        # VaR/CVaR
        try:
            result["var_historical"] = self.var_calc.historical_var(returns, 0.99)
            result["var_parametric"] = self.var_calc.parametric_var(returns, 0.99)
        except Exception as e:
            result["var_error"] = str(e)

        # Tail risk
        try:
            result["tail_risk"] = self.tail_risk.calculate_tail_risk(returns)
            result["evt"] = self.tail_risk.extreme_value_theory(returns)
        except Exception as e:
            result["tail_risk_error"] = str(e)

        # Drawdown
        try:
            equity = pd.Series((1 + pd.Series(returns)).cumprod().values)
            result["drawdown"] = self.drawdown.calculate(equity)
            result["pain_index"] = self.drawdown.calculate_pain_index(equity)
        except Exception as e:
            result["drawdown_error"] = str(e)

        # Summary metrics
        try:
            mu = np.mean(returns)
            sigma = np.std(returns, ddof=1)
            rfr = _daily_rfr()
            sharpe = (mu - rfr) / sigma * np.sqrt(TRADING_DAYS_ANNUAL) if sigma > 0 else 0
            result["summary"] = {
                "annual_return_pct": round(mu * TRADING_DAYS_ANNUAL * 100, 2),
                "annual_vol_pct": round(sigma * np.sqrt(TRADING_DAYS_ANNUAL) * 100, 2),
                "sharpe_ratio": round(float(sharpe), 4),
                "current_price": round(float(close.iloc[-1]), 2),
                "52w_high": round(float(close.tail(252).max()), 2),
                "52w_low": round(float(close.tail(252).min()), 2),
                "pct_from_52w_high": round((close.iloc[-1] / close.tail(252).max() - 1) * 100, 2),
            }
        except Exception as e:
            result["summary_error"] = str(e)

        return result
