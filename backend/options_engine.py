"""
Options Engine — Indian F&O Analytics
======================================
Comprehensive options analytics for NSE-listed F&O stocks and indices.
Uses real NSE API endpoints with proper session management.

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
from scipy.stats import norm
from scipy.optimize import brentq

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

# Index symbols handled via option-chain-indices endpoint
INDEX_SYMBOLS: set = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"}

# Default Indian risk-free rate (RBI repo rate proxy)
DEFAULT_RFR: float = 0.065

# Cache TTL for options data (seconds) — options data changes fast
OPT_CACHE_TTL: int = 120

# ─────────────────────────────────────────────────────────────────────────────
# PURE BLACK-SCHOLES FUNCTIONS (standalone)
# ─────────────────────────────────────────────────────────────────────────────

def black_scholes(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str = "call",
) -> float:
    """
    Black-Scholes option pricing formula.

    Parameters
    ----------
    S : float — current underlying price
    K : float — strike price
    T : float — time to expiry in years
    r : float — risk-free rate (annualised, decimal)
    sigma : float — implied volatility (annualised, decimal)
    option_type : str — "call" or "put"

    Returns
    -------
    float — theoretical option price
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        intrinsic = max(0.0, S - K) if option_type == "call" else max(0.0, K - S)
        return intrinsic

    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_type == "call":
        price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    else:
        price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

    return max(0.0, price)


def bs_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str = "call",
) -> Dict[str, float]:
    """
    Compute all first- and second-order Black-Scholes Greeks.

    Returns dict with: price, delta, gamma, theta, vega, rho, vanna, charm,
    speed, color, d1, d2
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return {
            "price": 0.0, "delta": 0.0, "gamma": 0.0,
            "theta": 0.0, "vega": 0.0, "rho": 0.0,
            "vanna": 0.0, "charm": 0.0, "speed": 0.0, "color": 0.0,
            "d1": 0.0, "d2": 0.0,
        }

    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    Nd1 = norm.cdf(d1)
    Nd2 = norm.cdf(d2)
    nd1 = norm.pdf(d1)  # standard normal PDF at d1

    discount = math.exp(-r * T)

    if option_type == "call":
        price = S * Nd1 - K * discount * Nd2
        delta = Nd1
        theta_base = (
            -(S * nd1 * sigma) / (2 * sqrt_T)
            - r * K * discount * Nd2
        )
        rho = K * T * discount * Nd2 / 100.0
    else:
        price = K * discount * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = Nd1 - 1.0
        theta_base = (
            -(S * nd1 * sigma) / (2 * sqrt_T)
            + r * K * discount * norm.cdf(-d2)
        )
        rho = -K * T * discount * norm.cdf(-d2) / 100.0

    gamma = nd1 / (S * sigma * sqrt_T)
    vega = S * nd1 * sqrt_T / 100.0         # per 1% change in IV
    theta = theta_base / 365.0               # per calendar day

    # Higher-order Greeks
    vanna = (vega / S) * (1.0 - d1 / (sigma * sqrt_T))   # ∂Delta/∂σ
    charm = -nd1 * (
        2 * r * T - d2 * sigma * sqrt_T
    ) / (2 * T * sigma * sqrt_T) / 365.0    # ∂Delta/∂t per day

    speed = -gamma / S * (d1 / (sigma * sqrt_T) + 1.0)   # ∂Gamma/∂S
    color = (
        -nd1 / (2 * S * T * sigma * sqrt_T)
        * (2 * r * T + 1 + d1 * (2 * r * T - d2 * sigma * sqrt_T) / (sigma * sqrt_T))
    )  # ∂Gamma/∂t

    return {
        "price": round(max(0.0, price), 2),
        "delta": round(delta, 6),
        "gamma": round(gamma, 8),
        "theta": round(theta, 4),
        "vega": round(vega, 4),
        "rho": round(rho, 4),
        "vanna": round(vanna, 6),
        "charm": round(charm, 8),
        "speed": round(speed, 10),
        "color": round(color, 8),
        "d1": round(d1, 6),
        "d2": round(d2, 6),
    }


def implied_volatility(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: str = "call",
) -> float:
    """
    Compute implied volatility using Brent's method (fast, robust).

    Returns IV as decimal (e.g., 0.25 = 25%) or 0.0 if no solution.
    """
    if T <= 0 or market_price <= 0 or S <= 0 or K <= 0:
        return 0.0

    intrinsic = max(0.0, S - K) if option_type == "call" else max(0.0, K - S)
    if market_price <= intrinsic * 1.0001:
        return 0.0

    def objective(sigma: float) -> float:
        return black_scholes(S, K, T, r, sigma, option_type) - market_price

    try:
        # Brent's method: bracket between 0.001 and 20 (0.1% to 2000% IV)
        low_val = objective(0.001)
        high_val = objective(20.0)
        if low_val * high_val > 0:
            return 0.0
        iv = brentq(objective, 0.001, 20.0, xtol=1e-6, maxiter=200)
        return round(float(iv), 6) if 0 < iv < 20 else 0.0
    except Exception:
        return 0.0


def calculate_gex(chain_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gamma Exposure (GEX) calculation.

    GEX = Gamma * Open Interest * Contract Size * Spot Price^2 * 0.01
    Negative GEX → dealers short gamma → amplified moves
    Positive GEX → dealers long gamma → dampening moves
    """
    spot = chain_data.get("underlying_price", 0)
    if not spot:
        return {"error": "no spot price", "gex_by_strike": {}, "net_gex": 0.0}

    contract_size = 50  # NSE standard lot size (proxy; actual varies per stock)
    gex_by_strike: Dict[float, float] = {}
    total_call_gex = 0.0
    total_put_gex = 0.0

    expiries = chain_data.get("expiries", [])
    if not expiries:
        return {"error": "no expiries", "gex_by_strike": {}, "net_gex": 0.0}

    # Use near-month expiry
    near_expiry = expiries[0]
    expiry_data = chain_data.get("data", {}).get(near_expiry, {})
    strikes = expiry_data.get("strikes", [])
    calls = expiry_data.get("calls", {})
    puts = expiry_data.get("puts", {})

    dte = expiry_data.get("dte", 30)
    T = max(dte / 365.0, 0.001)
    r = DEFAULT_RFR

    for strike in strikes:
        strike = float(strike)
        c_data = calls.get(str(strike), calls.get(strike, {}))
        p_data = puts.get(str(strike), puts.get(strike, {}))

        c_oi = float(c_data.get("oi", 0) or 0)
        p_oi = float(p_data.get("oi", 0) or 0)
        c_iv = float(c_data.get("iv", 0) or 0) / 100.0
        p_iv = float(p_data.get("iv", 0) or 0) / 100.0

        if c_oi > 0 and c_iv > 0:
            g = bs_greeks(spot, strike, T, r, c_iv, "call")["gamma"]
            call_gex = g * c_oi * contract_size * spot ** 2 * 0.01
            total_call_gex += call_gex
            gex_by_strike[strike] = gex_by_strike.get(strike, 0.0) + call_gex

        if p_oi > 0 and p_iv > 0:
            g = bs_greeks(spot, strike, T, r, p_iv, "put")["gamma"]
            # Put dealers are short puts → negative GEX contribution
            put_gex = -g * p_oi * contract_size * spot ** 2 * 0.01
            total_put_gex += put_gex
            gex_by_strike[strike] = gex_by_strike.get(strike, 0.0) + put_gex

    net_gex = total_call_gex + total_put_gex

    # Zero-gamma level: strike where cumulative GEX flips sign
    sorted_strikes = sorted(gex_by_strike.keys())
    zero_gamma_level: Optional[float] = None
    cumulative = 0.0
    for st in sorted_strikes:
        prev_cum = cumulative
        cumulative += gex_by_strike[st]
        if prev_cum * cumulative < 0 and prev_cum != 0:
            zero_gamma_level = round(st, 2)
            break

    return {
        "net_gex": round(net_gex / 1e9, 4),          # in billions
        "call_gex": round(total_call_gex / 1e9, 4),
        "put_gex": round(total_put_gex / 1e9, 4),
        "gex_by_strike": {
            round(k, 2): round(v / 1e9, 4)
            for k, v in gex_by_strike.items()
        },
        "zero_gamma_level": zero_gamma_level,
        "regime": "Long Gamma" if net_gex > 0 else "Short Gamma",
        "interpretation": (
            "Dealers long gamma — expect mean-reversion, dampened moves"
            if net_gex > 0
            else "Dealers short gamma — expect trend continuation, amplified moves"
        ),
    }


