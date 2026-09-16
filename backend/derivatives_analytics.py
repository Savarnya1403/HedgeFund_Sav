"""
Derivatives Analytics — Indian F&O Market Intelligence
=======================================================
Comprehensive futures & derivatives analytics for NSE-listed contracts.
Uses real NSE API endpoints with session management and intelligent caching.

Author: IndianHedgeFund Intelligence System
"""

from __future__ import annotations

import logging
import math
import time
import warnings
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
import yfinance as yf

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

NSE_BASE = "https://www.nseindia.com"
NSE_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.nseindia.com/",
}

# Cache TTL for derivatives data (seconds)
DERIV_CACHE_TTL: int = 120
FNO_STOCK_CACHE_TTL: int = 3600

# F&O segment index symbols
DERIVATIVE_INDICES: List[str] = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]

# Known NSE expiry weekdays: NIFTY weekly on Thursday, stocks monthly
NIFTY_EXPIRY_DAY = 3   # Thursday (0=Mon)
STOCK_EXPIRY_DAY = 3   # Last Thursday of month

# Default risk-free rate
DEFAULT_RFR: float = 0.065

# ─────────────────────────────────────────────────────────────────────────────
# SHARED NSE SESSION (requests-based)
# ─────────────────────────────────────────────────────────────────────────────

