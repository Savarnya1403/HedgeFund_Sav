"""
Trading Analytics Engine — Jane Street-style quantitative tools
Monte Carlo GBM, Pairs Trading, Correlation, Options Analytics, Market Breadth
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────
# MONTE CARLO — Geometric Brownian Motion
# ──────────────────────────────────────────────────────────────────

def monte_carlo_gbm(
    prices: List[float],
    days: int = 30,
    simulations: int = 2000,
    seed: int = 42,
) -> Dict:
    np.random.seed(seed)
    arr = np.array([p for p in prices if p and p > 0], dtype=float)
    if len(arr) < 20:
        return {"error": "insufficient price history"}

    log_ret = np.diff(np.log(arr))
    mu = float(np.mean(log_ret))
    sigma = float(np.std(log_ret))
    annual_vol = sigma * np.sqrt(252)
    S0 = float(arr[-1])

    # GBM paths: S(t) = S(t-1) * exp((mu - 0.5σ²) + σ*Z)
    Z = np.random.standard_normal((simulations, days))
    increments = np.exp((mu - 0.5 * sigma ** 2) + sigma * Z)
    paths = np.ones((simulations, days + 1))
    paths[:, 0] = S0
    for t in range(1, days + 1):
        paths[:, t] = paths[:, t - 1] * increments[:, t - 1]

    final = paths[:, -1]
    portfolio_returns = (final - S0) / S0

    pcts = [5, 25, 50, 75, 95]
    bands = {}
    for p in pcts:
        bands[f"p{p}"] = [round(float(np.percentile(paths[:, t], p)), 2) for t in range(days + 1)]

    var_95 = float(np.percentile(portfolio_returns, 5))
    var_99 = float(np.percentile(portfolio_returns, 1))
    cvar_95 = float(np.mean(portfolio_returns[portfolio_returns <= var_95]))

    return {
        "current_price": round(S0, 2),
        "days": days,
        "simulations": simulations,
        "daily_volatility_pct": round(sigma * 100, 3),
        "annual_volatility_pct": round(annual_vol * 100, 2),
        "daily_drift_pct": round(mu * 100, 4),
        "bands": bands,
        "var_95_pct": round(var_95 * 100, 2),
        "var_99_pct": round(var_99 * 100, 2),
        "cvar_95_pct": round(cvar_95 * 100, 2),
        "expected_price": round(float(np.mean(final)), 2),
        "expected_return_pct": round(float(np.mean(portfolio_returns)) * 100, 2),
        "prob_profit_pct": round(float(np.mean(final > S0)) * 100, 1),
        "prob_up5_pct": round(float(np.mean(final > S0 * 1.05)) * 100, 1),
        "prob_down5_pct": round(float(np.mean(final < S0 * 0.95)) * 100, 1),
        "prob_down10_pct": round(float(np.mean(final < S0 * 0.90)) * 100, 1),
        "price_range_95": {
            "low": round(float(np.percentile(final, 2.5)), 2),
            "high": round(float(np.percentile(final, 97.5)), 2),
        },
    }


# ──────────────────────────────────────────────────────────────────
# PAIRS TRADING — OLS hedge ratio + spread z-score
# ──────────────────────────────────────────────────────────────────

def compute_pair_spread(
    sym1: str,
    sym2: str,
    prices1: List[float],
    prices2: List[float],
    lookback: int = 60,
) -> Dict:
    n = min(len(prices1), len(prices2), lookback)
    if n < 20:
        return {"error": "insufficient data", "sym1": sym1, "sym2": sym2}

    p1 = np.array(prices1[-n:], dtype=float)
    p2 = np.array(prices2[-n:], dtype=float)

    # OLS: p1 = beta*p2 + alpha
    X = np.column_stack([p2, np.ones(n)])
    res = np.linalg.lstsq(X, p1, rcond=None)
    beta, alpha = float(res[0][0]), float(res[0][1])

    spread = p1 - beta * p2 - alpha
    spread_mean = float(np.mean(spread))
    spread_std = float(np.std(spread))
    if spread_std < 1e-10:
        return {"error": "zero spread variance", "sym1": sym1, "sym2": sym2}

    current_z = float((spread[-1] - spread_mean) / spread_std)

    # Ornstein-Uhlenbeck half-life
    try:
        delta_s = np.diff(spread)
        X2 = np.column_stack([spread[:-1], np.ones(len(delta_s))])
        phi = np.linalg.lstsq(X2, delta_s, rcond=None)[0][0]
        half_life = round(-np.log(2) / phi, 1) if phi < 0 else None
    except Exception:
        half_life = None

    # Correlation of raw log returns
    lr1 = np.diff(np.log(p1))
    lr2 = np.diff(np.log(p2))
    corr = float(np.corrcoef(lr1, lr2)[0, 1])

    if current_z > 2.0:
        signal, signal_color = f"SELL {sym1} / BUY {sym2}", "#ef4444"
        action = "sell_spread"
    elif current_z < -2.0:
        signal, signal_color = f"BUY {sym1} / SELL {sym2}", "#22c55e"
        action = "buy_spread"
    elif abs(current_z) < 0.5:
        signal, signal_color = "Exit / No Position", "#f59e0b"
        action = "exit"
    else:
        signal, signal_color = "Hold — Converging", "#555"
        action = "hold"

    zscore_series = [round(float((s - spread_mean) / spread_std), 3) for s in spread]

    return {
        "sym1": sym1, "sym2": sym2,
        "hedge_ratio": round(beta, 4),
        "alpha": round(alpha, 4),
        "current_zscore": round(current_z, 3),
        "half_life_days": half_life if (half_life and 0 < half_life < 250) else None,
        "correlation": round(corr, 3),
        "signal": signal,
        "signal_color": signal_color,
        "action": action,
        "zscore_series": zscore_series,
        "lookback": n,
    }


# ──────────────────────────────────────────────────────────────────
# CORRELATION MATRIX
# ──────────────────────────────────────────────────────────────────

def compute_correlation_matrix(price_dict: Dict[str, List[float]]) -> Dict:
    series: Dict[str, np.ndarray] = {}
    for sym, prices in price_dict.items():
        arr = np.array([p for p in prices if p and p > 0], dtype=float)
        if len(arr) >= 30:
            series[sym] = np.diff(np.log(arr))

    if len(series) < 2:
        return {"matrix": {}, "symbols": [], "pairs": []}

    min_len = min(len(v) for v in series.values())
    df = pd.DataFrame({k: v[-min_len:] for k, v in series.items()})
    corr = df.corr().round(3)
    syms = corr.columns.tolist()

    pairs: List[Dict] = []
    for i in range(len(syms)):
        for j in range(i + 1, len(syms)):
            pairs.append({"sym1": syms[i], "sym2": syms[j], "corr": round(float(corr.iloc[i, j]), 3)})

    pairs.sort(key=lambda x: abs(x["corr"]), reverse=True)

    return {
        "symbols": syms,
        "matrix": {s: {t: round(float(corr.loc[s, t]), 3) for t in syms} for s in syms},
        "top_correlated": [p for p in pairs if p["corr"] > 0][:15],
        "least_correlated": [p for p in pairs if abs(p["corr"]) < 0.4][:10],
        "negative_corr": [p for p in pairs if p["corr"] < 0][:5],
    }


# ──────────────────────────────────────────────────────────────────
# OPTIONS ANALYTICS — PCR, Max Pain, OI Distribution, IV
# ──────────────────────────────────────────────────────────────────

def analyze_option_chain(chain_data: Dict) -> Dict:
    records = (chain_data or {}).get("records", {})
    data = records.get("data", [])
    underlying = float(records.get("underlyingValue", 0) or 0)

    if not data:
        return {"error": "no option chain data", "underlying": underlying}

    call_oi = put_oi = 0
    call_doi = put_doi = 0
    strikes: List[Dict] = []

    for item in data:
        k = float(item.get("strikePrice", 0) or 0)
        ce = item.get("CE") or {}
        pe = item.get("PE") or {}

        c_oi = int(ce.get("openInterest", 0) or 0)
        p_oi = int(pe.get("openInterest", 0) or 0)
        c_doi = int(ce.get("changeinOpenInterest", 0) or 0)
        p_doi = int(pe.get("changeinOpenInterest", 0) or 0)
        call_oi += c_oi
        put_oi += p_oi
        call_doi += c_doi
        put_doi += p_doi

        strikes.append({
            "strike": k,
            "call_oi": c_oi, "put_oi": p_oi,
            "call_oi_chg": c_doi, "put_oi_chg": p_doi,
            "call_ltp": float(ce.get("lastPrice", 0) or 0),
            "put_ltp": float(pe.get("lastPrice", 0) or 0),
            "call_iv": float(ce.get("impliedVolatility", 0) or 0),
            "put_iv": float(pe.get("impliedVolatility", 0) or 0),
        })

    strikes.sort(key=lambda x: x["strike"])

    # PCR
    pcr = put_oi / call_oi if call_oi > 0 else 0
    pcr_signal = "Bullish" if pcr > 1.5 else "Bearish" if pcr < 0.7 else "Neutral"
    pcr_color = "#22c55e" if pcr > 1.5 else "#ef4444" if pcr < 0.7 else "#f59e0b"

    # Max Pain — strike minimizing total option buyer payoff
    max_pain_strike = None
    min_pain_val = float("inf")
    for candidate in strikes:
        s = candidate["strike"]
        pain = sum(max(0.0, s - row["strike"]) * row["call_oi"] +
                   max(0.0, row["strike"] - s) * row["put_oi"]
                   for row in strikes)
        if pain < min_pain_val:
            min_pain_val = pain
            max_pain_strike = s

    # ATM IV
    atm = min(strikes, key=lambda x: abs(x["strike"] - underlying)) if strikes and underlying else None
    atm_iv = atm["call_iv"] if atm else 0

    # Display range ±12% of underlying
    disp = [s for s in strikes if underlying and abs(s["strike"] - underlying) / underlying < 0.12]
    if not disp:
        disp = strikes

    # Key levels
    top_call_oi = sorted(strikes, key=lambda x: x["call_oi"], reverse=True)[:5]
    top_put_oi = sorted(strikes, key=lambda x: x["put_oi"], reverse=True)[:5]

    # Gamma wall: strike with highest combined OI (both calls + puts) near spot
    near_strikes = [s for s in strikes if underlying and abs(s["strike"] - underlying) / underlying < 0.05]
    gamma_wall = max(near_strikes, key=lambda x: x["call_oi"] + x["put_oi"])["strike"] if near_strikes else None

    return {
        "underlying": underlying,
        "pcr": round(pcr, 3),
        "pcr_signal": pcr_signal,
        "pcr_color": pcr_color,
        "max_pain": max_pain_strike,
        "max_pain_pct": round((max_pain_strike - underlying) / underlying * 100, 2) if max_pain_strike and underlying else 0,
        "gamma_wall": gamma_wall,
        "total_call_oi": call_oi,
        "total_put_oi": put_oi,
        "call_oi_chg": call_doi,
        "put_oi_chg": put_doi,
        "atm_iv": round(atm_iv, 2),
        "key_resistance": [s["strike"] for s in top_call_oi],
        "key_support": [s["strike"] for s in top_put_oi],
        "oi_distribution": disp,
    }


# ──────────────────────────────────────────────────────────────────
# MARKET BREADTH
# ──────────────────────────────────────────────────────────────────

def compute_market_breadth(quotes: List[Dict], histories: Dict[str, List[Dict]]) -> Dict:
    total = len(quotes)
    if total == 0:
        return {}

    advances = sum(1 for q in quotes if (q.get("change_pct") or 0) > 0)
    declines = sum(1 for q in quotes if (q.get("change_pct") or 0) < 0)
    adr = round(advances / declines, 2) if declines else 99.0

    above_50 = above_200 = near_high = near_low = 0
    rsi_vals: List[float] = []

    for q in quotes:
        sym = q.get("symbol", "")
        hist = histories.get(sym) or []
        closes = [h["close"] for h in hist if h.get("close")]
        if not closes:
            continue
        arr = np.array(closes, dtype=float)
        cur = arr[-1]

        if len(arr) >= 50 and cur > np.mean(arr[-50:]):
            above_50 += 1
        if len(arr) >= 200 and cur > np.mean(arr[-200:]):
            above_200 += 1

        if len(arr) >= 15:
            d = np.diff(arr[-30:])
            g = np.where(d > 0, d, 0.0)
            l = np.where(d < 0, -d, 0.0)
            ag, al = np.mean(g[-14:]), np.mean(l[-14:])
            if al > 0:
                rsi_vals.append(100 - 100 / (1 + ag / al))

        yh = q.get("year_high") or 0
        yl = q.get("year_low") or 0
        if yh > 0 and cur >= yh * 0.97:
            near_high += 1
        if yl > 0 and cur <= yl * 1.03:
            near_low += 1

    n = len([q for q in quotes if histories.get(q.get("symbol", ""))])
    med_rsi = round(float(np.median(rsi_vals)), 1) if rsi_vals else 50.0

    return {
        "total": total, "advances": advances, "declines": declines,
        "unchanged": total - advances - declines,
        "adr": adr,
        "pct_above_50dma": round(above_50 / n * 100, 1) if n else 0,
        "pct_above_200dma": round(above_200 / n * 100, 1) if n else 0,
        "median_rsi": med_rsi,
        "pct_overbought": round(sum(1 for r in rsi_vals if r > 70) / len(rsi_vals) * 100, 1) if rsi_vals else 0,
        "pct_oversold": round(sum(1 for r in rsi_vals if r < 30) / len(rsi_vals) * 100, 1) if rsi_vals else 0,
        "near_52w_high": near_high,
        "near_52w_low": near_low,
        "breadth_signal": "Bullish" if adr > 1.5 else "Bearish" if adr < 0.67 else "Neutral",
        "breadth_color": "#22c55e" if adr > 1.5 else "#ef4444" if adr < 0.67 else "#f59e0b",
    }


# ──────────────────────────────────────────────────────────────────
# SCREENER ENGINES
# ──────────────────────────────────────────────────────────────────

def rs_rank(prices_65d: List[float], prices_125d: List[float], prices_250d: List[float]) -> float:
    """IBD-style Relative Strength Rank (0.5 * 65d + 0.3 * 125d + 0.2 * 250d returns)"""
    def ret(p: List[float]) -> float:
        arr = [x for x in p if x and x > 0]
        return (arr[-1] / arr[0] - 1) * 100 if len(arr) >= 2 else 0.0
    return round(0.5 * ret(prices_65d) + 0.3 * ret(prices_125d) + 0.2 * ret(prices_250d), 2)


def mean_reversion_signal(closes: List[float]) -> Dict:
    arr = np.array([c for c in closes if c and c > 0], dtype=float)
    if len(arr) < 20:
        return {"zscore": 0.0, "bb_pct": 0.5, "rsi": 50.0, "signal": "neutral"}

    cur = arr[-1]
    window = arr[-20:]
    ma20, std20 = float(np.mean(window)), float(np.std(window))
    zscore = (cur - ma20) / std20 if std20 > 0 else 0.0
    upper, lower = ma20 + 2 * std20, ma20 - 2 * std20
    bb_pct = (cur - lower) / (upper - lower) if upper > lower else 0.5

    d = np.diff(arr[-30:])
    g = np.where(d > 0, d, 0.0)
    l = np.where(d < 0, -d, 0.0)
    ag, al = np.mean(g[-14:]), np.mean(l[-14:])
    rsi = 100 - 100 / (1 + ag / al) if al > 0 else 50.0

    if zscore < -2 and rsi < 35:
        sig = "strong_buy"
    elif zscore < -1.5 or rsi < 35:
        sig = "oversold"
    elif zscore > 2 and rsi > 65:
        sig = "strong_sell"
    elif zscore > 1.5 or rsi > 65:
        sig = "overbought"
    else:
        sig = "neutral"

    return {
        "zscore": round(float(zscore), 3),
        "bb_pct": round(float(bb_pct), 3),
        "rsi": round(float(rsi), 1),
        "signal": sig,
    }


def breakout_signal(closes: List[float], volumes: List[float], year_high: float) -> Dict:
    arr = np.array([c for c in closes if c and c > 0], dtype=float)
    if len(arr) < 20:
        return {"type": "none", "distance_pct": 0.0}

    cur = arr[-1]
    h52 = year_high if year_high > 0 else float(np.max(arr))
    dist_52wh = (cur / h52 - 1) * 100

    # Volume surge on today
    vols = np.array([v for v in volumes if v and v > 0], dtype=float)
    avg_vol = float(np.mean(vols[-20:])) if len(vols) >= 20 else 0
    today_vol = float(vols[-1]) if len(vols) > 0 else 0
    vol_ratio = today_vol / avg_vol if avg_vol > 0 else 1.0

    # 20-day resistance break
    r20 = float(np.max(arr[-20:-1])) if len(arr) >= 20 else cur
    broke_r20 = bool(cur > r20)

    if dist_52wh >= -2 and vol_ratio > 1.3:
        btype = "52w_high_breakout"
    elif broke_r20 and vol_ratio > 1.5:
        btype = "resistance_break"
    elif dist_52wh >= -1:
        btype = "near_52w_high"
    else:
        btype = "none"

    return {
        "type": btype,
        "distance_52wh_pct": round(dist_52wh, 2),
        "vol_ratio": round(vol_ratio, 2),
        "broke_r20": broke_r20,
    }