def calculate_vanna_charm(chain_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Vanna and Charm exposure across the options chain.

    Vanna Exposure: ∑ (Vanna × OI × ContractSize) — shows delta change due to IV moves
    Charm Exposure: ∑ (Charm × OI × ContractSize) — shows delta decay as time passes
    """
    spot = chain_data.get("underlying_price", 0)
    if not spot:
        return {"error": "no spot price"}

    contract_size = 50
    r = DEFAULT_RFR

    total_call_vanna = 0.0
    total_put_vanna = 0.0
    total_call_charm = 0.0
    total_put_charm = 0.0
    vanna_by_strike: Dict[float, float] = {}
    charm_by_strike: Dict[float, float] = {}

    expiries = chain_data.get("expiries", [])
    if not expiries:
        return {"error": "no expiries"}

    for expiry in expiries[:2]:  # near and next expiry
        expiry_data = chain_data.get("data", {}).get(expiry, {})
        strikes = expiry_data.get("strikes", [])
        calls = expiry_data.get("calls", {})
        puts = expiry_data.get("puts", {})
        dte = expiry_data.get("dte", 30)
        T = max(dte / 365.0, 0.001)

        for strike in strikes:
            strike_f = float(strike)
            c_data = calls.get(str(strike), calls.get(strike, {}))
            p_data = puts.get(str(strike), puts.get(strike, {}))

            c_oi = float(c_data.get("oi", 0) or 0)
            p_oi = float(p_data.get("oi", 0) or 0)
            c_iv = float(c_data.get("iv", 0) or 0) / 100.0
            p_iv = float(p_data.get("iv", 0) or 0) / 100.0

            if c_oi > 0 and c_iv > 0.001:
                g = bs_greeks(spot, strike_f, T, r, c_iv, "call")
                cv = g["vanna"] * c_oi * contract_size
                cc = g["charm"] * c_oi * contract_size
                total_call_vanna += cv
                total_call_charm += cc
                vanna_by_strike[strike_f] = vanna_by_strike.get(strike_f, 0.0) + cv
                charm_by_strike[strike_f] = charm_by_strike.get(strike_f, 0.0) + cc

            if p_oi > 0 and p_iv > 0.001:
                g = bs_greeks(spot, strike_f, T, r, p_iv, "put")
                pv = g["vanna"] * p_oi * contract_size
                pc = g["charm"] * p_oi * contract_size
                total_put_vanna += pv
                total_put_charm += pc
                vanna_by_strike[strike_f] = vanna_by_strike.get(strike_f, 0.0) + pv
                charm_by_strike[strike_f] = charm_by_strike.get(strike_f, 0.0) + pc

    net_vanna = total_call_vanna + total_put_vanna
    net_charm = total_call_charm + total_put_charm

    return {
        "net_vanna": round(net_vanna, 2),
        "call_vanna": round(total_call_vanna, 2),
        "put_vanna": round(total_put_vanna, 2),
        "net_charm": round(net_charm, 2),
        "call_charm": round(total_call_charm, 2),
        "put_charm": round(total_put_charm, 2),
        "vanna_by_strike": {
            round(k, 2): round(v, 2) for k, v in sorted(vanna_by_strike.items())
        },
        "charm_by_strike": {
            round(k, 2): round(v, 4) for k, v in sorted(charm_by_strike.items())
        },
        "vanna_interpretation": (
            "Positive net vanna — rising IV increases dealer delta-hedging buy pressure"
            if net_vanna > 0
            else "Negative net vanna — rising IV creates dealer selling pressure"
        ),
        "charm_interpretation": (
            "Positive charm — delta decay drives buying into expiry"
            if net_charm > 0
            else "Negative charm — delta decay drives selling into expiry"
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# NSE OPTIONS CLIENT
# ─────────────────────────────────────────────────────────────────────────────

class NSEOptionsClient:
    """
    Synchronous NSE API client with cookie-based session management.
    Handles 403 errors by refreshing the session automatically.
    """

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.verify = False
        self._session.headers.update(NSE_HEADERS)
        self._last_refresh: float = 0.0
        self._cache: Dict[str, Any] = {}
        self._cache_ts: Dict[str, float] = {}
        self._initialize_session()

    def _initialize_session(self) -> None:
        """Visit NSE homepage to seed cookies, then visit option-chain page."""
        try:
            # Step 1: Get NSE homepage cookies
            resp = self._session.get(
                NSE_BASE,
                headers={**NSE_HEADERS, "Accept": "text/html,application/xhtml+xml,*/*;q=0.9"},
                timeout=15,
            )
            resp.raise_for_status()
            time.sleep(0.5)

            # Step 2: Visit option-chain page to get additional cookies
            self._session.get(
                f"{NSE_BASE}/option-chain",
                headers={**NSE_HEADERS, "Accept": "text/html,application/xhtml+xml,*/*;q=0.9"},
                timeout=15,
            )
            time.sleep(0.3)
            self._last_refresh = time.time()
            logger.info("NSEOptionsClient: session initialized")
        except Exception as exc:
            logger.warning(f"NSEOptionsClient: session init error — {exc}")

    def _refresh_session(self) -> None:
        """Re-seed cookies when we get 403 errors."""
        logger.info("NSEOptionsClient: refreshing session after 403")
        self._initialize_session()

    def _cached(self, key: str, ttl: int = OPT_CACHE_TTL) -> Optional[Any]:
        if key in self._cache and (time.time() - self._cache_ts.get(key, 0)) < ttl:
            return self._cache[key]
        return None

    def _store(self, key: str, value: Any) -> None:
        self._cache[key] = value
        self._cache_ts[key] = time.time()

    def _get(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """GET with automatic 403 retry."""
        for attempt in range(3):
            try:
                resp = self._session.get(
                    url,
                    params=params,
                    headers=NSE_HEADERS,
                    timeout=20,
                )
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code == 403:
                    if attempt < 2:
                        self._refresh_session()
                        time.sleep(1.0)
                    continue
                logger.warning(f"NSE GET {url} → HTTP {resp.status_code}")
            except requests.exceptions.Timeout:
                logger.warning(f"NSE GET {url} → timeout (attempt {attempt+1})")
            except Exception as exc:
                logger.warning(f"NSE GET {url} → {exc} (attempt {attempt+1})")
                if attempt < 2:
                    time.sleep(0.5)
        return None

    def get_option_chain(self, symbol: str) -> Optional[Dict]:
        """
        Fetch the full option chain for a symbol.
        Uses /api/option-chain-indices for indices, /api/option-chain-equities for stocks.
        Falls back to nsepython if direct NSE session fails (Cloudflare blocked).
        """
        sym = symbol.upper().strip()
        cache_key = f"chain_{sym}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        # Primary: direct NSE API
        if sym in INDEX_SYMBOLS:
            url = f"{NSE_BASE}/api/option-chain-indices"
        else:
            url = f"{NSE_BASE}/api/option-chain-equities"

        data = self._get(url, params={"symbol": sym})
        if data and data.get("records"):
            self._store(cache_key, data)
            return data

        # Fallback 1: nsepython
        try:
            from nsepython import nse_optionchain_scrapper
            data = nse_optionchain_scrapper(sym)
            if data and isinstance(data, dict) and data.get("records"):
                self._store(cache_key, data)
                return data
        except Exception as e:
            logger.warning(f"nsepython fallback failed for {sym}: {e}")

        # Fallback 2: jugaad-data
        try:
            import subprocess, json as _json
            result = subprocess.run(
                ["curl", "-s", "-L", "--compressed",
                 "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                 "-H", "Accept: application/json, text/plain, */*",
                 "-H", "Accept-Encoding: gzip, deflate, br",
                 "-H", f"Referer: {NSE_BASE}/option-chain",
                 "-H", f"Origin: {NSE_BASE}",
                 "-A", "Mozilla/5.0",
                 f"{NSE_BASE}/api/option-chain-indices?symbol={sym}" if sym in INDEX_SYMBOLS
                 else f"{NSE_BASE}/api/option-chain-equities?symbol={sym}"],
                capture_output=True, text=True, timeout=20
            )
            if result.returncode == 0 and "records" in result.stdout:
                data = _json.loads(result.stdout)
                if data.get("records"):
                    self._store(cache_key, data)
                    return data
        except Exception as e:
            logger.warning(f"curl fallback failed for {sym}: {e}")

        logger.error(f"NSEOptionsClient.get_option_chain: all methods failed for {sym}")
        return None

    def get_oi_data(self, symbol: str) -> Optional[Dict]:
        """
        Fetch OI build-up data via NSE quote-derivative endpoint.
        """
        sym = symbol.upper().strip()
        cache_key = f"oi_{sym}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        url = f"{NSE_BASE}/api/quote-derivative"
        data = self._get(url, params={"symbol": sym})
        if data:
            self._store(cache_key, data)
            return data
        return None

    def get_fno_stocks(self) -> List[str]:
        """
        Return the list of all F&O eligible stocks from NSE.
        Fetches from NSE master list endpoint.
        """
        cache_key = "fno_stocks_list"
        cached = self._cached(cache_key, ttl=3600)  # cache 1 hour
        if cached is not None:
            return cached

        url = f"{NSE_BASE}/api/master-quote"
        data = self._get(url)
        if data and isinstance(data, list):
            symbols = [item.get("symbol", "") for item in data if item.get("symbol")]
            self._store(cache_key, symbols)
            return symbols

        # Fallback: return known F&O stocks
        fallback = [
            "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
            "HINDUNILVR", "BAJFINANCE", "BHARTIARTL", "SBIN", "KOTAKBANK",
            "ITC", "LT", "AXISBANK", "TITAN", "ASIANPAINT", "MARUTI",
            "WIPRO", "HCLTECH", "ADANIENT", "ADANIPORTS", "POWERGRID",
            "NTPC", "ONGC", "COALINDIA", "BAJAJFINSV", "TATASTEEL",
            "JSWSTEEL", "HDFCLIFE", "SBILIFE", "DIVISLAB", "CIPLA",
            "DRREDDY", "SUNPHARMA", "TECHM", "INDUSINDBK", "BPCL",
            "EICHERMOT", "BRITANNIA", "HINDALCO", "TATAMOTORS",
            "APOLLOHOSP", "HEROMOTOCO", "TATACONSUM", "BANKBARODA",
            "PFC", "RECLTD", "GAIL", "IOC", "HPCL", "BEL", "HAL",
            "ZOMATO", "NAUKRI", "DLF", "VEDL", "TVSMOTOR", "SAIL",
            "NMDC", "BHEL", "IRCTC", "AMBUJACEM", "ACC", "VOLTAS",
            "LUPIN", "ZYDUSLIFE", "TATACHEM", "JSWENERGY", "INDHOTEL",
            "HDFCAMC", "ICICIPRULI", "PIIND", "INDIGO", "MUTHOOTFIN",
            "CHOLAFIN", "BAJAJ-AUTO", "DMART", "SIEMENS", "HAVELLS",
        ]
        self._store(cache_key, fallback)
        return fallback


# ─────────────────────────────────────────────────────────────────────────────
# OPTIONS ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────

class OptionsAnalytics:
    """
    Comprehensive options analytics engine for Indian F&O markets.
    All methods operate on parsed NSE option chain data.
    """

    def __init__(self, client: Optional[NSEOptionsClient] = None) -> None:
        self._client = client or NSEOptionsClient()
        self._cache: Dict[str, Any] = {}
        self._cache_ts: Dict[str, float] = {}

    def _cached(self, key: str, ttl: int = OPT_CACHE_TTL) -> Optional[Any]:
        if key in self._cache and (time.time() - self._cache_ts.get(key, 0)) < ttl:
            return self._cache[key]
        return None

    def _store(self, key: str, val: Any) -> None:
        self._cache[key] = val
        self._cache_ts[key] = time.time()

    # ── 1. Parse Option Chain ─────────────────────────────────────────────────

    def parse_option_chain(self, raw_data: Dict, symbol: str) -> Dict[str, Any]:
        """
        Parse raw NSE option chain JSON into a structured analytics-ready dict.

        Returns
        -------
        dict with keys:
            symbol, underlying_price, expiries, data (per expiry: strikes, calls, puts,
            pcr_oi, pcr_volume, atm_strike, dte), near_expiry, total_call_oi,
            total_put_oi, pcr_overall
        """
        records = (raw_data.get("records") or {})
        filtered = (raw_data.get("filtered") or {})

        # Underlying price
        underlying_price = float(
            records.get("underlyingValue")
            or filtered.get("underlyingValue")
            or 0
        )

        # All expiry dates
        expiry_dates: List[str] = records.get("expiryDates") or []

        # Raw option data array
        data_array: List[Dict] = records.get("data") or []

        # Organise by expiry → strike
        chain_by_expiry: Dict[str, Dict] = {}
        for row in data_array:
            expiry = row.get("expiryDate", "")
            if not expiry:
                continue
            if expiry not in chain_by_expiry:
                chain_by_expiry[expiry] = {}

            strike = float(row.get("strikePrice", 0))
            ce = row.get("CE") or {}
            pe = row.get("PE") or {}

            chain_by_expiry[expiry][strike] = {
                "ce": {
                    "oi": int(ce.get("openInterest") or 0),
                    "change_oi": int(ce.get("changeinOpenInterest") or 0),
                    "ltp": float(ce.get("lastPrice") or 0),
                    "iv": float(ce.get("impliedVolatility") or 0),
                    "volume": int(ce.get("totalTradedVolume") or 0),
                    "bid": float(ce.get("bidprice") or 0),
                    "ask": float(ce.get("askPrice") or 0),
                    "delta": float(ce.get("delta") or 0),
                    "gamma": float(ce.get("gamma") or 0),
                    "theta": float(ce.get("theta") or 0),
                    "vega": float(ce.get("vega") or 0),
                    "underlying": float(ce.get("underlyingValue") or underlying_price),
                },
                "pe": {
                    "oi": int(pe.get("openInterest") or 0),
                    "change_oi": int(pe.get("changeinOpenInterest") or 0),
                    "ltp": float(pe.get("lastPrice") or 0),
                    "iv": float(pe.get("impliedVolatility") or 0),
                    "volume": int(pe.get("totalTradedVolume") or 0),
                    "bid": float(pe.get("bidprice") or 0),
                    "ask": float(pe.get("askPrice") or 0),
                    "delta": float(pe.get("delta") or 0),
                    "gamma": float(pe.get("gamma") or 0),
                    "theta": float(pe.get("theta") or 0),
                    "vega": float(pe.get("vega") or 0),
                    "underlying": float(pe.get("underlyingValue") or underlying_price),
                },
            }

        # Build structured per-expiry output
        today = datetime.now(timezone.utc).date()
        structured_data: Dict[str, Any] = {}
        for expiry in expiry_dates:
            if expiry not in chain_by_expiry:
                continue

            expiry_chain = chain_by_expiry[expiry]
            sorted_strikes = sorted(expiry_chain.keys())

            # Calculate DTE
            try:
                exp_date = datetime.strptime(expiry, "%d-%b-%Y").date()
            except ValueError:
                try:
                    exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
                except ValueError:
                    exp_date = today + timedelta(days=30)
            dte = max((exp_date - today).days, 0)

            # ATM strike: closest to underlying price
            atm_strike = min(
                sorted_strikes,
                key=lambda k: abs(k - underlying_price),
                default=underlying_price,
            )

            # OI and volume aggregation
            total_ce_oi = sum(expiry_chain[s]["ce"]["oi"] for s in sorted_strikes)
            total_pe_oi = sum(expiry_chain[s]["pe"]["oi"] for s in sorted_strikes)
            total_ce_vol = sum(expiry_chain[s]["ce"]["volume"] for s in sorted_strikes)
            total_pe_vol = sum(expiry_chain[s]["pe"]["volume"] for s in sorted_strikes)

            pcr_oi = round(total_pe_oi / total_ce_oi, 4) if total_ce_oi > 0 else 0.0
            pcr_volume = round(total_pe_vol / total_ce_vol, 4) if total_ce_vol > 0 else 0.0

            # Build flattened calls/puts dicts for downstream use
            calls: Dict[float, Dict] = {
                s: {
                    **expiry_chain[s]["ce"],
                    "strike": s,
                    "moneyness": round((s - underlying_price) / underlying_price * 100, 2)
                    if underlying_price else 0.0,
                }
                for s in sorted_strikes
            }
            puts: Dict[float, Dict] = {
                s: {
                    **expiry_chain[s]["pe"],
                    "strike": s,
                    "moneyness": round((underlying_price - s) / underlying_price * 100, 2)
                    if underlying_price else 0.0,
                }
                for s in sorted_strikes
            }

            structured_data[expiry] = {
                "strikes": sorted_strikes,
                "calls": calls,
                "puts": puts,
                "atm_strike": atm_strike,
                "dte": dte,
                "expiry_date": expiry,
                "pcr_oi": pcr_oi,
                "pcr_volume": pcr_volume,
                "total_call_oi": total_ce_oi,
                "total_put_oi": total_pe_oi,
                "total_call_volume": total_ce_vol,
                "total_put_volume": total_pe_vol,
            }

        # Overall PCR
        overall_call_oi = sum(
            d.get("total_call_oi", 0) for d in structured_data.values()
        )
        overall_put_oi = sum(
            d.get("total_put_oi", 0) for d in structured_data.values()
        )
        overall_pcr = (
            round(overall_put_oi / overall_call_oi, 4) if overall_call_oi > 0 else 0.0
        )

        return {
            "symbol": symbol,
            "underlying_price": round(underlying_price, 2),
            "expiries": expiry_dates,
            "near_expiry": expiry_dates[0] if expiry_dates else None,
            "data": structured_data,
            "total_call_oi": overall_call_oi,
            "total_put_oi": overall_put_oi,
            "pcr_overall": overall_pcr,
            "pcr_signal": (
                "Bullish" if overall_pcr > 1.2
                else "Bearish" if overall_pcr < 0.7
                else "Neutral"
            ),
            "timestamp": datetime.now().isoformat(),
        }

    # ── 2. Max Pain ───────────────────────────────────────────────────────────

    def calculate_max_pain(self, chain_data: Dict) -> Dict[str, Any]:
        """
        Max Pain: strike where total intrinsic loss to option buyers is maximum.

        For each candidate strike K_exp:
            Call pain = Σ max(0, K - K_exp) × CE_OI  for all K > K_exp
            Put pain  = Σ max(0, K_exp - K) × PE_OI  for all K < K_exp
            Total pain = Call pain + Put pain

        Max pain = strike with minimum total pain (sellers' optimal level).
        """
        spot = chain_data.get("underlying_price", 0)
        near_expiry = chain_data.get("near_expiry")
        if not near_expiry:
            return {"error": "no expiry data"}

        expiry_data = chain_data.get("data", {}).get(near_expiry, {})
        strikes = expiry_data.get("strikes", [])
        calls = expiry_data.get("calls", {})
        puts = expiry_data.get("puts", {})

        if not strikes:
            return {"error": "no strikes available"}

        pain_values: Dict[float, float] = {}
        for candidate in strikes:
            call_pain = sum(
                max(0.0, float(k) - float(candidate)) * float(calls.get(k, {}).get("oi", 0))
                for k in strikes
            )
            put_pain = sum(
                max(0.0, float(candidate) - float(k)) * float(puts.get(k, {}).get("oi", 0))
                for k in strikes
            )
            pain_values[float(candidate)] = call_pain + put_pain

        if not pain_values:
            return {"error": "could not compute pain values"}

        max_pain_strike = min(pain_values, key=pain_values.get)
        distance_pct = (
            round((max_pain_strike - spot) / spot * 100, 2) if spot else 0.0
        )

        # Sort by strike for charting
        sorted_pain = {
            round(k, 2): round(v / 1e7, 2)  # in crores
            for k, v in sorted(pain_values.items())
        }

        return {
            "max_pain_strike": round(max_pain_strike, 2),
            "current_price": round(spot, 2),
            "distance_pct": distance_pct,
            "direction": "above" if max_pain_strike > spot else "below",
            "pain_values_crores": sorted_pain,
            "min_pain": round(min(pain_values.values()) / 1e7, 2),
            "max_pain_total": round(pain_values[max_pain_strike] / 1e7, 2),
            "interpretation": (
                f"Max pain at {max_pain_strike:.0f} — "
                f"market may drift {'up' if max_pain_strike > spot else 'down'} "
                f"{abs(distance_pct):.1f}% to expiry"
            ),
        }

    # ── 3. IV Surface ─────────────────────────────────────────────────────────

    def calculate_iv_surface(self, chain_data: Dict) -> Dict[str, Any]:
        """
        Build an IV surface (strike × expiry) for heatmap visualisation.
        Also computes IV term structure (ATM IV across expiries).
        """
        spot = chain_data.get("underlying_price", 0)
        expiries = chain_data.get("expiries", [])

        iv_surface: Dict[str, Dict] = {}      # expiry → {strike: avg_iv}
        term_structure: List[Dict] = []       # [{expiry, dte, atm_iv}]
        all_ivs: List[float] = []

        for expiry in expiries:
            expiry_data = chain_data.get("data", {}).get(expiry, {})
            strikes = expiry_data.get("strikes", [])
            calls = expiry_data.get("calls", {})
            puts = expiry_data.get("puts", {})
            dte = expiry_data.get("dte", 30)
            atm = expiry_data.get("atm_strike", spot)

            iv_by_strike: Dict[float, float] = {}
            atm_iv_list: List[float] = []

            for strike in strikes:
                c_iv = float(calls.get(strike, {}).get("iv", 0) or 0)
                p_iv = float(puts.get(strike, {}).get("iv", 0) or 0)
                valid_ivs = [v for v in [c_iv, p_iv] if v > 0.5]  # min 0.5% IV
                if valid_ivs:
                    avg_iv = round(sum(valid_ivs) / len(valid_ivs), 2)
                    iv_by_strike[float(strike)] = avg_iv
                    all_ivs.append(avg_iv)
                    if abs(float(strike) - float(atm)) / max(float(atm), 1) < 0.02:
                        atm_iv_list.append(avg_iv)

            iv_surface[expiry] = iv_by_strike
            atm_iv = round(sum(atm_iv_list) / len(atm_iv_list), 2) if atm_iv_list else 0.0
            term_structure.append({
                "expiry": expiry,
                "dte": dte,
                "atm_iv": atm_iv,
                "t_sqrt": round(math.sqrt(max(dte, 1) / 365.0), 4),
            })

        # Volatility smile per near expiry
        near_expiry = chain_data.get("near_expiry")
        smile_data: List[Dict] = []
        if near_expiry and near_expiry in chain_data.get("data", {}):
            ed = chain_data["data"][near_expiry]
            for strike in ed.get("strikes", []):
                c_iv = float(ed["calls"].get(strike, {}).get("iv", 0) or 0)
                p_iv = float(ed["puts"].get(strike, {}).get("iv", 0) or 0)
                m = round((float(strike) - spot) / max(spot, 1) * 100, 2)
                smile_data.append({
                    "strike": float(strike),
                    "moneyness_pct": m,
                    "call_iv": c_iv,
                    "put_iv": p_iv,
                    "avg_iv": round((c_iv + p_iv) / 2, 2) if c_iv and p_iv else (c_iv or p_iv),
                })

        # IV percentile across the current surface
        current_atm_iv = term_structure[0]["atm_iv"] if term_structure else 0.0
        iv_percentile_surface = 0.0
        if all_ivs:
            below = sum(1 for v in all_ivs if v < current_atm_iv)
            iv_percentile_surface = round(below / len(all_ivs) * 100, 1)

        # Term structure slope
        term_slope = "Contango"  # normal: far IV > near IV
        if len(term_structure) >= 2:
            near_iv = term_structure[0]["atm_iv"]
            far_iv = term_structure[-1]["atm_iv"]
            if near_iv > far_iv * 1.05:
                term_slope = "Backwardation"  # stressed near-term

        return {
            "iv_surface": {
                exp: {round(k, 2): v for k, v in strikes_dict.items()}
                for exp, strikes_dict in iv_surface.items()
            },
            "term_structure": term_structure,
            "smile_near_expiry": smile_data,
            "current_atm_iv": current_atm_iv,
            "iv_percentile_intraday": iv_percentile_surface,
            "term_slope": term_slope,
            "min_iv": round(min(all_ivs), 2) if all_ivs else 0.0,
            "max_iv": round(max(all_ivs), 2) if all_ivs else 0.0,
            "median_iv": round(float(np.median(all_ivs)), 2) if all_ivs else 0.0,
        }

    # ── 4. Greeks for Chain ───────────────────────────────────────────────────

    def calculate_greeks_for_chain(
        self,
        chain_data: Dict,
        risk_free_rate: float = DEFAULT_RFR,
    ) -> Dict[str, Any]:
        """
        Compute Black-Scholes Greeks for every option in the chain.
        Uses NSE-provided IV where available; falls back to Newton-Raphson solve.
        """
        spot = chain_data.get("underlying_price", 0)
        if not spot:
            return {"error": "no underlying price"}

        results: Dict[str, Any] = {}
        for expiry, expiry_data in chain_data.get("data", {}).items():
            strikes = expiry_data.get("strikes", [])
            dte = expiry_data.get("dte", 30)
            T = max(dte / 365.0, 0.001)
            calls = expiry_data.get("calls", {})
            puts = expiry_data.get("puts", {})

            expiry_greeks: List[Dict] = []
            for strike in strikes:
                strike_f = float(strike)
                c_data = calls.get(strike, {})
                p_data = puts.get(strike, {})

                # Get or compute IV
                c_iv_pct = float(c_data.get("iv", 0) or 0)
                p_iv_pct = float(p_data.get("iv", 0) or 0)

                # If NSE IV is missing, try to compute from LTP
                if c_iv_pct < 0.01 and c_data.get("ltp", 0) > 0:
                    c_iv_pct = implied_volatility(
                        c_data["ltp"], spot, strike_f, T, risk_free_rate, "call"
                    ) * 100
                if p_iv_pct < 0.01 and p_data.get("ltp", 0) > 0:
                    p_iv_pct = implied_volatility(
                        p_data["ltp"], spot, strike_f, T, risk_free_rate, "put"
                    ) * 100

                c_sigma = c_iv_pct / 100.0
                p_sigma = p_iv_pct / 100.0

                c_greeks = bs_greeks(spot, strike_f, T, risk_free_rate, c_sigma, "call") if c_sigma > 0 else {}
                p_greeks = bs_greeks(spot, strike_f, T, risk_free_rate, p_sigma, "put") if p_sigma > 0 else {}

                moneyness = round((strike_f - spot) / spot * 100, 2)
                expiry_greeks.append({
                    "strike": strike_f,
                    "dte": dte,
                    "moneyness_pct": moneyness,
                    "call": {
                        "iv_pct": round(c_iv_pct, 2),
                        "ltp": c_data.get("ltp", 0),
                        "oi": c_data.get("oi", 0),
                        **c_greeks,
                    },
                    "put": {
                        "iv_pct": round(p_iv_pct, 2),
                        "ltp": p_data.get("ltp", 0),
                        "oi": p_data.get("oi", 0),
                        **p_greeks,
                    },
                })
            results[expiry] = expiry_greeks

        return {"symbol": chain_data.get("symbol"), "greeks_by_expiry": results}

    # ── 5. OI Analysis ────────────────────────────────────────────────────────

    def calculate_oi_analysis(self, chain_data: Dict) -> Dict[str, Any]:
        """
        Comprehensive OI analysis:
        - OI buildup by strike
        - OI change (adding vs unwinding)
        - Support (max Put OI) and Resistance (max Call OI)
        - OI-based price magnets
        - Interpretation signals
        """
        spot = chain_data.get("underlying_price", 0)
        near_expiry = chain_data.get("near_expiry")
        if not near_expiry:
            return {"error": "no near expiry"}

        expiry_data = chain_data.get("data", {}).get(near_expiry, {})
        strikes = expiry_data.get("strikes", [])
        calls = expiry_data.get("calls", {})
        puts = expiry_data.get("puts", {})

        # Build OI table
        oi_table: List[Dict] = []
        max_call_oi = 0.0
        max_put_oi = 0.0
        resistance_strike = spot
        support_strike = spot

        for strike in strikes:
            s = float(strike)
            c = calls.get(strike, {})
            p = puts.get(strike, {})
            c_oi = float(c.get("oi", 0) or 0)
            p_oi = float(p.get("oi", 0) or 0)
            c_chg = float(c.get("change_oi", 0) or 0)
            p_chg = float(p.get("change_oi", 0) or 0)
            c_ltp = float(c.get("ltp", 0) or 0)
            p_ltp = float(p.get("ltp", 0) or 0)

            oi_table.append({
                "strike": s,
                "call_oi": c_oi,
                "put_oi": p_oi,
                "call_oi_change": c_chg,
                "put_oi_change": p_chg,
                "call_ltp": c_ltp,
                "put_ltp": p_ltp,
                "total_oi": c_oi + p_oi,
                "oi_ratio": round(p_oi / c_oi, 2) if c_oi > 0 else 0.0,
            })

            if c_oi > max_call_oi:
                max_call_oi = c_oi
                resistance_strike = s
            if p_oi > max_put_oi:
                max_put_oi = p_oi
                support_strike = s

        # OI change signals
        call_oi_addition = [r for r in oi_table if r["call_oi_change"] > 0]
        put_oi_addition = [r for r in oi_table if r["put_oi_change"] > 0]
        call_oi_unwind = [r for r in oi_table if r["call_oi_change"] < 0]
        put_oi_unwind = [r for r in oi_table if r["put_oi_change"] < 0]

        total_call_oi_added = sum(r["call_oi_change"] for r in call_oi_addition)
        total_put_oi_added = sum(r["put_oi_change"] for r in put_oi_addition)

        # Top 5 OI strikes
        top_call_strikes = sorted(oi_table, key=lambda x: x["call_oi"], reverse=True)[:5]
        top_put_strikes = sorted(oi_table, key=lambda x: x["put_oi"], reverse=True)[:5]

        # Price magnets: strikes with OI in top 20% within 5% of spot
        oi_threshold = sorted([r["total_oi"] for r in oi_table], reverse=True)
        top_20pct_threshold = oi_threshold[max(len(oi_threshold) // 5, 1)] if oi_threshold else 0

        magnets = [
            r for r in oi_table
            if r["total_oi"] >= top_20pct_threshold
            and abs(r["strike"] - spot) / max(spot, 1) < 0.05
        ]

        # Interpretation
        net_call_oi_chg = sum(r["call_oi_change"] for r in oi_table)
        net_put_oi_chg = sum(r["put_oi_change"] for r in oi_table)
        pcr_oi = expiry_data.get("pcr_oi", 1.0)

        signals: List[str] = []
        if net_put_oi_chg > net_call_oi_chg > 0:
            signals.append("Put writing dominant — bullish sentiment (sellers expecting floor)")
        if net_call_oi_chg > net_put_oi_chg > 0:
            signals.append("Call writing dominant — bearish/capped sentiment")
        if total_put_oi_added > total_call_oi_added:
            signals.append(f"Put OI buildup +{total_put_oi_added:,.0f} — support building")
        if pcr_oi > 1.2:
            signals.append(f"PCR {pcr_oi:.2f} — elevated put OI, contrarian bullish signal")
        elif pcr_oi < 0.7:
            signals.append(f"PCR {pcr_oi:.2f} — low put OI, market complacent or bearish")

        return {
            "oi_table": oi_table,
            "resistance_strike": round(resistance_strike, 2),
            "support_strike": round(support_strike, 2),
            "resistance_call_oi": round(max_call_oi, 0),
            "support_put_oi": round(max_put_oi, 0),
            "top_5_call_oi_strikes": top_call_strikes,
            "top_5_put_oi_strikes": top_put_strikes,
            "price_magnets": magnets,
            "total_call_oi_added": round(total_call_oi_added, 0),
            "total_put_oi_added": round(total_put_oi_added, 0),
            "net_call_oi_change": round(net_call_oi_chg, 0),
            "net_put_oi_change": round(net_put_oi_chg, 0),
            "pcr_oi": pcr_oi,
            "signals": signals,
            "call_writing_buildup": net_call_oi_chg > 0,
            "put_writing_buildup": net_put_oi_chg > 0,
        }

    # ── 6. Volatility Skew ────────────────────────────────────────────────────

    def calculate_skew(self, chain_data: Dict) -> Dict[str, Any]:
        """
        Compute volatility skew metrics:
        - 25-delta skew (Put IV - Call IV at ±25 delta)
        - Risk reversal (25d Put - 25d Call)
        - Butterfly spread (0.5*(25d Call + 25d Put) - ATM)
        - Skew across all expiries
        """
        spot = chain_data.get("underlying_price", 0)
        if not spot:
            return {"error": "no underlying price"}

        skew_by_expiry: List[Dict] = []

        for expiry in chain_data.get("expiries", []):
            expiry_data = chain_data.get("data", {}).get(expiry, {})
            strikes = expiry_data.get("strikes", [])
            calls = expiry_data.get("calls", {})
            puts = expiry_data.get("puts", {})
            dte = expiry_data.get("dte", 30)
            T = max(dte / 365.0, 0.001)
            atm = expiry_data.get("atm_strike", spot)

            # ATM IV (average of call and put ATM)
            atm_c_iv = float(calls.get(atm, {}).get("iv", 0) or 0)
            atm_p_iv = float(puts.get(atm, {}).get("iv", 0) or 0)
            atm_iv = (atm_c_iv + atm_p_iv) / 2.0 if (atm_c_iv + atm_p_iv) > 0 else 20.0

            # Find 25-delta strikes by computing greeks
            target_delta_call = 0.25
            target_delta_put = -0.25

            best_25d_call_iv: Optional[float] = None
            best_25d_put_iv: Optional[float] = None
            best_call_delta_diff = float("inf")
            best_put_delta_diff = float("inf")

            for strike in strikes:
                strike_f = float(strike)
                c_iv_pct = float(calls.get(strike, {}).get("iv", 0) or 0)
                p_iv_pct = float(puts.get(strike, {}).get("iv", 0) or 0)

                if c_iv_pct > 0.5:
                    c_sigma = c_iv_pct / 100.0
                    g = bs_greeks(spot, strike_f, T, DEFAULT_RFR, c_sigma, "call")
                    diff = abs(g.get("delta", 0) - target_delta_call)
                    if diff < best_call_delta_diff:
                        best_call_delta_diff = diff
                        best_25d_call_iv = c_iv_pct

                if p_iv_pct > 0.5:
                    p_sigma = p_iv_pct / 100.0
                    g = bs_greeks(spot, strike_f, T, DEFAULT_RFR, p_sigma, "put")
                    diff = abs(g.get("delta", 0) - target_delta_put)
                    if diff < best_put_delta_diff:
                        best_put_delta_diff = diff
                        best_25d_put_iv = p_iv_pct

            # 25-delta skew
            skew_25d: Optional[float] = None
            risk_reversal: Optional[float] = None
            butterfly: Optional[float] = None

            if best_25d_put_iv is not None and best_25d_call_iv is not None:
                skew_25d = round(best_25d_put_iv - best_25d_call_iv, 2)
                risk_reversal = round(best_25d_put_iv - best_25d_call_iv, 2)
                butterfly = round(
                    0.5 * (best_25d_call_iv + best_25d_put_iv) - atm_iv, 2
                )

            # OTM skew: IV at 95% moneyness (put OTM) vs 105% (call OTM)
            otm_put_strike = min(strikes, key=lambda k: abs(float(k) - spot * 0.95), default=None)
            otm_call_strike = min(strikes, key=lambda k: abs(float(k) - spot * 1.05), default=None)
            otm_put_iv = float(puts.get(otm_put_strike, {}).get("iv", 0) or 0) if otm_put_strike else 0.0
            otm_call_iv = float(calls.get(otm_call_strike, {}).get("iv", 0) or 0) if otm_call_strike else 0.0
            otm_skew = round(otm_put_iv - otm_call_iv, 2) if (otm_put_iv and otm_call_iv) else None

            skew_by_expiry.append({
                "expiry": expiry,
                "dte": dte,
                "atm_iv": round(atm_iv, 2),
                "skew_25d": skew_25d,
                "risk_reversal_25d": risk_reversal,
                "butterfly_25d": butterfly,
                "otm_skew_5pct": otm_skew,
                "25d_put_iv": round(best_25d_put_iv, 2) if best_25d_put_iv else None,
                "25d_call_iv": round(best_25d_call_iv, 2) if best_25d_call_iv else None,
                "skew_interpretation": (
                    "Left-skewed (put premium — fear of downside)"
                    if (skew_25d or 0) > 2
                    else "Right-skewed (call premium — fear of upside/earnings)"
                    if (skew_25d or 0) < -2
                    else "Symmetric (balanced risk perception)"
                ),
            })

        near_skew = skew_by_expiry[0] if skew_by_expiry else {}
        return {
            "skew_by_expiry": skew_by_expiry,
            "near_expiry_skew": near_skew,
            "skew_term_structure": [
                {"expiry": s["expiry"], "dte": s["dte"], "skew_25d": s["skew_25d"]}
                for s in skew_by_expiry
            ],
        }

    # ── 7. Expected Move ──────────────────────────────────────────────────────

    def calculate_expected_move(self, chain_data: Dict, days: int = 30) -> Dict[str, Any]:
        """
        Expected move = ATM straddle price / spot price.
        1σ move = straddle / spot
        2σ move = 2 × straddle / spot
        Adjusted for custom horizon using IV sqrt-of-time scaling.
        """
        spot = chain_data.get("underlying_price", 0)
        if not spot:
            return {"error": "no spot price"}

        near_expiry = chain_data.get("near_expiry")
        if not near_expiry:
            return {"error": "no near expiry"}

        expiry_data = chain_data.get("data", {}).get(near_expiry, {})
        atm_strike = expiry_data.get("atm_strike", spot)
        calls = expiry_data.get("calls", {})
        puts = expiry_data.get("puts", {})
        dte = expiry_data.get("dte", 30)

        atm_call_ltp = float(calls.get(atm_strike, {}).get("ltp", 0) or 0)
        atm_put_ltp = float(puts.get(atm_strike, {}).get("ltp", 0) or 0)
        straddle_price = atm_call_ltp + atm_put_ltp

        # 1σ expected move at near-expiry DTE
        em_pct = straddle_price / spot * 100 if spot > 0 else 0.0

        # Scale to custom horizon
        atm_iv = expiry_data.get("pcr_oi", 1.0)  # fallback
        atm_call_iv = float(calls.get(atm_strike, {}).get("iv", 0) or 0)
        atm_put_iv = float(puts.get(atm_strike, {}).get("iv", 0) or 0)
        avg_atm_iv = (atm_call_iv + atm_put_iv) / 2.0 if (atm_call_iv + atm_put_iv) else 20.0

        # Scale expected move to `days` using IV × √(days/365)
        em_days_pct = avg_atm_iv * math.sqrt(days / 365.0) if avg_atm_iv > 0 else em_pct

        upper_1s = round(spot * (1 + em_days_pct / 100), 2)
        lower_1s = round(spot * (1 - em_days_pct / 100), 2)
        upper_2s = round(spot * (1 + 2 * em_days_pct / 100), 2)
        lower_2s = round(spot * (1 - 2 * em_days_pct / 100), 2)

        # Probability inside ±1σ: ~68.27% for normal distribution
        return {
            "spot": round(spot, 2),
            "atm_strike": round(float(atm_strike), 2),
            "straddle_price": round(straddle_price, 2),
            "straddle_pct": round(em_pct, 2),
            "atm_iv_pct": round(avg_atm_iv, 2),
            "horizon_days": days,
            "expected_move_pct_1sigma": round(em_days_pct, 2),
            "expected_move_pct_2sigma": round(2 * em_days_pct, 2),
            "range_1sigma": {"upper": upper_1s, "lower": lower_1s},
            "range_2sigma": {"upper": upper_2s, "lower": lower_2s},
            "prob_inside_1sigma": 68.27,
            "prob_inside_2sigma": 95.45,
            "dte_to_near_expiry": dte,
        }

    # ── 8. IV Rank / Percentile ───────────────────────────────────────────────

    def get_iv_rank_percentile(
        self, symbol: str, current_iv: float
    ) -> Dict[str, Any]:
        """
        IV Rank and IV Percentile using yfinance historical data.
        We use historical volatility (HV) as a proxy for IV history.

        IV Rank = (current_iv - 52w_low_iv) / (52w_high_iv - 52w_low_iv) × 100
        IV Percentile = % of days where IV was below current
        """
        cache_key = f"iv_rank_{symbol}_{round(current_iv, 1)}"
        cached = self._cached(cache_key, ttl=3600)
        if cached is not None:
            return cached

        try:
            ticker = yf.Ticker(f"{symbol}.NS")
            hist = ticker.history(period="1y")

            if hist.empty or len(hist) < 30:
                raise ValueError("insufficient history")

            closes = hist["Close"].dropna()
            # Rolling 20-day HV (annualised)
            log_returns = np.log(closes / closes.shift(1)).dropna()
            rolling_hv = log_returns.rolling(20).std() * math.sqrt(252) * 100
            hv_series = rolling_hv.dropna()

            if len(hv_series) < 2:
                raise ValueError("insufficient HV series")

            iv_52w_high = float(hv_series.max())
            iv_52w_low = float(hv_series.min())
            hv_values = hv_series.tolist()

            iv_rank = (
                (current_iv - iv_52w_low) / (iv_52w_high - iv_52w_low) * 100
                if (iv_52w_high - iv_52w_low) > 0
                else 50.0
            )
            iv_percentile = (
                sum(1 for v in hv_values if v < current_iv) / len(hv_values) * 100
            )

            current_hv20 = float(hv_series.iloc[-1]) if not hv_series.empty else 0.0
            iv_hv_ratio = round(current_iv / current_hv20, 2) if current_hv20 > 0 else 0.0

            result = {
                "symbol": symbol,
                "current_iv": round(current_iv, 2),
                "current_hv20": round(current_hv20, 2),
                "iv_hv_ratio": iv_hv_ratio,
                "iv_rank": round(iv_rank, 1),
                "iv_percentile": round(iv_percentile, 1),
                "iv_52w_high": round(iv_52w_high, 2),
                "iv_52w_low": round(iv_52w_low, 2),
                "iv_regime": (
                    "High IV — options expensive, favour selling strategies"
                    if iv_rank > 70
                    else "Low IV — options cheap, favour buying strategies"
                    if iv_rank < 30
                    else "Moderate IV — balanced approach"
                ),
                "strategy_bias": (
                    "Sell premium (straddles, iron condors)"
                    if iv_rank > 70
                    else "Buy premium (straddles, debit spreads)"
                    if iv_rank < 30
                    else "Neutral — context-dependent"
                ),
            }
            self._store(cache_key, result)
            return result

        except Exception as exc:
            logger.warning(f"IV rank for {symbol}: {exc}")
            return {
                "symbol": symbol,
                "current_iv": round(current_iv, 2),
                "iv_rank": 50.0,
                "iv_percentile": 50.0,
                "iv_52w_high": current_iv * 1.5,
                "iv_52w_low": current_iv * 0.5,
                "error": str(exc),
            }

    # ── 9. Build Options Dashboard ────────────────────────────────────────────

    def build_options_dashboard(self, symbol: str) -> Dict[str, Any]:
        """
        Master function: fetch + parse + analyse options for a symbol.
        Returns a complete options dashboard payload.
        """
        cache_key = f"dashboard_{symbol.upper()}"
        cached = self._cached(cache_key, ttl=60)
        if cached is not None:
            return cached

        sym = symbol.upper()
        raw = self._client.get_option_chain(sym)
        if not raw:
            return {"error": f"Could not fetch option chain for {sym}", "symbol": sym}

        chain = self.parse_option_chain(raw, sym)
        if not chain.get("expiries"):
            return {"error": "Empty option chain", "symbol": sym, "raw_keys": list(raw.keys())}

        # Near expiry ATM IV for IV rank
        near_expiry = chain.get("near_expiry")
        current_iv = 0.0
        if near_expiry:
            ed = chain["data"].get(near_expiry, {})
            atm = ed.get("atm_strike")
            if atm:
                c_iv = float(ed.get("calls", {}).get(atm, {}).get("iv", 0) or 0)
                p_iv = float(ed.get("puts", {}).get(atm, {}).get("iv", 0) or 0)
                current_iv = (c_iv + p_iv) / 2.0 if (c_iv + p_iv) else 0.0

        # Run all analytics
        max_pain = self.calculate_max_pain(chain)
        iv_surface = self.calculate_iv_surface(chain)
        greeks = self.calculate_greeks_for_chain(chain)
        oi_analysis = self.calculate_oi_analysis(chain)
        skew = self.calculate_skew(chain)
        expected_move = self.calculate_expected_move(chain, days=near_expiry and
            chain["data"].get(near_expiry, {}).get("dte", 30) or 30)
        iv_rank = self.get_iv_rank_percentile(sym, current_iv) if current_iv > 0 else {}
        gex = calculate_gex(chain)
        vanna_charm = calculate_vanna_charm(chain)

        result = {
            "symbol": sym,
            "underlying_price": chain.get("underlying_price"),
            "timestamp": datetime.now().isoformat(),
            "chain_summary": {
                "expiries": chain.get("expiries", []),
                "near_expiry": near_expiry,
                "total_call_oi": chain.get("total_call_oi"),
                "total_put_oi": chain.get("total_put_oi"),
                "pcr_overall": chain.get("pcr_overall"),
                "pcr_signal": chain.get("pcr_signal"),
            },
            "max_pain": max_pain,
            "iv_surface": iv_surface,
            "greeks": greeks,
            "oi_analysis": oi_analysis,
            "skew": skew,
            "expected_move": expected_move,
            "iv_rank": iv_rank,
            "gamma_exposure": gex,
            "vanna_charm": vanna_charm,
        }

        self._store(cache_key, result)
        return result

    # ── 10. Rollover Data ─────────────────────────────────────────────────────

    def get_rollover_data(self, symbol: str) -> Dict[str, Any]:
        """
        Analyse F&O rollover metrics between near month and next month.
        Computes rollover %, cost of carry, and direction bias.
        """
        raw_oi = self._client.get_oi_data(symbol)
        if not raw_oi:
            return {"error": f"No OI data for {symbol}"}

        # Parse futures data from quote-derivative response
        futures_data = raw_oi.get("stocks", [])
        near_month_futures: Optional[Dict] = None
        next_month_futures: Optional[Dict] = None
        near_month_oi = 0
        next_month_oi = 0

        for item in futures_data:
            meta = item.get("metadata", {})
            inst_type = meta.get("instrumentType", "")
            if inst_type not in ("Stock Futures", "Index Futures", "FUTSTK", "FUTIDX"):
                continue
            exp = meta.get("expiryDate", "")
            oi_val = float(meta.get("openInterest", 0) or 0)

            if near_month_futures is None:
                near_month_futures = meta
                near_month_oi = oi_val
            elif next_month_futures is None:
                next_month_futures = meta
                next_month_oi = oi_val

        if not near_month_futures:
            return {"error": "No futures data found in OI response"}

        total_oi = near_month_oi + next_month_oi
        rollover_pct = (
            round(next_month_oi / total_oi * 100, 2) if total_oi > 0 else 0.0
        )

        near_fut_price = float(near_month_futures.get("lastPrice", 0) or 0)
        spot_price = float(raw_oi.get("underlyingValue", 0)
                          or raw_oi.get("info", {}).get("underlyingValue", 0) or 0)

        # Cost of carry
        today = datetime.now(timezone.utc).date()
        try:
            exp_date = datetime.strptime(
                near_month_futures.get("expiryDate", ""), "%d-%b-%Y"
            ).date()
            dte = max((exp_date - today).days, 1)
        except Exception:
            dte = 30

        basis = round(near_fut_price - spot_price, 2) if (near_fut_price and spot_price) else 0.0
        basis_pct = round(basis / spot_price * 100, 2) if spot_price else 0.0
        annualised_coc = (
            round(basis_pct * (365.0 / dte), 2) if dte > 0 and spot_price else 0.0
        )

        # Rollover direction: rising next month OI with rising prices = bullish roll
        near_price_chg = float(near_month_futures.get("change", 0) or 0)
        rollover_bias = (
            "Bullish" if (next_month_oi > near_month_oi * 0.3 and near_price_chg > 0)
            else "Bearish" if (next_month_oi > near_month_oi * 0.3 and near_price_chg < 0)
            else "Neutral"
        )

        return {
            "symbol": symbol,
            "near_month_oi": near_month_oi,
            "next_month_oi": next_month_oi,
            "total_oi": total_oi,
            "rollover_pct": rollover_pct,
            "near_futures_price": round(near_fut_price, 2),
            "spot_price": round(spot_price, 2),
            "basis": basis,
            "basis_pct": basis_pct,
            "annualised_cost_of_carry": annualised_coc,
            "dte_to_near_expiry": dte,
            "rollover_bias": rollover_bias,
            "interpretation": (
                f"Rollover {rollover_pct:.1f}% complete. "
                f"Basis {basis_pct:+.2f}% ({annualised_coc:+.2f}% annualised COC). "
                f"Rollover sentiment: {rollover_bias}."
            ),
        }

    # ── 11. Strategy Analyser ─────────────────────────────────────────────────

    def analyze_options_strategy(
        self,
        symbol: str,
        strategy: str,
        strikes: List[float],
        expiry: str,
    ) -> Dict[str, Any]:
        """
        Analyse a multi-leg options strategy.

        Supported strategies:
            straddle, strangle, bull_spread, bear_spread,
            iron_condor, covered_call
        """
        sym = symbol.upper()
        raw = self._client.get_option_chain(sym)
        if not raw:
            return {"error": f"No chain data for {sym}"}

        chain = self.parse_option_chain(raw, sym)
        spot = chain.get("underlying_price", 0)

        # Find expiry data
        expiry_data = chain.get("data", {}).get(expiry)
        if not expiry_data:
            # Try nearest expiry
            expiry = chain.get("near_expiry", "")
            expiry_data = chain.get("data", {}).get(expiry, {})

        dte = expiry_data.get("dte", 30)
        T = max(dte / 365.0, 0.001)
        r = DEFAULT_RFR
        calls_chain = expiry_data.get("calls", {})
        puts_chain = expiry_data.get("puts", {})

        def get_option(strike: float, opt_type: str) -> Dict:
            s = strike
            data = (calls_chain if opt_type == "call" else puts_chain).get(s, {})
            if not data:
                # Try rounded strike
                all_strikes = list(calls_chain.keys() if opt_type == "call" else puts_chain.keys())
                closest = min(all_strikes, key=lambda k: abs(float(k) - strike), default=strike)
                data = (calls_chain if opt_type == "call" else puts_chain).get(closest, {})
            ltp = float(data.get("ltp", 0) or 0)
            iv = float(data.get("iv", 0) or 0) / 100.0
            if iv < 0.01 and ltp > 0:
                iv = implied_volatility(ltp, spot, strike, T, r, opt_type)
            return {"ltp": ltp, "iv": iv, "oi": data.get("oi", 0), "strike": strike}

        # Build legs based on strategy
        legs: List[Dict] = []  # {type, strike, qty (+ long, - short)}
        strategy_lower = strategy.lower()

        if strategy_lower == "straddle":
            k = strikes[0] if strikes else expiry_data.get("atm_strike", spot)
            c = get_option(k, "call")
            p = get_option(k, "put")
            legs = [
                {"type": "call", "strike": k, "qty": +1, "premium": c["ltp"], "iv": c["iv"]},
                {"type": "put", "strike": k, "qty": +1, "premium": p["ltp"], "iv": p["iv"]},
            ]
        elif strategy_lower == "strangle":
            k_call = strikes[0] if len(strikes) > 0 else spot * 1.03
            k_put = strikes[1] if len(strikes) > 1 else spot * 0.97
            c = get_option(k_call, "call")
            p = get_option(k_put, "put")
            legs = [
                {"type": "call", "strike": k_call, "qty": +1, "premium": c["ltp"], "iv": c["iv"]},
                {"type": "put", "strike": k_put, "qty": +1, "premium": p["ltp"], "iv": p["iv"]},
            ]
        elif strategy_lower == "bull_spread":
            k_low = strikes[0] if len(strikes) > 0 else spot
            k_high = strikes[1] if len(strikes) > 1 else spot * 1.05
            c_low = get_option(k_low, "call")
            c_high = get_option(k_high, "call")
            legs = [
                {"type": "call", "strike": k_low, "qty": +1, "premium": c_low["ltp"], "iv": c_low["iv"]},
                {"type": "call", "strike": k_high, "qty": -1, "premium": c_high["ltp"], "iv": c_high["iv"]},
            ]
        elif strategy_lower == "bear_spread":
            k_high = strikes[0] if len(strikes) > 0 else spot
            k_low = strikes[1] if len(strikes) > 1 else spot * 0.95
            p_high = get_option(k_high, "put")
            p_low = get_option(k_low, "put")
            legs = [
                {"type": "put", "strike": k_high, "qty": +1, "premium": p_high["ltp"], "iv": p_high["iv"]},
                {"type": "put", "strike": k_low, "qty": -1, "premium": p_low["ltp"], "iv": p_low["iv"]},
            ]
        elif strategy_lower == "iron_condor":
            k_put_sell = strikes[0] if len(strikes) > 0 else spot * 0.97
            k_put_buy = strikes[1] if len(strikes) > 1 else spot * 0.95
            k_call_sell = strikes[2] if len(strikes) > 2 else spot * 1.03
            k_call_buy = strikes[3] if len(strikes) > 3 else spot * 1.05
            ps = get_option(k_put_sell, "put")
            pb = get_option(k_put_buy, "put")
            cs = get_option(k_call_sell, "call")
            cb = get_option(k_call_buy, "call")
            legs = [
                {"type": "put", "strike": k_put_sell, "qty": -1, "premium": ps["ltp"], "iv": ps["iv"]},
                {"type": "put", "strike": k_put_buy, "qty": +1, "premium": pb["ltp"], "iv": pb["iv"]},
                {"type": "call", "strike": k_call_sell, "qty": -1, "premium": cs["ltp"], "iv": cs["iv"]},
                {"type": "call", "strike": k_call_buy, "qty": +1, "premium": cb["ltp"], "iv": cb["iv"]},
            ]
        elif strategy_lower == "covered_call":
            k_call = strikes[0] if strikes else spot * 1.03
            c = get_option(k_call, "call")
            legs = [
                {"type": "stock", "strike": spot, "qty": +1, "premium": spot, "iv": 0.0},
                {"type": "call", "strike": k_call, "qty": -1, "premium": c["ltp"], "iv": c["iv"]},
            ]
        else:
            return {"error": f"Unknown strategy: {strategy}"}

        # Net premium (positive = debit, negative = credit)
        net_premium = sum(
            leg["qty"] * leg["premium"]
            for leg in legs
            if leg["type"] in ("call", "put")
        )

        # P&L across price range
        price_range = [round(spot * m / 100, 2) for m in range(80, 121, 2)]
        pnl_curve: List[Dict] = []
        for price_at_exp in price_range:
            total_pnl = 0.0
            for leg in legs:
                qty = leg["qty"]
                k = leg["strike"]
                ltype = leg["type"]
                prem = leg["premium"]
                if ltype == "call":
                    intrinsic = max(0.0, price_at_exp - k)
                    total_pnl += qty * (intrinsic - prem)
                elif ltype == "put":
                    intrinsic = max(0.0, k - price_at_exp)
                    total_pnl += qty * (intrinsic - prem)
                elif ltype == "stock":
                    total_pnl += qty * (price_at_exp - k)
            pnl_curve.append({"price": price_at_exp, "pnl": round(total_pnl, 2)})

        max_profit_row = max(pnl_curve, key=lambda x: x["pnl"])
        max_loss_row = min(pnl_curve, key=lambda x: x["pnl"])

        # Breakevens (sign changes in P&L curve)
        breakevens: List[float] = []
        for i in range(1, len(pnl_curve)):
            if pnl_curve[i - 1]["pnl"] * pnl_curve[i]["pnl"] < 0:
                breakevens.append(
                    round((pnl_curve[i - 1]["price"] + pnl_curve[i]["price"]) / 2, 2)
                )

        # Combined Greeks for position
        def position_greeks() -> Dict[str, float]:
            total = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
            for leg in legs:
                if leg["type"] == "stock":
                    total["delta"] += leg["qty"]
                    continue
                iv = leg["iv"]
                if iv <= 0:
                    continue
                g = bs_greeks(spot, leg["strike"], T, r, iv, leg["type"])
                for greek in ("delta", "gamma", "theta", "vega"):
                    total[greek] += leg["qty"] * g.get(greek, 0.0)
            return {k: round(v, 4) for k, v in total.items()}

        pos_greeks = position_greeks()

        return {
            "symbol": sym,
            "strategy": strategy,
            "expiry": expiry,
            "spot_price": round(spot, 2),
            "dte": dte,
            "legs": legs,
            "net_premium": round(net_premium, 2),
            "position_type": "Debit" if net_premium > 0 else "Credit",
            "max_profit": max_profit_row["pnl"],
            "max_loss": max_loss_row["pnl"],
            "breakevens": breakevens,
            "pnl_curve": pnl_curve,
            "position_greeks": pos_greeks,
        }
