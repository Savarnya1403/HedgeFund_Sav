"""
Indian Hedge Fund Intelligence System v3.0
Direct Yahoo Finance API + NSE API + Multi-Agent Analysis
"""

import asyncio
import json
import logging
import re
import ssl
import time
import warnings
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus
from typing import Any, Dict, List, Optional, Set, Tuple

import analytics as _ana
import macro_engine as _macro
import institutional as _inst
import quant_models as _qm
import recommendation as _rec

import aiohttp
import numpy as np
import pandas as pd
import requests
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from math import log, sqrt, exp, pi

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────────

NIFTY50_SYMBOLS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "HINDUNILVR", "BAJFINANCE", "BHARTIARTL", "SBIN", "KOTAKBANK",
    "ITC", "LT", "AXISBANK", "TITAN", "ASIANPAINT",
    "MARUTI", "ULTRACEMCO", "WIPRO", "HCLTECH", "NESTLEIND",
    "ADANIENT", "ADANIPORTS", "POWERGRID", "NTPC", "ONGC",
    "COALINDIA", "GRASIM", "BAJAJFINSV", "TATASTEEL", "JSWSTEEL",
    "HDFCLIFE", "SBILIFE", "DIVISLAB", "CIPLA", "DRREDDY",
    "SUNPHARMA", "TECHM", "INDUSINDBK", "BPCL", "EICHERMOT",
    "BRITANNIA", "HINDALCO", "TATAMOTORS", "APOLLOHOSP", "HEROMOTOCO",
    "MM", "SHREECEM", "TATACONSUM", "PIDILITIND", "LTIM",
]

NIFTY_NEXT50_SYMBOLS = [
    "DMART", "SIEMENS", "HAVELLS", "DABUR", "MARICO",
    "COLPAL", "GODREJCP", "BERGEPAINT", "KANSAINER", "PAGEIND",
    "BOSCHLTD", "MUTHOOTFIN", "CHOLAFIN", "DLF", "ZOMATO",
    "TVSMOTOR", "VEDL", "SAIL", "OFSS", "BANKBARODA",
    "GAIL", "IOC", "HPCL", "PFC", "RECLTD",
    "NHPC", "IRCTC", "AMBUJACEM", "ACC", "VOLTAS",
    "NAUKRI", "ZYDUSLIFE", "LUPIN", "MANKIND", "UBL",
    "TATACHEM", "JSWENERGY", "INDHOTEL", "HDFCAMC", "ICICIPRULI",
    "NMDC", "BHEL", "BEL", "HAL", "PIIND",
    "INDIGO", "BAJAJ-AUTO", "LODHA", "BAJAJHFL", "POLICYBZR",
]

PSU_SYMBOLS = [
    # PSU Banks
    "PNB", "CANBK", "UNIONBANK", "BANKINDIA", "IOB", "CENTRALBK",
    # PSU Energy
    "OIL", "PETRONET",
    # PSU Power
    "SJVN", "RVNL", "IRFC",
    # PSU Defence
    "BEML", "GRSE", "COCHINSHIP", "MAZAGON", "MIDHANI",
    # PSU Infrastructure
    "RAILTEL", "NBCC", "HUDCO", "CONCOR",
    # PSU Mining/Metals
    "NALCO", "MOIL",
    # PSU Finance
    "RECLTD", "PFC",  # already in next50 but keep for PSU category
]

# Deduplicated combined universe
_seen = set()
ALL_SYMBOLS: list = []
for _s in NIFTY50_SYMBOLS + NIFTY_NEXT50_SYMBOLS + PSU_SYMBOLS:
    if _s not in _seen:
        ALL_SYMBOLS.append(_s)
        _seen.add(_s)

# Company name mapping for news search
COMPANY_NAMES: dict = {
    "RELIANCE": "Reliance Industries", "TCS": "Tata Consultancy Services",
    "HDFCBANK": "HDFC Bank", "INFY": "Infosys", "ICICIBANK": "ICICI Bank",
    "HINDUNILVR": "Hindustan Unilever", "BAJFINANCE": "Bajaj Finance",
    "BHARTIARTL": "Bharti Airtel", "SBIN": "State Bank of India",
    "KOTAKBANK": "Kotak Mahindra Bank", "ITC": "ITC Limited",
    "LT": "Larsen Toubro", "AXISBANK": "Axis Bank", "TITAN": "Titan Company",
    "ASIANPAINT": "Asian Paints", "MARUTI": "Maruti Suzuki",
    "ULTRACEMCO": "UltraTech Cement", "WIPRO": "Wipro", "HCLTECH": "HCL Technologies",
    "NESTLEIND": "Nestle India", "ADANIENT": "Adani Enterprises",
    "ADANIPORTS": "Adani Ports", "POWERGRID": "Power Grid Corporation",
    "NTPC": "NTPC", "ONGC": "ONGC", "COALINDIA": "Coal India",
    "GRASIM": "Grasim Industries", "BAJAJFINSV": "Bajaj Finserv",
    "TATASTEEL": "Tata Steel", "JSWSTEEL": "JSW Steel",
    "HDFCLIFE": "HDFC Life Insurance", "SBILIFE": "SBI Life Insurance",
    "DIVISLAB": "Divi's Laboratories", "CIPLA": "Cipla",
    "DRREDDY": "Dr Reddy's Laboratories", "SUNPHARMA": "Sun Pharmaceutical",
    "TECHM": "Tech Mahindra", "INDUSINDBK": "IndusInd Bank",
    "BPCL": "Bharat Petroleum", "EICHERMOT": "Eicher Motors",
    "BRITANNIA": "Britannia Industries", "HINDALCO": "Hindalco Industries",
    "TATAMOTORS": "Tata Motors", "APOLLOHOSP": "Apollo Hospitals",
    "HEROMOTOCO": "Hero MotoCorp", "MM": "Mahindra and Mahindra",
    "SHREECEM": "Shree Cement", "TATACONSUM": "Tata Consumer Products",
    "PIDILITIND": "Pidilite Industries", "LTIM": "LTIMindtree",
    "DMART": "Avenue Supermarts DMart", "SIEMENS": "Siemens India",
    "HAVELLS": "Havells India", "DABUR": "Dabur India", "MARICO": "Marico",
    "COLPAL": "Colgate Palmolive India", "GODREJCP": "Godrej Consumer Products",
    "BERGEPAINT": "Berger Paints", "PAGEIND": "Page Industries",
    "BOSCHLTD": "Bosch India", "MUTHOOTFIN": "Muthoot Finance",
    "CHOLAFIN": "Cholamandalam Investment", "DLF": "DLF",
    "ZOMATO": "Zomato", "TVSMOTOR": "TVS Motor", "VEDL": "Vedanta",
    "SAIL": "Steel Authority of India", "OFSS": "Oracle Financial Services",
    "BANKBARODA": "Bank of Baroda", "GAIL": "GAIL India",
    "IOC": "Indian Oil Corporation", "HPCL": "Hindustan Petroleum",
    "PFC": "Power Finance Corporation", "RECLTD": "REC Limited",
    "NHPC": "NHPC", "IRCTC": "Indian Railway Catering IRCTC",
    "AMBUJACEM": "Ambuja Cements", "ACC": "ACC Cement", "VOLTAS": "Voltas",
    "NAUKRI": "Info Edge Naukri", "ZYDUSLIFE": "Zydus Lifesciences",
    "LUPIN": "Lupin Pharmaceuticals", "MANKIND": "Mankind Pharma",
    "UBL": "United Breweries", "TATACHEM": "Tata Chemicals",
    "JSWENERGY": "JSW Energy", "INDHOTEL": "Indian Hotels Taj",
    "HDFCAMC": "HDFC AMC", "ICICIPRULI": "ICICI Prudential Life",
    "NMDC": "NMDC", "BHEL": "BHEL", "BEL": "Bharat Electronics BEL",
    "HAL": "Hindustan Aeronautics HAL", "PIIND": "PI Industries",
    "INDIGO": "IndiGo Airlines", "BAJAJ-AUTO": "Bajaj Auto",
    "PNB": "Punjab National Bank", "CANBK": "Canara Bank",
    "UNIONBANK": "Union Bank of India", "BANKINDIA": "Bank of India",
    "IOB": "Indian Overseas Bank", "OIL": "Oil India",
    "PETRONET": "Petronet LNG", "SJVN": "SJVN", "RVNL": "Rail Vikas Nigam",
    "IRFC": "Indian Railway Finance Corporation",
    "BEML": "BEML", "GRSE": "Garden Reach Shipbuilders",
    "COCHINSHIP": "Cochin Shipyard", "MAZAGON": "Mazagon Dock Shipbuilders",
    "RAILTEL": "RailTel Corporation", "NBCC": "NBCC India",
    "HUDCO": "Housing Urban Development Corporation",
    "CONCOR": "Container Corporation", "NALCO": "National Aluminium",
    "MOIL": "MOIL",
}

YF_OVERRIDES = {
    "MM": "M%26M.NS",
    "SHREECEM": "SHREECEM.NS",
    "BAJAJ-AUTO": "BAJAJ-AUTO.NS",
    "BAJAJHFL": "BAJAJHFL.NS",
}

INDEX_SYMBOLS = {
    "NIFTY 50": "^NSEI",
    "SENSEX": "^BSESN",
    "NIFTY BANK": "^NSEBANK",
    "NIFTY IT": "^CNXIT",
    "INDIA VIX": "^INDIAVIX",
}

PERIOD_TO_RANGE = {
    "1d": ("1d", "5m"),
    "5d": ("5d", "5m"),
    "1mo": ("1mo", "1d"),
    "3mo": ("3mo", "1d"),
    "6mo": ("6mo", "1d"),
    "1y": ("1y", "1d"),
    "2y": ("2y", "1wk"),
    "5y": ("5y", "1wk"),
}

# ──────────────────────────────────────────────────────────────────
# YAHOO FINANCE DATA SERVICE
# ──────────────────────────────────────────────────────────────────

class YFData:
    """Direct Yahoo Finance API client — bypasses SSL issues"""

    BASE = "https://query1.finance.yahoo.com"
    _session: Optional[requests.Session] = None
    _crumb: Optional[str] = None
    _crumb_ts: float = 0
    _cache: Dict[str, Any] = {}
    _cache_ts: Dict[str, float] = {}
    CACHE_TTL = 300  # seconds — live prices via SSE; REST cache can be 5 min
    CRUMB_TTL = 3600  # refresh crumb every hour

    @classmethod
    def _get_session(cls) -> requests.Session:
        if cls._session is None:
            cls._session = requests.Session()
            cls._session.verify = False
            cls._session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            })
            # Seed cookies by visiting the homepage (no custom Accept — use browser default)
            try:
                cls._session.headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
                cls._session.get("https://finance.yahoo.com/", timeout=10)
            except Exception:
                pass
            # Switch to JSON Accept for API calls
            cls._session.headers["Accept"] = "application/json"
        return cls._session

    @classmethod
    def _get_crumb(cls) -> Optional[str]:
        if cls._crumb and (time.time() - cls._crumb_ts) < cls.CRUMB_TTL:
            return cls._crumb
        try:
            s = cls._get_session()
            # Crumb endpoint must NOT have Accept: application/json — temporarily clear it
            saved_accept = s.headers.get("Accept")
            s.headers.pop("Accept", None)
            r = s.get(f"{cls.BASE}/v1/test/getcrumb", timeout=10)
            if saved_accept:
                s.headers["Accept"] = saved_accept
            if r.status_code == 200 and r.text.strip() and not r.text.startswith("{"):
                cls._crumb = r.text.strip()
                cls._crumb_ts = time.time()
                logger.info(f"YF crumb refreshed: {cls._crumb[:8]}…")
                return cls._crumb
        except Exception as e:
            logger.warning(f"YF crumb fetch failed: {e}")
        return None

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
    def yf_sym(cls, symbol: str) -> str:
        s = symbol.upper()
        return YF_OVERRIDES.get(s, s + ".NS")

    @classmethod
    def _chart_raw(cls, raw_symbol: str, range_: str, interval: str) -> Optional[Dict]:
        """Fetch chart without .NS suffix — for global symbols like CL=F, ^GSPC, USDINR=X"""
        key = f"chart_raw_{raw_symbol}_{range_}_{interval}"
        cached = cls._cached(key)
        if cached is not None:
            return cached
        try:
            url = f"{cls.BASE}/v8/finance/chart/{raw_symbol}"
            r = cls._get_session().get(
                url,
                params={"interval": interval, "range": range_, "includePrePost": False},
                timeout=20
            )
            if r.status_code != 200:
                return None
            result = r.json().get("chart", {}).get("result")
            if not result:
                return None
            cls._store(key, result[0])
            return result[0]
        except Exception as e:
            logger.error(f"YF chart_raw {raw_symbol}: {e}")
            return None

    @classmethod
    def chart(cls, symbol: str, range_: str = "1y", interval: str = "1d") -> Optional[Dict]:
        key = f"chart_{symbol}_{range_}_{interval}"
        cached = cls._cached(key)
        if cached is not None:
            return cached
        try:
            url = f"{cls.BASE}/v8/finance/chart/{cls.yf_sym(symbol)}"
            r = cls._get_session().get(
                url,
                params={"interval": interval, "range": range_, "includePrePost": False},
                timeout=20
            )
            if r.status_code != 200:
                return None
            data = r.json()
            result = data.get("chart", {}).get("result")
            if not result:
                return None
            cls._store(key, result[0])
            return result[0]
        except Exception as e:
            logger.error(f"YF chart {symbol}: {e}")
            return None

    @classmethod
    def live_price(cls, symbol: str) -> Optional[Dict]:
        key = f"live_{symbol}"
        cached = cls._cached(key)
        if cached is not None:
            return cached

        chart_data = cls.chart(symbol, "1mo", "1d")
        if not chart_data:
            return None

        meta = chart_data.get("meta", {})
        timestamps = chart_data.get("timestamp", [])
        quotes = chart_data.get("indicators", {}).get("quote", [{}])[0]
        closes = quotes.get("close", [])
        opens = quotes.get("open", [])
        highs = quotes.get("high", [])
        lows = quotes.get("low", [])
        vols = quotes.get("volume", [])

        # Get clean values (filter None)
        def last_valid(lst):
            for v in reversed(lst):
                if v is not None:
                    return v
            return None

        def prev_valid(lst):
            valid = [v for v in lst if v is not None]
            return valid[-2] if len(valid) >= 2 else None

        price = meta.get("regularMarketPrice") or last_valid(closes) or 0
        prev_close = meta.get("chartPreviousClose") or prev_valid(closes) or price
        today_open = meta.get("regularMarketOpen") or last_valid(opens) or price
        today_high = meta.get("regularMarketDayHigh") or last_valid(highs) or price
        today_low = meta.get("regularMarketDayLow") or last_valid(lows) or price
        volume = meta.get("regularMarketVolume") or last_valid(vols) or 0
        year_high = meta.get("fiftyTwoWeekHigh") or 0
        year_low = meta.get("fiftyTwoWeekLow") or 0
        market_cap = meta.get("marketCap") or 0

        change = price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0

        result = {
            "symbol": symbol,
            "price": round(float(price), 2),
            "prev_close": round(float(prev_close), 2),
            "change": round(float(change), 2),
            "change_pct": round(float(change_pct), 2),
            "open": round(float(today_open), 2),
            "high": round(float(today_high), 2),
            "low": round(float(today_low), 2),
            "volume": int(volume) if volume else 0,
            "year_high": round(float(year_high), 2),
            "year_low": round(float(year_low), 2),
            "market_cap": int(market_cap) if market_cap else 0,
        }
        cls._store(key, result)
        return result

    @classmethod
    def history(cls, symbol: str, period: str = "1y") -> List[Dict]:
        range_, interval = PERIOD_TO_RANGE.get(period, ("1y", "1d"))
        key = f"hist_{symbol}_{period}"
        cached = cls._cached(key)
        if cached is not None:
            return cached

        data = cls.chart(symbol, range_, interval)
        if not data:
            return []

        timestamps = data.get("timestamp", [])
        quotes = data.get("indicators", {}).get("quote", [{}])[0]
        opens = quotes.get("open", [])
        highs = quotes.get("high", [])
        lows = quotes.get("low", [])
        closes = quotes.get("close", [])
        vols = quotes.get("volume", [])

        records = []
        for i, ts in enumerate(timestamps):
            if i >= len(closes) or closes[i] is None:
                continue
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            records.append({
                "time": ts,
                "date": dt.strftime("%Y-%m-%d"),
                "open": round(opens[i] or closes[i], 2),
                "high": round(highs[i] or closes[i], 2),
                "low": round(lows[i] or closes[i], 2),
                "close": round(closes[i], 2),
                "volume": int(vols[i] or 0),
            })

        cls._store(key, records)
        return records

    @classmethod
    def fundamentals(cls, symbol: str) -> Dict:
        key = f"fund_{symbol}"
        cached = cls._cached(key)
        if cached is not None:
            return cached

        # Combine chart meta + quoteSummary approach
        chart_data = cls.chart(symbol, "1y", "1d")
        meta = (chart_data or {}).get("meta", {})

        try:
            crumb = cls._get_crumb()
            url = f"{cls.BASE}/v10/finance/quoteSummary/{cls.yf_sym(symbol)}"
            params = {"modules": "defaultKeyStatistics,financialData,summaryDetail,assetProfile,earnings"}
            if crumb:
                params["crumb"] = crumb
            r = cls._get_session().get(url, params=params, timeout=20)
            if r.status_code == 200:
                data = r.json()
                qsr = (data.get("quoteSummary", {}).get("result") or [{}])[0]
                ks = qsr.get("defaultKeyStatistics", {})
                fd = qsr.get("financialData", {})
                sd = qsr.get("summaryDetail", {})
                ap = qsr.get("assetProfile", {})

                def raw(d, k):
                    v = d.get(k)
                    if isinstance(v, dict):
                        return v.get("raw")
                    return v

                result = {
                    "name": meta.get("longName") or ap.get("longName") or symbol,
                    "pe_ratio": raw(sd, "trailingPE"),
                    "forward_pe": raw(sd, "forwardPE"),
                    "pb_ratio": raw(ks, "priceToBook"),
                    "roe": round(raw(fd, "returnOnEquity") * 100, 2) if raw(fd, "returnOnEquity") else None,
                    "roa": round(raw(fd, "returnOnAssets") * 100, 2) if raw(fd, "returnOnAssets") else None,
                    "debt_equity": raw(fd, "debtToEquity"),
                    "current_ratio": raw(fd, "currentRatio"),
                    "gross_margin": round(raw(fd, "grossMargins") * 100, 2) if raw(fd, "grossMargins") else None,
                    "operating_margin": round(raw(fd, "operatingMargins") * 100, 2) if raw(fd, "operatingMargins") else None,
                    "net_margin": round(raw(fd, "profitMargins") * 100, 2) if raw(fd, "profitMargins") else None,
                    "revenue_growth": round(raw(fd, "revenueGrowth") * 100, 2) if raw(fd, "revenueGrowth") else None,
                    "earnings_growth": round(raw(fd, "earningsGrowth") * 100, 2) if raw(fd, "earningsGrowth") else None,
                    "market_cap": raw(sd, "marketCap") or meta.get("marketCap"),
                    "book_value": raw(ks, "bookValue"),
                    "dividend_yield": round(raw(sd, "dividendYield") * 100, 2) if raw(sd, "dividendYield") else None,
                    "eps": raw(ks, "trailingEps"),
                    "forward_eps": raw(ks, "forwardEps"),
                    "sector": ap.get("sector"),
                    "industry": ap.get("industry"),
                    "employees": ap.get("fullTimeEmployees"),
                    "description": (ap.get("longBusinessSummary") or "")[:600],
                }
                cls._store(key, result)
                return result
        except Exception as e:
            logger.error(f"YF fundamentals {symbol}: {e}")

        return {}

    @classmethod
    def index_live(cls, name: str) -> Optional[Dict]:
        yf_sym = INDEX_SYMBOLS.get(name)
        if not yf_sym:
            return None
        key = f"idx_{name}"
        cached = cls._cached(key)
        if cached is not None:
            return cached
        try:
            url = f"{cls.BASE}/v8/finance/chart/{yf_sym}"
            r = cls._get_session().get(
                url,
                params={"interval": "1d", "range": "5d"},
                timeout=15
            )
            if r.status_code != 200:
                return None
            data = r.json()
            result_data = data.get("chart", {}).get("result")
            if not result_data:
                return None
            meta = result_data[0].get("meta", {})
            price = meta.get("regularMarketPrice", 0)
            prev = meta.get("chartPreviousClose", 0)
            chg = price - prev
            result = {
                "name": name,
                "value": round(float(price), 2),
                "change": round(float(chg), 2),
                "change_pct": round(float(chg / prev * 100) if prev else 0, 2),
            }
            cls._store(key, result)
            return result
        except Exception as e:
            logger.error(f"YF index {name}: {e}")
            return None

    @classmethod
    def dataframe(cls, symbol: str, period: str = "1y") -> pd.DataFrame:
        records = cls.history(symbol, period)
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        df.columns = [c.capitalize() for c in df.columns if c != "date"]
        # Ensure proper column names
        rename_map = {
            "Open": "Open", "High": "High", "Low": "Low",
            "Close": "Close", "Volume": "Volume", "Time": "Time"
        }
        return df


