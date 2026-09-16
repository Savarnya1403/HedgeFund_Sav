"""
Alternative & Economic Data Module for IndiaHedge Terminal
Sources: Google Trends, World Bank API, NSE FII data, RSS news feeds,
         Yahoo Finance proxies for macro indicators
All real data — no simulation.
"""
from __future__ import annotations
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import warnings

import numpy as np
import pandas as pd
import requests
import yfinance as yf

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# GOOGLE TRENDS
# ─────────────────────────────────────────────────────────────────────────────

class GoogleTrendsData:
    _cache: Dict[str, Any] = {}
    _cache_ts: Dict[str, float] = {}
    CACHE_TTL = 3600

    @classmethod
    def _cached(cls, key: str) -> Optional[Any]:
        if key in cls._cache and (time.time() - cls._cache_ts.get(key, 0)) < cls.CACHE_TTL:
            return cls._cache[key]
        return None

    @classmethod
    def _store(cls, key: str, val: Any):
        cls._cache[key] = val
        cls._cache_ts[key] = time.time()

    @classmethod
    def get_search_trends(cls, symbol: str, company_name: str,
                          timeframe: str = "today 12-m") -> Dict[str, Any]:
        key = f"trends_{symbol}_{timeframe}"
        cached = cls._cached(key)
        if cached:
            return cached
        try:
            from pytrends.request import TrendReq
            pt = TrendReq(hl="en-US", tz=330, timeout=(10, 25))
            kw = f"{company_name} share price"
            pt.build_payload([kw], cat=0, timeframe=timeframe, geo="IN")
            iot = pt.interest_over_time()
            if iot is None or iot.empty:
                return {"symbol": symbol, "error": "no data"}
            vals = iot[kw].tolist()
            dates = [str(d)[:10] for d in iot.index.tolist()]
            avg_6m = float(np.mean(vals[-26:])) if len(vals) >= 26 else float(np.mean(vals))
            current = float(vals[-1]) if vals else 0
            direction = "RISING" if current > avg_6m * 1.1 else "FALLING" if current < avg_6m * 0.9 else "STABLE"
            result = {
                "symbol": symbol, "keyword": kw,
                "current_interest": current, "avg_6m": round(avg_6m, 1),
                "direction": direction, "timeframe": timeframe,
                "series": [{"date": d, "value": v} for d, v in zip(dates, vals)],
                "signal": "BULLISH" if direction == "RISING" else "BEARISH" if direction == "FALLING" else "NEUTRAL",
                "interpretation": (
                    "Rising retail search interest may precede price moves" if direction == "RISING"
                    else "Declining retail interest — stock fading from attention" if direction == "FALLING"
                    else "Stable retail search interest"
                ),
            }
            cls._store(key, result)
            return result
        except ImportError:
            return {"symbol": symbol, "error": "pytrends not installed"}
        except Exception as e:
            logger.debug(f"Trends {symbol}: {e}")
            return {"symbol": symbol, "error": str(e)}

    @classmethod
    def get_relative_interest(cls, symbols_names: Dict[str, str]) -> Dict[str, Any]:
        """Compare search interest for up to 5 companies."""
        key = "trends_relative_" + "_".join(list(symbols_names.keys())[:5])
        cached = cls._cached(key)
        if cached:
            return cached
        try:
            from pytrends.request import TrendReq
            pt = TrendReq(hl="en-US", tz=330, timeout=(10, 25))
            kws = [f"{name} share price" for name in list(symbols_names.values())[:5]]
            pt.build_payload(kws, cat=0, timeframe="today 3-m", geo="IN")
            iot = pt.interest_over_time()
            if iot is None or iot.empty:
                return {"error": "no data"}
            scores = {}
            for sym, name in list(symbols_names.items())[:5]:
                kw = f"{name} share price"
                if kw in iot.columns:
                    scores[sym] = round(float(iot[kw].mean()), 1)
            result = {"relative_scores": scores, "generated_at": datetime.now().isoformat()}
            cls._store(key, result)
            return result
        except Exception as e:
            logger.debug(f"Relative trends: {e}")
            return {"error": str(e)}

    @classmethod
    def get_breakout_searches(cls, company_names: Dict[str, str],
                              threshold: int = 70) -> List[Dict]:
        results = []
        for sym, name in list(company_names.items())[:10]:
            try:
                data = cls.get_search_trends(sym, name, "today 3-m")
                if data.get("current_interest", 0) >= threshold:
                    results.append({
                        "symbol": sym, "company": name,
                        "current_interest": data["current_interest"],
                        "direction": data.get("direction"),
                        "signal": data.get("signal"),
                    })
                time.sleep(0.5)
            except Exception:
                pass
        return sorted(results, key=lambda x: x["current_interest"], reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# ECONOMIC INDICATORS
# ─────────────────────────────────────────────────────────────────────────────

class EconomicIndicators:
    _cache: Dict[str, Any] = {}
    _cache_ts: Dict[str, float] = {}

    @classmethod
    def _cached(cls, key: str, ttl: int = 3600) -> Optional[Any]:
        if key in cls._cache and (time.time() - cls._cache_ts.get(key, 0)) < ttl:
            return cls._cache[key]
        return None

    @classmethod
    def _store(cls, key: str, val: Any):
        cls._cache[key] = val
        cls._cache_ts[key] = time.time()

    @classmethod
    def get_india_gdp_data(cls) -> Dict[str, Any]:
        cached = cls._cached("india_gdp", 86400)
        if cached:
            return cached
        try:
            url = ("https://api.worldbank.org/v2/country/IN/indicator/"
                   "NY.GDP.MKTP.KD.ZG?format=json&mrv=10&per_page=10")
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                payload = r.json()
                if isinstance(payload, list) and len(payload) > 1:
                    entries = [e for e in payload[1] if e.get("value") is not None]
                    entries.sort(key=lambda x: x.get("date", ""), reverse=True)
                    result = {
                        "latest_growth_pct": round(float(entries[0]["value"]), 2) if entries else None,
                        "latest_year": entries[0]["date"] if entries else None,
                        "history": [
                            {"year": e["date"], "growth_pct": round(float(e["value"]), 2)}
                            for e in entries[:8]
                        ],
                        "source": "World Bank",
                    }
                    cls._store("india_gdp", result)
                    return result
        except Exception as e:
            logger.debug(f"GDP: {e}")
        return {"error": "unavailable"}

    @classmethod
    def get_india_cpi(cls) -> Dict[str, Any]:
        cached = cls._cached("india_cpi", 43200)
        if cached:
            return cached
        try:
            url = ("https://api.worldbank.org/v2/country/IN/indicator/"
                   "FP.CPI.TOTL.ZG?format=json&mrv=12&per_page=12")
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                payload = r.json()
                if isinstance(payload, list) and len(payload) > 1:
                    entries = [e for e in payload[1] if e.get("value") is not None]
                    entries.sort(key=lambda x: x.get("date", ""), reverse=True)
                    latest = round(float(entries[0]["value"]), 2) if entries else None
                    result = {
                        "latest_cpi_yoy_pct": latest,
                        "latest_year": entries[0]["date"] if entries else None,
                        "trend": (
                            "RISING" if len(entries) >= 2 and entries[0]["value"] > entries[1]["value"]
                            else "FALLING" if len(entries) >= 2 and entries[0]["value"] < entries[1]["value"]
                            else "STABLE"
                        ),
                        "rbi_target": 4.0,
                        "above_target": latest > 4.0 if latest else None,
                        "history": [
                            {"year": e["date"], "cpi_pct": round(float(e["value"]), 2)}
                            for e in entries[:8]
                        ],
                        "source": "World Bank",
                    }
                    cls._store("india_cpi", result)
                    return result
        except Exception as e:
            logger.debug(f"CPI: {e}")
        return {"error": "unavailable"}

    @classmethod
    def get_us_macro_via_yfinance(cls) -> Dict[str, Any]:
        cached = cls._cached("us_macro", 900)
        if cached:
            return cached
        try:
            symbols = {
                "us_10y_yield": "^TNX", "us_2y_yield": "^IRX",
                "dollar_index": "DX-Y.NYB", "sp500": "^GSPC",
                "gold": "GC=F", "oil_wti": "CL=F",
                "vix": "^VIX", "nasdaq": "^IXIC",
            }
            result: Dict[str, Any] = {}
            for name, sym in symbols.items():
                try:
                    ticker = yf.Ticker(sym)
                    hist = ticker.history(period="5d")
                    if not hist.empty:
                        c = hist["Close"]
                        price = float(c.iloc[-1])
                        chg_1d = float((c.iloc[-1] / c.iloc[-2] - 1) * 100) if len(c) >= 2 else 0
                        chg_1m = float((c.iloc[-1] / c.iloc[0] - 1) * 100)
                        result[name] = {"price": round(price, 3), "chg_1d_pct": round(chg_1d, 2), "chg_5d_pct": round(chg_1m, 2)}
                except Exception:
                    pass
            # Yield curve inversion
            us10 = result.get("us_10y_yield", {}).get("price", 0)
            us2 = result.get("us_2y_yield", {}).get("price", 0)
            if us10 and us2:
                spread = us10 - us2
                result["yield_curve"] = {
                    "spread_10y_2y": round(spread, 3),
                    "inverted": spread < 0,
                    "signal": "RECESSION_RISK" if spread < 0 else "NORMAL",
                }
            cls._store("us_macro", result)
            return result
        except Exception as e:
            logger.debug(f"US macro: {e}")
            return {"error": str(e)}

    @classmethod
    def get_india_macro_via_yfinance(cls) -> Dict[str, Any]:
        cached = cls._cached("india_macro_yf", 900)
        if cached:
            return cached
        try:
            symbols = {
                "nifty50": "^NSEI", "sensex": "^BSESN",
                "nifty_bank": "^NSEBANK", "india_vix": "^INDIAVIX",
                "nifty_it": "^CNXIT",
                "usdinr": "USDINR=X", "eurinr": "EURINR=X",
            }
            result: Dict[str, Any] = {}
            for name, sym in symbols.items():
                try:
                    ticker = yf.Ticker(sym)
                    hist = ticker.history(period="1mo")
                    if not hist.empty:
                        c = hist["Close"]
                        price = float(c.iloc[-1])
                        chg_1d = float((c.iloc[-1] / c.iloc[-2] - 1) * 100) if len(c) >= 2 else 0
                        chg_1m = float((c.iloc[-1] / c.iloc[0] - 1) * 100)
                        result[name] = {
                            "price": round(price, 2),
                            "chg_1d_pct": round(chg_1d, 2),
                            "chg_1m_pct": round(chg_1m, 2),
                        }
                except Exception:
                    pass
            cls._store("india_macro_yf", result)
            return result
        except Exception as e:
            return {"error": str(e)}

    @classmethod
    def get_fii_monthly_trend(cls) -> Dict[str, Any]:
        cached = cls._cached("fii_monthly", 3600)
        if cached:
            return cached
        try:
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Referer": "https://www.nseindia.com/",
            }
            s = requests.Session()
            s.verify = False
            s.headers.update(headers)
            s.get("https://www.nseindia.com/", timeout=10)
            r = s.get("https://www.nseindia.com/api/fiidiiTradeReact", timeout=15)
            if r.status_code == 200:
                data = r.json()
                rows = data if isinstance(data, list) else data.get("data", [])
                monthly: Dict[str, Dict[str, float]] = {}
                for row in rows:
                    date_str = row.get("date", "")
                    try:
                        dt = datetime.strptime(date_str, "%d-%b-%Y")
                        month_key = dt.strftime("%Y-%m")
                    except Exception:
                        continue
                    fii_buy = float(str(row.get("fiiBuy", 0) or 0).replace(",", ""))
                    fii_sell = float(str(row.get("fiiSell", 0) or 0).replace(",", ""))
                    net = fii_buy - fii_sell
                    if month_key not in monthly:
                        monthly[month_key] = {"buy": 0, "sell": 0, "net": 0, "days": 0}
                    monthly[month_key]["buy"] += fii_buy
                    monthly[month_key]["sell"] += fii_sell
                    monthly[month_key]["net"] += net
                    monthly[month_key]["days"] += 1

                monthly_list = sorted(
                    [{"month": k, **v} for k, v in monthly.items()],
                    key=lambda x: x["month"], reverse=True
                )[:12]

                # 3-month trend
                nets_3m = [m["net"] for m in monthly_list[:3]]
                trend_3m = "BUYING" if sum(nets_3m) > 0 else "SELLING"

                result = {
                    "monthly": monthly_list,
                    "trend_3m": trend_3m,
                    "total_net_3m_cr": round(sum(nets_3m) / 1e7, 0),
                    "sentiment": "BULLISH" if trend_3m == "BUYING" else "BEARISH",
                }
                cls._store("fii_monthly", result)
                return result
        except Exception as e:
            logger.debug(f"FII monthly: {e}")
        return {"error": "unavailable"}


