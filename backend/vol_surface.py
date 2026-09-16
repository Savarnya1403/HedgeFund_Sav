"""
Volatility Surface & Options Strategy Builder — Citadel-Grade Options Analytics
3D vol surface, term structure, 25d RR/Butterfly, multi-leg P&L diagrams
"""
import numpy as np
from typing import Dict, List, Any
from math import log, sqrt, exp, erf, pi


def _norm_cdf(x: float) -> float:
    return (1 + erf(x / sqrt(2))) / 2


def _norm_pdf(x: float) -> float:
    return exp(-0.5 * x * x) / sqrt(2 * pi)


def bs_price(S: float, K: float, T: float, sigma: float, opt_type: str, r: float = 0.065) -> float:
    if T <= 0:
        return max(0.0, S - K) if opt_type == "call" else max(0.0, K - S)
    if sigma <= 0:
        return 0.0
    d1 = (log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt(T))
    d2 = d1 - sigma * sqrt(T)
    if opt_type == "call":
        return S * _norm_cdf(d1) - K * exp(-r * T) * _norm_cdf(d2)
    return K * exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)


def bs_greeks(S: float, K: float, T: float, sigma: float, opt_type: str, r: float = 0.065) -> Dict:
    if T <= 0 or sigma <= 0:
        return {"delta": 0, "gamma": 0, "theta": 0, "vega": 0, "rho": 0}
    d1 = (log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt(T))
    d2 = d1 - sigma * sqrt(T)
    delta = _norm_cdf(d1) if opt_type == "call" else _norm_cdf(d1) - 1
    gamma = _norm_pdf(d1) / (S * sigma * sqrt(T))
    vega = S * _norm_pdf(d1) * sqrt(T) / 100
    if opt_type == "call":
        theta = (-S * _norm_pdf(d1) * sigma / (2 * sqrt(T)) - r * K * exp(-r * T) * _norm_cdf(d2)) / 365
        rho = K * T * exp(-r * T) * _norm_cdf(d2) / 100
    else:
        theta = (-S * _norm_pdf(d1) * sigma / (2 * sqrt(T)) + r * K * exp(-r * T) * _norm_cdf(-d2)) / 365
        rho = -K * T * exp(-r * T) * _norm_cdf(-d2) / 100
    return {"delta": round(delta, 4), "gamma": round(gamma, 6),
            "theta": round(theta, 4), "vega": round(vega, 4), "rho": round(rho, 4)}


# ── VOLATILITY SURFACE ─────────────────────────────────────────────

def build_vol_surface(spot: float, atm_iv: float) -> Dict[str, Any]:
    """
    Build a parametric volatility surface using SVI-like smile.
    Expiries: 1M, 2M, 3M, 4M
    Moneyness: 80% – 120% of spot
    """
    atm_iv = max(0.08, min(1.5, atm_iv))

    moneyness = [0.80, 0.85, 0.90, 0.92, 0.94, 0.96, 0.98,
                 1.00, 1.02, 1.04, 1.06, 1.08, 1.10, 1.15, 1.20]

    expiries = {
        "Near (1M)": {"T": 1/12, "term_bump": 0.025},
        "Mid (2M)":  {"T": 2/12, "term_bump": 0.008},
        "Far (3M)":  {"T": 3/12, "term_bump": -0.002},
        "Qtrly (4M)":{"T": 4/12, "term_bump": -0.010},
    }

    surface: Dict[str, Dict] = {}
    term_structure: Dict[str, float] = {}

    for name, meta in expiries.items():
        T = meta["T"]
        base_vol = atm_iv + meta["term_bump"]
        term_structure[name] = round(base_vol * 100, 2)
        surface[name] = {}
        for m in moneyness:
            lm = log(m)
            # Negative equity skew (puts costlier) + smile curvature
            skew = -0.18 * lm
            smile = 0.90 * lm ** 2
            # Term dampening of skew at longer tenors
            skew *= (1 - meta["T"] * 0.5)
            vol = max(0.05, min(2.0, base_vol + skew + smile))
            surface[name][f"{int(m * 100)}%"] = round(vol * 100, 2)

    # 25-delta Risk Reversal and Butterfly (skew metrics)
    T_near = 1/12
    base_near = atm_iv + 0.025
    iv_25c = base_near + -0.18 * log(exp(0.25 * base_near * sqrt(T_near))) + 0.90 * log(exp(0.25 * base_near * sqrt(T_near))) ** 2
    iv_25p = base_near + -0.18 * log(exp(-0.25 * base_near * sqrt(T_near))) + 0.90 * log(exp(-0.25 * base_near * sqrt(T_near))) ** 2
    rr_25d = round((iv_25p - iv_25c) * 100, 2)
    bf_25d = round(((iv_25c + iv_25p) / 2 - base_near) * 100, 2)

    vol_rank = round(min(100, max(0, (atm_iv - 0.08) / (0.60 - 0.08) * 100)), 1)
    vol_regime = "Low" if atm_iv < 0.14 else "Normal" if atm_iv < 0.25 else "Elevated" if atm_iv < 0.38 else "Crisis"

    return {
        "spot": spot,
        "atm_iv_pct": round(atm_iv * 100, 2),
        "surface": surface,
        "term_structure": term_structure,
        "moneyness_labels": [f"{int(m * 100)}%" for m in moneyness],
        "expiry_labels": list(expiries.keys()),
        "skew": {
            "rr_25d_pct": rr_25d,
            "butterfly_25d_pct": bf_25d,
            "note": f"25Δ RR = {rr_25d:.1f}% (positive = put skew, normal for equities)",
        },
        "vol_rank_pct": vol_rank,
        "vol_regime": vol_regime,
    }