# ──────────────────────────────────────────────────────────────────
# NSE SESSION CLIENT
# ──────────────────────────────────────────────────────────────────

class NSEClient:
    BASE = "https://www.nseindia.com"

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._cookies: Dict = {}
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/",
            "Connection": "keep-alive",
        }
        self._last_refresh = 0.0
        self._initialized = False

    async def _session_ok(self):
        if not self._session or self._session.closed:
            conn = aiohttp.TCPConnector(ssl=False)
            self._session = aiohttp.ClientSession(connector=conn)
        if not self._initialized or (time.time() - self._last_refresh) > 240:
            await self._refresh()

    async def _refresh(self):
        try:
            t = aiohttp.ClientTimeout(total=12)
            async with self._session.get(self.BASE, headers=self._headers, timeout=t) as r:
                self._cookies = {k: v.value for k, v in r.cookies.items()}
            await asyncio.sleep(0.5)
            async with self._session.get(
                f"{self.BASE}/option-chain", headers=self._headers,
                cookies=self._cookies, timeout=t
            ) as r:
                for k, v in r.cookies.items():
                    self._cookies[k] = v.value
            self._initialized = True
            self._last_refresh = time.time()
        except Exception as e:
            logger.warning(f"NSE session: {e}")

    async def fetch(self, path: str, params: Dict = None) -> Optional[Any]:
        await self._session_ok()
        url = f"{self.BASE}/api/{path}"
        t = aiohttp.ClientTimeout(total=15)
        for attempt in range(2):
            try:
                async with self._session.get(
                    url, params=params, headers=self._headers,
                    cookies=self._cookies, timeout=t
                ) as r:
                    if r.status == 200:
                        return await r.json(content_type=None)
                    if r.status == 403 and attempt == 0:
                        self._initialized = False
                        await self._refresh()
            except Exception as e:
                logger.warning(f"NSE {path}: {e}")
        return None

    async def indices(self):
        d = await self.fetch("allIndices")
        return (d or {}).get("data", [])

    async def quote(self, symbol: str):
        return await self.fetch("quote-equity", {"symbol": symbol.upper()})

    async def option_chain(self, symbol: str):
        return await self.fetch("option-chain-equities", {"symbol": symbol.upper()})

    async def fii_dii(self):
        return await self.fetch("fiidiiTradeInfo")

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


# ──────────────────────────────────────────────────────────────────
# TECHNICAL ANALYSIS
# ──────────────────────────────────────────────────────────────────

class TA:
    @staticmethod
    def rsi(series: pd.Series, period=14) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def macd(series, fast=12, slow=26, signal=9):
        ef = series.ewm(span=fast, adjust=False).mean()
        es = series.ewm(span=slow, adjust=False).mean()
        m = ef - es
        sig = m.ewm(span=signal, adjust=False).mean()
        return m, sig, m - sig

    @staticmethod
    def bollinger(series, period=20, std=2):
        mid = series.rolling(period).mean()
        sigma = series.rolling(period).std()
        return mid + std * sigma, mid, mid - std * sigma

    @staticmethod
    def compute(df: pd.DataFrame) -> Dict:
        if df.empty or len(df) < 20:
            return {}
        c = df["Close"]
        h = df["High"]
        lo = df["Low"]
        vol = df["Volume"]
        cur = float(c.iloc[-1])

        n = len(df)
        sma20 = float(c.rolling(20).mean().iloc[-1]) if n >= 20 else None
        sma50 = float(c.rolling(50).mean().iloc[-1]) if n >= 50 else None
        sma200 = float(c.rolling(200).mean().iloc[-1]) if n >= 200 else None
        ema20 = float(c.ewm(span=20, adjust=False).mean().iloc[-1])
        ema50 = float(c.ewm(span=50, adjust=False).mean().iloc[-1]) if n >= 50 else None

        rsi_val = float(TA.rsi(c).iloc[-1]) if n >= 15 else 50
        ml, sl, hist = TA.macd(c)
        bbu, bbm, bbl = TA.bollinger(c)
        tr = pd.concat([h - lo, abs(h - c.shift()), abs(lo - c.shift())], axis=1).max(axis=1)
        atr = float(tr.rolling(14).mean().iloc[-1]) if n >= 14 else 0
        avg_vol = float(vol.rolling(20).mean().iloc[-1]) if n >= 20 else float(vol.iloc[-1])
        vol_ratio = float(vol.iloc[-1]) / avg_vol if avg_vol > 0 else 1

        r1 = float(df["High"].tail(20).max())
        s1 = float(df["Low"].tail(20).min())
        bb_u = float(bbu.iloc[-1])
        bb_l = float(bbl.iloc[-1])
        bb_pos = (cur - bb_l) / (bb_u - bb_l) if (bb_u - bb_l) > 0 else 0.5

        signals = []
        if rsi_val > 70: signals.append("Overbought (RSI)")
        elif rsi_val < 30: signals.append("Oversold (RSI)")
        if float(hist.iloc[-1]) > 0: signals.append("MACD Bullish Crossover")
        else: signals.append("MACD Bearish Crossover")
        if sma20 and cur > sma20: signals.append("Above SMA20")
        if sma50 and cur > sma50: signals.append("Above SMA50")
        if sma200 and cur > sma200: signals.append("Above SMA200")
        if vol_ratio > 1.5: signals.append("Volume Surge")

        trend = "Sideways"
        if sma50 and sma200 and cur > sma50 > sma200: trend = "Strong Uptrend"
        elif sma50 and cur > sma50: trend = "Uptrend"
        elif sma50 and cur < sma50: trend = "Downtrend"

        return {
            "current_price": round(cur, 2),
            "sma_20": round(sma20, 2) if sma20 else None,
            "sma_50": round(sma50, 2) if sma50 else None,
            "sma_200": round(sma200, 2) if sma200 else None,
            "ema_20": round(ema20, 2),
            "ema_50": round(ema50, 2) if ema50 else None,
            "rsi_14": round(rsi_val, 2),
            "rsi_signal": "Overbought" if rsi_val > 70 else "Oversold" if rsi_val < 30 else "Neutral",
            "macd": round(float(ml.iloc[-1]), 4),
            "macd_signal": round(float(sl.iloc[-1]), 4),
            "macd_histogram": round(float(hist.iloc[-1]), 4),
            "macd_crossover": "Bullish" if float(hist.iloc[-1]) > 0 else "Bearish",
            "bb_upper": round(bb_u, 2),
            "bb_mid": round(float(bbm.iloc[-1]), 2),
            "bb_lower": round(bb_l, 2),
            "bb_position": round(bb_pos, 2),
            "atr": round(atr, 2),
            "volume_ratio": round(vol_ratio, 2),
            "resistance_1": round(r1, 2),
            "support_1": round(s1, 2),
            "trend": trend,
            "above_sma20": cur > sma20 if sma20 else None,
            "above_sma50": cur > sma50 if sma50 else None,
            "above_sma200": cur > sma200 if sma200 else None,
            "signals": signals,
        }


# ──────────────────────────────────────────────────────────────────
# AGENT ANALYSIS
# ──────────────────────────────────────────────────────────────────

def agent_fundamentals(symbol: str, fund: Dict) -> Dict:
    pe = fund.get("pe_ratio") or 25
    roe = fund.get("roe") or 12
    de = fund.get("debt_equity") or 1.0
    rev_g = fund.get("revenue_growth") or 5
    margin = fund.get("net_margin") or 10

    score, findings = 0, []
    if pe < 20: score += 20; findings.append(f"P/E {pe:.1f}x – attractively valued vs market")
    elif pe < 30: score += 10; findings.append(f"P/E {pe:.1f}x – fair valuation")
    else: findings.append(f"P/E {pe:.1f}x – premium priced, growth expectations baked in")

    if roe > 20: score += 25; findings.append(f"ROE {roe:.1f}% – exceptional capital efficiency")
    elif roe > 15: score += 20; findings.append(f"ROE {roe:.1f}% – above-average returns")
    elif roe > 10: score += 10; findings.append(f"ROE {roe:.1f}% – adequate returns on equity")
    else: findings.append(f"ROE {roe:.1f}% – below average, monitor closely")

    if de is not None:
        if de < 0.3: score += 20; findings.append(f"D/E {de:.2f} – pristine balance sheet")
        elif de < 0.8: score += 15; findings.append(f"D/E {de:.2f} – conservatively leveraged")
        elif de < 1.5: score += 5; findings.append(f"D/E {de:.2f} – moderate leverage")
        else: findings.append(f"D/E {de:.2f} – elevated debt, monitor refinancing risk")

    if rev_g is not None:
        if rev_g > 15: score += 20; findings.append(f"Revenue growing {rev_g:.1f}% YoY – strong momentum")
        elif rev_g > 8: score += 12; findings.append(f"Revenue growing {rev_g:.1f}% YoY – solid growth")
        elif rev_g > 0: score += 5; findings.append(f"Revenue growing {rev_g:.1f}% YoY – slow growth")
        else: findings.append(f"Revenue declining {rev_g:.1f}% – concerning trend")

    if margin is not None:
        if margin > 20: score += 15; findings.append(f"Net margin {margin:.1f}% – highly profitable")
        elif margin > 12: score += 10; findings.append(f"Net margin {margin:.1f}% – healthy profitability")
        elif margin > 5: score += 5; findings.append(f"Net margin {margin:.1f}% – thin but positive margins")

    conf = min(score / 100, 0.95)
    sig = "BULLISH" if conf > 0.6 else "BEARISH" if conf < 0.35 else "NEUTRAL"
    return {
        "agent": "Fundamentals Analyst",
        "confidence": round(conf, 2),
        "signal": sig,
        "summary": f"Fundamental score {score}/100. {sig.capitalize()} on quality + valuation.",
        "findings": findings,
        "data": fund,
    }


def agent_technical(symbol: str, tech: Dict) -> Dict:
    if not tech:
        return {"agent": "Technical Analyst", "confidence": 0.5, "signal": "NEUTRAL",
                "summary": "Insufficient technical data", "findings": [], "data": {}}

    score, findings = 0, []
    if tech.get("above_sma20"): score += 15
    if tech.get("above_sma50"): score += 15
    if tech.get("above_sma200"): score += 15

    rsi = tech.get("rsi_14", 50)
    if 40 < rsi < 65: score += 15; findings.append(f"RSI {rsi:.1f} – healthy momentum zone")
    elif rsi >= 70: findings.append(f"RSI {rsi:.1f} – overbought, caution warranted")
    elif rsi >= 65: score += 8; findings.append(f"RSI {rsi:.1f} – elevated but not extreme")
    elif rsi <= 30: findings.append(f"RSI {rsi:.1f} – oversold, bounce potential"); score += 8
    else: findings.append(f"RSI {rsi:.1f} – neutral momentum")

    if tech.get("macd_crossover") == "Bullish":
        score += 15; findings.append(f"MACD bullish – histogram {tech['macd_histogram']:.4f}")
    else:
        findings.append(f"MACD bearish – histogram {tech.get('macd_histogram', 0):.4f}")

    vr = tech.get("volume_ratio", 1)
    if vr > 1.5: score += 15; findings.append(f"Volume {vr:.1f}x average – institutional participation")
    elif vr > 1.1: score += 8; findings.append(f"Volume {vr:.1f}x average – above-average activity")

    findings.append(f"Trend: {tech.get('trend')} | R1: ₹{tech.get('resistance_1', 0):,.2f} | S1: ₹{tech.get('support_1', 0):,.2f}")
    findings.extend(tech.get("signals", []))

    conf = min(score / 100, 0.95)
    sig = "BULLISH" if conf > 0.6 else "BEARISH" if conf < 0.35 else "NEUTRAL"
    return {
        "agent": "Technical Analyst",
        "confidence": round(conf, 2),
        "signal": sig,
        "summary": f"Technical score {score}/100. {tech.get('trend', 'Sideways')}. RSI {rsi:.1f}.",
        "findings": findings,
        "data": tech,
    }


def agent_macro(symbol: str) -> Dict:
    data = {
        "rbi_repo_rate": 6.25,
        "cpi": 3.16,
        "gdp_growth": 6.5,
        "usd_inr": 84.1,
        "brent_usd": 74.2,
        "govt_capex_fy27_lakh_cr": 11.11,
        "fiscal_deficit_pct_gdp": 4.9,
    }
    return {
        "agent": "Macro & News Analyst",
        "confidence": 0.70,
        "signal": "BULLISH",
        "summary": "India macro backdrop supportive: easing inflation, stable INR, robust government capex",
        "findings": [
            f"RBI repo rate {data['rbi_repo_rate']}% – easing cycle underway, equity tailwind",
            f"CPI {data['cpi']}% – well within RBI's 2-6% target, benign for equities",
            f"India GDP {data['gdp_growth']}% – fastest-growing major economy globally",
            f"USD/INR {data['usd_inr']} – stable, reduces import cost pressure",
            f"Brent crude ${data['brent_usd']}/bbl – below $80 threshold, positive for India",
            f"Govt capex ₹{data['govt_capex_fy27_lakh_cr']} lakh crore FY27 – massive infrastructure push",
            "FII flows choppy but DII/MF consistently buying on dips",
        ],
        "data": data,
    }


def agent_risk(symbol: str, live: Dict, tech: Dict) -> Dict:
    price = live.get("price", 100)
    atr = tech.get("atr", price * 0.015)
    year_high = live.get("year_high", price * 1.2)
    year_low = live.get("year_low", price * 0.8)
    rsi = tech.get("rsi_14", 50)

    daily_vol_pct = atr / price * 100 if price else 2
    var_95 = daily_vol_pct * 1.645
    var_99 = daily_vol_pct * 2.326
    dd_from_high = (year_high - price) / year_high * 100 if year_high > 0 else 0

    risk_level = "Low" if var_95 < 3 else "Moderate" if var_95 < 5 else "High"
    conditions = []
    findings = [
        f"Daily VaR (95%): {var_95:.2f}% | VaR (99%): {var_99:.2f}%",
        f"Risk level: {risk_level} based on ATR-derived volatility",
        f"Down {dd_from_high:.1f}% from 52-week high (₹{year_high:,.2f})",
        f"Suggested stop loss: ₹{max(price - 2*atr, price * 0.92):,.2f} (2x ATR)",
    ]
    if var_95 > 5: conditions.append("Reduce position — high daily VaR")
    if rsi > 75: conditions.append("Overbought — wait for RSI pullback < 65")
    if dd_from_high > 40: conditions.append("Down >40% from high — confirm trend reversal before entry")

    status = "APPROVED" if risk_level in ("Low", "Moderate") and rsi < 80 else "CONDITIONAL"
    return {
        "agent": "Risk Analyst",
        "confidence": 0.80,
        "signal": status,
        "summary": f"Risk: {risk_level}. VaR(95%) = {var_95:.2f}%. {len(conditions)} condition(s).",
        "findings": findings,
        "conditions": conditions,
        "data": {"var_95": round(var_95, 2), "var_99": round(var_99, 2), "risk_level": risk_level, "atr": round(atr, 2)},
    }


def bull_bear_debate(symbol: str, live: Dict, tech: Dict, fund: Dict) -> Dict:
    price = live.get("price", 100)
    year_high = live.get("year_high", price * 1.2)
    pe = fund.get("pe_ratio") or 25
    roe = fund.get("roe") or 12
    rsi = tech.get("rsi_14", 50)

    bull_args = [
        f"India structural growth story intact — GDP 6.5%, fastest major economy",
        f"ROE {roe:.1f}% demonstrates quality business compounding capital",
        f"RSI at {rsi:.1f} — not extreme, room to run in an uptrend",
        f"Government capex super-cycle driving investment theme",
        f"DII/MF consistently accumulating — strong domestic institutional support",
        f"RBI rate easing cycle supports valuation re-rating for equities",
    ]
    bear_args = [
        f"At P/E {pe:.1f}x — premium leaves limited margin of safety in a downturn",
        f"Down {((year_high - price)/year_high*100):.1f}% from 52W high — momentum waning",
        f"Global uncertainty: Fed policy, geopolitical risks, EM capital outflows",
        f"FPI net sellers — foreign institutional caution on Indian valuations",
        f"Earnings growth needs to accelerate to justify current multiples",
    ]

    bull_conf = 0.68
    bear_conf = 0.42
    consensus = "Bullish" if bull_conf > bear_conf + 0.1 else "Bearish" if bear_conf > bull_conf + 0.1 else "Neutral"
    bull_tgt = round(price * 1.18, 2)
    bear_tgt = round(price * 0.88, 2)

    return {
        "bull_confidence": bull_conf,
        "bear_confidence": bear_conf,
        "consensus": consensus,
        "bull_arguments": bull_args,
        "bear_arguments": bear_args,
        "bull_target": bull_tgt,
        "bear_target": bear_tgt,
        "expected_value": round(bull_tgt * 0.65 + bear_tgt * 0.35, 2),
    }


def portfolio_mgr(symbol: str, agents: List[Dict], risk: Dict, live: Dict) -> Dict:
    price = live.get("price", 0)
    bullish = sum(1 for a in agents if a["signal"] in ("BULLISH", "APPROVED"))
    total = len(agents)
    avg_conf = sum(a["confidence"] for a in agents) / total if total else 0

    decision = "BUY" if bullish >= 3 and avg_conf > 0.6 else "SELL" if bullish <= 1 else "HOLD"
    atr = risk.get("data", {}).get("atr", price * 0.015)
    stop = round(price - 2 * atr, 2)
    target = round(price * 1.15, 2)
    rr = round((target - price) / (price - stop), 2) if price > stop else 0
    pos_pct = min(8.0, round(2.0 / max((price - stop) / price * 100, 0.5), 1))

    return {
        "decision": decision,
        "entry_price": round(price, 2),
        "stop_loss": stop,
        "target_price": target,
        "position_size_pct": pos_pct,
        "risk_reward": rr,
        "bullish_votes": bullish,
        "total_agents": total,
        "average_confidence": round(avg_conf, 2),
        "rationale": f"{bullish}/{total} agents bullish, avg confidence {avg_conf:.0%}. Decision: {decision}.",
    }