class _NSESession:
    """Singleton-style NSE requests session with automatic cookie refresh."""

    _instance: Optional["_NSESession"] = None

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.verify = False
        self._session.headers.update(NSE_HEADERS)
        self._last_refresh: float = 0.0
        self._initialized: bool = False
        self._cache: Dict[str, Any] = {}
        self._cache_ts: Dict[str, float] = {}
        self._initialize()

    @classmethod
    def get(cls) -> "_NSESession":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _initialize(self) -> None:
        """Seed cookies from NSE homepage."""
        try:
            self._session.get(
                NSE_BASE,
                headers={**NSE_HEADERS, "Accept": "text/html,application/xhtml+xml,*/*;q=0.9"},
                timeout=15,
            )
            time.sleep(0.4)
            self._session.get(
                f"{NSE_BASE}/market-data/live-equity-market",
                headers={**NSE_HEADERS, "Accept": "text/html,application/xhtml+xml,*/*;q=0.9"},
                timeout=15,
            )
            time.sleep(0.2)
            self._initialized = True
            self._last_refresh = time.time()
            logger.info("NSE derivatives session initialized")
        except Exception as exc:
            logger.warning(f"NSE session init error: {exc}")

    def _refresh(self) -> None:
        logger.info("NSE derivatives session: refreshing after 403")
        self._initialize()

    def fetch(
        self,
        path: str,
        params: Optional[Dict] = None,
        cache_ttl: int = DERIV_CACHE_TTL,
    ) -> Optional[Any]:
        """Fetch NSE API endpoint with caching and 403 auto-retry."""
        cache_key = f"{path}:{str(sorted((params or {}).items()))}"
        if cache_key in self._cache:
            age = time.time() - self._cache_ts.get(cache_key, 0)
            if age < cache_ttl:
                return self._cache[cache_key]

        url = f"{NSE_BASE}/api/{path}"
        for attempt in range(3):
            try:
                resp = self._session.get(
                    url,
                    params=params,
                    headers=NSE_HEADERS,
                    timeout=20,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    self._cache[cache_key] = data
                    self._cache_ts[cache_key] = time.time()
                    return data
                if resp.status_code == 403:
                    if attempt < 2:
                        self._refresh()
                        time.sleep(1.0 + attempt)
                    continue
                logger.warning(f"NSE {path} → HTTP {resp.status_code}")
            except requests.exceptions.Timeout:
                logger.warning(f"NSE {path} timeout (attempt {attempt + 1})")
            except Exception as exc:
                logger.warning(f"NSE {path} error: {exc} (attempt {attempt + 1})")
                if attempt < 2:
                    time.sleep(0.5)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE UTILITY FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def get_india_vix_data() -> Dict[str, Any]:
    """
    Fetch India VIX level, change, and 52-week context via Yahoo Finance.
    VIX data from NSE API is supplemented with yfinance historical context.
    """
    cache_key = "india_vix"
    nse = _NSESession.get()
    cached = nse._cache.get(cache_key)
    if cached and (time.time() - nse._cache_ts.get(cache_key, 0)) < 120:
        return cached

    vix_level: Optional[float] = None
    vix_change: Optional[float] = None
    vix_change_pct: Optional[float] = None

    # Try NSE indices endpoint
    try:
        indices_data = nse.fetch("allIndices", cache_ttl=60)
        if indices_data and "data" in indices_data:
            for idx in indices_data["data"]:
                name = (idx.get("index") or idx.get("indexSymbol") or "").upper()
                if "VIX" in name:
                    vix_level = float(idx.get("last", 0) or idx.get("lastPrice", 0) or 0)
                    vix_change = float(idx.get("change", 0) or idx.get("variation", 0) or 0)
                    vix_change_pct = float(idx.get("percentChange", 0) or 0)
                    break
    except Exception as exc:
        logger.warning(f"VIX from NSE indices: {exc}")

    # Fallback: yfinance
    vix_52w_high: Optional[float] = None
    vix_52w_low: Optional[float] = None
    vix_percentile: Optional[float] = None
    historical_vix: List[float] = []

    try:
        ticker = yf.Ticker("^INDIAVIX")
        hist = ticker.history(period="1y")
        if not hist.empty:
            closes = hist["Close"].dropna()
            historical_vix = closes.tolist()
            vix_52w_high = float(closes.max())
            vix_52w_low = float(closes.min())
            if vix_level is None:
                vix_level = float(closes.iloc[-1])
            if historical_vix:
                below = sum(1 for v in historical_vix if v < (vix_level or 0))
                vix_percentile = round(below / len(historical_vix) * 100, 1)
    except Exception as exc:
        logger.warning(f"VIX from yfinance: {exc}")

    vix_level = vix_level or 0.0
    vix_regime = (
        "Extreme Fear" if vix_level > 30
        else "High Volatility" if vix_level > 20
        else "Moderate" if vix_level > 14
        else "Low Volatility / Complacency"
    )

    result = {
        "vix_level": round(vix_level, 2),
        "vix_change": round(vix_change or 0, 2),
        "vix_change_pct": round(vix_change_pct or 0, 2),
        "vix_52w_high": round(vix_52w_high, 2) if vix_52w_high else None,
        "vix_52w_low": round(vix_52w_low, 2) if vix_52w_low else None,
        "vix_percentile": vix_percentile,
        "vix_regime": vix_regime,
        "interpretation": (
            f"India VIX at {vix_level:.1f} — {vix_regime}. "
            + ("Elevated fear; options are expensive." if vix_level > 20
               else "Low fear; options are cheap; watch for volatility expansion.")
        ),
    }
    nse._cache[cache_key] = result
    nse._cache_ts[cache_key] = time.time()
    return result


def get_fno_expiry_calendar() -> Dict[str, Any]:
    """
    Return upcoming F&O expiry dates for NIFTY (weekly/monthly),
    BANKNIFTY (weekly), and equity stocks (monthly).
    """
    today = datetime.now(timezone.utc).date()
    calendar: Dict[str, List[str]] = {
        "NIFTY_weekly": [],
        "NIFTY_monthly": [],
        "BANKNIFTY_weekly": [],
        "BANKNIFTY_monthly": [],
        "stocks_monthly": [],
    }

    # Generate next 8 Thursdays for weekly expiries
    day = today
    thursdays_found = 0
    while thursdays_found < 8:
        day += timedelta(days=1)
        if day.weekday() == NIFTY_EXPIRY_DAY:  # Thursday
            date_str = day.strftime("%d-%b-%Y")
            calendar["NIFTY_weekly"].append(date_str)
            calendar["BANKNIFTY_weekly"].append(date_str)
            thursdays_found += 1

    # Monthly expiries: last Thursday of each month for next 3 months
    for month_offset in range(3):
        target_month = today.month + month_offset
        target_year = today.year + (target_month - 1) // 12
        target_month = ((target_month - 1) % 12) + 1

        # Find last Thursday
        # Start from end of month, go backwards
        if target_month == 12:
            next_month_first = datetime(target_year + 1, 1, 1).date()
        else:
            next_month_first = datetime(target_year, target_month + 1, 1).date()
        last_day = next_month_first - timedelta(days=1)
        days_back = (last_day.weekday() - NIFTY_EXPIRY_DAY) % 7
        last_thursday = last_day - timedelta(days=days_back)

        if last_thursday >= today:
            date_str = last_thursday.strftime("%d-%b-%Y")
            if date_str not in calendar["NIFTY_monthly"]:
                calendar["NIFTY_monthly"].append(date_str)
                calendar["BANKNIFTY_monthly"].append(date_str)
                calendar["stocks_monthly"].append(date_str)

    # Try NSE for confirmed expiry dates
    try:
        nse = _NSESession.get()
        chain_data = nse.fetch("option-chain-indices", params={"symbol": "NIFTY"}, cache_ttl=3600)
        if chain_data:
            nse_expiries = (chain_data.get("records") or {}).get("expiryDates", [])
            if nse_expiries:
                calendar["NIFTY_confirmed"] = nse_expiries[:12]
    except Exception:
        pass

    return {
        "expiry_calendar": calendar,
        "today": today.strftime("%d-%b-%Y"),
        "next_nifty_weekly": calendar["NIFTY_weekly"][0] if calendar["NIFTY_weekly"] else None,
        "next_monthly": calendar["NIFTY_monthly"][0] if calendar["NIFTY_monthly"] else None,
    }


def get_options_flow_summary() -> Dict[str, Any]:
    """
    Aggregate call/put buying and selling flow across the F&O universe.
    Sources: NSE OI spurts and option chain aggregate data.
    """
    nse = _NSESession.get()

    # OI spurt data
    oi_spurts = nse.fetch("oi-spurts", params={"limit": 50}, cache_ttl=120) or {}
    fno_data = nse.fetch("liveEquity-derivatives", cache_ttl=60) or {}

    total_call_oi = 0
    total_put_oi = 0
    total_call_vol = 0
    total_put_vol = 0
    call_oi_added = 0
    put_oi_added = 0
    call_oi_shed = 0
    put_oi_shed = 0

    # Aggregate from OI spurts
    spurt_records = (oi_spurts.get("data") or [])
    bullish_flow: List[str] = []
    bearish_flow: List[str] = []

    for item in spurt_records:
        sym = item.get("symbol", "")
        inst_type = (item.get("instrumentType") or item.get("instrument") or "").upper()
        oi_chg = float(item.get("oiChange") or item.get("changeinOpenInterest") or 0)
        price_chg = float(item.get("priceChange") or item.get("pChange") or 0)

        if "CE" in inst_type or "CALL" in inst_type:
            if oi_chg > 0:
                call_oi_added += oi_chg
                if price_chg < 0:
                    bearish_flow.append(sym)  # call writing bearish
            else:
                call_oi_shed += abs(oi_chg)
                if price_chg > 0:
                    bullish_flow.append(sym)  # call short cover bullish

        elif "PE" in inst_type or "PUT" in inst_type:
            if oi_chg > 0:
                put_oi_added += oi_chg
                if price_chg < 0:
                    bullish_flow.append(sym)  # put writing bullish
            else:
                put_oi_shed += abs(oi_chg)
                if price_chg > 0:
                    bearish_flow.append(sym)  # put short cover bearish

    # Market-wide PCR from NIFTY option chain
    market_pcr: Optional[float] = None
    try:
        nifty_chain = nse.fetch("option-chain-indices", params={"symbol": "NIFTY"}, cache_ttl=120)
        if nifty_chain:
            filtered = nifty_chain.get("filtered") or {}
            ce_oi = float(filtered.get("CE", {}).get("totOI") or 0)
            pe_oi = float(filtered.get("PE", {}).get("totOI") or 0)
            if ce_oi > 0:
                market_pcr = round(pe_oi / ce_oi, 4)
    except Exception:
        pass

    # Bias determination
    net_put_bias = put_oi_added - call_oi_added
    flow_bias = "Bullish" if net_put_bias > 0 else "Bearish"

    return {
        "timestamp": datetime.now().isoformat(),
        "market_pcr_nifty": market_pcr,
        "total_call_oi_added": round(call_oi_added),
        "total_put_oi_added": round(put_oi_added),
        "total_call_oi_shed": round(call_oi_shed),
        "total_put_oi_shed": round(put_oi_shed),
        "net_options_flow_bias": flow_bias,
        "bullish_flow_stocks": list(set(bullish_flow))[:10],
        "bearish_flow_stocks": list(set(bearish_flow))[:10],
        "interpretation": (
            f"Options flow bias: {flow_bias}. "
            f"Put OI added: {put_oi_added:,.0f} vs Call OI added: {call_oi_added:,.0f}. "
            f"NIFTY PCR: {market_pcr:.2f}" if market_pcr else ""
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# FUTURES ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────

class FuturesAnalytics:
    """
    Futures market analytics: basis, rollover, cost of carry, OI trends.
    """

    def __init__(self) -> None:
        self._nse = _NSESession.get()

    def get_futures_data(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch futures data for a symbol from NSE quote-derivative endpoint.

        Returns near/mid/far month futures: price, OI, volume, basis, COC.
        """
        sym = symbol.upper()
        raw = self._nse.fetch("quote-derivative", params={"symbol": sym})
        if not raw:
            return {"error": f"No futures data for {sym}", "symbol": sym}

        # Extract spot price
        spot = float(
            raw.get("underlyingValue")
            or raw.get("info", {}).get("underlyingValue")
            or 0
        )

        # Parse futures contracts
        stocks_data: List[Dict] = raw.get("stocks", [])
        futures_contracts: List[Dict] = []
        today = datetime.now(timezone.utc).date()

        for item in stocks_data:
            meta = item.get("metadata", {})
            inst = (meta.get("instrumentType") or "").upper()
            if not any(kw in inst for kw in ("FUT", "FUTURES")):
                continue

            fut_price = float(meta.get("lastPrice", 0) or 0)
            oi = float(meta.get("openInterest", 0) or 0)
            vol = float(meta.get("totalTradedVolume", 0) or 0)
            change = float(meta.get("change", 0) or 0)
            change_pct = float(meta.get("pChange", 0) or 0)
            expiry_str = meta.get("expiryDate", "")

            try:
                exp_date = datetime.strptime(expiry_str, "%d-%b-%Y").date()
                dte = max((exp_date - today).days, 0)
            except Exception:
                dte = 0

            basis = round(fut_price - spot, 2) if (fut_price and spot) else 0.0
            basis_pct = round(basis / spot * 100, 2) if spot else 0.0
            annualised_coc = (
                round(basis_pct * (365.0 / dte), 2) if dte > 0 else 0.0
            )

            futures_contracts.append({
                "expiry": expiry_str,
                "dte": dte,
                "price": round(fut_price, 2),
                "oi": round(oi),
                "volume": round(vol),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
                "basis": basis,
                "basis_pct": basis_pct,
                "annualised_coc": annualised_coc,
                "premium_or_discount": "Premium" if basis > 0 else "Discount",
            })

        # Sort by DTE ascending
        futures_contracts.sort(key=lambda x: x["dte"])

        near = futures_contracts[0] if len(futures_contracts) > 0 else {}
        mid = futures_contracts[1] if len(futures_contracts) > 1 else {}
        far = futures_contracts[2] if len(futures_contracts) > 2 else {}

        return {
            "symbol": sym,
            "spot_price": round(spot, 2),
            "near_month": near,
            "mid_month": mid,
            "far_month": far,
            "all_contracts": futures_contracts,
            "timestamp": datetime.now().isoformat(),
        }

    def calculate_basis(
        self,
        futures_price: float,
        spot_price: float,
        dte: int,
    ) -> Dict[str, Any]:
        """
        Compute basis metrics and cost of carry.

        Basis = Futures - Spot (positive = premium, bullish; negative = discount, bearish)
        Annualised COC = (Basis / Spot) × (365 / DTE) × 100
        """
        if spot_price <= 0:
            return {"error": "invalid spot price"}

        basis = futures_price - spot_price
        basis_pct = round(basis / spot_price * 100, 4)
        annualised_coc = round(basis_pct * (365.0 / max(dte, 1)), 2)

        # Fair value via cost-of-carry model: F = S × e^(r × T)
        T = dte / 365.0
        fair_value = spot_price * math.exp(DEFAULT_RFR * T)
        mispricing = round(futures_price - fair_value, 2)
        mispricing_pct = round(mispricing / fair_value * 100, 2) if fair_value else 0.0

        if abs(basis_pct) < 0.1:
            signal = "Neutral — fair value"
        elif basis_pct > 0:
            signal = "Premium — bullish; longs willing to pay above spot"
        else:
            signal = "Discount — bearish; market pricing below spot"

        return {
            "futures_price": round(futures_price, 2),
            "spot_price": round(spot_price, 2),
            "basis": round(basis, 2),
            "basis_pct": basis_pct,
            "annualised_coc": annualised_coc,
            "fair_value_bs": round(fair_value, 2),
            "mispricing": mispricing,
            "mispricing_pct": mispricing_pct,
            "dte": dte,
            "signal": signal,
        }

    def analyze_rollover(self, symbol: str) -> Dict[str, Any]:
        """
        Rollover analysis between near and next month contracts.

        Rollover % = (Next Month OI / Total OI) × 100
        High rollover with rising basis = bullish carry forward.
        High rollover with falling basis = bearish carry forward.
        """
        sym = symbol.upper()
        futures_data = self.get_futures_data(sym)
        if "error" in futures_data:
            return futures_data

        near = futures_data.get("near_month", {})
        next_m = futures_data.get("mid_month", {})
        far = futures_data.get("far_month", {})

        near_oi = near.get("oi", 0)
        next_oi = next_m.get("oi", 0)
        far_oi = far.get("oi", 0)
        total_oi = near_oi + next_oi + far_oi

        if total_oi == 0:
            return {"error": "zero total OI", "symbol": sym}

        # Rollover = positions shifted from near to next month
        # At start of expiry week: measure next/(near+next) as traditional rollover
        rollover_pct = round(next_oi / (near_oi + next_oi) * 100, 2) if (near_oi + next_oi) > 0 else 0.0

        near_coc = near.get("annualised_coc", 0)
        next_coc = next_m.get("annualised_coc", 0)
        coc_change = round(next_coc - near_coc, 2)

        # Near month price trend
        near_chg_pct = near.get("change_pct", 0)

        rollover_bias: str
        if near_chg_pct > 0 and next_oi > 0:
            rollover_bias = "Bullish Rollover — price up, OI shifting to next month"
        elif near_chg_pct < 0 and next_oi > 0:
            rollover_bias = "Bearish Rollover — price down, OI shifting out"
        elif near_oi < next_oi:
            rollover_bias = "Advanced Rollover — majority already in next month"
        else:
            rollover_bias = "Early Rollover — most OI still in near month"

        # Rolling cost (next basis - near basis)
        rolling_cost = round(
            (next_m.get("basis_pct", 0) - near.get("basis_pct", 0)), 2
        )

        return {
            "symbol": sym,
            "near_month_oi": near_oi,
            "next_month_oi": next_oi,
            "far_month_oi": far_oi,
            "total_oi": total_oi,
            "rollover_pct": rollover_pct,
            "near_basis_pct": near.get("basis_pct", 0),
            "next_basis_pct": next_m.get("basis_pct", 0),
            "near_annualised_coc": near_coc,
            "next_annualised_coc": next_coc,
            "coc_change": coc_change,
            "rolling_cost_pct": rolling_cost,
            "rollover_bias": rollover_bias,
            "near_month_expiry": near.get("expiry"),
            "next_month_expiry": next_m.get("expiry"),
        }

    def get_fno_bhav_copy(self) -> Dict[str, Any]:
        """
        Fetch NSE F&O bhavcopy (live derivatives market data).
        Returns a by-symbol summary of active futures contracts.
        """
        nse = self._nse
        data = nse.fetch("liveEquity-derivatives", cache_ttl=60)
        if not data:
            return {"error": "Could not fetch F&O bhavcopy"}

        by_symbol: Dict[str, List[Dict]] = {}
        records = data.get("data") or []

        for item in records:
            sym = (item.get("symbol") or item.get("underlying") or "").upper()
            inst = (item.get("instrument") or item.get("instrumentType") or "").upper()
            if not sym or not any(kw in inst for kw in ("FUT", "FUTURES")):
                continue

            if sym not in by_symbol:
                by_symbol[sym] = []

            by_symbol[sym].append({
                "expiry": item.get("expiryDate") or item.get("expiry", ""),
                "ltp": float(item.get("lastPrice") or item.get("ltp") or 0),
                "oi": float(item.get("openInterest") or item.get("oi") or 0),
                "volume": float(item.get("totalTradedVolume") or item.get("volume") or 0),
                "change_pct": float(item.get("pChange") or item.get("changePct") or 0),
            })

        return {
            "by_symbol": by_symbol,
            "total_symbols": len(by_symbol),
            "timestamp": datetime.now().isoformat(),
        }

    def calculate_futures_momentum(self, symbol: str) -> Dict[str, Any]:
        """
        Evaluate futures momentum using price and OI combined signals.

        OI Interpretation Matrix:
            Price ↑, OI ↑ → Long Buildup (Bullish)
            Price ↑, OI ↓ → Short Covering (Bullish short-term)
            Price ↓, OI ↑ → Short Buildup (Bearish)
            Price ↓, OI ↓ → Long Unwinding (Bearish short-term)
        """
        sym = symbol.upper()
        futures_data = self.get_futures_data(sym)
        if "error" in futures_data:
            return futures_data

        near = futures_data.get("near_month", {})
        price_chg = near.get("change_pct", 0)
        price_chg_abs = near.get("change", 0)
        oi = near.get("oi", 0)
        basis_pct = near.get("basis_pct", 0)

        # OI change: compare to mid month as proxy (actual OI change needs historical)
        mid_oi = futures_data.get("mid_month", {}).get("oi", 0)
        oi_trend = "Rising" if oi > mid_oi * 0.5 else "Falling"

        # Momentum interpretation
        if price_chg >= 0 and oi_trend == "Rising":
            signal = "Long Buildup"
            bias = "Bullish"
            detail = "New longs entering at higher prices — strong bullish momentum"
        elif price_chg >= 0 and oi_trend == "Falling":
            signal = "Short Covering"
            bias = "Mildly Bullish"
            detail = "Shorts closing positions driving price up — watch for sustainability"
        elif price_chg < 0 and oi_trend == "Rising":
            signal = "Short Buildup"
            bias = "Bearish"
            detail = "Fresh shorts entering at lower prices — bearish momentum"
        else:
            signal = "Long Unwinding"
            bias = "Mildly Bearish"
            detail = "Longs exiting driving price lower — potential support ahead"

        # Basis signal
        basis_signal = (
            "Premium suggests bullish carryforward" if basis_pct > 0.2
            else "Discount suggests bearish carryforward" if basis_pct < -0.2
            else "Neutral basis"
        )

        # Historical volatility from yfinance
        hv20: Optional[float] = None
        try:
            ticker = yf.Ticker(f"{sym}.NS")
            hist = ticker.history(period="3mo")
            if not hist.empty and len(hist) >= 20:
                log_ret = np.log(hist["Close"] / hist["Close"].shift(1)).dropna()
                hv20 = round(float(log_ret.rolling(20).std().iloc[-1] * math.sqrt(252) * 100), 2)
        except Exception:
            pass

        return {
            "symbol": sym,
            "near_month_price": near.get("price"),
            "price_change_pct": price_chg,
            "oi_trend": oi_trend,
            "momentum_signal": signal,
            "bias": bias,
            "detail": detail,
            "basis_pct": basis_pct,
            "basis_signal": basis_signal,
            "annualised_coc": near.get("annualised_coc"),
            "hv20_pct": hv20,
            "oi_matrix": {
                "price_up_oi_up": "Long Buildup (Bullish)",
                "price_up_oi_down": "Short Covering (Mildly Bullish)",
                "price_down_oi_up": "Short Buildup (Bearish)",
                "price_down_oi_down": "Long Unwinding (Mildly Bearish)",
            },
        }


# ─────────────────────────────────────────────────────────────────────────────
# DERIVATIVES SCREENER
# ─────────────────────────────────────────────────────────────────────────────

class DerivativesScreener:
    """
    Screens the F&O universe for actionable signals:
    OI buildup, unwinding, PCR extremes, max pain deviation, etc.
    """

    def __init__(self) -> None:
        self._nse = _NSESession.get()
        self._fa = FuturesAnalytics()

    def scan_high_oi_buildup(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Stocks with highest OI addition today from NSE OI spurts.
        Classifies into Long Buildup vs Short Buildup.
        """
        raw = self._nse.fetch("oi-spurts", params={"limit": 50}, cache_ttl=120)
        if not raw:
            return []

        items = raw.get("data") or []
        results: List[Dict] = []

        for item in items:
            oi_chg = float(item.get("oiChange") or item.get("changeinOpenInterest") or 0)
            if oi_chg <= 0:
                continue

            price_chg = float(item.get("priceChange") or item.get("pChange") or 0)
            sym = (item.get("symbol") or "").upper()
            ltp = float(item.get("lastPrice") or item.get("ltp") or 0)
            oi = float(item.get("openInterest") or item.get("oi") or 0)

            # OI buildup type
            if price_chg >= 0 and oi_chg > 0:
                oi_type = "Long Buildup"
                bias = "Bullish"
            elif price_chg < 0 and oi_chg > 0:
                oi_type = "Short Buildup"
                bias = "Bearish"
            else:
                oi_type = "Mixed"
                bias = "Neutral"

            results.append({
                "symbol": sym,
                "ltp": round(ltp, 2),
                "price_change_pct": round(price_chg, 2),
                "oi": round(oi),
                "oi_change": round(oi_chg),
                "oi_change_pct": round(oi_chg / max(oi - oi_chg, 1) * 100, 2),
                "oi_type": oi_type,
                "bias": bias,
            })

        results.sort(key=lambda x: x["oi_change"], reverse=True)
        return results[:limit]

    def scan_oi_unwinding(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Stocks with highest OI reduction today.
        Classifies into Long Unwinding vs Short Covering.
        """
        # NSE OI spurts may not directly give unwinding; try liveDerivatives
        raw = self._nse.fetch("liveEquity-derivatives", cache_ttl=60)
        if not raw:
            # Fallback: use oi-spurts with negative OI change
            raw_spurts = self._nse.fetch("oi-spurts", params={"limit": 100}, cache_ttl=120) or {}
            items = raw_spurts.get("data") or []
            results = []
            for item in items:
                oi_chg = float(item.get("oiChange") or 0)
                if oi_chg >= 0:
                    continue
                price_chg = float(item.get("priceChange") or 0)
                sym = (item.get("symbol") or "").upper()
                ltp = float(item.get("lastPrice") or 0)
                oi = float(item.get("openInterest") or 0)

                if price_chg < 0 and oi_chg < 0:
                    oi_type = "Long Unwinding"
                    bias = "Bearish"
                elif price_chg > 0 and oi_chg < 0:
                    oi_type = "Short Covering"
                    bias = "Mildly Bullish"
                else:
                    oi_type = "Mixed Unwinding"
                    bias = "Neutral"

                results.append({
                    "symbol": sym,
                    "ltp": round(ltp, 2),
                    "price_change_pct": round(price_chg, 2),
                    "oi": round(oi),
                    "oi_change": round(oi_chg),
                    "oi_type": oi_type,
                    "bias": bias,
                })
            results.sort(key=lambda x: x["oi_change"])
            return results[:limit]

        # Parse live derivatives data
        items = raw.get("data") or []
        results: List[Dict] = []
        seen: set = set()

        for item in items:
            sym = (item.get("symbol") or item.get("underlying") or "").upper()
            if not sym or sym in seen:
                continue
            inst = (item.get("instrument") or item.get("instrumentType") or "").upper()
            if not any(kw in inst for kw in ("FUT", "FUTURES")):
                continue

            oi_chg = float(item.get("oiChange") or item.get("changeinOpenInterest") or 0)
            if oi_chg >= 0:
                continue

            price_chg = float(item.get("pChange") or item.get("priceChange") or 0)
            ltp = float(item.get("lastPrice") or item.get("ltp") or 0)
            oi = float(item.get("openInterest") or item.get("oi") or 0)

            if price_chg < 0 and oi_chg < 0:
                oi_type = "Long Unwinding"
                bias = "Bearish"
            elif price_chg > 0 and oi_chg < 0:
                oi_type = "Short Covering"
                bias = "Mildly Bullish"
            else:
                oi_type = "Mixed"
                bias = "Neutral"

            results.append({
                "symbol": sym,
                "ltp": round(ltp, 2),
                "price_change_pct": round(price_chg, 2),
                "oi": round(oi),
                "oi_change": round(oi_chg),
                "oi_type": oi_type,
                "bias": bias,
            })
            seen.add(sym)

        results.sort(key=lambda x: x["oi_change"])  # Most negative first
        return results[:limit]

    def scan_put_call_ratio(
        self,
        threshold_bullish: float = 0.7,
        threshold_bearish: float = 1.3,
    ) -> List[Dict[str, Any]]:
        """
        Scan stocks with extreme PCR signalling directional bias.
        PCR < threshold_bullish → oversold puts (bearish sentiment = contrarian bullish)
        PCR > threshold_bearish → excess put buying (bearish sentiment)
        """
        # Get list of top F&O stocks to scan
        fno_stocks = [
            "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
            "BAJFINANCE", "SBIN", "AXISBANK", "LT", "WIPRO",
            "TATAMOTORS", "HINDALCO", "TATASTEEL", "ONGC", "NTPC",
            "MARUTI", "SUNPHARMA", "DRREDDY", "CIPLA", "ZOMATO",
        ]

        results: List[Dict] = []
        for sym in fno_stocks:
            try:
                raw = self._nse.fetch(
                    "option-chain-equities",
                    params={"symbol": sym},
                    cache_ttl=120,
                )
                if not raw:
                    continue

                filtered = raw.get("filtered") or {}
                ce_total_oi = float(filtered.get("CE", {}).get("totOI") or 0)
                pe_total_oi = float(filtered.get("PE", {}).get("totOI") or 0)

                if ce_total_oi == 0:
                    continue

                pcr = round(pe_total_oi / ce_total_oi, 3)
                if pcr <= threshold_bullish or pcr >= threshold_bearish:
                    underlying = float(raw.get("records", {}).get("underlyingValue") or 0)
                    results.append({
                        "symbol": sym,
                        "pcr_oi": pcr,
                        "total_call_oi": round(ce_total_oi),
                        "total_put_oi": round(pe_total_oi),
                        "underlying_price": round(underlying, 2),
                        "signal": (
                            "Extremely Bullish (Contrarian)" if pcr > threshold_bearish
                            else "Extremely Bearish" if pcr < threshold_bullish
                            else "Neutral"
                        ),
                        "interpretation": (
                            f"PCR {pcr:.2f} — "
                            + ("High put OI → bearish sentiment → contrarian bullish"
                               if pcr > threshold_bearish
                               else "Low put OI → put sellers cautious → bearish signal")
                        ),
                    })
                time.sleep(0.2)  # Rate limiting
            except Exception as exc:
                logger.debug(f"PCR scan {sym}: {exc}")

        results.sort(key=lambda x: x["pcr_oi"], reverse=True)
        return results

    def scan_max_pain_deviation(
        self, threshold_pct: float = 2.0
    ) -> List[Dict[str, Any]]:
        """
        Stocks where current price deviates significantly from options max pain.
        Extreme deviations suggest potential mean reversion to max pain by expiry.
        """
        from options_engine import NSEOptionsClient, OptionsAnalytics

        fno_stocks = [
            "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
            "BAJFINANCE", "SBIN", "AXISBANK", "LT", "WIPRO",
            "TATAMOTORS", "HINDALCO", "TATASTEEL", "MARUTI", "SUNPHARMA",
        ]

        client = NSEOptionsClient()
        analytics = OptionsAnalytics(client)
        results: List[Dict] = []

        for sym in fno_stocks:
            try:
                raw = client.get_option_chain(sym)
                if not raw:
                    continue
                chain = analytics.parse_option_chain(raw, sym)
                spot = chain.get("underlying_price", 0)
                if not spot:
                    continue
                max_pain_data = analytics.calculate_max_pain(chain)
                max_pain = max_pain_data.get("max_pain_strike", 0)
                deviation = abs(spot - max_pain) / max(spot, 1) * 100 if max_pain else 0

                if deviation >= threshold_pct:
                    results.append({
                        "symbol": sym,
                        "spot_price": round(spot, 2),
                        "max_pain_strike": round(max_pain, 2),
                        "deviation_pct": round(deviation, 2),
                        "direction": "above" if spot > max_pain else "below",
                        "interpretation": (
                            f"Price {deviation:.1f}% {'above' if spot > max_pain else 'below'} "
                            f"max pain {max_pain:.0f} — may drift towards max pain by expiry"
                        ),
                    })
                time.sleep(0.3)
            except Exception as exc:
                logger.debug(f"Max pain scan {sym}: {exc}")

        results.sort(key=lambda x: x["deviation_pct"], reverse=True)
        return results

    def get_nifty_derivatives_dashboard(self) -> Dict[str, Any]:
        """
        Complete derivatives dashboard for NIFTY and BANKNIFTY.
        Includes: PCR, max pain, IV, expected move, India VIX.
        """
        from options_engine import NSEOptionsClient, OptionsAnalytics

        client = NSEOptionsClient()
        analytics = OptionsAnalytics(client)
        dashboard: Dict[str, Any] = {}

        for index in ["NIFTY", "BANKNIFTY"]:
            try:
                raw = client.get_option_chain(index)
                if not raw:
                    dashboard[index] = {"error": "No chain data"}
                    continue

                chain = analytics.parse_option_chain(raw, index)
                near_expiry = chain.get("near_expiry")
                spot = chain.get("underlying_price", 0)
                ed = chain.get("data", {}).get(near_expiry or "", {})

                atm = ed.get("atm_strike", spot)
                calls = ed.get("calls", {})
                puts = ed.get("puts", {})
                atm_call_iv = float(calls.get(atm, {}).get("iv", 0) or 0)
                atm_put_iv = float(puts.get(atm, {}).get("iv", 0) or 0)
                atm_iv = (atm_call_iv + atm_put_iv) / 2.0

                max_pain_data = analytics.calculate_max_pain(chain)
                em_data = analytics.calculate_expected_move(chain, days=ed.get("dte", 30))

                dashboard[index] = {
                    "spot_price": round(spot, 2),
                    "near_expiry": near_expiry,
                    "dte": ed.get("dte"),
                    "pcr_oi": chain.get("pcr_overall"),
                    "pcr_signal": chain.get("pcr_signal"),
                    "total_call_oi": chain.get("total_call_oi"),
                    "total_put_oi": chain.get("total_put_oi"),
                    "atm_strike": round(float(atm), 2) if atm else None,
                    "atm_iv_pct": round(atm_iv, 2),
                    "max_pain": max_pain_data,
                    "expected_move": em_data,
                }
            except Exception as exc:
                logger.error(f"Derivatives dashboard {index}: {exc}")
                dashboard[index] = {"error": str(exc)}

        # India VIX
        dashboard["india_vix"] = get_india_vix_data()

        # Market-wide PCR (all indices combined)
        try:
            total_ce = sum(
                dashboard.get(idx, {}).get("total_call_oi", 0)
                for idx in ["NIFTY", "BANKNIFTY"]
            )
            total_pe = sum(
                dashboard.get(idx, {}).get("total_put_oi", 0)
                for idx in ["NIFTY", "BANKNIFTY"]
            )
            dashboard["market_wide_pcr"] = round(total_pe / total_ce, 4) if total_ce else None
        except Exception:
            dashboard["market_wide_pcr"] = None

        dashboard["timestamp"] = datetime.now().isoformat()
        return dashboard

    def get_short_buildup_stocks(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Stocks exhibiting short buildup: price falling AND OI rising.
        Bearish signal — fresh shorts entering the market.
        """
        raw = self._nse.fetch("liveEquity-derivatives", cache_ttl=60)
        items = (raw.get("data") or []) if raw else []

        results: List[Dict] = []
        seen: set = set()

        for item in items:
            sym = (item.get("symbol") or item.get("underlying") or "").upper()
            if not sym or sym in seen:
                continue
            inst = (item.get("instrument") or item.get("instrumentType") or "").upper()
            if not any(kw in inst for kw in ("FUT", "FUTURES")):
                continue

            price_chg = float(item.get("pChange") or item.get("priceChange") or 0)
            oi_chg = float(item.get("oiChange") or item.get("changeinOpenInterest") or 0)

            # Short buildup: price DOWN, OI UP
            if price_chg < -0.5 and oi_chg > 0:
                ltp = float(item.get("lastPrice") or item.get("ltp") or 0)
                oi = float(item.get("openInterest") or item.get("oi") or 0)
                results.append({
                    "symbol": sym,
                    "ltp": round(ltp, 2),
                    "price_change_pct": round(price_chg, 2),
                    "oi": round(oi),
                    "oi_change": round(oi_chg),
                    "signal": "Short Buildup",
                    "bias": "Bearish",
                    "detail": "Price falling + OI rising — fresh shorts entering",
                })
                seen.add(sym)

        # Also check OI spurts for short buildup
        if len(results) < 5:
            spurts_raw = self._nse.fetch("oi-spurts", params={"limit": 50}, cache_ttl=120) or {}
            for item in (spurts_raw.get("data") or []):
                sym = (item.get("symbol") or "").upper()
                if not sym or sym in seen:
                    continue
                price_chg = float(item.get("priceChange") or 0)
                oi_chg = float(item.get("oiChange") or 0)
                if price_chg < -0.5 and oi_chg > 0:
                    ltp = float(item.get("lastPrice") or 0)
                    oi = float(item.get("openInterest") or 0)
                    results.append({
                        "symbol": sym,
                        "ltp": round(ltp, 2),
                        "price_change_pct": round(price_chg, 2),
                        "oi": round(oi),
                        "oi_change": round(oi_chg),
                        "signal": "Short Buildup",
                        "bias": "Bearish",
                        "detail": "Price falling + OI rising — fresh shorts entering",
                    })
                    seen.add(sym)

        results.sort(key=lambda x: abs(x["price_change_pct"]), reverse=True)
        return results[:limit]

    def get_long_unwinding_stocks(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Stocks exhibiting long unwinding: price falling AND OI falling.
        Mildly bearish — existing longs exiting positions.
        """
        raw = self._nse.fetch("liveEquity-derivatives", cache_ttl=60)
        items = (raw.get("data") or []) if raw else []

        results: List[Dict] = []
        seen: set = set()

        for item in items:
            sym = (item.get("symbol") or item.get("underlying") or "").upper()
            if not sym or sym in seen:
                continue
            inst = (item.get("instrument") or item.get("instrumentType") or "").upper()
            if not any(kw in inst for kw in ("FUT", "FUTURES")):
                continue

            price_chg = float(item.get("pChange") or item.get("priceChange") or 0)
            oi_chg = float(item.get("oiChange") or item.get("changeinOpenInterest") or 0)

            # Long unwinding: price DOWN, OI DOWN
            if price_chg < -0.5 and oi_chg < 0:
                ltp = float(item.get("lastPrice") or item.get("ltp") or 0)
                oi = float(item.get("openInterest") or item.get("oi") or 0)
                results.append({
                    "symbol": sym,
                    "ltp": round(ltp, 2),
                    "price_change_pct": round(price_chg, 2),
                    "oi": round(oi),
                    "oi_change": round(oi_chg),
                    "signal": "Long Unwinding",
                    "bias": "Mildly Bearish",
                    "detail": "Price falling + OI falling — longs closing positions",
                })
                seen.add(sym)

        # Fallback: from OI spurts with negative OI and price change
        if len(results) < 5:
            spurts_raw = self._nse.fetch("oi-spurts", params={"limit": 100}, cache_ttl=120) or {}
            for item in (spurts_raw.get("data") or []):
                sym = (item.get("symbol") or "").upper()
                if not sym or sym in seen:
                    continue
                price_chg = float(item.get("priceChange") or 0)
                oi_chg = float(item.get("oiChange") or 0)
                if price_chg < -0.5 and oi_chg < 0:
                    results.append({
                        "symbol": sym,
                        "ltp": round(float(item.get("lastPrice") or 0), 2),
                        "price_change_pct": round(price_chg, 2),
                        "oi": round(float(item.get("openInterest") or 0)),
                        "oi_change": round(oi_chg),
                        "signal": "Long Unwinding",
                        "bias": "Mildly Bearish",
                        "detail": "Price falling + OI falling — longs exiting",
                    })
                    seen.add(sym)

        results.sort(key=lambda x: abs(x["price_change_pct"]), reverse=True)
        return results[:limit]

    def scan_short_covering_candidates(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Short covering stocks: price rising + OI falling.
        Mildly bullish — shorts being squeezed out.
        """
        raw = self._nse.fetch("liveEquity-derivatives", cache_ttl=60)
        items = (raw.get("data") or []) if raw else []

        results: List[Dict] = []
        seen: set = set()

        for item in items:
            sym = (item.get("symbol") or item.get("underlying") or "").upper()
            if not sym or sym in seen:
                continue
            inst = (item.get("instrument") or item.get("instrumentType") or "").upper()
            if not any(kw in inst for kw in ("FUT", "FUTURES")):
                continue

            price_chg = float(item.get("pChange") or 0)
            oi_chg = float(item.get("oiChange") or item.get("changeinOpenInterest") or 0)

            # Short covering: price UP, OI DOWN
            if price_chg > 0.5 and oi_chg < 0:
                ltp = float(item.get("lastPrice") or item.get("ltp") or 0)
                oi = float(item.get("openInterest") or 0)
                results.append({
                    "symbol": sym,
                    "ltp": round(ltp, 2),
                    "price_change_pct": round(price_chg, 2),
                    "oi": round(oi),
                    "oi_change": round(oi_chg),
                    "signal": "Short Covering",
                    "bias": "Mildly Bullish",
                    "detail": "Price up + OI down — shorts being squeezed out",
                })
                seen.add(sym)

        results.sort(key=lambda x: x["price_change_pct"], reverse=True)
        return results[:limit]


# ─────────────────────────────────────────────────────────────────────────────
# COMPLETE DERIVATIVES MASTER REPORT
# ─────────────────────────────────────────────────────────────────────────────

def build_derivatives_report(symbol: str) -> Dict[str, Any]:
    """
    Master derivatives report for a single F&O symbol.
    Combines: futures data, basis analysis, rollover, momentum.
    """
    fa = FuturesAnalytics()

    futures_data = fa.get_futures_data(symbol)
    if "error" in futures_data:
        return futures_data

    near = futures_data.get("near_month", {})
    spot = futures_data.get("spot_price", 0)
    fut_price = near.get("price", 0)
    dte = near.get("dte", 30)

    basis_data = fa.calculate_basis(fut_price, spot, dte) if fut_price and spot else {}
    rollover = fa.analyze_rollover(symbol)
    momentum = fa.calculate_futures_momentum(symbol)

    return {
        "symbol": symbol.upper(),
        "timestamp": datetime.now().isoformat(),
        "spot_price": spot,
        "futures": futures_data,
        "basis": basis_data,
        "rollover": rollover,
        "momentum": momentum,
    }


def get_market_wide_oi_summary() -> Dict[str, Any]:
    """
    Market-wide OI summary across all F&O segments.
    Uses NSE OI spurts and live derivatives data.
    """
    nse = _NSESession.get()
    screener = DerivativesScreener()

    long_buildup = screener.scan_high_oi_buildup(limit=10)
    short_buildup = screener.get_short_buildup_stocks(limit=10)
    long_unwinding = screener.get_long_unwinding_stocks(limit=10)
    short_covering = screener.scan_short_covering_candidates(limit=10)

    # Count by direction
    bullish_count = len(long_buildup) + len(short_covering)
    bearish_count = len(short_buildup) + len(long_unwinding)
    total = bullish_count + bearish_count

    market_bias = (
        "Bullish" if bullish_count > bearish_count * 1.2
        else "Bearish" if bearish_count > bullish_count * 1.2
        else "Mixed/Neutral"
    )

    return {
        "timestamp": datetime.now().isoformat(),
        "market_bias": market_bias,
        "bullish_signals": bullish_count,
        "bearish_signals": bearish_count,
        "long_buildup": long_buildup[:5],
        "short_buildup": short_buildup[:5],
        "long_unwinding": long_unwinding[:5],
        "short_covering": short_covering[:5],
        "interpretation": (
            f"Market OI signals: {bullish_count} bullish vs {bearish_count} bearish. "
            f"Overall bias: {market_bias}."
        ),
    }


def get_fii_derivative_data() -> Dict[str, Any]:
    """
    FII/FPI derivative position data from NSE.
    Returns FII index futures long/short, net position, and historical trend.
    """
    nse = _NSESession.get()
    raw = nse.fetch("fiidiiTradeInfo", cache_ttl=300)
    if not raw:
        return {"error": "No FII/DII data available"}

    result: Dict[str, Any] = {"timestamp": datetime.now().isoformat()}

    # Parse FII derivative data
    fii_data = raw if isinstance(raw, list) else raw.get("data") or []
    for item in (fii_data if isinstance(fii_data, list) else [fii_data]):
        cat = (item.get("category") or item.get("name") or "").upper()
        if "FII" not in cat and "FPI" not in cat:
            continue
        result["fii"] = {
            "buy_value": item.get("buyValue") or item.get("buy", 0),
            "sell_value": item.get("sellValue") or item.get("sell", 0),
            "net_value": item.get("netValue") or item.get("net", 0),
            "date": item.get("date") or item.get("tradingDate"),
        }
        break

    # Try specific derivatives FII endpoint
    raw_deriv = nse.fetch("fii-derivatives", cache_ttl=300)
    if raw_deriv:
        result["fii_derivatives"] = raw_deriv

    return result


def analyze_index_derivatives(index: str = "NIFTY") -> Dict[str, Any]:
    """
    Deep analysis of index derivatives (NIFTY/BANKNIFTY).
    Combines futures and options data for a complete picture.
    """
    from options_engine import NSEOptionsClient, OptionsAnalytics

    idx = index.upper()
    fa = FuturesAnalytics()
    client = NSEOptionsClient()
    analytics = OptionsAnalytics(client)

    # Futures analysis
    futures = fa.get_futures_data(idx)
    rollover = fa.analyze_rollover(idx)
    momentum = fa.calculate_futures_momentum(idx)

    # Options analysis
    raw_chain = client.get_option_chain(idx)
    options_data: Dict[str, Any] = {}
    if raw_chain:
        chain = analytics.parse_option_chain(raw_chain, idx)
        options_data = {
            "pcr": chain.get("pcr_overall"),
            "pcr_signal": chain.get("pcr_signal"),
            "max_pain": analytics.calculate_max_pain(chain),
            "iv_surface": analytics.calculate_iv_surface(chain),
            "oi_analysis": analytics.calculate_oi_analysis(chain),
            "expected_move": analytics.calculate_expected_move(chain),
            "skew": analytics.calculate_skew(chain),
        }

    # VIX context
    vix = get_india_vix_data()

    return {
        "index": idx,
        "timestamp": datetime.now().isoformat(),
        "futures": futures,
        "rollover": rollover,
        "momentum": momentum,
        "options": options_data,
        "india_vix": vix,
        "combined_bias": (
            momentum.get("bias", "Neutral")
            + " (Futures) + "
            + options_data.get("pcr_signal", "Neutral")
            + " (Options PCR)"
        ) if options_data else momentum.get("bias", "Neutral"),
    }