# ── OPTIONS STRATEGY BUILDER ───────────────────────────────────────

def strategy_pnl(legs: List[Dict], spot: float, iv: float = 0.20, days_to_expiry: int = 30) -> Dict[str, Any]:
    """
    Compute multi-leg option strategy P&L diagram + Greeks.
    leg = {"type": "call"|"put", "strike": float, "qty": int, "action": "buy"|"sell", "premium": float}
    """
    T = max(0.001, days_to_expiry / 365)

    net_premium = sum(
        (1 if lg["action"] == "buy" else -1) * lg["qty"] * lg.get("premium", 0)
        for lg in legs
    )

    price_range = np.linspace(spot * 0.65, spot * 1.35, 150)

    def leg_pnl(lg, S_val, at_expiry: bool):
        sign = 1 if lg["action"] == "buy" else -1
        K = lg["strike"]
        q = lg["qty"]
        entry = lg.get("premium", bs_price(spot, K, T, iv, lg["type"]))
        if at_expiry:
            intrinsic = max(0.0, S_val - K) if lg["type"] == "call" else max(0.0, K - S_val)
            return sign * q * (intrinsic - entry)
        else:
            current = bs_price(S_val, K, T, iv, lg["type"])
            return sign * q * (current - entry)

    pnl_exp = [round(float(sum(leg_pnl(lg, p, True) for lg in legs) - net_premium + net_premium), 2)
               for p in price_range]
    # corrected: net_premium already in leg_pnl as -entry; adjust:
    pnl_expiry_corrected = []
    for p_val in price_range:
        pnl = -net_premium
        for lg in legs:
            sign = 1 if lg["action"] == "buy" else -1
            K = lg["strike"]
            intrinsic = max(0.0, float(p_val) - K) if lg["type"] == "call" else max(0.0, K - float(p_val))
            pnl += sign * lg["qty"] * intrinsic
        pnl_expiry_corrected.append(round(pnl, 2))

    pnl_today = []
    for p_val in price_range:
        pnl = -net_premium
        for lg in legs:
            sign = 1 if lg["action"] == "buy" else -1
            K = lg["strike"]
            entry = lg.get("premium", bs_price(spot, K, T, iv, lg["type"]))
            current = bs_price(float(p_val), K, T, iv, lg["type"])
            pnl += sign * lg["qty"] * (current - entry)
        pnl_today.append(round(pnl, 2))

    # Breakevens
    breakevens = []
    for i in range(1, len(pnl_expiry_corrected)):
        if pnl_expiry_corrected[i - 1] * pnl_expiry_corrected[i] <= 0:
            breakevens.append(round(float(price_range[i]), 2))

    max_profit = max(pnl_expiry_corrected)
    max_loss = min(pnl_expiry_corrected)

    # Net Greeks at spot
    total = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}
    for lg in legs:
        sign = 1 if lg["action"] == "buy" else -1
        g = bs_greeks(spot, lg["strike"], T, iv, lg["type"])
        for k in total:
            total[k] += sign * lg["qty"] * g[k]

    return {
        "price_range": [round(float(p), 2) for p in price_range],
        "pnl_expiry": pnl_expiry_corrected,
        "pnl_today": pnl_today,
        "breakevens": breakevens,
        "max_profit": round(max_profit, 2),
        "max_loss": round(max_loss, 2),
        "net_premium_paid": round(net_premium, 2),
        "risk_reward": round(abs(max_profit / max_loss), 2) if max_loss != 0 else 999.0,
        "greeks": {k: round(v, 4) for k, v in total.items()},
    }


def _round50(x: float) -> float:
    return round(x / 50) * 50


STRATEGY_DESCRIPTIONS = {
    "long_straddle": "Buy ATM call + put. Profits from large move either direction. High premium.",
    "short_straddle": "Sell ATM call + put. Profits from low vol / range-bound. Unlimited risk.",
    "long_strangle": "Buy OTM call + put. Cheaper than straddle but needs larger move.",
    "short_strangle": "Sell OTM call + put. Income strategy, high tail risk.",
    "bull_call_spread": "Buy ATM call, sell OTM call. Defined risk bullish play.",
    "bear_put_spread": "Buy ATM put, sell OTM put. Defined risk bearish play.",
    "iron_condor": "Sell OTM strangle + buy wing protection. Delta-neutral income trade.",
    "iron_butterfly": "Sell ATM straddle + buy OTM wings. Tighter than condor, higher premium.",
    "butterfly": "Buy 2 wings, sell 2 ATM. Low cost; max profit at ATM at expiry.",
    "protective_put": "Buy OTM put on long stock. Portfolio insurance.",
    "covered_call": "Sell OTM call against long stock. Yield enhancement.",
    "ratio_spread": "Buy 1 ATM call, sell 2 OTM calls. Free or net credit. Has tail risk.",
}