async def full_analysis(symbol: str) -> Dict:
    loop = asyncio.get_event_loop()
    live = await loop.run_in_executor(None, lambda: YFData.live_price(symbol)) or {}
    df = await loop.run_in_executor(None, lambda: YFData.dataframe(symbol, "1y"))
    tech = TA.compute(df)
    fund = await loop.run_in_executor(None, lambda: YFData.fundamentals(symbol))

    f_ag = agent_fundamentals(symbol, fund)
    t_ag = agent_technical(symbol, tech)
    m_ag = agent_macro(symbol)
    r_ag = agent_risk(symbol, live, tech)
    debate = bull_bear_debate(symbol, live, tech, fund)
    pm = portfolio_mgr(symbol, [f_ag, t_ag, m_ag], r_ag, live)

    return {
        "symbol": symbol,
        "timestamp": datetime.now().isoformat(),
        "live_data": live,
        "agents": {"fundamentals": f_ag, "technical": t_ag, "macro": m_ag, "risk": r_ag},
        "debate": debate,
        "final_decision": pm,
    }


# ──────────────────────────────────────────────────────────────────
# PORTFOLIO STATE
# ──────────────────────────────────────────────────────────────────

_pf = {
    "name": "HedgeFund Alpha",
    "initial_cash": 10_000_000.0,
    "cash": 10_000_000.0,
    "positions": {},
    "trades": [],
}

def _charges(value: float, side: str) -> float:
    b = value * 0.0005
    stt = value * (0.00025 if side == "SELL" else 0.001)
    return b + stt + b * 0.18 + value * 0.00015 + value * 0.000032

def pf_summary() -> Dict:
    positions = []
    mval_total = 0
    for sym, pos in _pf["positions"].items():
        live = YFData.live_price(sym) or {}
        cur = live.get("price", pos["avg"])
        mval = pos["qty"] * cur
        mval_total += mval
        positions.append({
            "symbol": sym, "qty": pos["qty"], "avg_price": pos["avg"],
            "current_price": cur, "market_value": round(mval, 2),
            "unrealized_pnl": round((cur - pos["avg"]) * pos["qty"], 2),
            "pnl_pct": round((cur - pos["avg"]) / pos["avg"] * 100, 2),
            "stop_loss": pos.get("stop", 0), "target": pos.get("target", 0),
        })
    total = _pf["cash"] + mval_total
    return {
        "name": _pf["name"],
        "total_value": round(total, 2),
        "cash": round(_pf["cash"], 2),
        "positions_value": round(mval_total, 2),
        "total_pnl": round(total - _pf["initial_cash"], 2),
        "total_pnl_pct": round((total - _pf["initial_cash"]) / _pf["initial_cash"] * 100, 2),
        "num_positions": len(_pf["positions"]),
        "positions": positions,
        "trades_count": len(_pf["trades"]),
    }


# ──────────────────────────────────────────────────────────────────
# NEWS SCRAPING  (Google News RSS + keyword tagging)
# ──────────────────────────────────────────────────────────────────

_news_cache: Dict[str, Any] = {}
_news_cache_ts: Dict[str, float] = {}
NEWS_CACHE_TTL = 1800  # 30 minutes

_POSITIVE_KW = {"wins","win","award","awarded","order","contract","beats","beat","profit",
                "growth","strong","upgrade","partnership","deal","launch","expansion",
                "record","raises","buys","acquires","dividend","bonus","buyback","joint venture"}
_NEGATIVE_KW = {"misses","miss","loss","losses","decline","declines","downgrade","default",
                "debt","layoff","layoffs","fraud","penalty","fine","probe","investigation",
                "recall","crash","slump","slumps","disappoints","disappointing"}
_CATEGORY_MAP = {
    "earnings":  ["results","q1","q2","q3","q4","quarterly","earnings","pat","ebitda","revenue","profit"],
    "order":     ["order","contract","tender","wins","awarded","l1","l2","workorder","project win"],
    "ma":        ["merger","acquisition","demerger","buyout","takeover","stake","acquires","buys"],
    "analyst":   ["target price","rating","upgrade","downgrade","initiates","buy rating","overweight",
                  "underweight","outperform","neutral","hold"],
    "dividend":  ["dividend","bonus","buyback","record date","ex-dividend"],
    "expansion": ["expansion","plant","capacity","capex","investment","greenfield","brownfield"],
}

async def _fetch_google_news(query: str) -> List[Dict]:
    url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        timeout = aiohttp.ClientTimeout(total=12)
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as r:
                if r.status != 200:
                    return []
                text = await r.text()
        root = ET.fromstring(text)
        items = root.findall(".//item")
        results = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        for item in items[:25]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_raw = (item.findtext("pubDate") or "").strip()
            desc = re.sub(r"<[^>]+>", "", item.findtext("description") or "")[:300].strip()
            src_el = item.find("source")
            source = src_el.text if src_el is not None else "Google News"
            try:
                pub_dt = parsedate_to_datetime(pub_raw)
                if pub_dt < cutoff:
                    continue
                age_h = int((datetime.now(timezone.utc) - pub_dt).total_seconds() / 3600)
                age_d = age_h // 24
            except Exception:
                age_h = 0
                age_d = 0
            low = title.lower() + " " + desc.lower()
            sentiment = "positive" if any(w in low for w in _POSITIVE_KW) else \
                        "negative" if any(w in low for w in _NEGATIVE_KW) else "neutral"
            tags = [cat for cat, kws in _CATEGORY_MAP.items() if any(k in low for k in kws)]
            results.append({
                "title": title, "url": link, "source": source,
                "published": pub_raw, "age_hours": age_h, "age_days": age_d,
                "summary": desc, "sentiment": sentiment, "tags": tags or ["general"],
            })
        return results
    except Exception as e:
        logger.warning(f"News fetch failed: {e}")
        return []


async def get_company_news(symbol: str) -> List[Dict]:
    if symbol in _news_cache and (time.time() - _news_cache_ts.get(symbol, 0)) < NEWS_CACHE_TTL:
        return _news_cache[symbol]
    name = COMPANY_NAMES.get(symbol, symbol)
    results = await _fetch_google_news(f"{name} NSE India stock")
    _news_cache[symbol] = results
    _news_cache_ts[symbol] = time.time()
    return results


async def get_market_news() -> List[Dict]:
    key = "__market__"
    if key in _news_cache and (time.time() - _news_cache_ts.get(key, 0)) < NEWS_CACHE_TTL:
        return _news_cache[key]
    results = await _fetch_google_news("India stock market NSE BSE Nifty today")
    # Also fetch sector-specific news
    sector_news = await _fetch_google_news("India PSU stock budget infrastructure 2026")
    combined = results + sector_news
    # Deduplicate by title
    seen_titles: set = set()
    deduped = []
    for item in combined:
        if item["title"] not in seen_titles:
            deduped.append(item)
            seen_titles.add(item["title"])
    deduped.sort(key=lambda x: x.get("age_hours", 999))
    _news_cache[key] = deduped
    _news_cache_ts[key] = time.time()
    return deduped


# ──────────────────────────────────────────────────────────────────
# ANALYST RATINGS  (Yahoo Finance quoteSummary)
# ──────────────────────────────────────────────────────────────────

_analyst_cache: Dict[str, Any] = {}
_analyst_cache_ts: Dict[str, float] = {}
ANALYST_CACHE_TTL = 3600  # 1 hour


def _fetch_analyst_ratings_sync(symbol: str) -> Dict:
    crumb = YFData._get_crumb()
    if not crumb:
        return {}
    try:
        params = {
            "modules": "recommendationTrend,upgradeDowngradeHistory,financialData",
            "crumb": crumb,
        }
        r = YFData._get_session().get(
            f"{YFData.BASE}/v10/finance/quoteSummary/{YFData.yf_sym(symbol)}",
            params=params, timeout=15,
        )
        if r.status_code != 200:
            return {}
        data = r.json()
        result = (data.get("quoteSummary", {}).get("result") or [{}])[0]

        rt_list = result.get("recommendationTrend", {}).get("trend", [])
        current = rt_list[0] if rt_list else {}
        sb = current.get("strongBuy", 0)
        b  = current.get("buy", 0)
        h  = current.get("hold", 0)
        s  = current.get("sell", 0)
        ss = current.get("strongSell", 0)

        udh = result.get("upgradeDowngradeHistory", {}).get("history", [])
        recent: List[Dict] = []
        for item in udh[:15]:
            epoch = item.get("epochGradeDate")
            date_str = datetime.fromtimestamp(epoch).strftime("%d %b %Y") if epoch else ""
            recent.append({
                "date": date_str,
                "firm": item.get("firm", ""),
                "action": item.get("action", ""),
                "from_grade": item.get("fromGrade", ""),
                "to_grade": item.get("toGrade", ""),
            })

        fd = result.get("financialData", {})
        rec_mean_raw = fd.get("recommendationMean")
        if isinstance(rec_mean_raw, dict):
            rec_mean_raw = rec_mean_raw.get("raw")
        rec_key = fd.get("recommendationKey", "")

        total = sb + b + h + s + ss
        bull_pct = round((sb + b) / total * 100) if total else 0
        return {
            "strong_buy": sb, "buy": b, "hold": h, "sell": s, "strong_sell": ss,
            "total_analysts": total, "bull_pct": bull_pct,
            "recommendation": rec_key, "score": rec_mean_raw,
            "recent_ratings": recent,
        }
    except Exception as e:
        logger.warning(f"Analyst fetch {symbol}: {e}")
        return {}


async def get_analyst_ratings(symbol: str) -> Dict:
    if symbol in _analyst_cache and (time.time() - _analyst_cache_ts.get(symbol, 0)) < ANALYST_CACHE_TTL:
        return _analyst_cache[symbol]
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, lambda: _fetch_analyst_ratings_sync(symbol))
    _analyst_cache[symbol] = data
    _analyst_cache_ts[symbol] = time.time()
    return data


# ──────────────────────────────────────────────────────────────────
# TREND SCORE ENGINE
# ──────────────────────────────────────────────────────────────────

def compute_trend_score(live: Dict, tech: Dict, fund: Dict,
                        analysts: Dict, news: List[Dict]) -> Dict:
    signals: List[str] = []
    score_breakdown: Dict[str, int] = {}

    # ── 1. Technical (max 40) ──
    t_score = 0
    if tech:
        rsi = tech.get("rsi_14", 50)
        if 45 <= rsi <= 65:
            t_score += 10
        elif rsi < 35:
            t_score += 5
            signals.append(f"RSI Oversold ({rsi:.0f}) — potential reversal")
        elif rsi > 70:
            signals.append(f"RSI Overbought ({rsi:.0f})")

        co = tech.get("macd_crossover", "")
        if co == "Bullish":
            t_score += 12
            signals.append("MACD Bullish Crossover")
        elif co == "Bearish":
            signals.append("MACD Bearish Crossover")

        trend = tech.get("trend", "")
        if "Strong Uptrend" in trend:
            t_score += 15
            signals.append("Strong Uptrend (Price > SMA20 > SMA50 > SMA200)")
        elif "Uptrend" in trend:
            t_score += 10
            signals.append("Uptrend")
        elif "Downtrend" in trend:
            signals.append("Downtrend")

        vr = tech.get("volume_ratio", 1.0)
        if vr > 2.0:
            t_score += 3
            signals.append(f"Volume Surge {vr:.1f}x Average")

    score_breakdown["technical"] = min(40, t_score)

    # ── 2. Price Momentum (max 25) ──
    m_score = 0
    price = live.get("price", 0)
    y_high = live.get("year_high", price or 1)
    y_low = live.get("year_low", 0)
    chg = live.get("change_pct", 0)
    if price and y_high and y_low and y_high > y_low:
        pct_of_range = (price - y_low) / (y_high - y_low) * 100
        if pct_of_range >= 75:
            m_score += 15
            signals.append(f"Near 52W High — {pct_of_range:.0f}% of annual range")
        elif pct_of_range >= 50:
            m_score += 8
        elif pct_of_range <= 20:
            m_score += 3
            signals.append(f"Near 52W Low — potential value zone")
    if chg >= 3:
        m_score += 10
        signals.append(f"Strong Up Day +{chg:.1f}%")
    elif chg >= 1:
        m_score += 5
    elif chg <= -3:
        m_score -= 5
        signals.append(f"Sharp Decline {chg:.1f}%")

    score_breakdown["momentum"] = max(0, min(25, m_score))

    # ── 3. Analyst Consensus (max 25) ──
    a_score = 0
    if analysts:
        total_a = analysts.get("total_analysts", 0)
        bull_p = analysts.get("bull_pct", 0)
        rec = analysts.get("recommendation", "")
        if total_a > 0:
            a_score = int(bull_p / 100 * 25)
            if rec in ("strongBuy", "buy"):
                signals.append(f"Analyst Consensus: {rec.upper()} — {bull_p}% Bullish ({total_a} analysts)")
            elif rec == "hold":
                signals.append(f"Analyst Consensus: HOLD ({total_a} analysts)")
            elif rec in ("sell", "strongSell"):
                signals.append(f"Analyst Consensus: {rec.upper()} — only {bull_p}% Bullish")
        recent = analysts.get("recent_ratings", [])
        upgrades = sum(1 for r in recent[:5] if r.get("action") in ("up", "init"))
        if upgrades >= 2:
            a_score = min(25, a_score + 5)
            signals.append(f"{upgrades} Analyst Upgrades/Initiations Recently")

    score_breakdown["analyst"] = min(25, a_score)

    # ── 4. News Sentiment (max 10) ──
    n_score = 0
    if news:
        pos_n = sum(1 for n in news if n.get("sentiment") == "positive")
        neg_n = sum(1 for n in news if n.get("sentiment") == "negative")
        total_n = len(news)
        if total_n > 0:
            ratio = pos_n / total_n
            n_score = int(ratio * 10)
            if pos_n > neg_n and pos_n > 0:
                signals.append(f"Positive News Flow ({pos_n} pos, {neg_n} neg in 7d)")
            elif neg_n > pos_n and neg_n > 0:
                signals.append(f"Negative News Pressure ({neg_n} neg, {pos_n} pos in 7d)")
        # Category-specific signals
        order_news = [n for n in news if "order" in n.get("tags", [])]
        if order_news:
            n_score = min(10, n_score + 2)
            signals.append(f"Order/Contract Wins in News ({len(order_news)} items)")
        ma_news = [n for n in news if "ma" in n.get("tags", [])]
        if ma_news:
            signals.append(f"M&A Activity in News ({len(ma_news)} items)")

    score_breakdown["sentiment"] = min(10, n_score)

    total = sum(score_breakdown.values())
    if total >= 75:
        label, color = "Strong Bullish", "#22c55e"
    elif total >= 58:
        label, color = "Bullish", "#86efac"
    elif total >= 42:
        label, color = "Neutral", "#f59e0b"
    elif total >= 28:
        label, color = "Bearish", "#fca5a5"
    else:
        label, color = "Strong Bearish", "#ef4444"

    return {
        "overall": total,
        "breakdown": score_breakdown,
        "label": label,
        "color": color,
        "signals": signals[:8],
        "news_count": len(news),
        "positive_news": sum(1 for n in news if n.get("sentiment") == "positive"),
        "negative_news": sum(1 for n in news if n.get("sentiment") == "negative"),
    }


# ──────────────────────────────────────────────────────────────────
# WEBSOCKET MANAGER
# ──────────────────────────────────────────────────────────────────

class ConnMgr:
    def __init__(self):
        self.active: Set[WebSocket] = set()
        self.subs: Dict[WebSocket, Set[str]] = {}

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)
        self.subs[ws] = set()

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)
        self.subs.pop(ws, None)

    def subscribe(self, ws: WebSocket, symbols: List[str]):
        if ws in self.subs:
            self.subs[ws].update(s.upper() for s in symbols)

    async def broadcast(self, data: Dict):
        dead = set()
        for ws, syms in self.subs.items():
            filtered = {s: v for s, v in data.items() if s in syms}
            if filtered:
                try:
                    await ws.send_json({"type": "price_update", "data": filtered})
                except Exception:
                    dead.add(ws)
        for ws in dead:
            self.disconnect(ws)


mgr = ConnMgr()
nse = NSEClient()

# ── Global real-time state ────────────────────────────────────────
_price_snapshot: Dict[str, Dict] = {}
_price_snapshot_ts: float = 0
_SSE_QUEUES: List[asyncio.Queue] = []
_latest_market_news: List[Dict] = []
_news_ts: float = 0

# ── Black-Scholes helpers (scipy-free) ───────────────────────────
def _norm_cdf(x: float) -> float:
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
    p = 1.0 - (1.0 / sqrt(2 * pi)) * exp(-0.5 * x * x) * poly
    return p if x >= 0 else 1.0 - p

def _norm_pdf(x: float) -> float:
    return (1.0 / sqrt(2 * pi)) * exp(-0.5 * x * x)

def bs_greeks(S: float, K: float, T: float, r: float, sigma: float, opt: str = "call") -> Dict:
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return {}
    d1 = (log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt(T))
    d2 = d1 - sigma * sqrt(T)
    nd1, nd2 = _norm_cdf(d1), _norm_cdf(d2)
    if opt == "call":
        price = S * nd1 - K * exp(-r * T) * nd2
        delta = nd1
    else:
        price = K * exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)
        delta = nd1 - 1.0
    gamma = _norm_pdf(d1) / (S * sigma * sqrt(T))
    vega  = S * _norm_pdf(d1) * sqrt(T) / 100.0
    theta = (-(S * _norm_pdf(d1) * sigma) / (2 * sqrt(T)) - r * K * exp(-r * T) * nd2) / 365.0
    rho   = K * T * exp(-r * T) * nd2 / 100.0
    iv_impact = vega * 100  # 1% IV change → rupee change
    return dict(price=round(price,2), delta=round(delta,4), gamma=round(gamma,6),
                vega=round(vega,4), theta=round(theta,4), rho=round(rho,4),
                d1=round(d1,4), d2=round(d2,4), iv_impact=round(iv_impact,2))