# ─────────────────────────────────────────────────────────────────────────────
# SENTIMENT INDICATORS
# ─────────────────────────────────────────────────────────────────────────────

class SentimentIndicators:
    _cache: Dict[str, Any] = {}
    _cache_ts: Dict[str, float] = {}

    @classmethod
    def _cached(cls, key: str, ttl: int = 300) -> Optional[Any]:
        if key in cls._cache and (time.time() - cls._cache_ts.get(key, 0)) < ttl:
            return cls._cache[key]
        return None

    @classmethod
    def _store(cls, key: str, val: Any):
        cls._cache[key] = val
        cls._cache_ts[key] = time.time()

    @classmethod
    def get_fear_greed_india(cls) -> Dict[str, Any]:
        cached = cls._cached("fear_greed", 300)
        if cached:
            return cached
        try:
            components: Dict[str, float] = {}
            score_total = 0.0
            weight_total = 0.0

            # 1. Market Momentum — Nifty50 vs 125-day SMA (weight 25%)
            try:
                nifty = yf.Ticker("^NSEI")
                hist = nifty.history(period="1y")
                if not hist.empty and len(hist) >= 125:
                    c = hist["Close"].values
                    price = c[-1]
                    sma125 = np.mean(c[-125:])
                    momentum_score = min(100, max(0, 50 + (price / sma125 - 1) * 500))
                    components["market_momentum"] = round(float(momentum_score), 1)
                    score_total += momentum_score * 0.25
                    weight_total += 0.25
            except Exception:
                pass

            # 2. India VIX (weight 25%) — low VIX = greed
            try:
                vix_ticker = yf.Ticker("^INDIAVIX")
                vix_hist = vix_ticker.history(period="3mo")
                if not vix_hist.empty:
                    vix = float(vix_hist["Close"].iloc[-1])
                    vix_50d = float(vix_hist["Close"].tail(50).mean())
                    # Low VIX = greed; invert
                    if vix < vix_50d * 0.8:
                        vix_score = 75
                    elif vix > vix_50d * 1.3:
                        vix_score = 20
                    else:
                        vix_score = 50 - (vix - vix_50d) / vix_50d * 100
                    vix_score = min(100, max(0, vix_score))
                    components["india_vix"] = round(float(vix_score), 1)
                    components["vix_level"] = round(vix, 2)
                    score_total += vix_score * 0.25
                    weight_total += 0.25
            except Exception:
                pass

            # 3. 52W High vs Low breadth (weight 20%)
            try:
                nifty50_syms = [
                    "RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS",
                    "HINDUNILVR.NS","BAJFINANCE.NS","BHARTIARTL.NS","SBIN.NS","KOTAKBANK.NS",
                    "ITC.NS","LT.NS","AXISBANK.NS","TITAN.NS","ASIANPAINT.NS",
                    "MARUTI.NS","ULTRACEMCO.NS","WIPRO.NS","HCLTECH.NS","NESTLEIND.NS",
                ]
                highs = 0; lows = 0
                for sym in nifty50_syms[:15]:
                    try:
                        t = yf.Ticker(sym)
                        h = t.history(period="1y")
                        if not h.empty and len(h) >= 252:
                            c = h["Close"].values
                            pct_from_high = (c[-1] / np.max(c[-252:]) - 1) * 100
                            pct_from_low = (c[-1] / np.min(c[-252:]) - 1) * 100
                            if pct_from_high > -5:
                                highs += 1
                            if pct_from_low < 10:
                                lows += 1
                    except Exception:
                        pass
                total_checked = len(nifty50_syms[:15])
                if total_checked > 0:
                    breadth_score = min(100, max(0, (highs - lows) / total_checked * 100 + 50))
                    components["stock_strength"] = round(float(breadth_score), 1)
                    components["near_52w_high"] = highs
                    components["near_52w_low"] = lows
                    score_total += breadth_score * 0.20
                    weight_total += 0.20
            except Exception:
                pass

            # 4. Advance-Decline ratio from NIFTY50 1d returns (weight 15%)
            try:
                nifty_b = yf.Ticker("^NSEI")
                nifty_it = yf.Ticker("^CNXIT")
                nifty_bank = yf.Ticker("^NSEBANK")
                indices = [nifty_b, nifty_it, nifty_bank]
                advances = 0; declines = 0
                for idx in indices:
                    try:
                        h = idx.history(period="5d")
                        if not h.empty and len(h) >= 2:
                            ret = float(h["Close"].iloc[-1] / h["Close"].iloc[-2] - 1)
                            if ret > 0: advances += 1
                            else: declines += 1
                    except Exception:
                        pass
                total = advances + declines
                if total > 0:
                    ad_score = advances / total * 100
                    components["advance_decline"] = round(float(ad_score), 1)
                    score_total += ad_score * 0.15
                    weight_total += 0.15
            except Exception:
                pass

            # 5. Global risk appetite — S&P500 trend (weight 15%)
            try:
                sp = yf.Ticker("^GSPC")
                sp_hist = sp.history(period="3mo")
                if not sp_hist.empty:
                    c = sp_hist["Close"].values
                    sma50 = np.mean(c[-50:]) if len(c) >= 50 else np.mean(c)
                    risk_score = min(100, max(0, 50 + (c[-1] / sma50 - 1) * 300))
                    components["global_risk"] = round(float(risk_score), 1)
                    score_total += risk_score * 0.15
                    weight_total += 0.15
            except Exception:
                pass

            # Composite score
            composite = round(score_total / weight_total, 1) if weight_total > 0 else 50.0

            if composite <= 25:
                label = "EXTREME_FEAR"
                color = "#ff4444"
            elif composite <= 45:
                label = "FEAR"
                color = "#ff8800"
            elif composite <= 55:
                label = "NEUTRAL"
                color = "#ffcc00"
            elif composite <= 75:
                label = "GREED"
                color = "#88cc00"
            else:
                label = "EXTREME_GREED"
                color = "#00cc44"

            result = {
                "score": composite,
                "label": label,
                "color": color,
                "components": components,
                "interpretation": (
                    "Market in extreme fear — historically a BUY signal for contrarians" if label == "EXTREME_FEAR"
                    else "Fearful market — good entry opportunities may exist" if label == "FEAR"
                    else "Market balanced — no strong directional bias" if label == "NEUTRAL"
                    else "Market greedy — be cautious with new positions" if label == "GREED"
                    else "Extreme greed — high probability of pullback"
                ),
                "generated_at": datetime.now().isoformat(),
            }
            cls._store("fear_greed", result)
            return result
        except Exception as e:
            logger.error(f"Fear/greed: {e}")
            return {"score": 50, "label": "NEUTRAL", "error": str(e)}

    @classmethod
    def get_market_breadth_advanced(cls, symbols: List[str] = None) -> Dict[str, Any]:
        cached = cls._cached("breadth_adv", 300)
        if cached:
            return cached
        if symbols is None:
            symbols = [
                "RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK",
                "HINDUNILVR","BAJFINANCE","BHARTIARTL","SBIN","KOTAKBANK",
                "ITC","LT","AXISBANK","TITAN","ASIANPAINT",
                "MARUTI","ULTRACEMCO","WIPRO","HCLTECH","NESTLEIND",
                "ADANIENT","ADANIPORTS","POWERGRID","NTPC","ONGC",
                "COALINDIA","GRASIM","BAJAJFINSV","TATASTEEL","JSWSTEEL",
                "HDFCLIFE","SBILIFE","DIVISLAB","CIPLA","DRREDDY",
                "SUNPHARMA","TECHM","INDUSINDBK","BPCL","EICHERMOT",
                "BRITANNIA","HINDALCO","TATAMOTORS","APOLLOHOSP","HEROMOTOCO",
            ]

        above_50 = 0; above_200 = 0; advances = 0; declines = 0
        total = 0
        new_highs = 0; new_lows = 0

        for sym in symbols:
            try:
                ticker = yf.Ticker(f"{sym}.NS" if not sym.endswith(".NS") else sym)
                hist = ticker.history(period="1y")
                if hist.empty or len(hist) < 20:
                    continue
                c = hist["Close"].values
                price = c[-1]
                prev = c[-2] if len(c) >= 2 else price
                total += 1
                if price > prev:
                    advances += 1
                else:
                    declines += 1
                if len(c) >= 50 and price > np.mean(c[-50:]):
                    above_50 += 1
                if len(c) >= 200 and price > np.mean(c[-200:]):
                    above_200 += 1
                if len(c) >= 252:
                    if price >= np.max(c[-252:]) * 0.98:
                        new_highs += 1
                    if price <= np.min(c[-252:]) * 1.02:
                        new_lows += 1
            except Exception:
                pass

        if total == 0:
            return {"error": "no data"}

        ad_ratio = advances / declines if declines > 0 else advances
        result = {
            "total_stocks": total,
            "advances": advances,
            "declines": declines,
            "unchanged": total - advances - declines,
            "advance_decline_ratio": round(ad_ratio, 2),
            "pct_above_50dma": round(above_50 / total * 100, 1),
            "pct_above_200dma": round(above_200 / total * 100, 1),
            "new_52w_highs": new_highs,
            "new_52w_lows": new_lows,
            "high_low_index": round(new_highs / (new_highs + new_lows) * 100, 1) if (new_highs + new_lows) > 0 else 50,
            "breadth_signal": (
                "BULLISH" if above_50 / total > 0.65 and advances > declines
                else "BEARISH" if above_50 / total < 0.35 and declines > advances
                else "NEUTRAL"
            ),
            "generated_at": datetime.now().isoformat(),
        }
        cls._store("breadth_adv", result)
        return result

    @classmethod
    def get_fii_sentiment_score(cls) -> Dict[str, Any]:
        cached = cls._cached("fii_score", 900)
        if cached:
            return cached
        try:
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Referer": "https://www.nseindia.com/",
            }
            s = requests.Session()
            s.verify = False
            s.headers.update(headers)
            s.get("https://www.nseindia.com/", timeout=10)
            r = s.get("https://www.nseindia.com/api/fiidiiTradeReact", timeout=15)

            daily_nets: List[float] = []
            if r.status_code == 200:
                data = r.json()
                rows = data if isinstance(data, list) else data.get("data", [])
                for row in rows[:20]:
                    try:
                        buy = float(str(row.get("fiiBuy", 0) or 0).replace(",", ""))
                        sell = float(str(row.get("fiiSell", 0) or 0).replace(",", ""))
                        daily_nets.append(buy - sell)
                    except Exception:
                        pass

            if not daily_nets:
                return {"score": 50, "sentiment": "NEUTRAL", "error": "no data"}

            net_5d = sum(daily_nets[:5])
            net_10d = sum(daily_nets[:10])
            net_20d = sum(daily_nets[:20])

            # Score 0-100 based on cumulative flow
            def _flow_score(net: float, scale: float = 5000) -> float:
                return min(100, max(0, 50 + net / scale * 25))

            score_5d = _flow_score(net_5d, 5000)
            score_10d = _flow_score(net_10d, 8000)
            score_20d = _flow_score(net_20d, 12000)
            composite = score_5d * 0.5 + score_10d * 0.3 + score_20d * 0.2

            result = {
                "score": round(composite, 1),
                "net_5d_cr": round(net_5d / 1e7, 0),
                "net_10d_cr": round(net_10d / 1e7, 0),
                "net_20d_cr": round(net_20d / 1e7, 0),
                "sentiment": (
                    "STRONG_BUYING" if composite > 70
                    else "BUYING" if composite > 55
                    else "SELLING" if composite < 45
                    else "STRONG_SELLING" if composite < 30
                    else "NEUTRAL"
                ),
                "daily_nets": [round(n / 1e7, 0) for n in daily_nets[:10]],
            }
            cls._store("fii_score", result)
            return result
        except Exception as e:
            logger.debug(f"FII score: {e}")
            return {"score": 50, "sentiment": "NEUTRAL", "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# NEWS AGGREGATOR
# ─────────────────────────────────────────────────────────────────────────────

class NewsAggregator:
    _cache: Dict[str, Any] = {}
    _cache_ts: Dict[str, float] = {}
    CACHE_TTL = 300

    BULLISH_KW = {
        "surge","rally","rise","gain","profit","growth","record","beat","strong",
        "positive","upside","buy","upgrade","expand","acquisition","deal","invest",
        "boost","outperform","bullish","revenue","earnings","launch","win","award",
    }
    BEARISH_KW = {
        "fall","drop","crash","loss","decline","miss","weak","downgrade","cut",
        "risk","concern","sell","bearish","fraud","penalty","ban","issue","warning",
        "layoff","default","debt","investigation","lawsuit","fine","probe","halt",
    }

    @classmethod
    def _cached(cls, key: str) -> Optional[Any]:
        if key in cls._cache and (time.time() - cls._cache_ts.get(key, 0)) < cls.CACHE_TTL:
            return cls._cache[key]
        return None

    @classmethod
    def _store(cls, key: str, val: Any):
        cls._cache[key] = val
        cls._cache_ts[key] = time.time()

    @classmethod
    def _parse_rss(cls, url: str, max_items: int = 15) -> List[Dict]:
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            root = ET.fromstring(r.content)
            ns = {"media": "http://search.yahoo.com/mrss/"}
            items = []
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub = (item.findtext("pubDate") or "").strip()
                source_el = item.find("source")
                source = source_el.text if source_el is not None else ""
                desc = (item.findtext("description") or "").strip()
                # Strip HTML tags
                desc = re.sub(r"<[^>]+>", "", desc)[:200]
                sentiment = cls.calculate_news_sentiment(title + " " + desc)
                items.append({
                    "title": title,
                    "url": link,
                    "source": source,
                    "published_at": pub,
                    "summary": desc,
                    "sentiment": sentiment,
                })
                if len(items) >= max_items:
                    break
            return items
        except Exception as e:
            logger.debug(f"RSS {url}: {e}")
            return []

    @classmethod
    def get_economic_news(cls) -> List[Dict]:
        cached = cls._cached("eco_news")
        if cached:
            return cached
        url = "https://news.google.com/rss/search?q=india+economy+RBI+inflation&hl=en-IN&gl=IN&ceid=IN:en"
        items = cls._parse_rss(url, 20)
        cls._store("eco_news", items)
        return items

    @classmethod
    def get_market_news(cls) -> List[Dict]:
        cached = cls._cached("mkt_news")
        if cached:
            return cached
        url = "https://news.google.com/rss/search?q=NSE+BSE+nifty+sensex+stock+market&hl=en-IN&gl=IN&ceid=IN:en"
        items = cls._parse_rss(url, 25)
        cls._store("mkt_news", items)
        return items

    @classmethod
    def get_sector_news(cls, sector: str) -> List[Dict]:
        cached = cls._cached(f"sec_news_{sector}")
        if cached:
            return cached
        sector_kws = {
            "banking": "india banking HDFC ICICI SBI RBI interest rate",
            "it": "india IT technology TCS Infosys Wipro rupee dollar",
            "pharma": "india pharma drug FDA USFDA healthcare",
            "auto": "india auto EV electric vehicle Maruti Tata Motors",
            "infra": "india infrastructure roads highways railways",
            "energy": "india oil gas ONGC crude petroleum Reliance",
            "fmcg": "india FMCG consumer staples Hindustan Unilever ITC",
            "metals": "india steel metals commodity Tata JSW Hindalco",
            "realty": "india real estate DLF housing property market",
        }
        kw = sector_kws.get(sector.lower(), f"india {sector} stocks")
        url = f"https://news.google.com/rss/search?q={requests.utils.quote(kw)}&hl=en-IN&gl=IN&ceid=IN:en"
        items = cls._parse_rss(url, 15)
        cls._store(f"sec_news_{sector}", items)
        return items

    @classmethod
    def get_company_news(cls, symbol: str, company_name: str) -> List[Dict]:
        cached = cls._cached(f"co_news_{symbol}")
        if cached:
            return cached
        kw = f"{company_name} stock share NSE BSE"
        url = f"https://news.google.com/rss/search?q={requests.utils.quote(kw)}&hl=en-IN&gl=IN&ceid=IN:en"
        items = cls._parse_rss(url, 12)
        cls._store(f"co_news_{symbol}", items)
        return items

    @classmethod
    def get_regulatory_updates(cls) -> List[Dict]:
        cached = cls._cached("reg_updates")
        if cached:
            return cached
        url = "https://news.google.com/rss/search?q=SEBI+RBI+regulation+circular+india&hl=en-IN&gl=IN&ceid=IN:en"
        items = cls._parse_rss(url, 10)
        cls._store("reg_updates", items)
        return items

    @classmethod
    def calculate_news_sentiment(cls, text: str) -> Dict[str, Any]:
        words = set(text.lower().split())
        bull_hits = len(words & cls.BULLISH_KW)
        bear_hits = len(words & cls.BEARISH_KW)
        total = len(words)
        if total == 0:
            return {"label": "NEUTRAL", "score": 0, "bull": 0, "bear": 0}
        score = (bull_hits - bear_hits) / max(total, 1) * 100
        label = "POSITIVE" if score > 1 else "NEGATIVE" if score < -1 else "NEUTRAL"
        return {
            "label": label,
            "score": round(score, 2),
            "bull_signals": bull_hits,
            "bear_signals": bear_hits,
        }

    @classmethod
    def get_aggregate_sentiment(cls, news_list: List[Dict]) -> Dict[str, Any]:
        if not news_list:
            return {"label": "NEUTRAL", "score": 0, "positive": 0, "negative": 0, "neutral": 0}
        positive = sum(1 for n in news_list if n.get("sentiment", {}).get("label") == "POSITIVE")
        negative = sum(1 for n in news_list if n.get("sentiment", {}).get("label") == "NEGATIVE")
        neutral = len(news_list) - positive - negative
        scores = [n.get("sentiment", {}).get("score", 0) for n in news_list]
        avg_score = float(np.mean(scores)) if scores else 0
        return {
            "label": "POSITIVE" if avg_score > 1 else "NEGATIVE" if avg_score < -1 else "NEUTRAL",
            "score": round(avg_score, 2),
            "positive": positive,
            "negative": negative,
            "neutral": neutral,
        }


# ─────────────────────────────────────────────────────────────────────────────
# ALTERNATIVE DATA DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

import re  # needed for sentiment parsing

COMPANY_NAMES = {
    "RELIANCE": "Reliance Industries", "TCS": "Tata Consultancy Services",
    "HDFCBANK": "HDFC Bank", "INFY": "Infosys", "ICICIBANK": "ICICI Bank",
    "HINDUNILVR": "Hindustan Unilever", "BAJFINANCE": "Bajaj Finance",
    "BHARTIARTL": "Bharti Airtel", "SBIN": "State Bank of India",
    "KOTAKBANK": "Kotak Mahindra Bank", "ITC": "ITC", "LT": "Larsen Toubro",
    "AXISBANK": "Axis Bank", "TITAN": "Titan Company", "ASIANPAINT": "Asian Paints",
    "MARUTI": "Maruti Suzuki", "WIPRO": "Wipro", "HCLTECH": "HCL Technologies",
    "SUNPHARMA": "Sun Pharma", "TATAMOTORS": "Tata Motors", "ZOMATO": "Zomato",
    "ADANIENT": "Adani Enterprises", "NTPC": "NTPC", "ONGC": "ONGC",
    "TATASTEEL": "Tata Steel", "CIPLA": "Cipla", "DRREDDY": "Dr Reddys",
    "DLF": "DLF", "INDIGO": "IndiGo",
}


class AlternativeDataDashboard:

    @classmethod
    def get_full_alternative_snapshot(cls) -> Dict[str, Any]:
        """Complete alternative data dashboard"""
        result: Dict[str, Any] = {}

        # Economic indicators
        try:
            result["india_gdp"] = EconomicIndicators.get_india_gdp_data()
        except Exception:
            result["india_gdp"] = {}

        try:
            result["india_cpi"] = EconomicIndicators.get_india_cpi()
        except Exception:
            result["india_cpi"] = {}

        try:
            result["us_macro"] = EconomicIndicators.get_us_macro_via_yfinance()
        except Exception:
            result["us_macro"] = {}

        try:
            result["india_macro"] = EconomicIndicators.get_india_macro_via_yfinance()
        except Exception:
            result["india_macro"] = {}

        # FII monthly trend
        try:
            result["fii_trend"] = EconomicIndicators.get_fii_monthly_trend()
        except Exception:
            result["fii_trend"] = {}

        # Fear & Greed
        try:
            result["fear_greed"] = SentimentIndicators.get_fear_greed_india()
        except Exception:
            result["fear_greed"] = {}

        # Market breadth
        try:
            result["market_breadth"] = SentimentIndicators.get_market_breadth_advanced()
        except Exception:
            result["market_breadth"] = {}

        # FII sentiment score
        try:
            result["fii_sentiment"] = SentimentIndicators.get_fii_sentiment_score()
        except Exception:
            result["fii_sentiment"] = {}

        # Top market news
        try:
            news = NewsAggregator.get_market_news()
            result["market_news"] = news[:10]
            result["market_news_sentiment"] = NewsAggregator.get_aggregate_sentiment(news)
        except Exception:
            result["market_news"] = []

        result["generated_at"] = datetime.now().isoformat()
        return result

    @classmethod
    def get_stock_alternative_data(cls, symbol: str) -> Dict[str, Any]:
        """All alternative data for a specific stock"""
        company_name = COMPANY_NAMES.get(symbol.upper(), symbol)
        result: Dict[str, Any] = {"symbol": symbol, "company": company_name}

        # Google Trends
        try:
            result["search_trends"] = GoogleTrendsData.get_search_trends(symbol, company_name)
        except Exception as e:
            result["search_trends"] = {"error": str(e)}

        # Company news with sentiment
        try:
            news = NewsAggregator.get_company_news(symbol, company_name)
            result["news"] = news[:10]
            result["news_sentiment"] = NewsAggregator.get_aggregate_sentiment(news)
        except Exception:
            result["news"] = []
            result["news_sentiment"] = {}

        result["generated_at"] = datetime.now().isoformat()
        return result

    @classmethod
    def get_sector_intelligence(cls, sector: str) -> Dict[str, Any]:
        """Sector-level alternative data and news"""
        result: Dict[str, Any] = {"sector": sector}
        try:
            news = NewsAggregator.get_sector_news(sector)
            result["news"] = news
            result["news_sentiment"] = NewsAggregator.get_aggregate_sentiment(news)
        except Exception:
            result["news"] = []
        return result