def get_strategy(name: str, spot: float, iv: float = 0.20, days_to_expiry: int = 30) -> Dict[str, Any]:
    """Return pre-built strategy legs + full P&L data."""
    T = max(0.001, days_to_expiry / 365)
    atm = _round50(spot)
    otm_c = _round50(spot * 1.05)
    otm_p = _round50(spot * 0.95)
    wing_c = _round50(spot * 1.10)
    wing_p = _round50(spot * 0.90)

    def prem(K, t):
        return round(bs_price(spot, K, T, iv, t), 2)

    templates = {
        "long_straddle": [
            {"type": "call", "strike": atm, "qty": 1, "action": "buy", "premium": prem(atm, "call")},
            {"type": "put",  "strike": atm, "qty": 1, "action": "buy", "premium": prem(atm, "put")},
        ],
        "short_straddle": [
            {"type": "call", "strike": atm, "qty": 1, "action": "sell", "premium": prem(atm, "call")},
            {"type": "put",  "strike": atm, "qty": 1, "action": "sell", "premium": prem(atm, "put")},
        ],
        "long_strangle": [
            {"type": "call", "strike": otm_c, "qty": 1, "action": "buy", "premium": prem(otm_c, "call")},
            {"type": "put",  "strike": otm_p, "qty": 1, "action": "buy", "premium": prem(otm_p, "put")},
        ],
        "short_strangle": [
            {"type": "call", "strike": otm_c, "qty": 1, "action": "sell", "premium": prem(otm_c, "call")},
            {"type": "put",  "strike": otm_p, "qty": 1, "action": "sell", "premium": prem(otm_p, "put")},
        ],
        "bull_call_spread": [
            {"type": "call", "strike": atm,   "qty": 1, "action": "buy",  "premium": prem(atm,   "call")},
            {"type": "call", "strike": otm_c, "qty": 1, "action": "sell", "premium": prem(otm_c, "call")},
        ],
        "bear_put_spread": [
            {"type": "put", "strike": atm,   "qty": 1, "action": "buy",  "premium": prem(atm,   "put")},
            {"type": "put", "strike": otm_p, "qty": 1, "action": "sell", "premium": prem(otm_p, "put")},
        ],
        "iron_condor": [
            {"type": "put",  "strike": wing_p, "qty": 1, "action": "buy",  "premium": prem(wing_p, "put")},
            {"type": "put",  "strike": otm_p,  "qty": 1, "action": "sell", "premium": prem(otm_p,  "put")},
            {"type": "call", "strike": otm_c,  "qty": 1, "action": "sell", "premium": prem(otm_c,  "call")},
            {"type": "call", "strike": wing_c, "qty": 1, "action": "buy",  "premium": prem(wing_c, "call")},
        ],
        "iron_butterfly": [
            {"type": "put",  "strike": otm_p, "qty": 1, "action": "buy",  "premium": prem(otm_p, "put")},
            {"type": "put",  "strike": atm,   "qty": 1, "action": "sell", "premium": prem(atm,   "put")},
            {"type": "call", "strike": atm,   "qty": 1, "action": "sell", "premium": prem(atm,   "call")},
            {"type": "call", "strike": otm_c, "qty": 1, "action": "buy",  "premium": prem(otm_c, "call")},
        ],
        "butterfly": [
            {"type": "call", "strike": otm_p, "qty": 1, "action": "buy",  "premium": prem(otm_p, "call")},
            {"type": "call", "strike": atm,   "qty": 2, "action": "sell", "premium": prem(atm,   "call")},
            {"type": "call", "strike": otm_c, "qty": 1, "action": "buy",  "premium": prem(otm_c, "call")},
        ],
        "protective_put": [
            {"type": "put", "strike": otm_p, "qty": 1, "action": "buy", "premium": prem(otm_p, "put")},
        ],
        "covered_call": [
            {"type": "call", "strike": otm_c, "qty": 1, "action": "sell", "premium": prem(otm_c, "call")},
        ],
        "ratio_spread": [
            {"type": "call", "strike": atm,   "qty": 1, "action": "buy",  "premium": prem(atm,   "call")},
            {"type": "call", "strike": otm_c, "qty": 2, "action": "sell", "premium": prem(otm_c, "call")},
        ],
    }

    legs = templates.get(name, templates["long_straddle"])
    pnl_data = strategy_pnl(legs, spot, iv, days_to_expiry)

    return {
        "strategy": name,
        "description": STRATEGY_DESCRIPTIONS.get(name, ""),
        "legs": legs,
        "spot": spot,
        "iv_pct": round(iv * 100, 1),
        "days_to_expiry": days_to_expiry,
        **pnl_data,
    }


STRATEGY_NAMES = list(STRATEGY_DESCRIPTIONS.keys())