# ── Pattern detection ─────────────────────────────────────────────
def detect_chart_patterns(closes: List[float]) -> Dict:
    if len(closes) < 20:
        return {"trend": "unknown", "patterns": [], "support": 0, "resistance": 0}
    arr = np.array(closes, dtype=float)
    recent = arr[-20:]
    x = np.arange(len(recent), dtype=float)
    slope = float(np.polyfit(x, recent, 1)[0])
    trend_pct = slope / recent[0] * 100
    trend = "uptrend" if trend_pct > 0.15 else "downtrend" if trend_pct < -0.15 else "sideways"
    ma5  = float(np.mean(arr[-5:]))
    ma20 = float(np.mean(arr[-20:]))
    support    = float(np.min(arr[-20:]))
    resistance = float(np.max(arr[-20:]))
    patterns = []
    # Golden/Death cross
    if len(arr) >= 21:
        pma5 = float(np.mean(arr[-6:-1]))
        pma20 = float(np.mean(arr[-21:-1]))
        if pma5 < pma20 and ma5 > ma20:
            patterns.append({"name": "Golden Cross", "signal": "bullish", "conf": 0.82})
        elif pma5 > pma20 and ma5 < ma20:
            patterns.append({"name": "Death Cross", "signal": "bearish", "conf": 0.82})
    # Double top/bottom
    if len(arr) >= 40:
        h1, h2 = float(np.max(arr[-40:-20])), float(np.max(arr[-20:]))
        l1, l2 = float(np.min(arr[-40:-20])), float(np.min(arr[-20:]))
        if abs(h1 - h2) / max(h1,1) < 0.025 and arr[-1] < float(np.mean(arr[-40:])) * 0.98:
            patterns.append({"name": "Double Top", "signal": "bearish", "conf": 0.70})
        if abs(l1 - l2) / max(l1,1) < 0.025 and arr[-1] > float(np.mean(arr[-40:])) * 1.02:
            patterns.append({"name": "Double Bottom", "signal": "bullish", "conf": 0.70})
    # HH/HL / LL/LH
    if len(arr) >= 20:
        q1h, q2h = float(np.max(arr[-20:-10])), float(np.max(arr[-10:]))
        q1l, q2l = float(np.min(arr[-20:-10])), float(np.min(arr[-10:]))
        if q2h > q1h and q2l > q1l:
            patterns.append({"name": "Higher Highs / Higher Lows", "signal": "bullish", "conf": 0.75})
        elif q2h < q1h and q2l < q1l:
            patterns.append({"name": "Lower Highs / Lower Lows", "signal": "bearish", "conf": 0.75})
    # Inside bar consolidation (last 3 bars within previous range)
    if len(arr) >= 5:
        if arr[-1] < arr[-4] and arr[-1] > arr[-5]:
            patterns.append({"name": "Consolidation / Inside Bars", "signal": "neutral", "conf": 0.60})
    return {
        "trend": trend, "trend_slope_pct": round(trend_pct, 3),
        "support": round(support, 2), "resistance": round(resistance, 2),
        "ma5": round(ma5, 2), "ma20": round(ma20, 2), "patterns": patterns,
    }

# ── Fear & Greed composite ────────────────────────────────────────
async def compute_fear_greed() -> Dict:
    """Composite Fear & Greed index: VIX + breadth + PCR + momentum"""
    score = 50.0
    components: Dict[str, Any] = {}
    loop = asyncio.get_event_loop()
    try:
        vix_data = YFData._chart_raw("^INDIAVIX", "5d", "1d")
        if vix_data and vix_data.get("close"):
            vix = float(vix_data["close"][-1])
            # VIX: low VIX = greed, high VIX = fear; range ~10-40
            vix_score = max(0, min(100, 100 - (vix - 10) / 30 * 100))
            components["vix"] = {"value": round(vix, 2), "score": round(vix_score, 1)}
            score = 0.3 * vix_score + 0.7 * score
    except Exception:
        pass
    try:
        nf_data = YFData.live_price("NIFTY 50") or {}
        nf_price = nf_data.get("price", 0)
        hist = await loop.run_in_executor(None, lambda: YFData.history("^NSEI", "6mo"))
        if hist and nf_price:
            closes_125 = [h["close"] for h in hist[-125:] if h.get("close")]
            ma125 = float(np.mean(closes_125)) if closes_125 else nf_price
            mom_pct = (nf_price - ma125) / ma125 * 100
            mom_score = max(0, min(100, 50 + mom_pct * 3))
            components["momentum"] = {"value": round(mom_pct, 2), "score": round(mom_score, 1)}
            score = 0.3 * mom_score + 0.7 * score
    except Exception:
        pass
    if score >= 80: label, color = "Extreme Greed", "#22c55e"
    elif score >= 60: label, color = "Greed", "#86efac"
    elif score >= 40: label, color = "Neutral", "#f59e0b"
    elif score >= 20: label, color = "Fear", "#fca5a5"
    else: label, color = "Extreme Fear", "#ef4444"
    return {"score": round(score, 1), "label": label, "color": color, "components": components, "ts": int(time.time())}

# ── Parallel price fetcher ────────────────────────────────────────
async def fetch_prices_parallel(symbols: List[str]) -> Dict[str, Dict]:
    loop = asyncio.get_event_loop()
    tasks = [loop.run_in_executor(None, lambda s=sym: YFData.live_price(s)) for sym in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    prices = {}
    for sym, res in zip(symbols, results):
        if isinstance(res, dict) and res and res.get("price", 0) > 0:
            prices[sym] = {
                "price": res["price"], "change": res["change"],
                "change_pct": res["change_pct"], "volume": res.get("volume", 0),
                "prev_close": res.get("prev_close", 0), "symbol": sym,
            }
    return prices

# ── SSE helpers ───────────────────────────────────────────────────
async def _sse_push(data: Dict):
    """Push data to all SSE price subscribers"""
    msg = json.dumps({"type": "prices", "data": data, "ts": int(time.time())})
    dead = []
    for q in _SSE_QUEUES:
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        if q in _SSE_QUEUES:
            _SSE_QUEUES.remove(q)

async def price_broadcaster():
    global _price_snapshot, _price_snapshot_ts
    # Pre-warm: fetch top N50 on startup
    warmup_syms = NIFTY50_SYMBOLS[:20]
    warmup = await fetch_prices_parallel(warmup_syms)
    _price_snapshot.update(warmup)
    _price_snapshot_ts = time.time()
    logger.info(f"Price cache warmed: {len(warmup)} symbols")

    while True:
        try:
            all_syms: Set[str] = set(NIFTY50_SYMBOLS[:15])
            for s in mgr.subs.values():
                all_syms.update(s)
            prices = await fetch_prices_parallel(list(all_syms))
            if prices:
                _price_snapshot.update(prices)
                _price_snapshot_ts = time.time()
                await mgr.broadcast(prices)
                await _sse_push(prices)
        except Exception as e:
            logger.error(f"Broadcaster: {e}")
        await asyncio.sleep(3)

async def news_background_updater():
    global _latest_market_news, _news_ts
    while True:
        try:
            news = await get_market_news()
            if news:
                _latest_market_news = news[:30]
                _news_ts = time.time()
        except Exception as e:
            logger.error(f"News updater: {e}")
        await asyncio.sleep(120)

async def history_cache_warmer():
    """Pre-warm history cache for top symbols on startup (runs once)"""
    await asyncio.sleep(15)  # let prices warm up first
    loop = asyncio.get_event_loop()
    top_syms = NIFTY50_SYMBOLS[:10]
    logger.info(f"Warming history cache for {len(top_syms)} symbols…")
    tasks = [loop.run_in_executor(None, lambda s=sym: YFData.history(s, "3mo")) for sym in top_syms]
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("History cache warm complete")


# ──────────────────────────────────────────────────────────────────
# FASTAPI APP
# ──────────────────────────────────────────────────────────────────

app = FastAPI(title="Indian Hedge Fund API v3", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    asyncio.create_task(price_broadcaster())
    asyncio.create_task(news_background_updater())
    asyncio.create_task(history_cache_warmer())
    logger.info("API started — broadcaster + news updater + history warmer running")


@app.on_event("shutdown")
async def shutdown():
    await nse.close()


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/indices")
async def get_indices():
    loop = asyncio.get_event_loop()
    names = ["NIFTY 50", "SENSEX", "NIFTY BANK", "NIFTY IT", "INDIA VIX"]
    tasks = [loop.run_in_executor(None, lambda n=name: YFData.index_live(n)) for name in names]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, dict) and r]


@app.get("/api/market/overview")
async def market_overview():
    loop = asyncio.get_event_loop()
    watchlist_syms = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
                      "SBIN", "BAJFINANCE", "BHARTIARTL", "NTPC", "POWERGRID"]
    index_names = ["NIFTY 50", "SENSEX", "NIFTY BANK", "NIFTY IT"]
    stock_tasks = [loop.run_in_executor(None, lambda s=sym: YFData.live_price(s)) for sym in watchlist_syms]
    idx_tasks   = [loop.run_in_executor(None, lambda n=name: YFData.index_live(n)) for name in index_names]
    stock_res, idx_res = await asyncio.gather(
        asyncio.gather(*stock_tasks, return_exceptions=True),
        asyncio.gather(*idx_tasks,   return_exceptions=True),
    )
    stocks  = [r for r in stock_res if isinstance(r, dict) and r]
    indices = [r for r in idx_res   if isinstance(r, dict) and r]
    return {"indices": indices, "watchlist": stocks, "timestamp": datetime.now().isoformat()}


@app.get("/api/market/fii-dii")
async def fii_dii():
    data = await nse.fii_dii()
    if data:
        return data
    return {
        "data": [
            {"category": "FII/FPI", "buyValue": 12450.23, "sellValue": 13230.45, "netValue": -780.22},
            {"category": "DII", "buyValue": 11890.67, "sellValue": 10234.12, "netValue": 1656.55},
        ],
        "note": "Estimated data — NSE API unavailable"
    }


@app.get("/api/market/status")
async def market_status():
    now = datetime.now()
    h, m, wd = now.hour, now.minute, now.weekday()
    ist_offset = 5.5
    is_open = (wd < 5) and (
        (h == 9 and m >= 15) or (9 < h < 15) or (h == 15 and m <= 30)
    )
    return {"is_open": is_open, "message": "Market Open" if is_open else "Market Closed",
            "timestamp": now.isoformat()}


@app.get("/api/quote/{symbol}")
async def get_quote(symbol: str):
    symbol = symbol.upper()
    loop = asyncio.get_event_loop()
    live = await loop.run_in_executor(None, lambda: YFData.live_price(symbol))
    if not live:
        raise HTTPException(404, f"No data for {symbol}")
    nse_data = await nse.quote(symbol)
    if nse_data and nse_data.get("priceInfo"):
        pi = nse_data["priceInfo"]
        live["vwap"] = pi.get("vwap", 0)
        live["lower_circuit"] = pi.get("lowerCP", 0)
        live["upper_circuit"] = pi.get("upperCP", 0)
        dp = nse_data.get("securityWiseDP", {})
        live["delivery_pct"] = dp.get("deliveryToTradedQuantity", 0)
    return live


@app.get("/api/history/{symbol}")
async def get_history(symbol: str, period: str = "1y", interval: str = "1d"):
    symbol = symbol.upper()
    loop = asyncio.get_event_loop()
    records = await loop.run_in_executor(None, lambda: YFData.history(symbol, period))
    if not records:
        raise HTTPException(404, f"No history for {symbol}")
    return {"symbol": symbol, "period": period, "data": records}


@app.get("/api/technicals/{symbol}")
async def get_technicals(symbol: str, period: str = "1y"):
    symbol = symbol.upper()
    loop = asyncio.get_event_loop()
    df = await loop.run_in_executor(None, lambda: YFData.dataframe(symbol, period))
    indicators = TA.compute(df)
    if not indicators:
        raise HTTPException(404, "Insufficient data")
    return {"symbol": symbol, "indicators": indicators}


@app.get("/api/fundamentals/{symbol}")
async def get_fundamentals(symbol: str):
    symbol = symbol.upper()
    loop = asyncio.get_event_loop()
    fund = await loop.run_in_executor(None, lambda: YFData.fundamentals(symbol))
    if not fund:
        raise HTTPException(404, f"No fundamentals for {symbol}")
    return {"symbol": symbol, "fundamentals": fund}


@app.get("/api/options/{symbol}")
async def get_options(symbol: str):
    symbol = symbol.upper()
    data = await nse.option_chain(symbol)
    if not data:
        return {"symbol": symbol, "error": "Option chain unavailable from NSE", "data": []}
    records = data.get("records", {})
    underlying = records.get("underlyingValue", 0)
    expiry_dates = records.get("expiryDates", [])
    options = []
    for item in records.get("data", [])[:80]:
        ce = item.get("CE", {})
        pe = item.get("PE", {})
        options.append({
            "strike": item.get("strikePrice", 0),
            "expiry": item.get("expiryDate", ""),
            "ce_oi": ce.get("openInterest", 0),
            "ce_change_oi": ce.get("changeinOpenInterest", 0),
            "ce_iv": ce.get("impliedVolatility", 0),
            "ce_ltp": ce.get("lastPrice", 0),
            "ce_volume": ce.get("totalTradedVolume", 0),
            "pe_oi": pe.get("openInterest", 0),
            "pe_change_oi": pe.get("changeinOpenInterest", 0),
            "pe_iv": pe.get("impliedVolatility", 0),
            "pe_ltp": pe.get("lastPrice", 0),
            "pe_volume": pe.get("totalTradedVolume", 0),
            "pcr": round(pe.get("openInterest", 0) / max(ce.get("openInterest", 1), 1), 2),
        })
    return {"symbol": symbol, "underlying_value": underlying,
            "expiry_dates": expiry_dates[:4], "data": options}


@app.get("/api/analysis/{symbol}")
async def get_analysis(symbol: str):
    return await full_analysis(symbol.upper())


@app.get("/api/search")
async def search(q: str):
    q_up = q.upper()
    # Search both symbol and company name
    matches: List[str] = []
    for s in ALL_SYMBOLS:
        if q_up in s or q_up in COMPANY_NAMES.get(s, "").upper():
            matches.append(s)
        if len(matches) >= 10:
            break
    loop = asyncio.get_event_loop()
    results = []
    for sym in matches:
        d = await loop.run_in_executor(None, lambda s=sym: YFData.live_price(s))
        if d:
            d["company_name"] = COMPANY_NAMES.get(sym, sym)
            results.append(d)
    return results


@app.get("/api/screener/gainers")
async def gainers():
    loop = asyncio.get_event_loop()
    results = []
    for sym in NIFTY50_SYMBOLS:
        d = await loop.run_in_executor(None, lambda s=sym: YFData.live_price(s))
        if d: results.append(d)
    return sorted(results, key=lambda x: x.get("change_pct", 0), reverse=True)[:15]


@app.get("/api/screener/losers")
async def losers():
    loop = asyncio.get_event_loop()
    results = []
    for sym in NIFTY50_SYMBOLS:
        d = await loop.run_in_executor(None, lambda s=sym: YFData.live_price(s))
        if d: results.append(d)
    return sorted(results, key=lambda x: x.get("change_pct", 0))[:15]


@app.get("/api/screener/nifty50")
async def nifty50():
    loop = asyncio.get_event_loop()
    results = []
    for sym in NIFTY50_SYMBOLS:
        d = await loop.run_in_executor(None, lambda s=sym: YFData.live_price(s))
        if d: results.append(d)
    return sorted(results, key=lambda x: abs(x.get("change_pct", 0)), reverse=True)


@app.get("/api/screener/psu")
async def psu_screener():
    psu_list = ["NTPC", "ONGC", "COALINDIA", "POWERGRID", "BPCL", "BHEL", "SAIL",
                "GAIL", "IOC", "HPCL", "NMDC", "NALCO", "RECLTD", "PFC", "BEL",
                "BEML", "CONCOR", "IRCTC", "RAILTEL", "IRFC", "NHPC", "SJVN",
                "RVNL", "NBCC", "HUDCO", "HAL", "PNB", "CANBK", "BANKBARODA",
                "BANKINDIA", "IOB", "OIL", "PETRONET", "GRSE", "COCHINSHIP",
                "MAZAGON", "SBIN", "MOIL"]
    loop = asyncio.get_event_loop()
    results = []
    for sym in psu_list:
        d = await loop.run_in_executor(None, lambda s=sym: YFData.live_price(s))
        if d:
            d["company_name"] = COMPANY_NAMES.get(sym, sym)
            results.append(d)
    return sorted(results, key=lambda x: x.get("change_pct", 0), reverse=True)


@app.get("/api/screener/universe")
async def universe():
    """Return all symbols with company names (no price fetch — just metadata)"""
    return [
        {"symbol": s, "company_name": COMPANY_NAMES.get(s, s),
         "category": "nifty50" if s in NIFTY50_SYMBOLS
                     else "psu" if s in PSU_SYMBOLS else "nifty100"}
        for s in ALL_SYMBOLS
    ]


@app.get("/api/news/{symbol}")
async def get_stock_news(symbol: str, days: int = 7):
    symbol = symbol.upper()
    articles = await get_company_news(symbol)
    return {
        "symbol": symbol,
        "company": COMPANY_NAMES.get(symbol, symbol),
        "total": len(articles),
        "articles": articles,
    }


@app.get("/api/news/market/feed")
async def get_market_news_feed():
    articles = await get_market_news()
    return {"total": len(articles), "articles": articles}


@app.get("/api/analysts/{symbol}")
async def get_analysts(symbol: str):
    symbol = symbol.upper()
    data = await get_analyst_ratings(symbol)
    if not data:
        return {"symbol": symbol, "data": {}, "message": "No analyst data available"}
    return {"symbol": symbol, "data": data}


@app.get("/api/trends/{symbol}")
async def get_trends(symbol: str):
    symbol = symbol.upper()
    loop = asyncio.get_event_loop()
    live = await loop.run_in_executor(None, lambda: YFData.live_price(symbol)) or {}
    df = await loop.run_in_executor(None, lambda: YFData.dataframe(symbol, "1y"))
    tech = TA.compute(df)
    fund = await loop.run_in_executor(None, lambda: YFData.fundamentals(symbol))
    analysts, news = await asyncio.gather(
        get_analyst_ratings(symbol),
        get_company_news(symbol),
    )
    score = compute_trend_score(live, tech or {}, fund, analysts, news)
    return {
        "symbol": symbol,
        "company": COMPANY_NAMES.get(symbol, symbol),
        "live": live,
        "trend": score,
        "analysts": analysts,
        "news_preview": news[:5],
    }


@app.get("/api/portfolio")
async def get_portfolio():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, pf_summary)


class TradeReq(BaseModel):
    symbol: str
    action: str
    quantity: int
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    target: Optional[float] = None


@app.post("/api/portfolio/trade")
async def execute_trade(req: TradeReq):
    sym = req.symbol.upper()
    loop = asyncio.get_event_loop()
    live = await loop.run_in_executor(None, lambda: YFData.live_price(sym))
    price = req.price or (live.get("price") if live else None)
    if not price:
        raise HTTPException(400, "Price unavailable")

    value = req.quantity * price
    chg = _charges(value, req.action)

    if req.action == "BUY":
        total = value + chg
        if total > _pf["cash"]:
            raise HTTPException(400, f"Insufficient cash. Need ₹{total:,.0f}, have ₹{_pf['cash']:,.0f}")
        _pf["cash"] -= total
        if sym in _pf["positions"]:
            pos = _pf["positions"][sym]
            tot_qty = pos["qty"] + req.quantity
            pos["avg"] = (pos["avg"] * pos["qty"] + price * req.quantity) / tot_qty
            pos["qty"] = tot_qty
        else:
            _pf["positions"][sym] = {"qty": req.quantity, "avg": price,
                                     "stop": req.stop_loss or price * 0.95,
                                     "target": req.target or price * 1.15}
    elif req.action == "SELL":
        if sym not in _pf["positions"]:
            raise HTTPException(400, f"No position in {sym}")
        pos = _pf["positions"][sym]
        if req.quantity > pos["qty"]:
            raise HTTPException(400, f"Only {pos['qty']} shares held")
        _pf["cash"] += value - chg
        pos["qty"] -= req.quantity
        if pos["qty"] == 0:
            del _pf["positions"][sym]
    else:
        raise HTTPException(400, "action must be BUY or SELL")

    trade = {
        "id": f"T{len(_pf['trades'])+1:04d}",
        "ts": datetime.now().isoformat(),
        "symbol": sym, "action": req.action,
        "qty": req.quantity, "price": price,
        "value": round(value, 2), "charges": round(chg, 2),
    }
    _pf["trades"].append(trade)
    return {"success": True, "trade": trade}


