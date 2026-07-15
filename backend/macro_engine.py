"""
Global Macro Intelligence Engine
Tracks 60+ global assets: indices, FX, commodities, bonds, shipping, crypto
Real correlation matrices, yield curves, regime detection, cross-asset signals
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import requests

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────
# ASSET UNIVERSE  (Yahoo Finance tickers)
# ──────────────────────────────────────────────────────────────────

GLOBAL_INDICES = {
    # Indian
    "Nifty50":       "^NSEI",
    "Sensex":        "^BSESN",
    "Nifty Bank":    "^NSEBANK",
    "Nifty IT":      "^CNXIT",
    "India VIX":     "^INDIAVIX",
    # US
    "S&P 500":       "^GSPC",
    "Nasdaq 100":    "^NDX",
    "Dow Jones":     "^DJI",
    "Russell 2000":  "^RUT",
    "VIX":           "^VIX",
    # Europe
    "FTSE 100":      "^FTSE",
    "DAX":           "^GDAXI",
    "CAC 40":        "^FCHI",
    "Euro Stoxx 50": "^STOXX50E",
    # Asia-Pacific
    "Nikkei 225":    "^N225",
    "Hang Seng":     "^HSI",
    "Shanghai Comp": "000001.SS",
    "Kospi":         "^KS11",
    "ASX 200":       "^AXJO",
    "Straits Times": "^STI",
    "Taiwan Weighted":"^TWII",
    # EM
    "Brazil Bovespa":"^BVSP",
    "JSE South Africa":"^J203.JO",
    "Mexico IPC":    "^MXX",
}

FOREX = {
    "USD/INR":   "USDINR=X",
    "EUR/INR":   "EURINR=X",
    "GBP/INR":   "GBPINR=X",
    "JPY/INR":   "JPYINR=X",
    "EUR/USD":   "EURUSD=X",
    "GBP/USD":   "GBPUSD=X",
    "USD/JPY":   "JPY=X",
    "USD/CNY":   "CNY=X",
    "USD/CHF":   "CHF=X",
    "AUD/USD":   "AUDUSD=X",
    "DXY":       "DX-Y.NYB",
    "USD/SGD":   "SGDUSD=X",
    "USD/KRW":   "KRW=X",
    "USD/BRL":   "BRL=X",
    "USD/ZAR":   "ZAR=X",
    "USD/RUB":   "RUB=X",
    "USD/MXN":   "MXN=X",
    "USDINR NDF":"USDINR=X",
}

COMMODITIES = {
    # Energy
    "Crude Oil WTI":  "CL=F",
    "Crude Oil Brent":"BZ=F",
    "Natural Gas":    "NG=F",
    "Gasoline RBOB":  "RB=F",
    "Heating Oil":    "HO=F",
    # Metals
    "Gold":           "GC=F",
    "Silver":         "SI=F",
    "Copper":         "HG=F",
    "Platinum":       "PL=F",
    "Palladium":      "PA=F",
    "Aluminium":      "ALI=F",
    # Agri
    "Wheat":          "ZW=F",
    "Corn":           "ZC=F",
    "Soybean":        "ZS=F",
    "Sugar":          "SB=F",
    "Cotton":         "CT=F",
    "Coffee":         "KC=F",
    # Industrial
    "Steel HRC":      "HRC=F",
    "Iron Ore":       "TIO=F",
    # India MCX proxies
    "MCX Gold":       "GOLDIAM.NS",
    "MCX Silver":     "SILVER.NS",
}

BONDS_RATES = {
    # US Treasuries
    "US 2Y Yield":    "^IRX",
    "US 10Y Yield":   "^TNX",
    "US 30Y Yield":   "^TYX",
    # Spreads via ETFs
    "TLT (20Y Bond)": "TLT",
    "HYG (High Yield)":"HYG",
    "LQD (IG Corp)":  "LQD",
    # India
    "India 10Y GSec": "^INBMK",
    # Other Sovereign
    "Germany Bund 10Y":"DE10YT=RR",
    "Japan JGB 10Y":  "JP10YT=RR",
    "UK Gilt 10Y":    "GB10YT=RR",
}

SHIPPING_TRADE = {
    # Baltic indices via ETFs / proxies
    "Baltic Dry (BDI)":   "BDRY",      # ETF tracking BDI
    "Global Shipping":     "BOAT",      # Breakwave Dry Bulk Shipping ETF
    "Containership":       "KEX",       # Kirby Corp (marine transport)
    # India trade related
    "Adani Ports":         "ADANIPORTS.NS",
    "Concor":              "CONCOR.NS",
    "Cochin Shipyard":     "COCHINSHIP.NS",
    "Shipping Corp India": "SCI.NS",
    "GE Shipping":         "GESHIP.NS",
    # Global logistics
    "Maersk (proxy)":     "AMKBY",
    "FedEx":              "FDX",
    "UPS":                "UPS",
}

CRYPTO_MACRO = {
    "Bitcoin":    "BTC-USD",
    "Ethereum":   "ETH-USD",
    "Bitcoin Gold":"BTG-USD",
    "Crypto Fear ETF": "BITO",
}

# Sector ETFs for India (using sector indices where available)
INDIA_SECTORS = {
    "Nifty FMCG":      "^CNXFMCG",
    "Nifty Pharma":    "^CNXPHARMA",
    "Nifty Auto":      "^CNXAUTO",
    "Nifty Metals":    "^CNXMETAL",
    "Nifty Energy":    "^CNXENERGY",
    "Nifty Realty":    "^CNXREALTY",
    "Nifty Infra":     "^CNXINFRA",
    "Nifty PSE":       "^CNXPSE",
    "Nifty MNC":       "^CNXMNC",
    "Nifty Media":     "^CNXMEDIA",
    "Nifty IT":        "^CNXIT",
    "Nifty Financial": "^CNXFIN",
}

# ──────────────────────────────────────────────────────────────────
# CACHE
# ──────────────────────────────────────────────────────────────────

_macro_cache: Dict[str, Any] = {}
_macro_ts: Dict[str, float] = {}
MACRO_TTL = 300   # 5 min for most macro data
CORR_TTL  = 1800  # 30 min for correlation matrices


def _cached(key: str, ttl: float = MACRO_TTL) -> Optional[Any]:
    if key in _macro_cache and (time.time() - _macro_ts.get(key, 0)) < ttl:
        return _macro_cache[key]
    return None


def _store(key: str, val: Any):
    _macro_cache[key] = val
    _macro_ts[key] = time.time()


# ──────────────────────────────────────────────────────────────────
# SINGLE-ASSET PRICE FETCH  (uses YFData session if available)
# ──────────────────────────────────────────────────────────────────

def _fetch_price(ticker: str, session: requests.Session) -> Optional[Dict]:
    key = f"macro_price_{ticker}"
    cached = _cached(key)
    if cached is not None:
        return cached
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        r = session.get(url, params={"interval": "1d", "range": "5d"}, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        res = (data.get("chart", {}).get("result") or [None])[0]
        if not res:
            return None
        meta = res.get("meta", {})
        price = meta.get("regularMarketPrice", 0)
        prev  = meta.get("chartPreviousClose", price)
        change = price - prev
        change_pct = (change / prev * 100) if prev else 0
        result = {
            "ticker": ticker,
            "price": round(float(price), 4),
            "prev_close": round(float(prev), 4),
            "change": round(float(change), 4),
            "change_pct": round(float(change_pct), 3),
            "currency": meta.get("currency", ""),
            "exchange": meta.get("exchangeName", ""),
        }
        _store(key, result)
        return result
    except Exception as e:
        logger.debug(f"macro price {ticker}: {e}")
        return None


def _fetch_history_array(ticker: str, session: requests.Session, period: str = "1y") -> Optional[np.ndarray]:
    """Return numpy array of daily closes for correlation computation"""
    key = f"macro_hist_{ticker}_{period}"
    cached = _cached(key, CORR_TTL)
    if cached is not None:
        return cached
    range_map = {"1mo": "1mo", "3mo": "3mo", "6mo": "6mo", "1y": "1y", "2y": "2y", "5y": "5y"}
    yf_range = range_map.get(period, "1y")
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        r = session.get(url, params={"interval": "1d", "range": yf_range}, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        res = (data.get("chart", {}).get("result") or [None])[0]
        if not res:
            return None
        closes = res.get("indicators", {}).get("quote", [{}])[0].get("close", [])
        arr = np.array([c for c in closes if c is not None], dtype=float)
        if len(arr) < 10:
            return None
        _store(key, arr)
        return arr
    except Exception as e:
        logger.debug(f"macro hist {ticker}: {e}")
        return None


# ──────────────────────────────────────────────────────────────────
# GLOBAL SNAPSHOT  (parallel fetch of all asset classes)
# ──────────────────────────────────────────────────────────────────

def build_global_snapshot(session: requests.Session) -> Dict:
    key = "global_snapshot"
    cached = _cached(key, MACRO_TTL)
    if cached is not None:
        return cached

    def fetch_group(ticker_map: Dict[str, str]) -> List[Dict]:
        results = []
        for name, ticker in ticker_map.items():
            p = _fetch_price(ticker, session)
            if p:
                p["name"] = name
                results.append(p)
        return results

    snapshot = {
        "indices":   fetch_group(GLOBAL_INDICES),
        "forex":     fetch_group(FOREX),
        "commodities": fetch_group(COMMODITIES),
        "bonds":     fetch_group(BONDS_RATES),
        "shipping":  fetch_group(SHIPPING_TRADE),
        "crypto":    fetch_group(CRYPTO_MACRO),
        "india_sectors": fetch_group(INDIA_SECTORS),
        "computed_at": datetime.now().isoformat(),
    }
    _store(key, snapshot)
    return snapshot


# ──────────────────────────────────────────────────────────────────
# YIELD CURVE ANALYSIS
# ──────────────────────────────────────────────────────────────────

def compute_yield_curve(session: requests.Session) -> Dict:
    key = "yield_curve"
    cached = _cached(key, 1800)
    if cached is not None:
        return cached

    # ^IRX = 13-week T-bill (best free proxy for short end)
    # ^FVX = 5Y yield, ^TNX = 10Y yield, ^TYX = 30Y yield
    # All report in tenths of a percent (e.g. 45.0 = 4.50%)
    us_tickers = {
        "3M":  "^IRX",
        "5Y":  "^FVX",
        "10Y": "^TNX",
        "30Y": "^TYX",
    }

    # Fetch current yields (divide by 10 to convert to percentage)
    us_yields = {}
    for label, ticker in us_tickers.items():
        p = _fetch_price(ticker, session)
        if p and p.get("price"):
            us_yields[label] = round(float(p["price"]) / 10, 3)

    # India yield proxies
    india_10y = _fetch_price("^INBMK", session)
    india_yield = float(india_10y["price"]) if india_10y and india_10y.get("price") else 7.1

    # Use 3M-10Y spread (Fed's preferred recession indicator)
    spread_3m_10y = round((us_yields.get("10Y", 4.5) - us_yields.get("3M", 5.0)), 3)
    is_inverted = spread_3m_10y < 0

    # Historical 10Y for trend
    hist_10y = _fetch_history_array("^TNX", session, "1y")
    us_10y_trend = []
    if hist_10y is not None and len(hist_10y) > 0:
        # Downsample to weekly
        step = max(1, len(hist_10y) // 52)
        us_10y_trend = [round(float(v) / 10, 3) for v in hist_10y[::step]]

    result = {
        "us_curve": us_yields,
        "spread_3m_10y": spread_3m_10y,
        "spread_2_10": spread_3m_10y,   # kept for backward compat with frontend
        "is_inverted": is_inverted,
        "inversion_signal": "RECESSION RISK" if is_inverted else "NORMAL",
        "india_10y": round(india_yield, 2),
        "india_us_spread": round(india_yield - us_yields.get("10Y", 4.5), 2),
        "us_10y_trend": us_10y_trend[-52:],
        "interpretation": (
            "Inverted yield curve historically precedes recessions by 6-18 months. "
            "DII buying and IT/pharma exports may see pressure from strong dollar."
        ) if is_inverted else (
            "Normal upward slope. Growth environment supports cyclicals and financials."
        ),
        "computed_at": datetime.now().isoformat(),
    }
    _store(key, result)
    return result


# ──────────────────────────────────────────────────────────────────
# CORRELATION MATRIX  (Nifty50 vs 20 global assets)
# ──────────────────────────────────────────────────────────────────

CORR_ASSETS = {
    "Nifty50":     "^NSEI",
    "S&P 500":     "^GSPC",
    "Nasdaq":      "^NDX",
    "Nikkei":      "^N225",
    "Hang Seng":   "^HSI",
    "Gold":        "GC=F",
    "Crude WTI":   "CL=F",
    "Copper":      "HG=F",
    "DXY":         "DX-Y.NYB",
    "USD/INR":     "USDINR=X",
    "Bitcoin":     "BTC-USD",
    "US 10Y":      "^TNX",
    "VIX":         "^VIX",
    "Silver":      "SI=F",
    "DAX":         "^GDAXI",
    "FTSE":        "^FTSE",
    "India VIX":   "^INDIAVIX",
    "Natural Gas": "NG=F",
    "Brent":       "BZ=F",
    "Wheat":       "ZW=F",
}

def compute_correlation_matrix(session: requests.Session, period: str = "1y") -> Dict:
    key = f"corr_matrix_{period}"
    cached = _cached(key, CORR_TTL)
    if cached is not None:
        return cached

    arrays: Dict[str, np.ndarray] = {}
    for name, ticker in CORR_ASSETS.items():
        arr = _fetch_history_array(ticker, session, period)
        if arr is not None and len(arr) >= 20:
            arrays[name] = arr

    if len(arrays) < 3:
        return {"error": "insufficient data", "matrix": {}}

    # Align by shortest length
    min_len = min(len(v) for v in arrays.values())
    names = list(arrays.keys())
    returns = np.column_stack([
        np.diff(arrays[n][-min_len:]) / arrays[n][-min_len:-1]
        for n in names
    ])

    corr = np.corrcoef(returns.T)
    matrix: Dict[str, Dict[str, float]] = {}
    for i, n1 in enumerate(names):
        matrix[n1] = {}
        for j, n2 in enumerate(names):
            matrix[n1][n2] = round(float(corr[i, j]), 3)

    # Find top positive and negative correlations with Nifty
    nifty_idx = names.index("Nifty50") if "Nifty50" in names else 0
    nifty_corrs = [(names[j], round(float(corr[nifty_idx, j]), 3))
                   for j in range(len(names)) if j != nifty_idx]
    nifty_corrs.sort(key=lambda x: x[1], reverse=True)

    result = {
        "assets": names,
        "matrix": matrix,
        "period": period,
        "nifty_top_positive": nifty_corrs[:5],
        "nifty_top_negative": list(reversed(nifty_corrs))[:5],
        "data_points": min_len - 1,
        "computed_at": datetime.now().isoformat(),
    }
    _store(key, result)
    return result


# ──────────────────────────────────────────────────────────────────
# MACRO REGIME DETECTOR
# (Uses SPX momentum, VIX level, yield spread, DXY strength)
# ──────────────────────────────────────────────────────────────────

def detect_macro_regime(session: requests.Session) -> Dict:
    key = "macro_regime"
    cached = _cached(key, 900)  # 15 min
    if cached is not None:
        return cached

    def score_asset(ticker: str, lookback: int = 63) -> float:
        arr = _fetch_history_array(ticker, session, "1y")
        if arr is None or len(arr) < lookback + 1:
            return 0.0
        recent = arr[-lookback:]
        ret = (recent[-1] / recent[0] - 1) * 100
        return float(ret)

    signals = {}
    factors = []

    # 1. SPX momentum (3M return)
    spx_3m = score_asset("^GSPC", 63)
    signals["spx_momentum_3m"] = round(spx_3m, 2)
    factors.append(1 if spx_3m > 5 else -1 if spx_3m < -5 else 0)

    # 2. VIX level
    vix = _fetch_price("^VIX", session)
    vix_val = vix["price"] if vix else 20
    signals["vix"] = round(vix_val, 2)
    factors.append(-1 if vix_val > 25 else 1 if vix_val < 15 else 0)

    # 3. India VIX
    ivix = _fetch_price("^INDIAVIX", session)
    ivix_val = ivix["price"] if ivix else 14
    signals["india_vix"] = round(ivix_val, 2)
    factors.append(-1 if ivix_val > 18 else 1 if ivix_val < 12 else 0)

    # 4. DXY trend (strong $ = EM headwind)
    dxy_3m = score_asset("DX-Y.NYB", 63)
    signals["dxy_3m"] = round(dxy_3m, 2)
    factors.append(-1 if dxy_3m > 3 else 1 if dxy_3m < -3 else 0)

    # 5. Gold (safe haven / risk-off signal)
    gold_1m = score_asset("GC=F", 21)
    signals["gold_1m"] = round(gold_1m, 2)
    factors.append(-1 if gold_1m > 5 else 0)  # gold up = risk-off

    # 6. Crude oil (India = net importer; high crude = negative)
    crude_3m = score_asset("CL=F", 63)
    signals["crude_3m"] = round(crude_3m, 2)
    factors.append(-1 if crude_3m > 20 else 1 if crude_3m < -20 else 0)

    # 7. Nifty momentum
    nifty_3m = score_asset("^NSEI", 63)
    signals["nifty_3m"] = round(nifty_3m, 2)
    factors.append(1 if nifty_3m > 5 else -1 if nifty_3m < -5 else 0)

    # 8. Yield spread
    spread = signals.get("yield_spread", 0)
    factors.append(-1 if spread < -0.5 else 0)

    score = sum(factors)
    total = len(factors)
    pct = score / total

    if pct > 0.4:
        regime = "RISK-ON"
        color = "#00d084"
        desc = "Strong positive momentum across equities. FII inflows likely. Cyclicals, banks, infra preferred."
    elif pct < -0.4:
        regime = "RISK-OFF"
        color = "#ff3b3b"
        desc = "Elevated volatility, defensive positioning. Gold, IT exports, pharma may outperform. Reduce leverage."
    else:
        regime = "NEUTRAL"
        color = "#f59e0b"
        desc = "Mixed signals. Stock-specific catalysts driving returns. Wait for clearer macro direction."

    # What changed recently
    changes = []
    if abs(spx_3m) > 10:
        changes.append(f"S&P 500 {'up' if spx_3m > 0 else 'down'} {abs(spx_3m):.1f}% in 3M")
    if vix_val > 25:
        changes.append(f"VIX elevated at {vix_val:.1f}")
    if abs(dxy_3m) > 3:
        changes.append(f"DXY {'strengthening' if dxy_3m > 0 else 'weakening'} ({dxy_3m:+.1f}%)")
    if abs(crude_3m) > 15:
        changes.append(f"Crude {'up' if crude_3m > 0 else 'down'} {abs(crude_3m):.1f}%")

    result = {
        "regime": regime,
        "color": color,
        "score": score,
        "score_pct": round(pct * 100, 1),
        "description": desc,
        "signals": signals,
        "factor_scores": factors,
        "key_changes": changes,
        "india_impact": (
            "Bullish for domestic consumption, financials, capex plays"
        ) if regime == "RISK-ON" else (
            "Bearish for highly leveraged companies, NBFCs, FII-heavy stocks"
        ) if regime == "RISK-OFF" else (
            "Balanced — sector rotation likely"
        ),
        "computed_at": datetime.now().isoformat(),
    }
    _store(key, result)
    return result


# ──────────────────────────────────────────────────────────────────
# CROSS-ASSET MOMENTUM SCANNER
# Detects which asset classes are trending / reversing
# ──────────────────────────────────────────────────────────────────

MOMENTUM_UNIVERSE = {
    **{k: v for k, v in GLOBAL_INDICES.items()},
    **{k: v for k, v in COMMODITIES.items()},
    "DXY": "DX-Y.NYB",
    "USD/INR": "USDINR=X",
    "Bitcoin": "BTC-USD",
    "Gold": "GC=F",
    "Crude WTI": "CL=F",
}

def compute_cross_asset_momentum(session: requests.Session) -> Dict:
    key = "cross_asset_momentum"
    cached = _cached(key, 600)
    if cached is not None:
        return cached

    results = []
    for name, ticker in list(MOMENTUM_UNIVERSE.items())[:30]:
        try:
            arr = _fetch_history_array(ticker, session, "1y")
            if arr is None or len(arr) < 252:
                arr = _fetch_history_array(ticker, session, "6mo")
            if arr is None or len(arr) < 20:
                continue

            c = arr
            ret_1m  = (c[-1] / c[-22] - 1) * 100   if len(c) >= 22  else None
            ret_3m  = (c[-1] / c[-63] - 1) * 100   if len(c) >= 63  else None
            ret_6m  = (c[-1] / c[-126] - 1) * 100  if len(c) >= 126 else None
            ret_1y  = (c[-1] / c[-252] - 1) * 100  if len(c) >= 252 else None

            # Trend: price vs 20/50/200 SMA
            sma20  = np.mean(c[-20:])
            sma50  = np.mean(c[-50:])  if len(c) >= 50  else sma20
            sma200 = np.mean(c[-200:]) if len(c) >= 200 else sma50

            above_20  = c[-1] > sma20
            above_50  = c[-1] > sma50
            above_200 = c[-1] > sma200
            trend_score = sum([above_20, above_50, above_200])  # 0-3

            # Momentum composite
            rets = [r for r in [ret_1m, ret_3m, ret_6m] if r is not None]
            momentum_score = float(np.mean(rets)) if rets else 0.0

            results.append({
                "name": name,
                "ticker": ticker,
                "ret_1m": round(ret_1m, 2) if ret_1m is not None else None,
                "ret_3m": round(ret_3m, 2) if ret_3m is not None else None,
                "ret_6m": round(ret_6m, 2) if ret_6m is not None else None,
                "ret_1y": round(ret_1y, 2) if ret_1y is not None else None,
                "sma20": round(float(sma20), 4),
                "sma200": round(float(sma200), 4),
                "above_200sma": above_200,
                "trend_score": trend_score,
                "momentum_score": round(momentum_score, 2),
                "signal": "STRONG BUY" if trend_score == 3 and momentum_score > 10
                         else "BUY" if trend_score >= 2 and momentum_score > 3
                         else "SELL" if trend_score == 0 and momentum_score < -10
                         else "AVOID" if trend_score <= 1 and momentum_score < -3
                         else "HOLD",
            })
        except Exception as e:
            logger.debug(f"momentum {name}: {e}")

    results.sort(key=lambda x: x["momentum_score"], reverse=True)
    result = {
        "leaders": results[:8],     # top 8 momentum
        "laggards": results[-8:],   # bottom 8 momentum
        "all": results,
        "computed_at": datetime.now().isoformat(),
    }
    _store(key, result)
    return result


# ──────────────────────────────────────────────────────────────────
# INDIA-SPECIFIC MACRO INDICATORS
# Tracks INR sensitivity, FII flow proxies, oil sensitivity
# ──────────────────────────────────────────────────────────────────

INDIA_MACRO_PROXIES = {
    # INR sensitivity (exporters vs importers)
    "IT Exporters (TCS)":       "TCS.NS",
    "IT Exporters (Infosys)":   "INFY.NS",
    "Oil Importer (BPCL)":      "BPCL.NS",
    "Oil Importer (IOC)":       "IOC.NS",
    # Gold import
    "Gold (MCX proxy)":         "GC=F",
    # Capital goods / infra
    "Capital Goods (L&T)":      "LT.NS",
    "Defence (HAL)":            "HAL.NS",
    # Consumption
    "Rural FMCG (ITC)":         "ITC.NS",
    "Urban FMCG (HUL)":         "HINDUNILVR.NS",
    # Banking / credit cycle
    "HDFC Bank":                "HDFCBANK.NS",
    "SBI (PSU Bank)":           "SBIN.NS",
    # External sector
    "Adani Ports":              "ADANIPORTS.NS",
}

def compute_india_macro_sensitivity(session: requests.Session) -> Dict:
    """Computes how INR, crude, and global rates affect Indian sectors"""
    key = "india_macro_sensitivity"
    cached = _cached(key, CORR_TTL)
    if cached is not None:
        return cached

    tickers = {**INDIA_MACRO_PROXIES, "INR/USD": "USDINR=X", "Crude": "CL=F"}
    arrays: Dict[str, np.ndarray] = {}
    for name, ticker in tickers.items():
        arr = _fetch_history_array(ticker, session, "2y")
        if arr is not None and len(arr) >= 30:
            arrays[name] = arr

    if "INR/USD" not in arrays or "Crude" not in arrays:
        return {"error": "insufficient data"}

    min_len = min(len(v) for v in arrays.values())
    names = list(arrays.keys())
    rets = np.column_stack([
        np.diff(arrays[n][-min_len:]) / arrays[n][-min_len:-1]
        for n in names
    ])
    corr = np.corrcoef(rets.T)
    name_idx = {n: i for i, n in enumerate(names)}

    inr_idx   = name_idx.get("INR/USD")
    crude_idx = name_idx.get("Crude")

    sensitivity = []
    for n in names:
        if n in ("INR/USD", "Crude"):
            continue
        i = name_idx[n]
        inr_corr   = round(float(corr[i, inr_idx]), 3) if inr_idx is not None else None
        crude_corr = round(float(corr[i, crude_idx]), 3) if crude_idx is not None else None
        sensitivity.append({
            "stock": n,
            "inr_correlation": inr_corr,
            "crude_correlation": crude_corr,
            "inr_impact": "INR depreciation HELPS" if inr_corr and inr_corr > 0.2
                          else "INR depreciation HURTS" if inr_corr and inr_corr < -0.2
                          else "Neutral to INR",
            "crude_impact": "Higher crude HELPS" if crude_corr and crude_corr > 0.2
                            else "Higher crude HURTS" if crude_corr and crude_corr < -0.2
                            else "Neutral to crude",
        })

    result = {
        "sensitivity": sensitivity,
        "inr_level": arrays.get("INR/USD", np.array([83.0]))[-1],
        "crude_level": arrays.get("Crude", np.array([80.0]))[-1],
        "data_points": min_len - 1,
        "computed_at": datetime.now().isoformat(),
    }
    _store(key, result)
    return result


# ──────────────────────────────────────────────────────────────────
# SHIPPING & TRADE INTELLIGENCE
# Baltic Dry + container rates + India trade flows
# ──────────────────────────────────────────────────────────────────

def get_shipping_data(session: requests.Session) -> Dict:
    key = "shipping_data"
    cached = _cached(key, 900)
    if cached is not None:
        return cached

    shipping_tickers = {
        "Breakwave Dry ETF": "BDRY",
        "Global Shipping ETF": "BOAT",
        "Adani Ports": "ADANIPORTS.NS",
        "CONCOR": "CONCOR.NS",
        "Shipping Corp India": "SCI.NS",
        "GE Shipping": "GESHIP.NS",
        "Cochin Shipyard": "COCHINSHIP.NS",
        "Mazagon Dock": "MAZAGON.NS",
    }

    prices = {}
    for name, ticker in shipping_tickers.items():
        p = _fetch_price(ticker, session)
        if p:
            # get 3M return
            arr = _fetch_history_array(ticker, session, "6mo")
            ret_3m = None
            if arr is not None and len(arr) >= 63:
                ret_3m = round((arr[-1] / arr[-63] - 1) * 100, 2)
            prices[name] = {**p, "name": name, "ret_3m": ret_3m}

    # Trade intelligence
    trade_factors = {
        "crude_import_sensitivity": "HIGH — India imports ~85% of crude needs",
        "gold_import_sensitivity": "HIGH — 2nd largest gold importer globally",
        "electronics_import": "Growing — smartphone & semiconductor dependency",
        "pharma_export": "Strong — generic drugs to US/Europe",
        "it_services_export": "Strong — $250B+ annual IT exports",
        "auto_export": "Growing — Maruti, Tata exports to Africa/EM",
    }

    # Container freight proxy (using shipping ETF trend)
    bdry = prices.get("Breakwave Dry ETF", {})
    freight_trend = "Rising" if (bdry.get("change_pct", 0) or 0) > 2 \
                   else "Falling" if (bdry.get("change_pct", 0) or 0) < -2 \
                   else "Stable"

    result = {
        "shipping_stocks": list(prices.values()),
        "freight_trend": freight_trend,
        "trade_factors": trade_factors,
        "india_current_account": {
            "status": "Deficit",
            "crude_oil_pct": "~35% of import bill",
            "electronics_pct": "~18% of import bill",
            "gold_pct": "~7% of import bill",
            "it_services_surplus": "$250B+ annually",
            "remittances": "$120B+ annually (largest recipient)",
        },
        "shipping_impact_on_india": [
            "Rising BDI → Higher import costs → INR pressure → IT exporters benefit",
            "Port congestion → Inventory build → FMCG supply chain stress",
            "China export slowdown → India manufacturing opportunity",
            "Suez disruptions → Higher costs for European exports/imports",
        ],
        "computed_at": datetime.now().isoformat(),
    }
    _store(key, result)
    return result


# ──────────────────────────────────────────────────────────────────
# GEOPOLITICAL RISK SCORING
# ──────────────────────────────────────────────────────────────────

GEOPOLITICAL_RISKS = [
    {
        "region": "Russia-Ukraine",
        "risk_level": "HIGH",
        "india_impact": "Energy prices elevated; Russia discount crude benefits India",
        "color": "#ff3b3b",
        "sectors_impacted": ["Oil & Gas", "Defence", "Metals"],
        "opportunity": "HAL, BEL, defence PSUs benefit from geopolitical tensions",
    },
    {
        "region": "US-China Tech War",
        "risk_level": "HIGH",
        "india_impact": "India positioned as alternative supply chain hub; PLI schemes gaining traction",
        "color": "#ff3b3b",
        "sectors_impacted": ["IT", "Electronics", "Semiconductors"],
        "opportunity": "Indian IT services, electronics manufacturing (Dixon, Amber) benefit",
    },
    {
        "region": "Middle East Tensions",
        "risk_level": "MEDIUM",
        "india_impact": "~8M Indian workers in Gulf; remittances at risk; oil supply risk",
        "color": "#f59e0b",
        "sectors_impacted": ["Oil & Gas", "Aviation", "Paints"],
        "opportunity": "Defensive plays: ONGC, Oil India may benefit from higher crude",
    },
    {
        "region": "Taiwan Strait",
        "risk_level": "MEDIUM",
        "india_impact": "Semiconductor supply chain disruption; iPhone component risk",
        "color": "#f59e0b",
        "sectors_impacted": ["IT Hardware", "Telecom", "EMS"],
        "opportunity": "India semiconductor PLI could attract TSMC/Intel alternatives",
    },
    {
        "region": "India-Pakistan",
        "risk_level": "LOW",
        "india_impact": "Historical pattern: markets recover within 2-3 weeks post-escalation",
        "color": "#3b82f6",
        "sectors_impacted": ["Defence", "Insurance"],
        "opportunity": "HAL, Bharat Dynamics, DRDO-linked stocks spike on escalation",
    },
    {
        "region": "Africa Political Instability",
        "risk_level": "LOW",
        "india_impact": "Growing Indian corporate presence in Africa; Tata, Airtel exposed",
        "color": "#3b82f6",
        "sectors_impacted": ["Telecom", "Mining"],
        "opportunity": "Monitor Bharti Airtel Africa revenue concentration",
    },
]

HISTORICAL_GEOPOLITICAL_PATTERNS = [
    {
        "event": "India-Pakistan Pulwama (Feb 2019)",
        "nifty_reaction": "-0.3% in 3 days, full recovery in 2 weeks",
        "winners": ["HAL", "BEL", "DRDO-linked", "Gold"],
        "losers": ["Aviation", "Tourism", "Border trade sectors"],
        "duration_days": 14,
    },
    {
        "event": "Galwan Valley Clash (Jun 2020)",
        "nifty_reaction": "-1.2% immediate, flat in 1 month",
        "winners": ["Defence PSUs", "Domestic IT", "Border infra"],
        "losers": ["Chinese JV companies", "Import-heavy sectors"],
        "duration_days": 30,
    },
    {
        "event": "Russia-Ukraine Feb 2022",
        "nifty_reaction": "-3% in 1 week, +8% by end of 2022",
        "winners": ["ONGC", "Fertilizers (short term)", "Defence"],
        "losers": ["Airlines", "Paint companies", "Tyre makers"],
        "duration_days": 180,
    },
    {
        "event": "Israel-Hamas Oct 2023",
        "nifty_reaction": "-1% initial, recovered in 1 week",
        "winners": ["ONGC", "Gold ETFs", "Defence"],
        "losers": ["Airlines", "FMCG (input cost fears)"],
        "duration_days": 10,
    },
]

def get_geopolitical_dashboard() -> Dict:
    return {
        "risks": GEOPOLITICAL_RISKS,
        "historical_patterns": HISTORICAL_GEOPOLITICAL_PATTERNS,
        "overall_risk_level": "MEDIUM",
        "india_resilience_factors": [
            "Largest army globally — regional deterrent",
            "Non-aligned policy gives diplomatic flexibility",
            "Growing defence exports (₹21,083 Cr in FY24)",
            "Energy import diversification (Russia, UAE, Iraq)",
            "Strong forex reserves ($630B+) act as buffer",
        ],
        "watch_list": [
            "US Fed rate decisions (USD/INR sensitivity)",
            "China economic recovery (commodity demand)",
            "OPEC+ production decisions (crude price)",
            "Monsoon forecast (rural demand, agri inflation)",
            "India election calendar (policy continuity)",
        ],
        "computed_at": datetime.now().isoformat(),
    }
