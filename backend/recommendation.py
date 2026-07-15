"""
AI Recommendation Engine
Multi-factor scoring + natural language reasoning for buy/sell decisions
Based on: Technical signals + Fundamentals + Macro + Sentiment + Positioning
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

_rec_cache: Dict[str, Any] = {}
_rec_ts: Dict[str, float] = {}
REC_TTL = 600   # 10 min


def _cached(key: str, ttl: float = REC_TTL) -> Optional[Any]:
    if key in _rec_cache and (time.time() - _rec_ts.get(key, 0)) < ttl:
        return _rec_cache[key]
    return None


def _store(key: str, val: Any):
    _rec_cache[key] = val
    _rec_ts[key] = time.time()


# ──────────────────────────────────────────────────────────────────
# SCORING FRAMEWORK
# ──────────────────────────────────────────────────────────────────

class StockScorer:
    """
    6-pillar scoring system (0-100 each):
    1. Technical Score  (25%)  — trend, momentum, RSI, MACD
    2. Fundamental Score (25%) — PE, PB, ROE, ROCE, growth
    3. Macro Score (15%)       — sector tailwinds, FII flows, regime
    4. Quality Score (20%)     — profitability, balance sheet, mgmt
    5. Momentum Score (10%)    — price momentum, relative strength
    6. Risk Score (5%)         — volatility, drawdown, beta

    Final composite → Action (Strong Buy / Buy / Hold / Sell / Strong Sell)
    """

    PILLARS = ["technical", "fundamental", "macro", "quality", "momentum", "risk"]
    WEIGHTS  = [0.25, 0.25, 0.15, 0.20, 0.10, 0.05]

    def __init__(self, data: Dict):
        self.d = data
        self.scores: Dict[str, Optional[float]] = {}
        self.reasons: Dict[str, List[str]] = {p: [] for p in self.PILLARS}

    def _clamp(self, v: Optional[float], lo=0, hi=100) -> float:
        if v is None:
            return 50.0
        return max(lo, min(hi, float(v)))

    def score_technical(self) -> float:
        d = self.d
        pts = 50.0
        reasons = self.reasons["technical"]

        rsi = d.get("rsi_14")
        if rsi is not None:
            if rsi < 30:
                pts += 20; reasons.append(f"RSI {rsi:.0f} — oversold, potential bounce")
            elif rsi < 45:
                pts += 8; reasons.append(f"RSI {rsi:.0f} — mildly oversold, bullish setup")
            elif rsi > 75:
                pts -= 20; reasons.append(f"RSI {rsi:.0f} — overbought, correction risk")
            elif rsi > 60:
                pts -= 5; reasons.append(f"RSI {rsi:.0f} — mildly overbought")
            else:
                reasons.append(f"RSI {rsi:.0f} — neutral")

        price = d.get("price", 0)
        sma20  = d.get("sma_20")
        sma50  = d.get("sma_50")
        sma200 = d.get("sma_200")

        if price and sma200:
            if price > sma200:
                pts += 10; reasons.append("Price above 200-SMA — long-term uptrend intact")
            else:
                pts -= 15; reasons.append("Price below 200-SMA — bearish long-term structure")

        if price and sma50:
            if price > sma50:
                pts += 5; reasons.append("Above 50-SMA — medium-term bullish")
            else:
                pts -= 8; reasons.append("Below 50-SMA — medium-term bearish")

        if price and sma20:
            if price > sma20:
                pts += 3
            else:
                pts -= 5

        # Golden/death cross
        if sma50 and sma200:
            if sma50 > sma200:
                pts += 7; reasons.append("Golden cross (50 > 200 SMA) — structural bull signal")
            else:
                pts -= 7; reasons.append("Death cross (50 < 200 SMA) — structural bear signal")

        # MACD
        macd = d.get("macd")
        macd_signal_val = d.get("macd_signal")
        if macd is not None and macd_signal_val is not None:
            if macd > macd_signal_val:
                pts += 5; reasons.append("MACD above signal — bullish momentum")
            else:
                pts -= 5; reasons.append("MACD below signal — bearish momentum")

        # Volume
        vol_ratio = d.get("volume_ratio")
        if vol_ratio is not None:
            if vol_ratio > 2 and d.get("change_pct", 0) > 0:
                pts += 8; reasons.append(f"Volume {vol_ratio:.1f}x avg on up-day — strong accumulation")
            elif vol_ratio > 2 and d.get("change_pct", 0) < 0:
                pts -= 8; reasons.append(f"Volume {vol_ratio:.1f}x avg on down-day — heavy distribution")

        return self._clamp(pts)

    def score_fundamental(self) -> float:
        d = self.d
        pts = 50.0
        reasons = self.reasons["fundamental"]

        pe = d.get("pe_ratio")
        sector_pe = d.get("sector_avg_pe", 25)
        if pe is not None and pe > 0:
            relative = pe / sector_pe
            if relative < 0.7:
                pts += 15; reasons.append(f"P/E {pe:.1f}x is {(1-relative)*100:.0f}% below sector avg ({sector_pe}x) — undervalued")
            elif relative < 0.9:
                pts += 7; reasons.append(f"P/E {pe:.1f}x slightly below sector avg — fair value")
            elif relative > 1.5:
                pts -= 15; reasons.append(f"P/E {pe:.1f}x is {(relative-1)*100:.0f}% above sector avg — expensive")
            elif relative > 1.2:
                pts -= 7; reasons.append(f"P/E {pe:.1f}x above sector avg — premium valuation")

        roe = d.get("roe")
        if roe is not None:
            if roe > 20:
                pts += 15; reasons.append(f"ROE {roe:.1f}% — exceptional capital efficiency")
            elif roe > 15:
                pts += 8; reasons.append(f"ROE {roe:.1f}% — above-average returns on equity")
            elif roe < 8:
                pts -= 10; reasons.append(f"ROE {roe:.1f}% — weak capital efficiency")

        roce = d.get("roce")
        if roce is not None:
            if roce > 20:
                pts += 10; reasons.append(f"ROCE {roce:.1f}% — strong operating efficiency")
            elif roce < 10:
                pts -= 8; reasons.append(f"ROCE {roce:.1f}% — poor capital utilization")

        rev_growth = d.get("revenue_growth")
        if rev_growth is not None:
            if rev_growth > 0.20:
                pts += 12; reasons.append(f"Revenue growth {rev_growth*100:.0f}% — strong top-line expansion")
            elif rev_growth > 0.10:
                pts += 5; reasons.append(f"Revenue growth {rev_growth*100:.0f}% — steady")
            elif rev_growth < 0:
                pts -= 12; reasons.append(f"Revenue declining {rev_growth*100:.0f}% — headwinds")

        de = d.get("debt_equity")
        if de is not None:
            if de < 0.3:
                pts += 8; reasons.append(f"D/E {de:.2f} — near debt-free, strong balance sheet")
            elif de > 2:
                pts -= 12; reasons.append(f"D/E {de:.2f} — highly leveraged, sensitive to rate hikes")
            elif de > 1:
                pts -= 5; reasons.append(f"D/E {de:.2f} — above-average leverage")

        opm = d.get("operating_margin")
        if opm is not None:
            if opm > 0.25:
                pts += 8; reasons.append(f"Operating margin {opm*100:.0f}% — wide moat")
            elif opm < 0.08:
                pts -= 8; reasons.append(f"Operating margin {opm*100:.0f}% — thin margin business")

        return self._clamp(pts)

    def score_macro(self) -> float:
        d = self.d
        pts = 50.0
        reasons = self.reasons["macro"]

        macro_regime = d.get("macro_regime", "NEUTRAL")
        if macro_regime == "RISK-ON":
            pts += 15; reasons.append("Global macro regime: RISK-ON — FII inflows expected")
        elif macro_regime == "RISK-OFF":
            pts -= 15; reasons.append("Global macro regime: RISK-OFF — defensive stance recommended")

        inr_trend = d.get("inr_trend")  # "WEAKENING" / "STRENGTHENING" / "STABLE"
        sector = d.get("sector", "")
        if inr_trend == "WEAKENING" and sector in ("IT", "Pharmaceuticals"):
            pts += 10; reasons.append(f"INR weakening benefits {sector} exporters")
        elif inr_trend == "WEAKENING" and sector in ("Energy", "Chemicals"):
            pts -= 10; reasons.append(f"INR weakening raises import costs for {sector}")

        crude_trend = d.get("crude_trend")   # "UP" / "DOWN" / "STABLE"
        if crude_trend == "UP" and sector in ("Energy", "Oil & Gas"):
            pts += 12; reasons.append("Rising crude benefits upstream energy companies")
        elif crude_trend == "UP" and sector in ("Aviation", "Paints", "Tyres"):
            pts -= 12; reasons.append(f"Rising crude pressures {sector} margins")
        elif crude_trend == "DOWN" and sector in ("Aviation", "FMCG"):
            pts += 8; reasons.append(f"Falling crude lowers input costs for {sector}")

        fii_trend = d.get("fii_sentiment", "Neutral")
        if fii_trend == "Bullish":
            pts += 8; reasons.append("FII net buyers in recent sessions — tailwind")
        elif fii_trend == "Bearish":
            pts -= 8; reasons.append("FII net sellers — headwind for liquidity")

        interest_rate_sensitivity = d.get("rate_sensitivity", "LOW")
        rate_trend = d.get("rate_trend", "STABLE")
        if rate_trend == "UP" and interest_rate_sensitivity == "HIGH":
            pts -= 10; reasons.append("Rising rates negative for high-D/E and NBFC names")
        elif rate_trend == "DOWN" and interest_rate_sensitivity == "HIGH":
            pts += 10; reasons.append("Rate cuts will re-rate NBFCs and leveraged plays")

        return self._clamp(pts)

    def score_quality(self) -> float:
        d = self.d
        pts = 50.0
        reasons = self.reasons["quality"]

        # Promoter holding
        promoter_pct = d.get("promoter_pct")
        if promoter_pct is not None:
            if promoter_pct > 65:
                pts += 8; reasons.append(f"Promoter holding {promoter_pct:.1f}% — high conviction")
            elif promoter_pct < 25:
                pts -= 10; reasons.append(f"Low promoter holding {promoter_pct:.1f}% — ownership concern")

        # Pledged shares
        pledged_pct = d.get("pledged_pct", 0) or 0
        if pledged_pct > 30:
            pts -= 20; reasons.append(f"{pledged_pct:.1f}% shares pledged — severe governance risk")
        elif pledged_pct > 10:
            pts -= 8; reasons.append(f"{pledged_pct:.1f}% shares pledged — moderate risk")

        # Current ratio
        cr = d.get("current_ratio")
        if cr is not None:
            if cr > 2:
                pts += 5; reasons.append(f"Current ratio {cr:.2f} — ample liquidity")
            elif cr < 1:
                pts -= 10; reasons.append(f"Current ratio {cr:.2f} — liquidity stress")

        # Net profit margin trend
        npm = d.get("net_margin")
        if npm is not None:
            if npm > 0.15:
                pts += 10; reasons.append(f"Net margin {npm*100:.1f}% — profitable and efficient")
            elif npm < 0.03:
                pts -= 8; reasons.append(f"Net margin {npm*100:.1f}% — thin profitability")

        # MF holding count
        mf_count = d.get("mf_count", 0) or 0
        if mf_count >= 3:
            pts += 10; reasons.append(f"Held by {mf_count} major mutual funds — institutional validation")
        elif mf_count == 0:
            reasons.append("Not in major MF portfolios — limited institutional support")

        return self._clamp(pts)

    def score_momentum(self) -> float:
        d = self.d
        pts = 50.0
        reasons = self.reasons["momentum"]

        ret_1m  = d.get("ret_1m")
        ret_3m  = d.get("ret_3m")
        ret_6m  = d.get("ret_6m")
        ret_12m = d.get("ret_12m")

        if ret_12m is not None:
            if ret_12m > 40:
                pts += 20; reasons.append(f"12M return +{ret_12m:.0f}% — exceptional 52-week momentum")
            elif ret_12m > 15:
                pts += 10; reasons.append(f"12M return +{ret_12m:.0f}% — strong price momentum")
            elif ret_12m < -20:
                pts -= 20; reasons.append(f"12M return {ret_12m:.0f}% — severe price weakness")
            elif ret_12m < -5:
                pts -= 10; reasons.append(f"12M return {ret_12m:.0f}% — underperforming")

        if ret_3m is not None:
            if ret_3m > 15:
                pts += 10; reasons.append(f"3M return +{ret_3m:.0f}% — near-term strength")
            elif ret_3m < -10:
                pts -= 10; reasons.append(f"3M return {ret_3m:.0f}% — recent deterioration")

        # Relative strength vs index
        rs_vs_nifty = d.get("rs_vs_nifty")
        if rs_vs_nifty is not None:
            if rs_vs_nifty > 1.1:
                pts += 8; reasons.append(f"Outperforming Nifty50 by {(rs_vs_nifty-1)*100:.0f}% — relative strength")
            elif rs_vs_nifty < 0.9:
                pts -= 8; reasons.append(f"Underperforming Nifty50 by {(1-rs_vs_nifty)*100:.0f}% — relative weakness")

        # Near 52W high / low
        dist_52wh = d.get("dist_from_52wh_pct")   # negative = below 52W high
        dist_52wl = d.get("dist_from_52wl_pct")   # positive = above 52W low
        if dist_52wh is not None and dist_52wh > -5:
            pts += 12; reasons.append(f"Within {abs(dist_52wh):.1f}% of 52W high — breakout potential")
        if dist_52wl is not None and dist_52wl < 5:
            pts -= 12; reasons.append(f"Within {dist_52wl:.1f}% of 52W low — price weakness")

        return self._clamp(pts)

    def score_risk(self) -> float:
        d = self.d
        pts = 70.0   # start at 70 (risk score inverted — higher is lower risk)
        reasons = self.reasons["risk"]

        # Beta
        beta = d.get("beta", 1.0) or 1.0
        if beta > 1.5:
            pts -= 20; reasons.append(f"High beta {beta:.2f} — volatile, amplifies market moves")
        elif beta < 0.7:
            pts += 10; reasons.append(f"Low beta {beta:.2f} — defensive, less market sensitivity")

        # Max drawdown
        max_dd = d.get("max_drawdown_pct")   # should be negative
        if max_dd is not None:
            if max_dd < -40:
                pts -= 20; reasons.append(f"Max drawdown {max_dd:.0f}% — history of severe drops")
            elif max_dd < -25:
                pts -= 10; reasons.append(f"Max drawdown {max_dd:.0f}% — meaningful downside history")
            elif max_dd > -15:
                pts += 8; reasons.append(f"Max drawdown {max_dd:.0f}% — limited historical downside")

        # Sharpe ratio
        sharpe = d.get("sharpe_1y")
        if sharpe is not None:
            if sharpe > 1.5:
                pts += 10; reasons.append(f"Sharpe {sharpe:.2f} — excellent risk-adjusted returns")
            elif sharpe < 0:
                pts -= 10; reasons.append(f"Sharpe {sharpe:.2f} — negative risk-adjusted returns")

        # Liquidity (avg volume)
        avg_vol = d.get("avg_volume", 0) or 0
        if avg_vol < 50000:
            pts -= 15; reasons.append("Low liquidity — wide bid/ask spreads, hard to exit")
        elif avg_vol > 5000000:
            pts += 5; reasons.append("High liquidity — easy entry/exit")

        return self._clamp(pts)

    def compute(self) -> Dict:
        pillar_scores = {
            "technical":   self.score_technical(),
            "fundamental": self.score_fundamental(),
            "macro":       self.score_macro(),
            "quality":     self.score_quality(),
            "momentum":    self.score_momentum(),
            "risk":        self.score_risk(),
        }

        composite = sum(
            pillar_scores[p] * w
            for p, w in zip(self.PILLARS, self.WEIGHTS)
        )

        return pillar_scores, composite, self.reasons


def generate_recommendation(symbol: str, data: Dict) -> Dict:
    """Generate full buy/sell recommendation with reasoning"""
    key = f"rec_{symbol}"
    cached = _cached(key)
    if cached is not None:
        return cached

    scorer = StockScorer(data)
    pillar_scores, composite, reasons = scorer.compute()

    # Action classification
    if composite >= 72:
        action = "STRONG BUY"
        color  = "#00d084"
        icon   = "▲▲"
        risk_reward = "HIGH"
    elif composite >= 60:
        action = "BUY"
        color  = "#22c55e"
        icon   = "▲"
        risk_reward = "FAVORABLE"
    elif composite >= 45:
        action = "HOLD"
        color  = "#f59e0b"
        icon   = "→"
        risk_reward = "NEUTRAL"
    elif composite >= 33:
        action = "SELL"
        color  = "#ef4444"
        icon   = "▼"
        risk_reward = "UNFAVORABLE"
    else:
        action = "STRONG SELL"
        color  = "#ff3b3b"
        icon   = "▼▼"
        risk_reward = "HIGH RISK"

    # Build bull and bear arguments
    all_bull = []
    all_bear = []
    for pillar, pillar_reasons in reasons.items():
        score = pillar_scores[pillar]
        for reason in pillar_reasons:
            if score >= 55:
                all_bull.append(reason)
            elif score <= 45:
                all_bear.append(reason)

    # Price targets (rough estimate based on scoring)
    price = data.get("price", 0)
    sma200 = data.get("sma_200")
    pe = data.get("pe_ratio")

    upside_pct  = (composite - 50) * 0.6  # rough: 1% per 0.6 score points above 50
    downside_pct = (50 - composite) * 0.5

    target_price = round(price * (1 + upside_pct / 100), 2) if price else None
    stop_loss    = round(price * (1 - max(5, downside_pct / 2) / 100), 2) if price else None

    # Conviction level
    if composite >= 70 or composite <= 30:
        conviction = "HIGH"
    elif composite >= 60 or composite <= 40:
        conviction = "MEDIUM"
    else:
        conviction = "LOW"

    # Position sizing suggestion (Kelly-inspired)
    if composite >= 70:
        position_size_suggestion = "3-5% of portfolio"
    elif composite >= 60:
        position_size_suggestion = "1-3% of portfolio"
    elif composite <= 40:
        position_size_suggestion = "Exit or reduce"
    else:
        position_size_suggestion = "Hold existing, no new buying"

    # Time horizon
    if pillar_scores["technical"] > 65:
        time_horizon = "Short-term (1-3 months)"
    elif pillar_scores["fundamental"] > 65 and pillar_scores["quality"] > 65:
        time_horizon = "Long-term (12-24 months)"
    else:
        time_horizon = "Medium-term (3-6 months)"

    # One-line summary
    top_bull = all_bull[:2] if all_bull else []
    top_bear = all_bear[:2] if all_bear else []
    if action in ("STRONG BUY", "BUY"):
        summary = f"{symbol} scores {composite:.0f}/100 — {action} with {conviction} conviction. " + (top_bull[0] if top_bull else "Technical and fundamental tailwinds align.")
    elif action in ("STRONG SELL", "SELL"):
        summary = f"{symbol} scores {composite:.0f}/100 — {action} with {conviction} conviction. " + (top_bear[0] if top_bear else "Multiple risk factors present.")
    else:
        summary = f"{symbol} scores {composite:.0f}/100 — HOLD. Mixed signals; wait for clearer setup."

    result = {
        "symbol": symbol,
        "action": action,
        "color": color,
        "icon": icon,
        "composite_score": round(composite, 1),
        "conviction": conviction,
        "risk_reward": risk_reward,
        "pillar_scores": {k: round(v, 1) for k, v in pillar_scores.items()},
        "pillar_weights": dict(zip(StockScorer.PILLARS, StockScorer.WEIGHTS)),
        "bull_arguments": all_bull[:6],
        "bear_arguments": all_bear[:6],
        "target_price": target_price,
        "stop_loss": stop_loss,
        "upside_pct": round(upside_pct, 1),
        "time_horizon": time_horizon,
        "position_size_suggestion": position_size_suggestion,
        "summary": summary,
        "computed_at": datetime.now().isoformat(),
    }

    _store(key, result)
    return result


# ──────────────────────────────────────────────────────────────────
# UNIVERSE SCREENER — Rank all Nifty50 stocks
# ──────────────────────────────────────────────────────────────────

def rank_universe(stock_data_list: List[Dict]) -> List[Dict]:
    """
    Given a list of stock data dicts (each has all fields needed for StockScorer),
    rank them by composite score and return sorted list.
    """
    ranked = []
    for data in stock_data_list:
        symbol = data.get("symbol", "UNKNOWN")
        try:
            scorer = StockScorer(data)
            pillar_scores, composite, reasons = scorer.compute()
            ranked.append({
                "symbol": symbol,
                "composite_score": round(composite, 1),
                "action": _action_label(composite),
                "color": _action_color(composite),
                "pillar_scores": {k: round(v, 1) for k, v in pillar_scores.items()},
                "top_reason": _top_reason(reasons, composite),
                "price": data.get("price"),
                "change_pct": data.get("change_pct"),
                "sector": data.get("sector", ""),
            })
        except Exception as e:
            logger.debug(f"rank {symbol}: {e}")

    ranked.sort(key=lambda x: x["composite_score"], reverse=True)
    return ranked


def _action_label(score: float) -> str:
    if score >= 72: return "STRONG BUY"
    if score >= 60: return "BUY"
    if score >= 45: return "HOLD"
    if score >= 33: return "SELL"
    return "STRONG SELL"


def _action_color(score: float) -> str:
    if score >= 72: return "#00d084"
    if score >= 60: return "#22c55e"
    if score >= 45: return "#f59e0b"
    if score >= 33: return "#ef4444"
    return "#ff3b3b"


def _top_reason(reasons: Dict[str, List[str]], composite: float) -> str:
    """Pick the single most impactful reason"""
    if composite >= 55:
        for pillar in ["quality", "fundamental", "technical", "momentum", "macro"]:
            if reasons.get(pillar):
                return reasons[pillar][0]
    else:
        for pillar in ["quality", "fundamental", "risk", "technical", "macro"]:
            if reasons.get(pillar):
                return reasons[pillar][0]
    return "Multiple factors considered"


# ──────────────────────────────────────────────────────────────────
# SECTOR ROTATION MODEL
# ──────────────────────────────────────────────────────────────────

SECTOR_ROTATION_SEQUENCE = [
    # Economic cycle → preferred sectors
    ("Early Recovery",   ["Financials", "Consumer Discretionary", "IT", "Real Estate"]),
    ("Mid Expansion",    ["IT", "Industrials", "Materials", "Energy"]),
    ("Late Cycle",       ["Energy", "Materials", "FMCG", "Healthcare"]),
    ("Recession/Bear",   ["FMCG", "Healthcare", "Utilities", "Telecom"]),
]

SECTOR_INDICATORS = {
    "Financials":            {"rate_sensitive": "HIGH",   "crude_sensitive": "LOW",    "inr_sensitive": "LOW"},
    "IT":                    {"rate_sensitive": "LOW",    "crude_sensitive": "LOW",    "inr_sensitive": "HIGH"},
    "Energy":                {"rate_sensitive": "LOW",    "crude_sensitive": "HIGH",   "inr_sensitive": "MEDIUM"},
    "FMCG":                  {"rate_sensitive": "MEDIUM", "crude_sensitive": "MEDIUM", "inr_sensitive": "LOW"},
    "Pharma":                {"rate_sensitive": "LOW",    "crude_sensitive": "LOW",    "inr_sensitive": "HIGH"},
    "Auto":                  {"rate_sensitive": "HIGH",   "crude_sensitive": "HIGH",   "inr_sensitive": "LOW"},
    "Metals":                {"rate_sensitive": "MEDIUM", "crude_sensitive": "HIGH",   "inr_sensitive": "LOW"},
    "Real Estate":           {"rate_sensitive": "HIGH",   "crude_sensitive": "MEDIUM", "inr_sensitive": "LOW"},
    "Infrastructure":        {"rate_sensitive": "HIGH",   "crude_sensitive": "MEDIUM", "inr_sensitive": "LOW"},
    "Consumer Discretionary":{"rate_sensitive": "HIGH",   "crude_sensitive": "LOW",    "inr_sensitive": "LOW"},
}

def get_sector_rotation_signal(macro_regime: str, rate_trend: str, crude_trend: str, inr_trend: str) -> Dict:
    sector_scores: Dict[str, int] = {}

    for sector, meta in SECTOR_INDICATORS.items():
        score = 0
        if macro_regime == "RISK-ON":
            if sector in ("Financials", "IT", "Auto", "Consumer Discretionary"):
                score += 2
        elif macro_regime == "RISK-OFF":
            if sector in ("FMCG", "Pharma"):
                score += 2
            else:
                score -= 1

        if rate_trend == "UP":
            if meta["rate_sensitive"] == "HIGH":
                score -= 2
            elif meta["rate_sensitive"] == "LOW":
                score += 1
        elif rate_trend == "DOWN":
            if meta["rate_sensitive"] == "HIGH":
                score += 2

        if crude_trend == "UP":
            if meta["crude_sensitive"] == "HIGH" and sector in ("Energy",):
                score += 2
            elif meta["crude_sensitive"] == "HIGH" and sector in ("Auto", "FMCG"):
                score -= 1
        elif crude_trend == "DOWN":
            if meta["crude_sensitive"] == "HIGH" and sector in ("Auto", "Airlines", "FMCG"):
                score += 1

        if inr_trend == "WEAKENING":
            if meta["inr_sensitive"] == "HIGH":
                score += 2
            elif meta["inr_sensitive"] == "LOW":
                score -= 1
        elif inr_trend == "STRENGTHENING":
            if meta["inr_sensitive"] == "HIGH":
                score -= 1

        sector_scores[sector] = score

    sorted_sectors = sorted(sector_scores.items(), key=lambda x: x[1], reverse=True)

    return {
        "preferred_sectors": [s for s, sc in sorted_sectors if sc > 0][:4],
        "avoid_sectors": [s for s, sc in sorted_sectors if sc < 0][:3],
        "all_scores": dict(sorted_sectors),
        "macro_regime": macro_regime,
        "rate_trend": rate_trend,
        "crude_trend": crude_trend,
        "inr_trend": inr_trend,
        "reasoning": _sector_rotation_narrative(macro_regime, rate_trend, crude_trend, inr_trend),
        "computed_at": datetime.now().isoformat(),
    }


def _sector_rotation_narrative(macro: str, rates: str, crude: str, inr: str) -> str:
    parts = []
    if macro == "RISK-ON":
        parts.append("Risk-on environment favors cyclicals and growth sectors")
    else:
        parts.append("Risk-off pushes capital toward defensives")

    if rates == "UP":
        parts.append("rising rates pressure NBFCs, real estate, and leveraged capex plays")
    elif rates == "DOWN":
        parts.append("rate cuts re-rate rate-sensitive sectors — NBFCs, real estate, consumer durables")

    if crude == "UP":
        parts.append("elevated crude benefits upstream energy but pressures aviation and paint companies")
    elif crude == "DOWN":
        parts.append("lower crude boosts margins for auto, FMCG, airlines")

    if inr == "WEAKENING":
        parts.append("weaker INR benefits IT exporters and pharmaceutical companies with USD revenues")

    return "; ".join(parts) + "." if parts else "Multiple factors in balance — selective stock picking preferred."


# ──────────────────────────────────────────────────────────────────
# PATTERN RECOGNITION — REPEATING MARKET SETUPS
# ──────────────────────────────────────────────────────────────────

REPEATING_PATTERNS = [
    {
        "id": "pre_budget_rally",
        "name": "Pre-Budget Rally",
        "description": "Markets tend to rally in the 30-45 days before Union Budget (typically Feb 1)",
        "sectors": ["Infrastructure", "Defence", "Railways", "Real Estate"],
        "avg_return_pct": 6.2,
        "reliability_pct": 70,
        "trigger": "India Union Budget announcement (Jan 31 - Feb 1 annually)",
        "action": "Accumulate infra, defence, capex plays 45 days before budget",
    },
    {
        "id": "rbi_rate_decision",
        "name": "RBI Rate Decision Play",
        "description": "NIFTY Bank reacts strongly on RBI MPC days (rate + commentary)",
        "sectors": ["Banking", "NBFCs", "Housing Finance"],
        "avg_return_pct": 2.4,
        "reliability_pct": 68,
        "trigger": "RBI MPC meeting (every 2 months)",
        "action": "Trade BANKNIFTY options around MPC day; direction depends on rate action",
    },
    {
        "id": "quarterly_earnings",
        "name": "Earnings Season Rotation",
        "description": "Large caps that beat estimates in first 2 weeks get 5-10% pop; miss = -3% to -8%",
        "sectors": ["IT", "Banking", "FMCG", "Auto"],
        "avg_return_pct": 6.5,
        "reliability_pct": 72,
        "trigger": "First week of Jan, Apr, Jul, Oct (quarterly results)",
        "action": "Monitor consensus estimates vs actuals; position before announcement",
    },
    {
        "id": "monsoon_agri_play",
        "name": "Monsoon Agri Play",
        "description": "Good monsoon boosts rural demand; bad monsoon hits FMCG and agri input cos",
        "sectors": ["FMCG", "Agri inputs", "Tractors", "Rural Finance"],
        "avg_return_pct": 4.0,
        "reliability_pct": 63,
        "trigger": "IMD monsoon forecast (June-September)",
        "action": "Track IMD June forecasts; buy rural FMCG on above-normal monsoon prediction",
    },
    {
        "id": "crude_oil_refinery_lag",
        "name": "Crude-Refinery 90-Day Lag",
        "description": "Refineries buy crude at spot; refining margin benefits arrive 3 months later in P&L",
        "sectors": ["Oil & Gas", "Refining (BPCL, IOC, RIL)"],
        "avg_return_pct": 8.0,
        "reliability_pct": 58,
        "trigger": "Crude price drops >15% in 3M → buy refiners 60-90 days later",
        "action": "Buy BPCL, IOC after sustained crude correction (3M lag to P&L improvement)",
    },
    {
        "id": "us_fed_rate_em_flows",
        "name": "US Fed → EM Reallocation",
        "description": "When Fed pauses/cuts → USD weakens → EM gets FII inflows → Nifty rallies",
        "sectors": ["Banking", "IT", "Pharma", "Consumer"],
        "avg_return_pct": 12.0,
        "reliability_pct": 75,
        "trigger": "US Fed rate pause signal (historical: Nifty +12% on average post-pause)",
        "action": "Position aggressively in quality Indian equities when Fed signals pause",
    },
    {
        "id": "china_plus_one_beneficiary",
        "name": "China + 1 Manufacturing Shift",
        "description": "US-China tensions accelerate manufacturing shift to India; PLI beneficiaries re-rate",
        "sectors": ["Electronics", "Chemicals", "Textiles", "Defence"],
        "avg_return_pct": 25.0,
        "reliability_pct": 60,
        "trigger": "New US tariffs on China / export restrictions / supply chain disruption",
        "action": "Screen for PLI-approved companies in electronics, chemicals, specialty chemicals",
    },
    {
        "id": "diwali_seasonal",
        "name": "Diwali Seasonal Effect",
        "description": "Consumer stocks, auto, FMCG rally into Oct-Nov Diwali season",
        "sectors": ["Auto", "FMCG", "Consumer Durables", "Jewellery"],
        "avg_return_pct": 5.5,
        "reliability_pct": 67,
        "trigger": "Diwali (October/November); start buying 45 days before",
        "action": "Accumulate Titan, Maruti, Asian Paints, Bajaj Finance in Sep-Oct",
    },
    {
        "id": "nifty_june_fy_end",
        "name": "March FY-End Institutional Buying",
        "description": "Mutual funds adjust portfolios for FY reporting; high-quality large-caps get bought",
        "sectors": ["Large Cap Quality", "Banking", "IT"],
        "avg_return_pct": 3.0,
        "reliability_pct": 60,
        "trigger": "March 1-25 (pre FY-end rebalancing)",
        "action": "Watch for large-cap quality stocks with strong YTD performance to get further bought",
    },
    {
        "id": "iip_pmi_composite_signal",
        "name": "IIP + PMI Composite Signal",
        "description": "Manufacturing PMI > 55 AND IIP growth > 8% → industrials and capex stocks outperform",
        "sectors": ["Capital Goods", "Infrastructure", "Engineering", "Metals"],
        "avg_return_pct": 7.0,
        "reliability_pct": 65,
        "trigger": "Monthly IIP data (12th of each month) + S&P India PMI (1st business day)",
        "action": "Buy L&T, BHEL, ABB, Siemens when PMI > 55 and IIP accelerating",
    },
]

def get_current_patterns(current_month: int, macro_regime: str, fii_sentiment: str) -> List[Dict]:
    """Returns which patterns are currently active or approaching"""
    active = []
    for p in REPEATING_PATTERNS:
        # Budget play: active Dec-Jan
        if p["id"] == "pre_budget_rally" and current_month in (12, 1):
            active.append({**p, "status": "ACTIVE", "urgency": "HIGH"})

        # Earnings play: active Jan, Apr, Jul, Oct
        elif p["id"] == "quarterly_earnings" and current_month in (1, 4, 7, 10):
            active.append({**p, "status": "ACTIVE", "urgency": "HIGH"})

        # Monsoon play
        elif p["id"] == "monsoon_agri_play" and current_month in (5, 6):
            active.append({**p, "status": "APPROACHING", "urgency": "MEDIUM"})

        # Diwali (approx Oct-Nov)
        elif p["id"] == "diwali_seasonal" and current_month in (8, 9):
            active.append({**p, "status": "APPROACHING", "urgency": "MEDIUM"})

        # Always show macro-driven ones
        elif p["id"] == "us_fed_rate_em_flows" and fii_sentiment == "Bullish":
            active.append({**p, "status": "POSSIBLE", "urgency": "MEDIUM"})

        elif p["id"] == "china_plus_one_beneficiary":
            active.append({**p, "status": "ONGOING", "urgency": "LOW"})

    return active