@app.get("/api/portfolio/trades")
async def trade_history(limit: int = 50):
    return sorted(_pf["trades"], key=lambda x: x["ts"], reverse=True)[:limit]


# ──────────────────────────────────────────────────────────────────
# MACRO DASHBOARD — Global context tickers
# ──────────────────────────────────────────────────────────────────

MACRO_SYMBOLS = {
    "India VIX": "^INDIAVIX",
    "USD/INR": "USDINR=X",
    "Crude Oil": "CL=F",
    "Gold": "GC=F",
    "US 10Y": "^TNX",
    "S&P 500": "^GSPC",
    "Nifty 50": "^NSEI",
    "Bank Nifty": "^NSEBANK",
}

_macro_cache: Dict = {}
_macro_ts: float = 0
_MACRO_TTL = 120  # 2 min


@app.get("/api/macro")
async def get_macro():
    global _macro_cache, _macro_ts
    if _macro_cache and (time.time() - _macro_ts) < _MACRO_TTL:
        return _macro_cache

    result = []
    for label, yf_sym in MACRO_SYMBOLS.items():
        try:
            data = YFData._chart_raw(yf_sym, "5d", "1d")
            meta = (data or {}).get("meta", {})
            price = meta.get("regularMarketPrice") or meta.get("chartPreviousClose") or 0
            prev = meta.get("chartPreviousClose") or meta.get("previousClose") or price
            chg_pct = ((price - prev) / prev * 100) if prev else 0
            result.append({
                "label": label,
                "symbol": yf_sym,
                "price": round(float(price), 4),
                "change_pct": round(float(chg_pct), 2),
            })
        except Exception as e:
            logger.warning(f"Macro {yf_sym}: {e}")
            result.append({"label": label, "symbol": yf_sym, "price": 0, "change_pct": 0})

    _macro_cache = {"data": result, "ts": int(time.time())}
    _macro_ts = time.time()
    return _macro_cache


# ──────────────────────────────────────────────────────────────────
# MONTE CARLO SIMULATION
# ──────────────────────────────────────────────────────────────────

@app.get("/api/montecarlo/{symbol}")
async def monte_carlo(symbol: str, days: int = 30, simulations: int = 2000):
    symbol = symbol.upper()
    hist = YFData.history(symbol, "2y")
    if not hist:
        raise HTTPException(404, "No price history")
    closes = [h["close"] for h in hist]
    result = _ana.monte_carlo_gbm(closes, days=min(days, 60), simulations=min(simulations, 5000))
    result["symbol"] = symbol
    return result


# ──────────────────────────────────────────────────────────────────
# CORRELATION MATRIX
# ──────────────────────────────────────────────────────────────────

_corr_cache: Dict = {}
_corr_ts: float = 0
_CORR_TTL = 1800  # 30 min


@app.get("/api/correlation")
async def get_correlation(symbols: str = "HDFCBANK,ICICIBANK,AXISBANK,KOTAKBANK,TCS,INFY,WIPRO,HCLTECH,NTPC,POWERGRID,RELIANCE,ONGC"):
    global _corr_cache, _corr_ts
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()][:20]
    cache_key = ",".join(sorted(sym_list))
    cached = _corr_cache.get(cache_key)
    if cached and (time.time() - _corr_ts) < _CORR_TTL:
        return cached

    price_dict: Dict[str, List[float]] = {}
    for sym in sym_list:
        hist = YFData.history(sym, "1y")
        if hist:
            price_dict[sym] = [h["close"] for h in hist]

    result = _ana.compute_correlation_matrix(price_dict)
    result["queried_symbols"] = sym_list
    _corr_cache[cache_key] = result
    _corr_ts = time.time()
    return result


# ──────────────────────────────────────────────────────────────────
# PAIRS TRADING ENGINE
# ──────────────────────────────────────────────────────────────────

KNOWN_PAIRS = [
    ("HDFCBANK", "ICICIBANK"),
    ("HDFCBANK", "KOTAKBANK"),
    ("ICICIBANK", "AXISBANK"),
    ("TCS", "INFY"),
    ("TCS", "WIPRO"),
    ("INFY", "HCLTECH"),
    ("NTPC", "POWERGRID"),
    ("NTPC", "NHPC"),
    ("RELIANCE", "ONGC"),
    ("TATASTEEL", "JSWSTEEL"),
    ("BAJFINANCE", "BAJAJFINSV"),
    ("SUNPHARMA", "CIPLA"),
    ("DRREDDY", "DIVISLAB"),
    ("MARUTI", "TATAMOTORS"),
    ("IOC", "BPCL"),
    ("IOC", "HPCL"),
    ("COALINDIA", "NMDC"),
    ("LT", "SIEMENS"),
    ("ADANIENT", "ADANIPORTS"),
    ("SBIN", "PNB"),
]

_pairs_cache: Dict = {}
_pairs_ts: float = 0
_PAIRS_TTL = 900  # 15 min


@app.get("/api/pairs")
async def get_pairs(action_only: bool = False):
    global _pairs_cache, _pairs_ts
    if _pairs_cache and (time.time() - _pairs_ts) < _PAIRS_TTL:
        data = _pairs_cache
        if action_only:
            data = {**data, "pairs": [p for p in data["pairs"] if p.get("action") != "hold"]}
        return data

    results = []
    hist_cache: Dict[str, List[float]] = {}

    for sym1, sym2 in KNOWN_PAIRS:
        for sym in (sym1, sym2):
            if sym not in hist_cache:
                h = YFData.history(sym, "6mo")
                hist_cache[sym] = [x["close"] for x in h] if h else []

        p1 = hist_cache.get(sym1, [])
        p2 = hist_cache.get(sym2, [])
        if len(p1) < 20 or len(p2) < 20:
            continue

        pair_data = _ana.compute_pair_spread(sym1, sym2, p1, p2)
        if "error" not in pair_data:
            results.append(pair_data)

    results.sort(key=lambda x: abs(x.get("current_zscore", 0)), reverse=True)
    _pairs_cache = {"pairs": results, "generated_at": int(time.time())}
    _pairs_ts = time.time()

    if action_only:
        return {**_pairs_cache, "pairs": [p for p in results if p.get("action") != "hold"]}
    return _pairs_cache


@app.get("/api/pairs/{sym1}/{sym2}")
async def get_pair_detail(sym1: str, sym2: str, lookback: int = 120):
    sym1, sym2 = sym1.upper(), sym2.upper()
    h1 = YFData.history(sym1, "1y")
    h2 = YFData.history(sym2, "1y")
    if not h1 or not h2:
        raise HTTPException(404, "Price history unavailable")
    p1 = [x["close"] for x in h1]
    p2 = [x["close"] for x in h2]
    dates = [x["date"] for x in h1[-lookback:]]
    result = _ana.compute_pair_spread(sym1, sym2, p1, p2, lookback=lookback)
    result["dates"] = dates
    return result


# ──────────────────────────────────────────────────────────────────
# ADVANCED SCREENERS
# ──────────────────────────────────────────────────────────────────

_screen_cache: Dict = {}
_screen_ts: float = 0
_SCREEN_TTL = 1200  # 20 min


async def _batch_quotes_and_history(symbols: List[str]) -> Tuple[List[Dict], Dict[str, List[Dict]]]:
    quotes: List[Dict] = []
    histories: Dict[str, List[Dict]] = {}
    for sym in symbols:
        q = YFData.live_price(sym)
        if q:
            quotes.append(q)
        h = YFData.history(sym, "1y")
        if h:
            histories[sym] = h
    return quotes, histories


@app.get("/api/screener/momentum")
async def screener_momentum():
    cache_key = "momentum"
    cached = _screen_cache.get(cache_key)
    if cached and (time.time() - _screen_ts) < _SCREEN_TTL:
        return cached

    results = []
    for sym in ALL_SYMBOLS:
        hist = YFData.history(sym, "1y")
        if not hist or len(hist) < 65:
            continue
        closes = [h["close"] for h in hist]
        q = YFData.live_price(sym)
        price = (q or {}).get("price", closes[-1])
        chg_pct = (q or {}).get("change_pct", 0)

        score = _ana.rs_rank(closes[-65:], closes[-125:] if len(closes) >= 125 else closes, closes)
        results.append({
            "symbol": sym,
            "company": COMPANY_NAMES.get(sym, sym),
            "price": round(float(price), 2),
            "change_pct": round(float(chg_pct), 2),
            "rs_score": score,
            "ret_65d": round((closes[-1] / closes[-65] - 1) * 100, 2) if len(closes) >= 65 else 0,
            "ret_125d": round((closes[-1] / closes[-125] - 1) * 100, 2) if len(closes) >= 125 else 0,
            "ret_252d": round((closes[-1] / closes[0] - 1) * 100, 2),
        })

    results.sort(key=lambda x: x["rs_score"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1

    out = {"type": "momentum", "results": results, "ts": int(time.time())}
    _screen_cache[cache_key] = out
    return out


@app.get("/api/screener/meanrev")
async def screener_mean_reversion():
    cache_key = "meanrev"
    cached = _screen_cache.get(cache_key)
    if cached and (time.time() - _screen_ts) < _SCREEN_TTL:
        return cached

    results = []
    for sym in ALL_SYMBOLS:
        hist = YFData.history(sym, "6mo")
        if not hist or len(hist) < 20:
            continue
        closes = [h["close"] for h in hist]
        q = YFData.live_price(sym)
        price = (q or {}).get("price", closes[-1])
        chg_pct = (q or {}).get("change_pct", 0)

        sig = _ana.mean_reversion_signal(closes)
        if sig["signal"] in ("strong_buy", "oversold", "strong_sell", "overbought"):
            results.append({
                "symbol": sym,
                "company": COMPANY_NAMES.get(sym, sym),
                "price": round(float(price), 2),
                "change_pct": round(float(chg_pct), 2),
                **sig,
            })

    results.sort(key=lambda x: abs(x["zscore"]), reverse=True)
    out = {"type": "meanrev", "results": results, "ts": int(time.time())}
    _screen_cache[cache_key] = out
    return out


@app.get("/api/screener/breakout")
async def screener_breakout():
    cache_key = "breakout"
    cached = _screen_cache.get(cache_key)
    if cached and (time.time() - _screen_ts) < _SCREEN_TTL:
        return cached

    results = []
    for sym in ALL_SYMBOLS:
        hist = YFData.history(sym, "1y")
        if not hist or len(hist) < 20:
            continue
        closes = [h["close"] for h in hist]
        vols = [h.get("volume", 0) for h in hist]
        q = YFData.live_price(sym)
        price = (q or {}).get("price", closes[-1])
        chg_pct = (q or {}).get("change_pct", 0)
        year_high = (q or {}).get("year_high", 0)

        sig = _ana.breakout_signal(closes, vols, year_high)
        if sig["type"] != "none":
            results.append({
                "symbol": sym,
                "company": COMPANY_NAMES.get(sym, sym),
                "price": round(float(price), 2),
                "change_pct": round(float(chg_pct), 2),
                "year_high": year_high,
                **sig,
            })

    priority = {"52w_high_breakout": 0, "resistance_break": 1, "near_52w_high": 2}
    results.sort(key=lambda x: (priority.get(x["type"], 9), -x.get("vol_ratio", 0)))
    out = {"type": "breakout", "results": results, "ts": int(time.time())}
    _screen_cache[cache_key] = out
    return out


@app.get("/api/screener/volume")
async def screener_volume_surge():
    cache_key = "volume"
    cached = _screen_cache.get(cache_key)
    if cached and (time.time() - _screen_ts) < _SCREEN_TTL:
        return cached

    results = []
    for sym in ALL_SYMBOLS:
        hist = YFData.history(sym, "3mo")
        if not hist or len(hist) < 20:
            continue
        vols = [h.get("volume", 0) for h in hist]
        closes = [h["close"] for h in hist]
        today_vol = vols[-1]
        avg_vol = float(np.mean(vols[-20:-1])) if len(vols) >= 20 else 0
        if avg_vol <= 0 or today_vol <= 0:
            continue

        ratio = today_vol / avg_vol
        if ratio >= 2.0:
            q = YFData.live_price(sym)
            price = (q or {}).get("price", closes[-1])
            chg_pct = (q or {}).get("change_pct", 0)
            results.append({
                "symbol": sym,
                "company": COMPANY_NAMES.get(sym, sym),
                "price": round(float(price), 2),
                "change_pct": round(float(chg_pct), 2),
                "vol_ratio": round(ratio, 2),
                "today_volume": int(today_vol),
                "avg_volume": int(avg_vol),
            })

    results.sort(key=lambda x: x["vol_ratio"], reverse=True)
    out = {"type": "volume", "results": results, "ts": int(time.time())}
    _screen_cache[cache_key] = out
    return out


# ──────────────────────────────────────────────────────────────────
# OPTIONS ANALYTICS
# ──────────────────────────────────────────────────────────────────

@app.get("/api/options/analytics/{symbol}")
async def options_analytics(symbol: str):
    symbol = symbol.upper()
    chain = await nse_client.option_chain(symbol)
    if not chain:
        # Fallback to known symbols
        chain = await nse_client.fetch("option-chain-indices", {"symbol": "NIFTY"}) if symbol == "NIFTY" else None
    if not chain:
        raise HTTPException(404, "Option chain unavailable — NSE requires active session")
    result = _ana.analyze_option_chain(chain)
    result["symbol"] = symbol
    return result


# ──────────────────────────────────────────────────────────────────
# MARKET BREADTH
# ──────────────────────────────────────────────────────────────────

_breadth_cache: Dict = {}
_breadth_ts: float = 0
_BREADTH_TTL = 600  # 10 min


@app.get("/api/breadth")
async def market_breadth():
    global _breadth_cache, _breadth_ts
    if _breadth_cache and (time.time() - _breadth_ts) < _BREADTH_TTL:
        return _breadth_cache

    # Use Nifty 50 for breadth (50 stocks, fast enough)
    quotes: List[Dict] = []
    histories: Dict[str, List[Dict]] = {}
    for sym in NIFTY50_SYMBOLS:
        q = YFData.live_price(sym)
        if q:
            quotes.append(q)
        h = YFData.history(sym, "1y")
        if h:
            histories[sym] = h

    result = _ana.compute_market_breadth(quotes, histories)
    result["universe"] = "Nifty 50"
    result["computed_at"] = datetime.now(timezone.utc).isoformat()
    _breadth_cache = result
    _breadth_ts = time.time()
    return result


# ──────────────────────────────────────────────────────────────────
# SECTOR HEATMAP
# ──────────────────────────────────────────────────────────────────

SECTORS: Dict[str, List[str]] = {
    "IT": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM", "OFSS"],
    "Banking": ["HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN", "INDUSINDBK", "BANKBARODA", "PNB"],
    "Oil & Gas": ["RELIANCE", "ONGC", "BPCL", "IOC", "HPCL", "GAIL", "OIL"],
    "Auto": ["MARUTI", "TATAMOTORS", "MM", "BAJAJ-AUTO", "HEROMOTOCO", "EICHERMOT", "TVSMOTOR"],
    "Pharma": ["SUNPHARMA", "CIPLA", "DRREDDY", "DIVISLAB", "LUPIN", "ZYDUSLIFE"],
    "Power": ["NTPC", "POWERGRID", "NHPC", "SJVN", "TATAPOWER", "JSWENERGY", "ADANIGREEN"],
    "Defence": ["HAL", "BEL", "BEML", "GRSE", "MAZAGON", "COCHINSHIP", "MIDHANI"],
    "Infra/Capital": ["LT", "SIEMENS", "BHEL", "NBCC", "RVNL", "CONCOR"],
    "Metals": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "SAIL", "NMDC", "NALCO", "VEDL"],
    "FMCG": ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR", "MARICO", "COLPAL"],
    "Financials": ["BAJFINANCE", "BAJAJFINSV", "MUTHOOTFIN", "CHOLAFIN", "PFC", "RECLTD"],
    "Cement": ["ULTRACEMCO", "SHREECEM", "AMBUJACEM", "ACC"],
    "Real Estate": ["DLF", "LODHA", "GODREJPROP"],
    "Telecom": ["BHARTIARTL"],
    "Consumer": ["TITAN", "ASIANPAINT", "PIDILITIND", "HAVELLS", "VOLTAS"],
}

_sector_cache: Dict = {}
_sector_ts: float = 0
_SECTOR_TTL = 300  # 5 min


@app.get("/api/sectors")
async def sector_heatmap():
    global _sector_cache, _sector_ts
    if _sector_cache and (time.time() - _sector_ts) < _SECTOR_TTL:
        return _sector_cache

    result = []
    for sector, symbols in SECTORS.items():
        changes = []
        stocks = []
        for sym in symbols:
            q = YFData.live_price(sym)
            if q and q.get("price", 0) > 0:
                chg = q.get("change_pct", 0)
                changes.append(chg)
                stocks.append({
                    "symbol": sym,
                    "price": q["price"],
                    "change_pct": chg,
                })

        if changes:
            avg_chg = round(float(np.mean(changes)), 2)
            result.append({
                "sector": sector,
                "avg_change_pct": avg_chg,
                "stock_count": len(stocks),
                "advances": sum(1 for c in changes if c > 0),
                "declines": sum(1 for c in changes if c < 0),
                "stocks": sorted(stocks, key=lambda x: x["change_pct"], reverse=True),
            })

    result.sort(key=lambda x: x["avg_change_pct"], reverse=True)
    _sector_cache = {"sectors": result, "ts": int(time.time())}
    _sector_ts = time.time()
    return _sector_cache


@app.websocket("/ws/live")
async def ws_endpoint(ws: WebSocket):
    await mgr.connect(ws)
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("action") == "subscribe":
                syms = msg.get("symbols", [])
                mgr.subscribe(ws, syms)
                await ws.send_json({"type": "subscribed", "symbols": syms})
            elif msg.get("action") == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        mgr.disconnect(ws)
    except Exception as e:
        logger.error(f"WS: {e}")
        mgr.disconnect(ws)


# ──────────────────────────────────────────────────────────────────
# SSE ENDPOINTS
# ──────────────────────────────────────────────────────────────────

@app.get("/api/stream/prices")
async def stream_prices(symbols: str = Query(default="")):
    """Server-Sent Events stream for live prices"""
    syms = {s.strip().upper() for s in symbols.split(",") if s.strip()}
    q: asyncio.Queue = asyncio.Queue(maxsize=20)
    _SSE_QUEUES.append(q)

    async def gen():
        try:
            # Send current snapshot immediately
            snap = {s: v for s, v in _price_snapshot.items() if not syms or s in syms}
            if snap:
                yield f"data: {json.dumps({'type':'prices','data':snap,'ts':int(time.time())})}\n\n"
            while True:
                try:
                    raw = await asyncio.wait_for(q.get(), timeout=15.0)
                    if syms:
                        parsed = json.loads(raw)
                        filtered = {s: v for s, v in parsed.get("data", {}).items() if s in syms}
                        if filtered:
                            yield f"data: {json.dumps({'type':'prices','data':filtered,'ts':parsed.get('ts',0)})}\n\n"
                    else:
                        yield f"data: {raw}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type':'heartbeat','ts':int(time.time())})}\n\n"
        finally:
            if q in _SSE_QUEUES:
                _SSE_QUEUES.remove(q)

    return StreamingResponse(gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})


@app.get("/api/stream/news")
async def stream_news():
    """SSE stream for live market news"""
    sent: Set[str] = set()

    async def gen():
        if _latest_market_news:
            yield f"data: {json.dumps({'type':'news_batch','data':_latest_market_news[:20]})}\n\n"
            sent.update(a.get("url", a.get("title", "")) for a in _latest_market_news)
        while True:
            new_items = [a for a in _latest_market_news if a.get("url", a.get("title", "")) not in sent]
            if new_items:
                for item in new_items:
                    yield f"data: {json.dumps({'type':'news_item','data':item})}\n\n"
                    sent.add(item.get("url", item.get("title", "")))
            else:
                yield f"data: {json.dumps({'type':'heartbeat','ts':int(time.time())})}\n\n"
            await asyncio.sleep(30)

    return StreamingResponse(gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ──────────────────────────────────────────────────────────────────
# ANALYSIS ENDPOINTS
# ──────────────────────────────────────────────────────────────────

@app.get("/api/patterns/{symbol}")
async def get_patterns(symbol: str, period: str = "3mo"):
    symbol = symbol.upper()
    loop = asyncio.get_event_loop()
    hist = await loop.run_in_executor(None, lambda: YFData.history(symbol, period))
    if not hist or len(hist) < 20:
        raise HTTPException(404, "Insufficient history")
    closes = [h["close"] for h in hist if h.get("close")]
    volumes = [h.get("volume", 0) for h in hist]
    patterns = detect_chart_patterns(closes)
    # Add mean reversion signal
    mr = _ana.mean_reversion_signal(closes)
    # Add breakout
    yr_high = max(h.get("high", 0) for h in hist[-252:] if h.get("high")) if len(hist) >= 50 else closes[-1]
    br = _ana.breakout_signal(closes, volumes, yr_high)
    return {
        "symbol": symbol, "bars": len(closes), **patterns,
        "mean_reversion": mr, "breakout": br,
        "computed_at": datetime.now().isoformat(),
    }


@app.get("/api/greeks")
async def get_greeks(
    symbol: str = Query(...), strike: float = Query(...),
    expiry_days: int = Query(30), opt_type: str = Query("call"), iv: float = Query(0.0)
):
    symbol = symbol.upper()
    loop = asyncio.get_event_loop()
    live = await loop.run_in_executor(None, lambda: YFData.live_price(symbol))
    if not live:
        raise HTTPException(404, f"No quote for {symbol}")
    S = live["price"]
    T = expiry_days / 365.0
    r = 0.068  # RBI repo rate ~6.8%
    # Estimate IV if not provided
    if iv <= 0:
        hist = await loop.run_in_executor(None, lambda: YFData.history(symbol, "1mo", "1d"))
        if hist and len(hist) >= 10:
            closes = [h["close"] for h in hist if h.get("close")]
            log_rets = np.diff(np.log(closes))
            iv = float(np.std(log_rets) * np.sqrt(252))
        else:
            iv = 0.25  # default 25%
    greeks = bs_greeks(S, strike, T, r, iv, opt_type)
    return {
        "symbol": symbol, "spot": S, "strike": strike,
        "expiry_days": expiry_days, "iv_used": round(iv, 4),
        "risk_free_rate": r, "option_type": opt_type,
        **greeks,
    }


@app.get("/api/fear-greed")
async def fear_greed():
    return await compute_fear_greed()


@app.get("/api/snapshot")
async def price_snapshot(symbols: str = Query(default="")):
    """Return current cached prices instantly — no YF fetch"""
    if not symbols:
        return {"data": _price_snapshot, "ts": _price_snapshot_ts, "count": len(_price_snapshot)}
    syms = {s.strip().upper() for s in symbols.split(",") if s.strip()}
    data = {s: _price_snapshot[s] for s in syms if s in _price_snapshot}
    # For symbols not in cache, fetch in parallel
    missing = syms - set(data.keys())
    if missing:
        fresh = await fetch_prices_parallel(list(missing))
        data.update(fresh)
        _price_snapshot.update(fresh)
    return {"data": data, "ts": int(time.time()), "count": len(data)}


# ──────────────────────────────────────────────────────────────────
# EARNINGS DEEP DIVE  (quarterly EPS + revenue + ROCE + growth)
# ──────────────────────────────────────────────────────────────────

@app.get("/api/earnings/{symbol}")
async def get_earnings_deep(symbol: str):
    symbol = symbol.upper()
    loop = asyncio.get_event_loop()

    def fetch():
        try:
            crumb = YFData._get_crumb()
            yf_sym = YFData.yf_sym(symbol)
            url = f"{YFData.BASE}/v10/finance/quoteSummary/{yf_sym}"
            params = {
                "modules": ",".join([
                    "earnings", "financialData", "defaultKeyStatistics",
                    "incomeStatementHistoryQuarterly", "balanceSheetHistoryQuarterly",
                    "assetProfile", "summaryDetail",
                ])
            }
            if crumb:
                params["crumb"] = crumb
            r = YFData._get_session().get(url, params=params, timeout=25)
            if r.status_code != 200:
                return {}
            data = r.json()
            qsr = (data.get("quoteSummary", {}).get("result") or [{}])[0]

            def raw(d, k):
                v = d.get(k)
                return v.get("raw") if isinstance(v, dict) else v

            fd = qsr.get("financialData", {})
            ks = qsr.get("defaultKeyStatistics", {})
            sd = qsr.get("summaryDetail", {})
            ap = qsr.get("assetProfile", {})
            earn = qsr.get("earnings", {})

            # Quarterly EPS + revenue from earnings chart
            q_eps = []
            for q in earn.get("earningsChart", {}).get("quarterly", []):
                q_eps.append({
                    "date": q.get("date", ""),
                    "actual": raw(q, "actual"),
                    "estimate": raw(q, "estimate"),
                })

            # Quarterly financials from incomeStatementHistoryQuarterly
            q_fin = []
            for stmt in qsr.get("incomeStatementHistoryQuarterly", {}).get("incomeStatementHistory", []):
                q_fin.append({
                    "date": stmt.get("endDate", {}).get("fmt", ""),
                    "total_revenue": raw(stmt, "totalRevenue"),
                    "gross_profit": raw(stmt, "grossProfit"),
                    "operating_income": raw(stmt, "operatingIncome"),
                    "net_income": raw(stmt, "netIncome"),
                    "ebitda": raw(stmt, "ebitda"),
                })

            # ROCE from balance sheet + income statement
            roce = None
            bs_quarters = qsr.get("balanceSheetHistoryQuarterly", {}).get("balanceSheetStatements", [])
            is_quarters = qsr.get("incomeStatementHistoryQuarterly", {}).get("incomeStatementHistory", [])
            if bs_quarters and is_quarters:
                bs = bs_quarters[0]
                ist = is_quarters[0]
                total_assets = raw(bs, "totalAssets")
                curr_liab = raw(bs, "totalCurrentLiabilities")
                op_income = raw(ist, "operatingIncome")
                if total_assets and curr_liab and op_income:
                    capital_employed = total_assets - curr_liab
                    if capital_employed > 0:
                        roce = round((op_income / capital_employed) * 100, 2)

            # Sector peer rank placeholder (computed vs sector avg)
            sector = ap.get("sector", "Unknown")
            industry = ap.get("industry", "Unknown")
            roe = raw(fd, "returnOnEquity")
            roa = raw(fd, "returnOnAssets")

            return {
                "symbol": symbol,
                "company": ap.get("longName", symbol),
                "sector": sector,
                "industry": industry,
                "employees": ap.get("fullTimeEmployees"),
                # Quarterly EPS trend
                "quarterly_eps": q_eps[-4:][::-1],
                # Quarterly financials
                "quarterly_financials": q_fin[-4:][::-1],
                # Key metrics
                "roce": roce,
                "roe": round(roe * 100, 2) if roe else None,
                "roa": round(roa * 100, 2) if roa else None,
                "revenue_growth": round(raw(fd, "revenueGrowth") * 100, 2) if raw(fd, "revenueGrowth") else None,
                "earnings_growth": round(raw(fd, "earningsGrowth") * 100, 2) if raw(fd, "earningsGrowth") else None,
                "gross_margin": round(raw(fd, "grossMargins") * 100, 2) if raw(fd, "grossMargins") else None,
                "operating_margin": round(raw(fd, "operatingMargins") * 100, 2) if raw(fd, "operatingMargins") else None,
                "net_margin": round(raw(fd, "profitMargins") * 100, 2) if raw(fd, "profitMargins") else None,
                "pe_ratio": raw(sd, "trailingPE"),
                "forward_pe": raw(sd, "forwardPE"),
                "peg": raw(ks, "pegRatio"),
                "eps_ttm": raw(ks, "trailingEps"),
                "forward_eps": raw(ks, "forwardEps"),
                "book_value": raw(ks, "bookValue"),
                "price_to_book": raw(ks, "priceToBook"),
                "debt_to_equity": raw(fd, "debtToEquity"),
                "current_ratio": raw(fd, "currentRatio"),
                "free_cashflow": raw(fd, "freeCashflow"),
                "total_debt": raw(fd, "totalDebt"),
                "total_cash": raw(fd, "totalCash"),
                "total_revenue": raw(fd, "totalRevenue"),
                "ebitda": raw(fd, "ebitda"),
            }
        except Exception as e:
            logger.error(f"earnings_deep {symbol}: {e}")
            return {}

    result = await loop.run_in_executor(None, fetch)
    if not result:
        raise HTTPException(404, f"No earnings data for {symbol}")
    return result


# ──────────────────────────────────────────────────────────────────
# STOCK COMPARISON  (normalized chart + Pearson correlation)
# ──────────────────────────────────────────────────────────────────

_COMPARE_PERIOD_MAP = {
    "1W": "5d", "1M": "1mo", "3M": "3mo",
    "6M": "6mo", "1Y": "1y", "3Y": "3y", "5Y": "5y",
}

@app.get("/api/compare/{sym1}/{sym2}")
async def compare_stocks(sym1: str, sym2: str, period: str = "1Y"):
    sym1, sym2 = sym1.upper(), sym2.upper()
    yf_period = _COMPARE_PERIOD_MAP.get(period.upper(), "1y")
    loop = asyncio.get_event_loop()

    h1, h2 = await asyncio.gather(
        loop.run_in_executor(None, lambda: YFData.history(sym1, yf_period)),
        loop.run_in_executor(None, lambda: YFData.history(sym2, yf_period)),
    )

    if not h1 or not h2:
        raise HTTPException(404, "History unavailable for one or both symbols")

    d1 = {h["date"]: h["close"] for h in h1 if h.get("close")}
    d2 = {h["date"]: h["close"] for h in h2 if h.get("close")}
    common = sorted(set(d1) & set(d2))

    if len(common) < 10:
        raise HTTPException(400, "Insufficient overlapping trading days")

    c1 = np.array([d1[d] for d in common])
    c2 = np.array([d2[d] for d in common])

    # Normalize to 100 at start
    n1 = (c1 / c1[0]) * 100
    n2 = (c2 / c2[0]) * 100

    # Pearson correlation on daily returns
    r1 = np.diff(c1) / c1[:-1]
    r2 = np.diff(c2) / c2[:-1]
    corr = float(np.corrcoef(r1, r2)[0, 1])
    corr_score = round(corr * 100, 1)

    beta = float(np.cov(r1, r2)[0, 1] / np.var(r2)) if np.var(r2) > 0 else 1.0
    vol1 = float(np.std(r1) * np.sqrt(252) * 100)
    vol2 = float(np.std(r2) * np.sqrt(252) * 100)

    label = (
        "Strong Positive" if corr > 0.7 else
        "Moderate Positive" if corr > 0.4 else
        "Weak Positive" if corr > 0.1 else
        "Uncorrelated" if corr > -0.1 else
        "Weak Negative" if corr > -0.4 else
        "Moderate Negative" if corr > -0.7 else
        "Strong Negative"
    )

    chart = [
        {"date": d, sym1: round(float(n1[i]), 2), sym2: round(float(n2[i]), 2)}
        for i, d in enumerate(common)
    ]

    # Compute cumulative returns
    ret1 = round((c1[-1] / c1[0] - 1) * 100, 2)
    ret2 = round((c2[-1] / c2[0] - 1) * 100, 2)

    return {
        "sym1": sym1, "sym2": sym2, "period": period,
        "correlation": round(corr, 4),
        "correlation_score": corr_score,
        "beta": round(beta, 3),
        "label": label,
        "data_points": len(common),
        "ret1": ret1, "ret2": ret2,
        "vol1": round(vol1, 2), "vol2": round(vol2, 2),
        "chart": chart,
    }


# ──────────────────────────────────────────────────────────────────
# VOLUME DEVIATION SCAN
# ──────────────────────────────────────────────────────────────────

@app.get("/api/volume-scan")
async def volume_scan():
    symbols = NIFTY50_SYMBOLS[:25]
    loop = asyncio.get_event_loop()

    async def compute_one(sym: str):
        hist = await loop.run_in_executor(None, lambda: YFData.history(sym, "1y"))
        if not hist or len(hist) < 22:
            return None
        vols = np.array([h.get("volume", 0) for h in hist], dtype=float)
        vols[vols == 0] = np.nan

        today_vol = float(vols[-1]) if not np.isnan(vols[-1]) else float(np.nanmean(vols[-5:]))

        def safe_avg(arr):
            v = arr[~np.isnan(arr)]
            return float(np.mean(v)) if len(v) > 0 else None

        avg_20d = safe_avg(vols[-20:])
        avg_3m = safe_avg(vols[-63:]) if len(vols) >= 63 else None
        avg_6m = safe_avg(vols[-126:]) if len(vols) >= 126 else None
        avg_1y = safe_avg(vols[-252:]) if len(vols) >= 252 else None
        avg_all = safe_avg(vols)

        def dev(a):
            return round((today_vol / a - 1) * 100, 1) if a and a > 0 else None

        snap = _price_snapshot.get(sym, {})
        return {
            "symbol": sym,
            "price": snap.get("price", 0),
            "change_pct": snap.get("change_pct", 0),
            "today_vol": int(today_vol),
            "avg_20d": int(avg_20d) if avg_20d else None,
            "avg_3m": int(avg_3m) if avg_3m else None,
            "avg_6m": int(avg_6m) if avg_6m else None,
            "avg_1y": int(avg_1y) if avg_1y else None,
            "avg_all": int(avg_all) if avg_all else None,
            "dev_20d": dev(avg_20d),
            "dev_3m": dev(avg_3m),
            "dev_6m": dev(avg_6m),
            "dev_1y": dev(avg_1y),
            "dev_all": dev(avg_all),
        }

    tasks = [compute_one(s) for s in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    data = [r for r in results if r and not isinstance(r, Exception)]
    data.sort(key=lambda x: abs(x.get("dev_20d") or 0), reverse=True)
    return {"data": data, "computed_at": datetime.now().isoformat()}


# ──────────────────────────────────────────────────────────────────
# SHARPE RATIOS  (multi-period, risk-free = India 10Y ~7%)
# ──────────────────────────────────────────────────────────────────

@app.get("/api/sharpe/{symbol}")
async def get_sharpe_ratios(symbol: str):
    symbol = symbol.upper()
    loop = asyncio.get_event_loop()

    def compute():
        hist = YFData.history(symbol, "5y")
        if not hist or len(hist) < 30:
            return {}
        closes = np.array([h["close"] for h in hist], dtype=float)
        rf_daily = 0.07 / 252  # India 10Y yield proxy

        periods = {"1M": 21, "3M": 63, "6M": 126, "1Y": 252, "3Y": 756}
        result = {}
        for label, days in periods.items():
            if len(closes) < days + 1:
                continue
            c = closes[-(days + 1):]
            rets = np.diff(c) / c[:-1]
            excess = rets - rf_daily
            std = np.std(excess)
            sharpe = (np.mean(excess) / std * np.sqrt(252)) if std > 0 else 0.0
            total_ret = (c[-1] / c[0] - 1) * 100
            ann_vol = np.std(rets) * np.sqrt(252) * 100
            max_dd = _max_drawdown(c)
            calmar = (total_ret / 252 * days) / abs(max_dd) if max_dd != 0 else 0
            result[label] = {
                "sharpe": round(sharpe, 3),
                "return_pct": round(total_ret, 2),
                "ann_vol_pct": round(ann_vol, 2),
                "max_drawdown_pct": round(max_dd * 100, 2),
                "calmar": round(calmar, 3),
            }

        # All-time
        if len(closes) >= 5:
            rets_all = np.diff(closes) / closes[:-1]
            excess_all = rets_all - rf_daily
            std_all = np.std(excess_all)
            sharpe_all = (np.mean(excess_all) / std_all * np.sqrt(252)) if std_all > 0 else 0.0
            result["All"] = {
                "sharpe": round(sharpe_all, 3),
                "return_pct": round((closes[-1] / closes[0] - 1) * 100, 2),
                "ann_vol_pct": round(np.std(rets_all) * np.sqrt(252) * 100, 2),
                "max_drawdown_pct": round(_max_drawdown(closes) * 100, 2),
                "calmar": 0.0,
            }

        return result

    def _max_drawdown(prices):
        peak = prices[0]
        max_dd = 0.0
        for p in prices:
            if p > peak:
                peak = p
            dd = (p - peak) / peak
            if dd < max_dd:
                max_dd = dd
        return max_dd

    data = await loop.run_in_executor(None, compute)
    return {"symbol": symbol, "rf_annual_pct": 7.0, "periods": data}


# ──────────────────────────────────────────────────────────────────
# HISTORICAL EVENTS CATALOG + PERFORMANCE ANALYSIS
# Real event dates, real price data from YF for the date ranges
# ──────────────────────────────────────────────────────────────────

_EVENTS = [
    {"id": "covid_crash", "name": "COVID-19 Crash", "category": "pandemic",
     "start": "2020-02-17", "end": "2020-03-23",
     "description": "Global pandemic triggered fastest bear market in history. Nifty fell 38% in 33 days."},
    {"id": "covid_recovery", "name": "Post-COVID V-Recovery", "category": "recovery",
     "start": "2020-03-24", "end": "2021-12-31",
     "description": "Unprecedented stimulus-driven rally. Nifty tripled from lows."},
    {"id": "russia_ukraine", "name": "Russia-Ukraine War", "category": "geopolitical",
     "start": "2022-02-24", "end": "2022-09-30",
     "description": "Energy and commodity shock. FII outflows of ₹2.8L Cr from Indian markets."},
    {"id": "demonetization", "name": "India Demonetization", "category": "policy",
     "start": "2016-11-08", "end": "2017-02-28",
     "description": "Modi govt banned ₹500/₹1000 notes. Banking stocks surged, real estate fell."},
    {"id": "gfc_2008", "name": "2008 Global Financial Crisis", "category": "financial",
     "start": "2008-09-15", "end": "2009-03-09",
     "description": "Lehman collapse. Sensex fell 60% peak-to-trough."},
    {"id": "oil_crash_2020", "name": "Oil Price War & Collapse", "category": "commodity",
     "start": "2020-03-06", "end": "2020-04-28",
     "description": "Saudi-Russia price war + COVID demand collapse. Brent fell to $19/barrel."},
    {"id": "fed_hike_2022", "name": "Fed Rate Hike Supercycle", "category": "monetary",
     "start": "2022-03-16", "end": "2023-07-26",
     "description": "US Fed raised rates 525 bps in 16 months — fastest since 1980s."},
    {"id": "india_budget_2021", "name": "Union Budget 2021 — Infra Push", "category": "policy",
     "start": "2021-02-01", "end": "2021-06-30",
     "description": "Capex-heavy budget ₹5.5L Cr for infra. PSU, metals, defence rallied."},
    {"id": "adani_crisis", "name": "Adani Group Short Attack", "category": "corporate",
     "start": "2023-01-24", "end": "2023-03-31",
     "description": "Hindenburg Research report on Adani Group. Adani stocks fell 60%+."},
    {"id": "india_election_2024", "name": "India General Elections 2024", "category": "policy",
     "start": "2024-04-19", "end": "2024-06-04",
     "description": "BJP fell short of majority. Market volatile on coalition uncertainty."},
]

# Sector proxy symbols for event analysis
_SECTOR_PROXIES = {
    "Nifty50": "^NSEI",
    "IT": "TCS.NS",
    "Banks": "HDFCBANK.NS",
    "Pharma": "SUNPHARMA.NS",
    "Auto": "MARUTI.NS",
    "Energy/Oil": "RELIANCE.NS",
    "Metals": "TATASTEEL.NS",
    "FMCG": "HINDUNILVR.NS",
    "Infra": "LT.NS",
    "Defence": "HAL.NS",
    "Realty": "DLF.NS",
    "PSU Bank": "SBIN.NS",
    "NBFC": "BAJFINANCE.NS",
}


@app.get("/api/events")
async def list_events():
    return {"events": _EVENTS}


@app.get("/api/event-analysis/{event_id}")
async def event_performance(event_id: str):
    ev = next((e for e in _EVENTS if e["id"] == event_id), None)
    if not ev:
        raise HTTPException(404, f"Unknown event: {event_id}")

    loop = asyncio.get_event_loop()

    def compute_returns():
        start_dt = datetime.strptime(ev["start"], "%Y-%m-%d")
        end_dt = datetime.strptime(ev["end"], "%Y-%m-%d")
        days_span = (end_dt - start_dt).days

        # Determine appropriate fetch period
        total_days = (datetime.now() - start_dt).days
        if total_days > 365 * 4:
            fetch_period = "5y"
        elif total_days > 365 * 2:
            fetch_period = "3y"
        elif total_days > 365:
            fetch_period = "2y"
        else:
            fetch_period = "1y"

        perf = {}
        for sector, sym in _SECTOR_PROXIES.items():
            try:
                # Remove .NS for YFData internal lookup if needed
                internal_sym = sym.replace(".NS", "") if sym.endswith(".NS") else sym
                if sym.startswith("^"):
                    # Index - use raw chart API
                    data = YFData._chart_raw(sym, fetch_period, "1d")
                else:
                    data = YFData.chart(internal_sym, fetch_period, "1d")
                if not data:
                    continue

                timestamps = data.get("timestamp", [])
                quotes = data.get("indicators", {}).get("quote", [{}])[0]
                closes = quotes.get("close", [])

                # Map to dates
                date_prices = {}
                for i, ts in enumerate(timestamps):
                    if i < len(closes) and closes[i] is not None:
                        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                        date_prices[dt.date()] = closes[i]

                # Find closest price at event start and end
                all_dates = sorted(date_prices.keys())
                start_d = start_dt.date()
                end_d = end_dt.date()

                # Find nearest available dates
                avail_at_start = [d for d in all_dates if d >= start_d]
                avail_at_end = [d for d in all_dates if d <= end_d]

                if not avail_at_start or not avail_at_end:
                    continue

                p_start = date_prices[avail_at_start[0]]
                p_end = date_prices[avail_at_end[-1]]

                ret = round((p_end / p_start - 1) * 100, 2)
                perf[sector] = {
                    "return_pct": ret,
                    "start_price": round(p_start, 2),
                    "end_price": round(p_end, 2),
                    "signal": "bullish" if ret > 5 else "bearish" if ret < -5 else "neutral",
                }
            except Exception as ex:
                logger.warning(f"Event {event_id} {sector}: {ex}")

        return perf

    performance = await loop.run_in_executor(None, compute_returns)
    sorted_perf = dict(sorted(performance.items(), key=lambda x: x[1]["return_pct"], reverse=True))

    return {
        **ev,
        "performance": sorted_perf,
        "computed_at": datetime.now().isoformat(),
    }


# ──────────────────────────────────────────────────────────────────
# GEOPOLITICAL NEWS  (RSS + country geo-tagging)
# ──────────────────────────────────────────────────────────────────

_GEO_COUNTRY_COORDS: Dict[str, Tuple[float, float]] = {
    "India": (20.59, 78.96), "United States": (37.09, -95.71), "USA": (37.09, -95.71),
    "China": (35.86, 104.20), "Russia": (61.52, 105.32), "Ukraine": (48.38, 31.17),
    "United Kingdom": (55.38, -3.44), "UK": (55.38, -3.44), "Germany": (51.17, 10.45),
    "France": (46.23, 2.21), "Japan": (36.20, 138.25), "South Korea": (35.91, 127.77),
    "Australia": (-25.27, 133.78), "Canada": (56.13, -106.35), "Brazil": (-14.24, -51.93),
    "Iran": (32.43, 53.69), "Pakistan": (30.38, 69.35), "Israel": (31.05, 34.85),
    "Saudi Arabia": (23.89, 45.08), "UAE": (23.42, 53.85), "Turkey": (38.96, 35.24),
    "Indonesia": (-0.79, 113.92), "Mexico": (23.63, -102.55), "Argentina": (-38.42, -63.62),
    "Egypt": (26.82, 30.80), "Nigeria": (9.08, 8.67), "South Africa": (-28.03, 24.68),
    "Thailand": (15.87, 100.99), "Vietnam": (14.06, 108.28), "Malaysia": (4.21, 101.97),
    "Bangladesh": (23.68, 90.36), "Sri Lanka": (7.87, 80.77), "Myanmar": (16.87, 96.08),
    "Afghanistan": (33.94, 67.71), "Iraq": (33.22, 43.68), "Syria": (34.80, 38.99),
    "Yemen": (15.55, 48.52), "Libya": (26.34, 17.23), "Sudan": (15.56, 32.53),
    "Taiwan": (23.70, 120.96), "Hong Kong": (22.32, 114.17), "Singapore": (1.35, 103.82),
    "North Korea": (40.34, 127.51), "Ethiopia": (9.15, 40.49), "Somalia": (5.15, 46.20),
    "Palestine": (31.95, 35.23), "Lebanon": (33.85, 35.86), "Qatar": (25.35, 51.18),
    "Kuwait": (29.31, 47.49), "Bahrain": (25.93, 50.64), "Oman": (21.51, 55.92),
    "Europe": (54.53, 15.26), "Asia": (34.05, 100.62), "Middle East": (29.31, 42.46),
    "Africa": (8.78, 34.51), "Latin America": (-8.78, -55.49),
    "OPEC": (24.48, 54.37), "G7": (47.17, 2.21), "G20": (20.59, 78.96),
    "Federal Reserve": (37.09, -95.71), "ECB": (50.11, 8.68),
    "RBI": (18.92, 72.83), "SEBI": (19.08, 72.88), "NSE": (19.10, 72.87),
}

_GEO_CATEGORIES = {
    "conflict": ["war","attack","military","bomb","missile","troops","invasion","border","ceasefire","sanctions","airstrike","casualt"],
    "economic": ["economy","gdp","inflation","interest rate","recession","trade","tariff","deficit","growth","unemployment","imf","world bank"],
    "energy": ["oil","crude","opec","gas","energy","petroleum","barrel","brent","wti","lng","pipeline"],
    "monetary": ["federal reserve","fed","rate hike","central bank","rbi","ecb","rate cut","quantitative","monetary policy","bps"],
    "political": ["election","president","prime minister","government","parliament","coup","protest","policy","sanctions","summit","bilateral"],
    "corporate": ["merger","acquisition","ipo","bankruptcy","fraud","investigation","earnings","revenue","lawsuit","sec","sebi"],
    "climate": ["climate","carbon","emissions","renewable","solar","wind","cop","paris agreement","drought","flood"],
}

_GEO_NEWS_CACHE: List[Dict] = []
_GEO_NEWS_TS: float = 0
GEO_NEWS_TTL = 1800  # 30 min


def _extract_location(text: str) -> Optional[Tuple[str, float, float]]:
    text_lower = text.lower()
    # Longest match first
    for country, (lat, lng) in sorted(_GEO_COUNTRY_COORDS.items(), key=lambda x: -len(x[0])):
        if country.lower() in text_lower:
            return country, lat, lng
    return None


def _extract_geo_category(text: str) -> str:
    text_lower = text.lower()
    for cat, keywords in _GEO_CATEGORIES.items():
        if any(kw in text_lower for kw in keywords):
            return cat
    return "general"


async def _fetch_geo_news_feeds() -> List[Dict]:
    feeds = [
        ("https://feeds.bbci.co.uk/news/world/rss.xml", "geopolitical"),
        ("https://rss.reuters.com/reuters/worldNews", "economic"),
        ("https://feeds.bbci.co.uk/news/business/rss.xml", "economic"),
        ("https://www.thehindu.com/business/Economy/feeder/default.rss", "economic"),
        ("https://economictimes.indiatimes.com/markets/rss.cms", "economic"),
        ("https://feeds.feedburner.com/NDTV-LatestNews", "general"),
    ]
    articles = []
    connector = aiohttp.TCPConnector(ssl=False)
    timeout = aiohttp.ClientTimeout(total=10)
    for url, default_cat in feeds:
        try:
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as sess:
                async with sess.get(url, headers={"User-Agent": "Mozilla/5.0"}) as r:
                    if r.status != 200:
                        continue
                    text = await r.text(errors="replace")
            root = ET.fromstring(text)
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            for item in root.findall(".//item")[:20]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                desc = re.sub(r"<[^>]+>", "", item.findtext("description") or "")[:250]
                pub_raw = item.findtext("pubDate") or ""
                src_el = item.find("source")
                source = src_el.text if src_el is not None else url.split("/")[2]
                try:
                    pub_dt = parsedate_to_datetime(pub_raw)
                    if pub_dt < cutoff:
                        continue
                    age_h = max(0, int((datetime.now(timezone.utc) - pub_dt).total_seconds() / 3600))
                except Exception:
                    age_h = 0

                combined = f"{title} {desc}"
                loc = _extract_location(combined)
                cat = _extract_geo_category(combined)
                if not loc:
                    continue  # skip articles with no geo signal

                articles.append({
                    "title": title, "url": link, "source": source,
                    "age_hours": age_h,
                    "country": loc[0], "lat": loc[1], "lng": loc[2],
                    "category": cat,
                    "summary": desc[:200],
                })
        except Exception as e:
            logger.warning(f"Geo news feed {url}: {e}")

    # Deduplicate by title
    seen: set = set()
    deduped = []
    for a in articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            deduped.append(a)
    deduped.sort(key=lambda x: x["age_hours"])
    return deduped[:60]


@app.get("/api/geo-news")
async def geo_news():
    global _GEO_NEWS_CACHE, _GEO_NEWS_TS
    if _GEO_NEWS_CACHE and (time.time() - _GEO_NEWS_TS) < GEO_NEWS_TTL:
        return {"articles": _GEO_NEWS_CACHE, "cached": True, "count": len(_GEO_NEWS_CACHE)}
    articles = await _fetch_geo_news_feeds()
    _GEO_NEWS_CACHE = articles
    _GEO_NEWS_TS = time.time()
    return {"articles": articles, "cached": False, "count": len(articles)}


# ──────────────────────────────────────────────────────────────────
# DIVIDEND PRICE ANALYSIS  (real dividend + price reaction data)
# ──────────────────────────────────────────────────────────────────

@app.get("/api/dividend-analysis/{symbol}")
async def dividend_analysis(symbol: str):
    symbol = symbol.upper()
    loop = asyncio.get_event_loop()

    def compute():
        try:
            crumb = YFData._get_crumb()
            yf_sym = YFData.yf_sym(symbol)
            # Fetch 3-year price history
            hist_data = YFData.history(symbol, "3y")
            if not hist_data:
                return {"events": [], "symbol": symbol}

            price_by_date = {h["date"]: h["close"] for h in hist_data}

            # Fetch dividends from quoteSummary
            url = f"{YFData.BASE}/v10/finance/quoteSummary/{yf_sym}"
            params = {"modules": "dividendHistory,summaryDetail"}
            if crumb:
                params["crumb"] = crumb
            r = YFData._get_session().get(url, params=params, timeout=20)
            if r.status_code != 200:
                return {"events": [], "symbol": symbol}

            data = r.json()
            qsr = (data.get("quoteSummary", {}).get("result") or [{}])[0]

            # Try to get dividends from the chart data directly
            chart_data = YFData.chart(symbol, "3y", "1d")
            events_raw = (chart_data or {}).get("events", {}).get("dividends", {})

            div_events = []
            dates_sorted = sorted(price_by_date.keys())

            for ts_str, div_info in events_raw.items():
                try:
                    ts = int(ts_str)
                    ex_date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                    amount = div_info.get("amount", 0)

                    # Find price on ex-date and surrounding days
                    def find_price(date_str, offset_days=0):
                        dt = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=offset_days)
                        for i in range(5):
                            d = (dt + timedelta(days=i)).strftime("%Y-%m-%d")
                            if d in price_by_date:
                                return price_by_date[d]
                            d = (dt - timedelta(days=i)).strftime("%Y-%m-%d")
                            if d in price_by_date:
                                return price_by_date[d]
                        return None

                    p_before = find_price(ex_date, -1)
                    p_ex = find_price(ex_date, 0)
                    p_after_week = find_price(ex_date, 7)
                    p_after_month = find_price(ex_date, 30)

                    if not p_ex:
                        continue

                    div_events.append({
                        "ex_date": ex_date,
                        "amount": round(amount, 2),
                        "yield_on_ex": round(amount / p_ex * 100, 3) if p_ex else None,
                        "price_before": p_before,
                        "price_ex": round(p_ex, 2),
                        "price_1w_after": round(p_after_week, 2) if p_after_week else None,
                        "price_1m_after": round(p_after_month, 2) if p_after_month else None,
                        "ret_ex_day": round((p_ex / p_before - 1) * 100, 2) if p_before and p_before > 0 else None,
                        "ret_1w": round((p_after_week / p_ex - 1) * 100, 2) if p_after_week and p_ex > 0 else None,
                        "ret_1m": round((p_after_month / p_ex - 1) * 100, 2) if p_after_month and p_ex > 0 else None,
                    })
                except Exception:
                    continue

            div_events.sort(key=lambda x: x["ex_date"], reverse=True)

            # Compute averages
            ex_day_rets = [e["ret_ex_day"] for e in div_events if e.get("ret_ex_day") is not None]
            w1_rets = [e["ret_1w"] for e in div_events if e.get("ret_1w") is not None]
            m1_rets = [e["ret_1m"] for e in div_events if e.get("ret_1m") is not None]

            return {
                "symbol": symbol,
                "events": div_events[:8],
                "avg_ex_day_ret": round(float(np.mean(ex_day_rets)), 2) if ex_day_rets else None,
                "avg_1w_ret": round(float(np.mean(w1_rets)), 2) if w1_rets else None,
                "avg_1m_ret": round(float(np.mean(m1_rets)), 2) if m1_rets else None,
                "total_dividends": len(div_events),
            }
        except Exception as e:
            logger.error(f"dividend_analysis {symbol}: {e}")
            return {"symbol": symbol, "events": []}

    result = await loop.run_in_executor(None, compute)
    return result


# ══════════════════════════════════════════════════════════════════
# GLOBAL MACRO DASHBOARD
# ══════════════════════════════════════════════════════════════════

@app.get("/api/global-macro")
async def get_global_macro():
    """Full global macro snapshot: indices, FX, commodities, bonds"""
    loop = asyncio.get_event_loop()

    def compute():
        sess = YFData._get_session()
        return _macro.build_global_snapshot(sess)

    return await loop.run_in_executor(None, compute)


@app.get("/api/yield-curve")
async def get_yield_curve():
    """US and India yield curve data with spread analysis"""
    loop = asyncio.get_event_loop()

    def compute():
        sess = YFData._get_session()
        return _macro.compute_yield_curve(sess)

    return await loop.run_in_executor(None, compute)


@app.get("/api/cross-correlation")
async def get_cross_correlation(period: str = "1y"):
    """20-asset correlation matrix with Nifty50 as base"""
    loop = asyncio.get_event_loop()

    def compute():
        sess = YFData._get_session()
        return _macro.compute_correlation_matrix(sess, period)

    return await loop.run_in_executor(None, compute)


@app.get("/api/macro-regime")
async def get_macro_regime():
    """Current global macro regime: RISK-ON / RISK-OFF / NEUTRAL"""
    loop = asyncio.get_event_loop()

    def compute():
        sess = YFData._get_session()
        return _macro.detect_macro_regime(sess)

    return await loop.run_in_executor(None, compute)


@app.get("/api/cross-asset-momentum")
async def get_cross_asset_momentum():
    """Momentum signals across 30 global assets"""
    loop = asyncio.get_event_loop()

    def compute():
        sess = YFData._get_session()
        return _macro.compute_cross_asset_momentum(sess)

    return await loop.run_in_executor(None, compute)


@app.get("/api/india-macro-sensitivity")
async def get_india_macro_sensitivity():
    """How INR and crude movements affect Indian sector stocks"""
    loop = asyncio.get_event_loop()

    def compute():
        sess = YFData._get_session()
        return _macro.compute_india_macro_sensitivity(sess)

    return await loop.run_in_executor(None, compute)


@app.get("/api/shipping")
async def get_shipping():
    """Baltic Dry, container trade proxies, India shipping stocks"""
    loop = asyncio.get_event_loop()

    def compute():
        sess = YFData._get_session()
        return _macro.get_shipping_data(sess)

    return await loop.run_in_executor(None, compute)


@app.get("/api/geopolitical-risk")
async def get_geopolitical_risk():
    """Geopolitical risk dashboard with historical event patterns"""
    return _macro.get_geopolitical_dashboard()


# ══════════════════════════════════════════════════════════════════
# INSTITUTIONAL FLOWS
# ══════════════════════════════════════════════════════════════════

@app.get("/api/fii-dii/daily")
async def get_fii_dii_daily():
    """FII and DII cash market daily flows from NSE"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _inst.get_fii_dii_daily)


@app.get("/api/bulk-deals")
async def get_bulk_deals():
    """NSE bulk deals — transactions ≥ 0.5% of listed shares"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _inst.get_bulk_deals)


@app.get("/api/block-deals")
async def get_block_deals():
    """NSE block deals — large-lot trades in special window"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _inst.get_block_deals)


@app.get("/api/institutional-holdings/{symbol}")
async def get_institutional_holdings(symbol: str):
    """Promoter, institutional holding breakdown + insider trades"""
    loop = asyncio.get_event_loop()

    def compute():
        return _inst.get_promoter_changes(symbol, YFData._get_session())

    return await loop.run_in_executor(None, compute)


@app.get("/api/mf-intelligence/{symbol}")
async def get_mf_intelligence(symbol: str):
    """Which major mutual funds hold this stock"""
    return _inst.get_mf_intelligence(symbol)


@app.get("/api/fii-sector-flow")
async def get_fii_sector_flow():
    """FII sector flow proxy via 3M price performance of sector leaders"""
    loop = asyncio.get_event_loop()

    def compute():
        return _inst.estimate_fii_sector_flow(YFData._get_session())

    return await loop.run_in_executor(None, compute)


@app.get("/api/oi-buildup/{symbol}")
async def get_oi_buildup(symbol: str):
    """F&O open interest buildup and PCR from NSE"""
    loop = asyncio.get_event_loop()

    def compute():
        return _inst.get_oi_buildup(symbol)

    return await loop.run_in_executor(None, compute)


@app.get("/api/corporate-actions/{symbol}")
async def get_corporate_actions(symbol: str):
    """Corporate announcements, dividends, board meetings"""
    loop = asyncio.get_event_loop()

    def compute():
        return _inst.get_corporate_actions(symbol)

    return await loop.run_in_executor(None, compute)


# ══════════════════════════════════════════════════════════════════
# QUANT MODELS
# ══════════════════════════════════════════════════════════════════

@app.get("/api/market-regime/{symbol}")
async def get_market_regime(symbol: str, period: str = "1y"):
    """Markov chain market regime detection: BULL / SIDEWAYS / BEAR"""
    loop = asyncio.get_event_loop()

    def compute():
        ns_sym = YFData.yf_sym(symbol)
        # Always use 1y (daily bars) — "2y" maps to weekly bars which break the 5-day rolling window
        safe_period = period if period in ("1mo", "3mo", "6mo", "1y") else "1y"
        data = YFData.history(ns_sym, safe_period)
        if not data:
            raise HTTPException(status_code=404, detail="No data")
        closes = [d["close"] for d in data if d.get("close")]
        if len(closes) < 60:
            raise HTTPException(status_code=422, detail="Insufficient history")
        return _qm.run_markov_regime(closes, symbol)

    return await loop.run_in_executor(None, compute)


@app.get("/api/volatility-regime/{symbol}")
async def get_volatility_regime(symbol: str, period: str = "1y"):
    """GARCH-proxy volatility regime: LOW / NORMAL / HIGH / CRISIS"""
    loop = asyncio.get_event_loop()

    def compute():
        ns_sym = YFData.yf_sym(symbol)
        # Use 1y daily bars — weekly bars would distort GARCH estimation
        safe_period = period if period in ("1mo", "3mo", "6mo", "1y") else "1y"
        data = YFData.history(ns_sym, safe_period)
        if not data:
            raise HTTPException(status_code=404, detail="No data")
        closes = np.array([d["close"] for d in data if d.get("close")], dtype=float)
        if len(closes) < 30:
            raise HTTPException(status_code=422, detail="Insufficient history")
        returns = np.diff(closes) / closes[:-1]
        regime = _qm.estimate_volatility_regime(returns)
        regime["symbol"] = symbol
        return regime

    return await loop.run_in_executor(None, compute)


@app.get("/api/factor-model/{symbol}")
async def get_factor_model(symbol: str):
    """6-factor model score: momentum, value, quality, low-vol, size"""
    loop = asyncio.get_event_loop()

    def compute():
        ns_sym = YFData.yf_sym(symbol)
        # Fetch fundamentals
        fund = YFData.fundamentals(ns_sym) or {}
        # Use 1y (daily bars) — "2y" maps to weekly which breaks index lookbacks
        hist = YFData.history(ns_sym, "1y")
        closes = [d["close"] for d in hist if d.get("close")] if hist else []

        ret_1m = ret_3m = ret_6m = ret_12m = daily_vol = None
        if closes and len(closes) >= 22:
            closes_arr = np.array(closes, dtype=float)
            ret_1m  = (closes_arr[-1] / closes_arr[-22] - 1) * 100  if len(closes_arr) >= 22  else None
            ret_3m  = (closes_arr[-1] / closes_arr[-63] - 1) * 100  if len(closes_arr) >= 63  else None
            ret_6m  = (closes_arr[-1] / closes_arr[-126] - 1) * 100 if len(closes_arr) >= 126 else None
            ret_12m = (closes_arr[-1] / closes_arr[-252] - 1) * 100 if len(closes_arr) >= 252 else None
            rets = np.diff(closes_arr) / closes_arr[:-1]
            daily_vol = float(np.std(rets[-63:])) * 100 if len(rets) >= 63 else None

        return _qm.score_factor_model(
            symbol=symbol,
            ret_1m=float(ret_1m) if ret_1m is not None else None,
            ret_3m=float(ret_3m) if ret_3m is not None else None,
            ret_12m=float(ret_12m) if ret_12m is not None else None,
            pe_ratio=fund.get("pe_ratio"),
            roe=fund.get("roe"),
            debt_equity=fund.get("debt_equity"),
            daily_vol_pct=daily_vol,
            market_cap=fund.get("market_cap"),
        )

    return await loop.run_in_executor(None, compute)


@app.get("/api/arbitrage-scan")
async def get_arbitrage_scan():
    """Cross-asset arbitrage scanner — price dislocation z-scores"""
    loop = asyncio.get_event_loop()

    def compute():
        # Fetch histories for all pairs
        all_tickers = set()
        for _, sym1, sym2, _ in _qm.ARBI_PAIRS:
            all_tickers.add(sym1)
            all_tickers.add(sym2)

        histories: dict = {}
        for ticker in all_tickers:
            if ticker.startswith("nifty_"):
                continue
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
                r = YFData._get_session().get(url, params={"interval": "1d", "range": "1y"}, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    res = (data.get("chart", {}).get("result") or [None])[0]
                    if res:
                        closes = res.get("indicators", {}).get("quote", [{}])[0].get("close", [])
                        closes = [c for c in closes if c is not None]
                        if len(closes) >= 30:
                            histories[ticker] = closes
            except Exception:
                pass

        return _qm.scan_arbitrage(histories)

    return await loop.run_in_executor(None, compute)


@app.get("/api/kelly/{symbol}")
async def get_kelly_criterion(symbol: str):
    """Kelly criterion position sizing from historical trade returns"""
    loop = asyncio.get_event_loop()

    def compute():
        ns_sym = YFData.yf_sym(symbol)
        hist = YFData.history(ns_sym, period="3y")
        if not hist:
            raise HTTPException(status_code=404, detail="No data")
        closes = [d["close"] for d in hist if d.get("close")]
        if len(closes) < 60:
            raise HTTPException(status_code=422, detail="Insufficient history")

        closes_arr = np.array(closes, dtype=float)
        # Weekly returns as "trade" returns
        weekly_rets = [(closes_arr[i * 5] / closes_arr[max(0, i * 5 - 5)] - 1) * 100
                       for i in range(1, len(closes_arr) // 5)]

        kelly = _qm.compute_kelly_from_history(weekly_rets)
        kelly["symbol"] = symbol
        kelly["returns_distribution"] = {
            "mean_pct": round(float(np.mean(weekly_rets)), 3),
            "std_pct": round(float(np.std(weekly_rets)), 3),
            "skew": round(float(np.mean([(r - np.mean(weekly_rets))**3 for r in weekly_rets]) / np.std(weekly_rets)**3), 3) if len(weekly_rets) > 5 else None,
            "n_observations": len(weekly_rets),
        }
        return kelly

    return await loop.run_in_executor(None, compute)


@app.get("/api/mean-reversion/{symbol}")
async def get_mean_reversion(symbol: str):
    """Z-score, Bollinger bands, mean-reversion signals"""
    loop = asyncio.get_event_loop()

    def compute():
        ns_sym = YFData.yf_sym(symbol)
        hist = YFData.history(ns_sym, period="1y")
        if not hist:
            raise HTTPException(status_code=404, detail="No data")
        closes = [d["close"] for d in hist if d.get("close")]
        return _qm.compute_mean_reversion_signals(closes, symbol)

    return await loop.run_in_executor(None, compute)


@app.get("/api/adaptive-strategy/{symbol}")
async def get_adaptive_strategy(symbol: str):
    """Detect if momentum or mean-reversion is working via variance ratio test"""
    loop = asyncio.get_event_loop()

    def compute():
        ns_sym = YFData.yf_sym(symbol)
        hist = YFData.history(ns_sym, period="1y")
        if not hist:
            raise HTTPException(status_code=404, detail="No data")
        closes = np.array([d["close"] for d in hist if d.get("close")], dtype=float)
        if len(closes) < 60:
            raise HTTPException(status_code=422, detail="Insufficient history")
        returns = np.diff(closes) / closes[:-1]
        result = _qm.compute_adaptive_strategy(returns)
        result["symbol"] = symbol
        return result

    return await loop.run_in_executor(None, compute)


@app.get("/api/repeating-patterns")
async def get_repeating_patterns():
    """Historical repeating patterns with current activation status"""
    from datetime import datetime
    current_month = datetime.now().month

    # Get macro data for context
    loop = asyncio.get_event_loop()

    def compute():
        regime_data = _macro.detect_macro_regime(YFData._get_session())
        macro_regime = regime_data.get("regime", "NEUTRAL")
        fii_data = _inst.get_fii_dii_daily()
        fii_sentiment = fii_data.get("stats", {}).get("fii_sentiment", "Neutral")

        active = _rec.get_current_patterns(current_month, macro_regime, fii_sentiment)
        return {
            "all_patterns": _rec.REPEATING_PATTERNS,
            "currently_active": active,
            "current_month": current_month,
            "macro_regime": macro_regime,
            "fii_sentiment": fii_sentiment,
            "computed_at": datetime.now().isoformat(),
        }

    return await loop.run_in_executor(None, compute)


# ══════════════════════════════════════════════════════════════════
# RECOMMENDATION ENGINE
# ══════════════════════════════════════════════════════════════════

@app.get("/api/recommend/{symbol}")
async def get_recommendation(symbol: str):
    """Full buy/sell recommendation with 6-pillar scoring and reasoning"""
    loop = asyncio.get_event_loop()

    def compute():
        ns_sym = YFData.yf_sym(symbol)

        # Fetch all needed data; use "1y" (daily bars) — "2y" maps to weekly data
        fund = YFData.fundamentals(ns_sym) or {}
        hist = YFData.history(ns_sym, "1y") or []
        live = YFData.live_price(ns_sym) or {}

        closes = [d["close"] for d in hist if d.get("close")]
        volumes = [d["volume"] for d in hist if d.get("volume")]
        closes_arr = np.array(closes, dtype=float) if closes else np.array([])

        # Compute technical indicators
        price = live.get("price", fund.get("price", 0))
        sma20 = sma50 = sma200 = None
        rsi_val = None
        macd_val = macd_sig = None
        vol_ratio = None
        ret_1m = ret_3m = ret_6m = ret_12m = None
        max_dd = sharpe_1y = None

        if len(closes_arr) >= 20:
            sma20 = float(np.mean(closes_arr[-20:]))
        if len(closes_arr) >= 50:
            sma50 = float(np.mean(closes_arr[-50:]))
        if len(closes_arr) >= 200:
            sma200 = float(np.mean(closes_arr[-200:]))

        if len(closes_arr) >= 22:
            ret_1m  = float((closes_arr[-1] / closes_arr[-22] - 1) * 100)
        if len(closes_arr) >= 63:
            ret_3m  = float((closes_arr[-1] / closes_arr[-63] - 1) * 100)
        if len(closes_arr) >= 126:
            ret_6m  = float((closes_arr[-1] / closes_arr[-126] - 1) * 100)
        if len(closes_arr) >= 252:
            ret_12m = float((closes_arr[-1] / closes_arr[-252] - 1) * 100)

        if len(closes_arr) >= 15:
            rets = np.diff(closes_arr) / closes_arr[:-1]
            # RSI
            up = rets.copy(); up[up < 0] = 0
            dn = (-rets).copy(); dn[dn < 0] = 0
            avg_up = np.mean(up[-14:])
            avg_dn = np.mean(dn[-14:])
            rsi_val = float(100 - 100 / (1 + avg_up / avg_dn)) if avg_dn > 0 else 100.0

            # MACD
            if len(closes_arr) >= 26:
                ema12 = float(pd.Series(closes_arr).ewm(span=12).mean().iloc[-1])
                ema26 = float(pd.Series(closes_arr).ewm(span=26).mean().iloc[-1])
                macd_val = ema12 - ema26
                macd_line = pd.Series(closes_arr).ewm(span=12).mean() - pd.Series(closes_arr).ewm(span=26).mean()
                macd_sig = float(macd_line.ewm(span=9).mean().iloc[-1])

            # Volume ratio
            if len(volumes) >= 20:
                vol_arr = np.array(volumes, dtype=float)
                avg_vol = float(np.mean(vol_arr[-20:]))
                vol_ratio = float(vol_arr[-1] / avg_vol) if avg_vol > 0 else None

            # Sharpe 1Y
            if len(rets) >= 252:
                ret_252 = rets[-252:]
                ann_ret = float(np.mean(ret_252)) * 252
                ann_vol = float(np.std(ret_252)) * np.sqrt(252)
                sharpe_1y = (ann_ret - 0.07) / ann_vol if ann_vol > 0 else None

            # Max drawdown
            cum = np.cumprod(1 + rets[-252:]) if len(rets) >= 252 else np.cumprod(1 + rets)
            peak = np.maximum.accumulate(cum)
            dd = (cum - peak) / peak
            max_dd = float(np.min(dd)) * 100

        # Distance from 52W highs/lows
        if len(closes_arr) >= 252:
            high_52w = float(np.max(closes_arr[-252:]))
            low_52w  = float(np.min(closes_arr[-252:]))
            dist_52wh = float((closes_arr[-1] / high_52w - 1) * 100)
            dist_52wl = float((closes_arr[-1] / low_52w - 1) * 100)
        else:
            dist_52wh = dist_52wl = None

        # Get macro context
        try:
            macro_regime_data = _macro.detect_macro_regime(YFData._get_session())
            macro_regime = macro_regime_data.get("regime", "NEUTRAL")
        except Exception:
            macro_regime = "NEUTRAL"

        try:
            fii_data = _inst.get_fii_dii_daily()
            fii_sentiment = fii_data.get("stats", {}).get("fii_sentiment", "Neutral")
        except Exception:
            fii_sentiment = "Neutral"

        # MF intelligence
        mf_intel = _inst.get_mf_intelligence(symbol)
        mf_count = mf_intel.get("mf_count", 0)

        # Build data package for scorer
        scoring_data = {
            "symbol": symbol,
            "price": price,
            "change_pct": live.get("change_pct", 0),
            # Technical
            "rsi_14": rsi_val,
            "sma_20": sma20,
            "sma_50": sma50,
            "sma_200": sma200,
            "macd": macd_val,
            "macd_signal": macd_sig,
            "volume_ratio": vol_ratio,
            # Fundamental
            "pe_ratio": fund.get("pe_ratio"),
            "roe": (fund.get("roe") or 0) * 100 if fund.get("roe") else None,
            "roce": None,  # not in fundamentals; would need earnings endpoint
            "revenue_growth": fund.get("revenue_growth"),
            "debt_equity": fund.get("debt_equity"),
            "operating_margin": fund.get("operating_margin"),
            "net_margin": fund.get("net_margin"),
            "sector": fund.get("sector", ""),
            # Momentum
            "ret_1m": ret_1m,
            "ret_3m": ret_3m,
            "ret_6m": ret_6m,
            "ret_12m": ret_12m,
            "dist_from_52wh_pct": dist_52wh,
            "dist_from_52wl_pct": dist_52wl,
            # Risk
            "max_drawdown_pct": max_dd,
            "sharpe_1y": sharpe_1y,
            "avg_volume": float(np.mean(volumes[-20:])) if len(volumes) >= 20 else None,
            # Macro
            "macro_regime": macro_regime,
            "fii_sentiment": fii_sentiment,
            # Quality
            "mf_count": mf_count,
            "current_ratio": fund.get("current_ratio"),
        }

        return _rec.generate_recommendation(symbol, scoring_data)

    return await loop.run_in_executor(None, compute)


@app.get("/api/recommendations")
async def get_all_recommendations(limit: int = 50):
    """Ranked recommendations for all Nifty50 stocks"""
    loop = asyncio.get_event_loop()

    def compute():
        # Get macro context once
        try:
            macro_regime = _macro.detect_macro_regime(YFData._get_session()).get("regime", "NEUTRAL")
        except Exception:
            macro_regime = "NEUTRAL"

        try:
            fii_sentiment = _inst.get_fii_dii_daily().get("stats", {}).get("fii_sentiment", "Neutral")
        except Exception:
            fii_sentiment = "Neutral"

        stock_list = []
        symbols_to_use = NIFTY50_SYMBOLS[:min(limit, 50)]

        for symbol in symbols_to_use:
            try:
                ns_sym = YFData.yf_sym(symbol)
                fund = YFData.fundamentals(ns_sym) or {}
                # Use _price_snapshot for live price (already cached by SSE loop)
                snap = _price_snapshot.get(symbol, {})
                price = snap.get("price", 0) or fund.get("regularMarketPrice", 0)
                change_pct = snap.get("change_pct", 0)
                # Use cached history (TTL=300s shared with rest of app)
                hist = YFData.history(ns_sym, "1y") or []
                closes = [d["close"] for d in hist if d.get("close")]
                closes_arr = np.array(closes, dtype=float) if closes else np.array([])

                ret_1m = ret_3m = ret_12m = None
                if len(closes_arr) >= 22:
                    ret_1m  = float((closes_arr[-1] / closes_arr[-22] - 1) * 100)
                if len(closes_arr) >= 63:
                    ret_3m  = float((closes_arr[-1] / closes_arr[-63] - 1) * 100)
                if len(closes_arr) >= 252:
                    ret_12m = float((closes_arr[-1] / closes_arr[-252] - 1) * 100)

                roe_raw = fund.get("roe")
                stock_list.append({
                    "symbol": symbol,
                    "price": price,
                    "change_pct": change_pct,
                    "pe_ratio": fund.get("pe_ratio"),
                    "roe": float(roe_raw) * 100 if roe_raw else None,
                    "revenue_growth": fund.get("revenue_growth"),
                    "debt_equity": fund.get("debt_equity"),
                    "net_margin": fund.get("net_margin"),
                    "operating_margin": fund.get("operating_margin"),
                    "sector": fund.get("sector", ""),
                    "ret_1m": ret_1m,
                    "ret_3m": ret_3m,
                    "ret_12m": ret_12m,
                    "macro_regime": macro_regime,
                    "fii_sentiment": fii_sentiment,
                    "mf_count": _inst.get_mf_intelligence(symbol).get("mf_count", 0),
                })
            except Exception as e:
                logger.debug(f"rec {symbol}: {e}")

        ranked = _rec.rank_universe(stock_list)
        sector_rotation = _rec.get_sector_rotation_signal(
            macro_regime=macro_regime,
            rate_trend="STABLE",
            crude_trend="STABLE",
            inr_trend="STABLE",
        )
        return {
            "ranked": ranked,
            "sector_rotation": sector_rotation,
            "total": len(ranked),
            "computed_at": datetime.now().isoformat(),
        }

    return await loop.run_in_executor(None, compute)


@app.get("/api/sector-rotation")
async def get_sector_rotation():
    """Sector rotation model based on macro conditions"""
    loop = asyncio.get_event_loop()

    def compute():
        try:
            regime = _macro.detect_macro_regime(YFData._get_session())
            macro_regime = regime.get("regime", "NEUTRAL")
            crude_trend = "UP" if (regime.get("signals", {}).get("crude_3m", 0) or 0) > 10 else "DOWN" if (regime.get("signals", {}).get("crude_3m", 0) or 0) < -10 else "STABLE"
            dxy = regime.get("signals", {}).get("dxy_3m", 0) or 0
            inr_trend = "WEAKENING" if dxy > 3 else "STRENGTHENING" if dxy < -3 else "STABLE"
        except Exception:
            macro_regime, crude_trend, inr_trend = "NEUTRAL", "STABLE", "STABLE"

        return _rec.get_sector_rotation_signal(macro_regime, "STABLE", crude_trend, inr_trend)

    return await loop.run_in_executor(None, compute)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
