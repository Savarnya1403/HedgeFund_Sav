"""
Advanced Multi-Factor Screener Engine for IndiaHedge Terminal
Implements: Quality, Value, Growth, GARP, Insider Activity,
            Earnings Momentum, Technical-Fundamental combo screens
"""

from __future__ import annotations
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
import warnings

import numpy as np
import pandas as pd
import yfinance as yf
import requests

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# UNIVERSE CONSTANTS (mirrors main.py)
# ────────────────────────────────────────────────────────────────────────────

NIFTY50 = [
    "RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","HINDUNILVR","BAJFINANCE",
    "BHARTIARTL","SBIN","KOTAKBANK","ITC","LT","AXISBANK","TITAN","ASIANPAINT",
    "MARUTI","ULTRACEMCO","WIPRO","HCLTECH","NESTLEIND","ADANIENT","ADANIPORTS",
    "POWERGRID","NTPC","ONGC","COALINDIA","GRASIM","BAJAJFINSV","TATASTEEL",
    "JSWSTEEL","HDFCLIFE","SBILIFE","DIVISLAB","CIPLA","DRREDDY","SUNPHARMA",
    "TECHM","INDUSINDBK","BPCL","EICHERMOT","BRITANNIA","HINDALCO","TATAMOTORS",
    "APOLLOHOSP","HEROMOTOCO","MM","SHREECEM","TATACONSUM","PIDILITIND","LTIM",
]

NIFTY_NEXT50 = [
    "DMART","SIEMENS","HAVELLS","DABUR","MARICO","COLPAL","GODREJCP","BERGEPAINT",
    "KANSAINER","PAGEIND","BOSCHLTD","MUTHOOTFIN","CHOLAFIN","DLF","ZOMATO",
    "TVSMOTOR","VEDL","SAIL","OFSS","BANKBARODA","GAIL","IOC","HPCL","PFC",
    "RECLTD","NHPC","IRCTC","AMBUJACEM","ACC","VOLTAS","NAUKRI","ZYDUSLIFE",
    "LUPIN","MANKIND","UBL","TATACHEM","JSWENERGY","INDHOTEL","HDFCAMC",
    "ICICIPRULI","NMDC","BHEL","BEL","HAL","PIIND","INDIGO","BAJAJ-AUTO",
    "LODHA","BAJAJHFL","POLICYBZR",
]

PSU_SYMBOLS = [
    "PNB","CANBK","UNIONBANK","BANKINDIA","IOB","CENTRALBK","OIL","PETRONET",
    "SJVN","RVNL","IRFC","BEML","GRSE","COCHINSHIP","MAZAGON","MIDHANI",
    "RAILTEL","NBCC","HUDCO","CONCOR","NALCO","MOIL",
]

YF_OVERRIDES = {"MM": "M%26M.NS", "BAJAJ-AUTO": "BAJAJ-AUTO.NS"}

SECTOR_MAP: Dict[str, str] = {
    "RELIANCE": "Energy", "ONGC": "Energy", "BPCL": "Energy", "IOC": "Energy",
    "HPCL": "Energy", "OIL": "Energy", "PETRONET": "Energy", "GAIL": "Energy",
    "TCS": "IT", "INFY": "IT", "WIPRO": "IT", "HCLTECH": "IT", "TECHM": "IT",
    "LTIM": "IT", "OFSS": "IT",
    "HDFCBANK": "Banking", "ICICIBANK": "Banking", "SBIN": "Banking",
    "KOTAKBANK": "Banking", "AXISBANK": "Banking", "INDUSINDBK": "Banking",
    "BAJFINANCE": "NBFC", "BAJAJFINSV": "NBFC", "MUTHOOTFIN": "NBFC",
    "CHOLAFIN": "NBFC", "HDFCAMC": "AMC", "HDFCLIFE": "Insurance",
    "SBILIFE": "Insurance", "ICICIPRULI": "Insurance",
    "SUNPHARMA": "Pharma", "DRREDDY": "Pharma", "CIPLA": "Pharma",
    "DIVISLAB": "Pharma", "LUPIN": "Pharma", "ZYDUSLIFE": "Pharma", "MANKIND": "Pharma",
    "HINDUNILVR": "FMCG", "ITC": "FMCG", "NESTLEIND": "FMCG", "BRITANNIA": "FMCG",
    "DABUR": "FMCG", "MARICO": "FMCG", "COLPAL": "FMCG", "GODREJCP": "FMCG",
    "TATACONSUM": "FMCG", "UBL": "FMCG",
    "MARUTI": "Auto", "TATAMOTORS": "Auto", "EICHERMOT": "Auto", "HEROMOTOCO": "Auto",
    "MM": "Auto", "TVSMOTOR": "Auto", "BAJAJ-AUTO": "Auto",
    "LT": "Capital Goods", "SIEMENS": "Capital Goods", "BHEL": "Capital Goods",
    "BEL": "Defence", "HAL": "Defence", "BEML": "Defence", "MAZAGON": "Defence",
    "GRSE": "Defence", "MIDHANI": "Defence",
    "TATASTEEL": "Metals", "JSWSTEEL": "Metals", "HINDALCO": "Metals",
    "SAIL": "Metals", "VEDL": "Metals", "NALCO": "Metals", "MOIL": "Metals",
    "ADANIENT": "Conglomerate", "ADANIPORTS": "Infrastructure",
    "POWERGRID": "Power", "NTPC": "Power", "SJVN": "Power", "JSWENERGY": "Power",
    "NHPC": "Power", "RVNL": "Infrastructure", "IRFC": "Finance",
    "COALINDIA": "Mining", "NMDC": "Mining",
    "ASIANPAINT": "Paints", "BERGEPAINT": "Paints", "KANSAINER": "Paints",
    "PIDILITIND": "Chemicals", "PIIND": "Agrochem",
    "ULTRACEMCO": "Cement", "AMBUJACEM": "Cement", "ACC": "Cement", "SHREECEM": "Cement",
    "TITAN": "Consumer", "HAVELLS": "Consumer", "VOLTAS": "Consumer",
    "DMART": "Retail", "ZOMATO": "Tech", "NAUKRI": "Tech",
    "APOLLOHOSP": "Healthcare", "INDHOTEL": "Hotels",
    "INDIGO": "Aviation", "IRCTC": "Railways",
    "CONCOR": "Logistics", "RAILTEL": "Infrastructure",
    "DLF": "Real Estate", "LODHA": "Real Estate", "HUDCO": "Finance",
    "NBCC": "Real Estate", "GRASIM": "Diversified",
    "PFC": "Finance", "RECLTD": "Finance", "BAJAJHFL": "Finance",
    "POLICYBZR": "Insurtech", "PNB": "PSU Bank", "CANBK": "PSU Bank",
    "UNIONBANK": "PSU Bank", "BANKINDIA": "PSU Bank", "IOB": "PSU Bank",
    "CENTRALBK": "PSU Bank", "BANKBARODA": "PSU Bank",
    "TATACHEM": "Chemicals", "PAGEIND": "Consumer", "BOSCHLTD": "Auto Ancillary",
    "COCHINSHIP": "Defence", "TATAMOTORS": "Auto",
}

# ────────────────────────────────────────────────────────────────────────────
# DATA FETCHER
# ────────────────────────────────────────────────────────────────────────────

class StockDataFetcher:
    """Fetch OHLCV + fundamentals for a symbol via yfinance"""

    _cache: Dict[str, Any] = {}
    _cache_ts: Dict[str, float] = {}
    CACHE_TTL = 300

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
    def get_price_data(cls, symbol: str, period: str = "1y") -> Optional[pd.DataFrame]:
        key = f"price_{symbol}_{period}"
        cached = cls._cached(key)
        if cached is not None:
            return cached
        try:
            ticker = yf.Ticker(cls.yf_sym(symbol))
            df = ticker.history(period=period, auto_adjust=True)
            if df.empty:
                return None
            cls._store(key, df)
            return df
        except Exception as e:
            logger.debug(f"price fetch {symbol}: {e}")
            return None

    @classmethod
    def get_fundamentals(cls, symbol: str) -> Dict[str, Any]:
        key = f"fund_{symbol}"
        cached = cls._cached(key)
        if cached is not None:
            return cached
        try:
            ticker = yf.Ticker(cls.yf_sym(symbol))
            info = ticker.info or {}
            result = {
                "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
                "forward_pe": info.get("forwardPE"),
                "pb_ratio": info.get("priceToBook"),
                "ps_ratio": info.get("priceToSalesTrailingTwelveMonths"),
                "ev_ebitda": info.get("enterpriseToEbitda"),
                "roe": (info.get("returnOnEquity") or 0) * 100,
                "roa": (info.get("returnOnAssets") or 0) * 100,
                "revenue_growth": (info.get("revenueGrowth") or 0) * 100,
                "earnings_growth": (info.get("earningsGrowth") or 0) * 100,
                "net_margin": (info.get("profitMargins") or 0) * 100,
                "operating_margin": (info.get("operatingMargins") or 0) * 100,
                "gross_margin": (info.get("grossMargins") or 0) * 100,
                "debt_equity": info.get("debtToEquity"),
                "current_ratio": info.get("currentRatio"),
                "quick_ratio": info.get("quickRatio"),
                "market_cap": info.get("marketCap"),
                "enterprise_value": info.get("enterpriseValue"),
                "dividend_yield": (info.get("dividendYield") or 0) * 100,
                "payout_ratio": (info.get("payoutRatio") or 0) * 100,
                "beta": info.get("beta"),
                "sector": info.get("sector", SECTOR_MAP.get(symbol, "Unknown")),
                "fcf": info.get("freeCashflow"),
                "revenue": info.get("totalRevenue"),
                "ebitda": info.get("ebitda"),
                "shares_outstanding": info.get("sharesOutstanding"),
                "float_shares": info.get("floatShares"),
                "held_pct_institutions": (info.get("heldPercentInstitutions") or 0) * 100,
                "short_ratio": info.get("shortRatio"),
                "52w_high": info.get("fiftyTwoWeekHigh"),
                "52w_low": info.get("fiftyTwoWeekLow"),
                "analyst_target": info.get("targetMeanPrice"),
                "analyst_rating": info.get("recommendationKey"),
                "num_analysts": info.get("numberOfAnalystOpinions"),
                "eps_ttm": info.get("trailingEps"),
                "eps_fwd": info.get("forwardEps"),
                "book_value": info.get("bookValue"),
                "revenue_per_share": info.get("revenuePerShare"),
            }
            cls._store(key, result)
            return result
        except Exception as e:
            logger.debug(f"fund fetch {symbol}: {e}")
            return {}

    @classmethod
    def compute_technicals(cls, df: pd.DataFrame) -> Dict[str, Any]:
        if df is None or len(df) < 20:
            return {}
        closes = df["Close"].values
        highs = df["High"].values
        lows = df["Low"].values
        volumes = df["Volume"].values

        # RSI
        def _rsi(arr: np.ndarray, n: int = 14) -> float:
            if len(arr) < n + 1:
                return 50.0
            delta = np.diff(arr)
            gain = np.where(delta > 0, delta, 0.0)
            loss = np.where(delta < 0, -delta, 0.0)
            avg_gain = np.mean(gain[-n:])
            avg_loss = np.mean(loss[-n:])
            if avg_loss == 0:
                return 100.0
            rs = avg_gain / avg_loss
            return 100.0 - 100.0 / (1.0 + rs)

        # SMA
        def _sma(arr: np.ndarray, n: int) -> Optional[float]:
            return float(np.mean(arr[-n:])) if len(arr) >= n else None

        # EMA
        def _ema(arr: np.ndarray, n: int) -> Optional[float]:
            if len(arr) < n:
                return None
            k = 2.0 / (n + 1)
            ema = arr[0]
            for x in arr[1:]:
                ema = x * k + ema * (1 - k)
            return float(ema)

        # ATR
        def _atr(h, l, c, n=14) -> float:
            if len(h) < n + 1:
                return 0.0
            tr = np.maximum(h[1:] - l[1:],
                   np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
            return float(np.mean(tr[-n:]))

        rsi = _rsi(closes)
        sma20 = _sma(closes, 20)
        sma50 = _sma(closes, 50)
        sma200 = _sma(closes, 200)
        ema20 = _ema(closes, 20)
        price = float(closes[-1])

        # MACD
        ema12 = _ema(closes, 12)
        ema26 = _ema(closes, 26)
        macd = (ema12 - ema26) if (ema12 and ema26) else 0

        # Bollinger Bands
        if sma20:
            bb_std = float(np.std(closes[-20:]))
            bb_upper = sma20 + 2 * bb_std
            bb_lower = sma20 - 2 * bb_std
            bb_pct = (price - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5
        else:
            bb_upper = bb_lower = bb_pct = None

        # Volume analysis
        avg_vol_20 = float(np.mean(volumes[-20:])) if len(volumes) >= 20 else 0
        vol_ratio = float(volumes[-1]) / avg_vol_20 if avg_vol_20 > 0 else 1.0

        # Returns
        returns = np.diff(closes) / closes[:-1]
        ret_1m = float((closes[-1] / closes[-22] - 1) * 100) if len(closes) >= 22 else None
        ret_3m = float((closes[-1] / closes[-63] - 1) * 100) if len(closes) >= 63 else None
        ret_6m = float((closes[-1] / closes[-126] - 1) * 100) if len(closes) >= 126 else None
        ret_12m = float((closes[-1] / closes[-252] - 1) * 100) if len(closes) >= 252 else None

        # Volatility
        ann_vol = float(np.std(returns[-252:]) * np.sqrt(252) * 100) if len(returns) >= 252 else float(np.std(returns) * np.sqrt(252) * 100)

        # 52W data
        high_52w = float(np.max(closes[-252:])) if len(closes) >= 252 else float(np.max(closes))
        low_52w = float(np.min(closes[-252:])) if len(closes) >= 252 else float(np.min(closes))
        dist_52wh = (price / high_52w - 1) * 100
        dist_52wl = (price / low_52w - 1) * 100

        # Trend
        trend = "UPTREND"
        if sma50 and sma200:
            if price < sma200:
                trend = "DOWNTREND"
            elif price < sma50:
                trend = "MIXED"

        # ATR
        atr = _atr(highs, lows, closes)
        atr_pct = (atr / price * 100) if price > 0 else 0

        # Max drawdown
        cum = np.cumprod(1 + returns[-252:]) if len(returns) >= 252 else np.cumprod(1 + returns)
        peak = np.maximum.accumulate(cum)
        dd = (cum - peak) / peak
        max_dd = float(np.min(dd) * 100)

        # Sharpe
        if len(returns) >= 252:
            ann_ret = float(np.mean(returns[-252:])) * 252
            ann_vol_d = float(np.std(returns[-252:])) * np.sqrt(252)
            sharpe = (ann_ret - 0.065) / ann_vol_d if ann_vol_d > 0 else 0
        else:
            sharpe = None

        return {
            "price": price,
            "rsi": rsi,
            "macd": macd,
            "sma20": sma20,
            "sma50": sma50,
            "sma200": sma200,
            "ema20": ema20,
            "bb_upper": bb_upper,
            "bb_lower": bb_lower,
            "bb_pct": bb_pct,
            "vol_ratio": vol_ratio,
            "avg_volume": avg_vol_20,
            "atr": atr,
            "atr_pct": atr_pct,
            "ret_1m": ret_1m,
            "ret_3m": ret_3m,
            "ret_6m": ret_6m,
            "ret_12m": ret_12m,
            "ann_vol": ann_vol,
            "max_drawdown": max_dd,
            "sharpe": sharpe,
            "high_52w": high_52w,
            "low_52w": low_52w,
            "dist_52wh": dist_52wh,
            "dist_52wl": dist_52wl,
            "trend": trend,
        }


# ────────────────────────────────────────────────────────────────────────────
# SCREENER CRITERIA
# ────────────────────────────────────────────────────────────────────────────

class QualityGrowthScreener:
    """GARP: Growth at a Reasonable Price"""

    @staticmethod
    def screen(symbols: List[str], limit: int = 20) -> List[Dict]:
        results = []
        for sym in symbols:
            try:
                df = StockDataFetcher.get_price_data(sym, "1y")
                fund = StockDataFetcher.get_fundamentals(sym)
                ta = StockDataFetcher.compute_technicals(df)
                if not fund or not ta:
                    continue

                pe = fund.get("pe_ratio") or 0
                fwd_pe = fund.get("forward_pe") or pe
                roe = fund.get("roe") or 0
                revenue_growth = fund.get("revenue_growth") or 0
                earnings_growth = fund.get("earnings_growth") or 0
                net_margin = fund.get("net_margin") or 0
                debt_equity = fund.get("debt_equity") or 100

                # PEG ratio (PE / earnings growth)
                peg = pe / earnings_growth if (earnings_growth > 0 and pe > 0) else None

                # Quality filters
                if roe < 12:
                    continue
                if debt_equity > 100:
                    continue
                if net_margin < 8:
                    continue
                if revenue_growth < 8:
                    continue

                # GARP score
                score = 0
                if peg and peg < 1.5:
                    score += 30
                elif peg and peg < 2.5:
                    score += 15
                if roe > 25:
                    score += 25
                elif roe > 18:
                    score += 15
                if revenue_growth > 20:
                    score += 20
                elif revenue_growth > 12:
                    score += 10
                if earnings_growth > 20:
                    score += 15
                elif earnings_growth > 10:
                    score += 8
                if net_margin > 20:
                    score += 10
                elif net_margin > 12:
                    score += 5
                if ta.get("trend") == "UPTREND":
                    score += 10
                if ta.get("rsi", 50) < 65:
                    score += 5

                results.append({
                    "symbol": sym,
                    "sector": SECTOR_MAP.get(sym, fund.get("sector", "Unknown")),
                    "price": ta.get("price"),
                    "pe": round(pe, 1) if pe else None,
                    "fwd_pe": round(fwd_pe, 1) if fwd_pe else None,
                    "peg": round(peg, 2) if peg else None,
                    "roe": round(roe, 1),
                    "revenue_growth": round(revenue_growth, 1),
                    "earnings_growth": round(earnings_growth, 1),
                    "net_margin": round(net_margin, 1),
                    "debt_equity": round(debt_equity, 1),
                    "rsi": round(ta.get("rsi", 50), 1),
                    "ret_1m": ta.get("ret_1m"),
                    "ret_3m": ta.get("ret_3m"),
                    "score": score,
                    "screen": "GARP",
                })
            except Exception as e:
                logger.debug(f"GARP {sym}: {e}")
        return sorted(results, key=lambda x: x["score"], reverse=True)[:limit]


class DeepValueScreener:
    """Graham-style deep value with modern adjustments"""

    @staticmethod
    def screen(symbols: List[str], limit: int = 20) -> List[Dict]:
        results = []
        for sym in symbols:
            try:
                df = StockDataFetcher.get_price_data(sym, "1y")
                fund = StockDataFetcher.get_fundamentals(sym)
                ta = StockDataFetcher.compute_technicals(df)
                if not fund or not ta:
                    continue

                pe = fund.get("pe_ratio") or 0
                pb = fund.get("pb_ratio") or 0
                ps = fund.get("ps_ratio") or 0
                ev_ebitda = fund.get("ev_ebitda") or 0
                div_yield = fund.get("dividend_yield") or 0
                roe = fund.get("roe") or 0
                current_ratio = fund.get("current_ratio") or 0

                # Graham number screen
                eps = fund.get("eps_ttm") or 0
                bv = fund.get("book_value") or 0
                graham_number = (22.5 * eps * bv) ** 0.5 if (eps > 0 and bv > 0) else None
                graham_pct = ((ta.get("price", 0) / graham_number) - 1) * 100 if graham_number else None

                # Value filters
                if pe <= 0 or pe > 25:
                    continue
                if pb <= 0 or pb > 4:
                    continue
                if current_ratio < 1.0:
                    continue
                if roe < 8:
                    continue

                score = 0
                if pe < 10:
                    score += 35
                elif pe < 15:
                    score += 20
                elif pe < 20:
                    score += 10
                if pb < 1.5:
                    score += 25
                elif pb < 2.5:
                    score += 15
                elif pb < 3.5:
                    score += 5
                if div_yield > 3:
                    score += 20
                elif div_yield > 1.5:
                    score += 10
                if ev_ebitda > 0 and ev_ebitda < 8:
                    score += 15
                elif ev_ebitda > 0 and ev_ebitda < 12:
                    score += 8
                if graham_pct and graham_pct < -20:
                    score += 20  # trading below Graham number
                if current_ratio > 2:
                    score += 5

                results.append({
                    "symbol": sym,
                    "sector": SECTOR_MAP.get(sym, fund.get("sector", "Unknown")),
                    "price": ta.get("price"),
                    "pe": round(pe, 1),
                    "pb": round(pb, 2),
                    "ps": round(ps, 2) if ps else None,
                    "ev_ebitda": round(ev_ebitda, 1) if ev_ebitda else None,
                    "div_yield": round(div_yield, 2),
                    "roe": round(roe, 1),
                    "current_ratio": round(current_ratio, 2),
                    "graham_number": round(graham_number, 2) if graham_number else None,
                    "graham_premium_pct": round(graham_pct, 1) if graham_pct else None,
                    "dist_52wl": ta.get("dist_52wl"),
                    "score": score,
                    "screen": "DEEP_VALUE",
                })
            except Exception as e:
                logger.debug(f"DeepValue {sym}: {e}")
        return sorted(results, key=lambda x: x["score"], reverse=True)[:limit]


class HighQualityCompounders:
    """High ROIC compounders with pricing power"""

    @staticmethod
    def screen(symbols: List[str], limit: int = 20) -> List[Dict]:
        results = []
        for sym in symbols:
            try:
                df = StockDataFetcher.get_price_data(sym, "2y")
                fund = StockDataFetcher.get_fundamentals(sym)
                ta = StockDataFetcher.compute_technicals(df)
                if not fund or not ta:
                    continue

                roe = fund.get("roe") or 0
                roa = fund.get("roa") or 0
                operating_margin = fund.get("operating_margin") or 0
                gross_margin = fund.get("gross_margin") or 0
                revenue_growth = fund.get("revenue_growth") or 0
                debt_equity = fund.get("debt_equity") or 100
                fcf = fund.get("fcf") or 0
                market_cap = fund.get("market_cap") or 0
                fcf_yield = (fcf / market_cap * 100) if (fcf and market_cap) else None

                # Quality filters
                if roe < 20:
                    continue
                if operating_margin < 15:
                    continue
                if debt_equity > 60:
                    continue

                score = 0
                if roe > 35:
                    score += 30
                elif roe > 25:
                    score += 20
                elif roe > 20:
                    score += 10
                if operating_margin > 30:
                    score += 25
                elif operating_margin > 20:
                    score += 15
                elif operating_margin > 15:
                    score += 8
                if gross_margin > 50:
                    score += 20
                elif gross_margin > 35:
                    score += 10
                if revenue_growth > 15:
                    score += 15
                elif revenue_growth > 8:
                    score += 8
                if fcf and fcf > 0:
                    score += 10
                if ta.get("sharpe", 0) and ta["sharpe"] > 1:
                    score += 10
                if ta.get("ret_12m", 0) and ta["ret_12m"] > 15:
                    score += 5

                results.append({
                    "symbol": sym,
                    "sector": SECTOR_MAP.get(sym, fund.get("sector", "Unknown")),
                    "price": ta.get("price"),
                    "roe": round(roe, 1),
                    "roa": round(roa, 1),
                    "operating_margin": round(operating_margin, 1),
                    "gross_margin": round(gross_margin, 1),
                    "revenue_growth": round(revenue_growth, 1),
                    "debt_equity": round(debt_equity, 1),
                    "fcf_yield": round(fcf_yield, 2) if fcf_yield else None,
                    "sharpe_1y": round(ta.get("sharpe", 0), 2) if ta.get("sharpe") else None,
                    "ret_12m": ta.get("ret_12m"),
                    "max_drawdown": ta.get("max_drawdown"),
                    "score": score,
                    "screen": "QUALITY_COMPOUNDER",
                })
            except Exception as e:
                logger.debug(f"Compounder {sym}: {e}")
        return sorted(results, key=lambda x: x["score"], reverse=True)[:limit]


class TurnaroundScreener:
    """Turnaround candidates: improving metrics from depressed levels"""

    @staticmethod
    def screen(symbols: List[str], limit: int = 20) -> List[Dict]:
        results = []
        for sym in symbols:
            try:
                df = StockDataFetcher.get_price_data(sym, "1y")
                fund = StockDataFetcher.get_fundamentals(sym)
                ta = StockDataFetcher.compute_technicals(df)
                if not fund or not ta:
                    continue

                pe = fund.get("pe_ratio") or 0
                forward_pe = fund.get("forward_pe") or pe
                earnings_growth = fund.get("earnings_growth") or 0
                revenue_growth = fund.get("revenue_growth") or 0
                rsi = ta.get("rsi", 50)
                dist_52wl = ta.get("dist_52wl", 0)
                dist_52wh = ta.get("dist_52wh", -100)
                ret_1m = ta.get("ret_1m", 0) or 0
                ret_3m = ta.get("ret_3m", 0) or 0

                # Turnaround: beaten down but earnings improving
                if earnings_growth < 5:
                    continue
                if dist_52wl < 10:  # too close to 52W low, not turned yet
                    continue
                if dist_52wh > -10:  # near 52W high, already played out
                    continue

                # PE compression opportunity
                pe_compression = (pe - forward_pe) if (pe > 0 and forward_pe > 0) else 0

                score = 0
                if earnings_growth > 30:
                    score += 35
                elif earnings_growth > 15:
                    score += 20
                if revenue_growth > 15:
                    score += 20
                elif revenue_growth > 8:
                    score += 10
                if pe_compression > 5:
                    score += 20
                if dist_52wl > 30 and dist_52wl < 80:
                    score += 15  # recovered enough to be safe but still room
                if rsi > 40 and rsi < 60:
                    score += 10  # not overbought
                if ret_1m > 3:
                    score += 10  # recent momentum
                if ret_3m > 0 and ret_3m < 20:
                    score += 5

                results.append({
                    "symbol": sym,
                    "sector": SECTOR_MAP.get(sym, fund.get("sector", "Unknown")),
                    "price": ta.get("price"),
                    "pe": round(pe, 1) if pe else None,
                    "forward_pe": round(forward_pe, 1) if forward_pe else None,
                    "pe_compression_pts": round(pe_compression, 1),
                    "earnings_growth": round(earnings_growth, 1),
                    "revenue_growth": round(revenue_growth, 1),
                    "dist_from_52wl": round(dist_52wl, 1),
                    "dist_from_52wh": round(dist_52wh, 1),
                    "rsi": round(rsi, 1),
                    "ret_1m": round(ret_1m, 1) if ret_1m else None,
                    "ret_3m": round(ret_3m, 1) if ret_3m else None,
                    "score": score,
                    "screen": "TURNAROUND",
                })
            except Exception as e:
                logger.debug(f"Turnaround {sym}: {e}")
        return sorted(results, key=lambda x: x["score"], reverse=True)[:limit]


class LowVolatilityScreener:
    """Low volatility anomaly — low vol stocks historically outperform on risk-adjusted basis"""

    @staticmethod
    def screen(symbols: List[str], limit: int = 20) -> List[Dict]:
        results = []
        for sym in symbols:
            try:
                df = StockDataFetcher.get_price_data(sym, "2y")
                fund = StockDataFetcher.get_fundamentals(sym)
                ta = StockDataFetcher.compute_technicals(df)
                if not fund or not ta:
                    continue

                ann_vol = ta.get("ann_vol", 100)
                max_dd = ta.get("max_drawdown", -100)
                sharpe = ta.get("sharpe")
                beta = fund.get("beta") or 1.0
                div_yield = fund.get("dividend_yield") or 0
                roe = fund.get("roe") or 0

                if ann_vol > 30:
                    continue
                if max_dd < -35:
                    continue
                if roe < 10:
                    continue

                score = 0
                if ann_vol < 15:
                    score += 35
                elif ann_vol < 20:
                    score += 25
                elif ann_vol < 25:
                    score += 15
                if beta and beta < 0.7:
                    score += 25
                elif beta and beta < 0.9:
                    score += 15
                if sharpe and sharpe > 1.5:
                    score += 20
                elif sharpe and sharpe > 1.0:
                    score += 12
                if max_dd > -15:
                    score += 15
                elif max_dd > -25:
                    score += 8
                if div_yield > 2:
                    score += 10
                if roe > 18:
                    score += 5

                results.append({
                    "symbol": sym,
                    "sector": SECTOR_MAP.get(sym, fund.get("sector", "Unknown")),
                    "price": ta.get("price"),
                    "ann_vol": round(ann_vol, 1),
                    "max_drawdown": round(max_dd, 1),
                    "sharpe": round(sharpe, 2) if sharpe else None,
                    "beta": round(beta, 2) if beta else None,
                    "div_yield": round(div_yield, 2),
                    "roe": round(roe, 1),
                    "ret_12m": ta.get("ret_12m"),
                    "ret_3m": ta.get("ret_3m"),
                    "score": score,
                    "screen": "LOW_VOLATILITY",
                })
            except Exception as e:
                logger.debug(f"LowVol {sym}: {e}")
        return sorted(results, key=lambda x: x["score"], reverse=True)[:limit]


class DividendYieldScreener:
    """High dividend yield with sustainability check"""

    @staticmethod
    def screen(symbols: List[str], limit: int = 20) -> List[Dict]:
        results = []
        for sym in symbols:
            try:
                df = StockDataFetcher.get_price_data(sym, "1y")
                fund = StockDataFetcher.get_fundamentals(sym)
                ta = StockDataFetcher.compute_technicals(df)
                if not fund or not ta:
                    continue

                div_yield = fund.get("dividend_yield") or 0
                payout_ratio = fund.get("payout_ratio") or 0
                fcf = fund.get("fcf") or 0
                net_margin = fund.get("net_margin") or 0
                debt_equity = fund.get("debt_equity") or 0
                revenue_growth = fund.get("revenue_growth") or 0

                if div_yield < 1.5:
                    continue
                if payout_ratio > 90:  # unsustainable
                    continue

                # Dividend sustainability: FCF coverage
                market_cap = fund.get("market_cap") or 0
                div_fcf_cover = (fcf / market_cap * 100) / div_yield if (fcf > 0 and market_cap > 0 and div_yield > 0) else None

                score = 0
                if div_yield > 5:
                    score += 35
                elif div_yield > 3:
                    score += 25
                elif div_yield > 2:
                    score += 15
                if payout_ratio < 40:
                    score += 20
                elif payout_ratio < 60:
                    score += 10
                if div_fcf_cover and div_fcf_cover > 1.5:
                    score += 20
                if net_margin > 15:
                    score += 15
                if debt_equity < 30:
                    score += 10
                if revenue_growth > 5:
                    score += 5

                results.append({
                    "symbol": sym,
                    "sector": SECTOR_MAP.get(sym, fund.get("sector", "Unknown")),
                    "price": ta.get("price"),
                    "div_yield": round(div_yield, 2),
                    "payout_ratio": round(payout_ratio, 1),
                    "fcf_div_cover": round(div_fcf_cover, 2) if div_fcf_cover else None,
                    "net_margin": round(net_margin, 1),
                    "debt_equity": round(debt_equity, 1),
                    "revenue_growth": round(revenue_growth, 1),
                    "ret_12m": ta.get("ret_12m"),
                    "score": score,
                    "screen": "DIVIDEND_YIELD",
                })
            except Exception as e:
                logger.debug(f"Dividend {sym}: {e}")
        return sorted(results, key=lambda x: x["score"], reverse=True)[:limit]


class TechnicalSetupScreener:
    """Technical pattern and setup based screening"""

    @staticmethod
    def screen_golden_crossover(symbols: List[str]) -> List[Dict]:
        """50 SMA crossing above 200 SMA — classic bullish signal"""
        results = []
        for sym in symbols:
            try:
                df = StockDataFetcher.get_price_data(sym, "2y")
                if df is None or len(df) < 200:
                    continue
                closes = df["Close"].values
                sma50 = np.array([np.mean(closes[max(0,i-50):i]) for i in range(50, len(closes))])
                sma200_vals = np.array([np.mean(closes[max(0,i-200):i]) for i in range(200, len(closes))])
                # Align
                min_len = min(len(sma50), len(sma200_vals))
                sma50 = sma50[-min_len:]
                sma200_vals = sma200_vals[-min_len:]

                if min_len < 5:
                    continue

                # Check golden cross in last 10 days
                for i in range(max(1, min_len-10), min_len):
                    if sma50[i] > sma200_vals[i] and sma50[i-1] < sma200_vals[i-1]:
                        days_ago = min_len - i
                        ta = StockDataFetcher.compute_technicals(df)
                        results.append({
                            "symbol": sym,
                            "sector": SECTOR_MAP.get(sym, "Unknown"),
                            "price": ta.get("price"),
                            "sma50": round(sma50[-1], 2),
                            "sma200": round(sma200_vals[-1], 2),
                            "days_since_cross": days_ago,
                            "rsi": round(ta.get("rsi", 50), 1),
                            "vol_ratio": ta.get("vol_ratio"),
                            "screen": "GOLDEN_CROSS",
                        })
                        break
            except Exception as e:
                logger.debug(f"GoldenCross {sym}: {e}")
        return results

    @staticmethod
    def screen_oversold_bounce(symbols: List[str], rsi_threshold: float = 35) -> List[Dict]:
        """RSI oversold with positive divergence setup"""
        results = []
        for sym in symbols:
            try:
                df = StockDataFetcher.get_price_data(sym, "6mo")
                fund = StockDataFetcher.get_fundamentals(sym)
                ta = StockDataFetcher.compute_technicals(df)
                if not ta:
                    continue

                rsi = ta.get("rsi", 50)
                bb_pct = ta.get("bb_pct", 0.5)
                vol_ratio = ta.get("vol_ratio", 1)
                dist_52wl = ta.get("dist_52wl", 0)

                if rsi > rsi_threshold:
                    continue

                score = (rsi_threshold - rsi) * 2  # more oversold = higher score
                if bb_pct and bb_pct < 0.2:
                    score += 20
                if vol_ratio > 1.5:
                    score += 10  # volume surge on dip
                if dist_52wl and dist_52wl > 15:
                    score += 10  # not at 52W low

                results.append({
                    "symbol": sym,
                    "sector": SECTOR_MAP.get(sym, "Unknown"),
                    "price": ta.get("price"),
                    "rsi": round(rsi, 1),
                    "bb_position": round(bb_pct, 2) if bb_pct else None,
                    "vol_ratio": round(vol_ratio, 2),
                    "dist_52wl": round(dist_52wl, 1) if dist_52wl else None,
                    "pe": fund.get("pe_ratio"),
                    "score": round(score, 1),
                    "screen": "OVERSOLD_BOUNCE",
                })
            except Exception as e:
                logger.debug(f"Oversold {sym}: {e}")
        return sorted(results, key=lambda x: x["score"], reverse=True)

    @staticmethod
    def screen_52w_breakout(symbols: List[str], threshold_pct: float = 2.0) -> List[Dict]:
        """Stocks breaking out of 52W high — momentum continuation"""
        results = []
        for sym in symbols:
            try:
                df = StockDataFetcher.get_price_data(sym, "1y")
                ta = StockDataFetcher.compute_technicals(df)
                if not ta:
                    continue

                dist_52wh = ta.get("dist_52wh", -100)
                if dist_52wh is None or dist_52wh < -threshold_pct:
                    continue

                vol_ratio = ta.get("vol_ratio", 1)
                rsi = ta.get("rsi", 50)
                ret_1m = ta.get("ret_1m", 0)

                results.append({
                    "symbol": sym,
                    "sector": SECTOR_MAP.get(sym, "Unknown"),
                    "price": ta.get("price"),
                    "dist_52wh_pct": round(dist_52wh, 2),
                    "high_52w": ta.get("high_52w"),
                    "vol_ratio": round(vol_ratio, 2),
                    "rsi": round(rsi, 1),
                    "ret_1m": round(ret_1m, 1) if ret_1m else None,
                    "screen": "52W_BREAKOUT",
                })
            except Exception as e:
                logger.debug(f"52wBreak {sym}: {e}")
        return sorted(results, key=lambda x: x["dist_52wh_pct"], reverse=True)


class EarningsMomentumScreener:
    """Stocks with strong earnings estimate revisions — estimate revision momentum"""

    @staticmethod
    def screen(symbols: List[str], limit: int = 20) -> List[Dict]:
        results = []
        for sym in symbols:
            try:
                ticker = yf.Ticker(StockDataFetcher.yf_sym(sym))
                fund = StockDataFetcher.get_fundamentals(sym)
                ta = StockDataFetcher.compute_technicals(StockDataFetcher.get_price_data(sym, "1y"))
                if not fund or not ta:
                    continue

                # Analyst recommendation
                analyst_rating = fund.get("analyst_rating", "")
                num_analysts = fund.get("num_analysts", 0) or 0
                analyst_target = fund.get("analyst_target")
                price = ta.get("price", 0)

                # Upside to target
                upside = ((analyst_target / price) - 1) * 100 if (analyst_target and price > 0) else None

                # EPS trend
                eps_ttm = fund.get("eps_ttm") or 0
                eps_fwd = fund.get("eps_fwd") or 0
                eps_growth_fwd = ((eps_fwd / eps_ttm) - 1) * 100 if (eps_ttm > 0 and eps_fwd > 0) else None

                earnings_growth = fund.get("earnings_growth") or 0
                revenue_growth = fund.get("revenue_growth") or 0

                if num_analysts < 3:
                    continue
                if earnings_growth < 10 and (eps_growth_fwd or 0) < 10:
                    continue

                score = 0
                if analyst_rating in ["strongBuy", "strong_buy"]:
                    score += 30
                elif analyst_rating in ["buy"]:
                    score += 20
                if upside and upside > 30:
                    score += 30
                elif upside and upside > 20:
                    score += 20
                elif upside and upside > 10:
                    score += 10
                if eps_growth_fwd and eps_growth_fwd > 20:
                    score += 20
                elif eps_growth_fwd and eps_growth_fwd > 10:
                    score += 12
                if earnings_growth > 20:
                    score += 15
                if num_analysts > 15:
                    score += 5

                results.append({
                    "symbol": sym,
                    "sector": SECTOR_MAP.get(sym, fund.get("sector", "Unknown")),
                    "price": price,
                    "analyst_rating": analyst_rating,
                    "num_analysts": num_analysts,
                    "target_price": analyst_target,
                    "upside_pct": round(upside, 1) if upside else None,
                    "eps_ttm": round(eps_ttm, 2) if eps_ttm else None,
                    "eps_fwd": round(eps_fwd, 2) if eps_fwd else None,
                    "fwd_eps_growth": round(eps_growth_fwd, 1) if eps_growth_fwd else None,
                    "revenue_growth": round(revenue_growth, 1),
                    "earnings_growth": round(earnings_growth, 1),
                    "score": score,
                    "screen": "EARNINGS_MOMENTUM",
                })
            except Exception as e:
                logger.debug(f"EarningsMom {sym}: {e}")
        return sorted(results, key=lambda x: x["score"], reverse=True)[:limit]


class SectorStrengthScreener:
    """Identify strongest sectors and top stocks within them"""

    @staticmethod
    def get_sector_performance(symbols: List[str]) -> Dict[str, Any]:
        sector_data: Dict[str, List[float]] = {}
        sector_stocks: Dict[str, List[Dict]] = {}

        for sym in symbols:
            sector = SECTOR_MAP.get(sym, "Unknown")
            try:
                df = StockDataFetcher.get_price_data(sym, "3mo")
                ta = StockDataFetcher.compute_technicals(df)
                if ta and ta.get("ret_3m") is not None:
                    sector_data.setdefault(sector, []).append(ta["ret_3m"])
                    sector_stocks.setdefault(sector, []).append({
                        "symbol": sym,
                        "ret_3m": ta["ret_3m"],
                        "ret_1m": ta.get("ret_1m"),
                        "rsi": ta.get("rsi"),
                        "trend": ta.get("trend"),
                    })
            except Exception:
                pass

        sector_performance = {}
        for sec, rets in sector_data.items():
            avg_ret = np.mean(rets)
            # Breadth
            positive = sum(1 for r in rets if r > 0)
            sector_performance[sec] = {
                "sector": sec,
                "avg_return_3m": round(float(avg_ret), 1),
                "stock_count": len(rets),
                "positive_count": positive,
                "breadth_pct": round(positive / len(rets) * 100, 1) if rets else 0,
                "top_stocks": sorted(sector_stocks.get(sec, []), key=lambda x: x.get("ret_3m", 0), reverse=True)[:3],
            }

        return {
            "sectors": sorted(sector_performance.values(), key=lambda x: x["avg_return_3m"], reverse=True),
            "total_sectors": len(sector_performance),
        }


# ────────────────────────────────────────────────────────────────────────────
# COMPOSITE SCREENER ORCHESTRATOR
# ────────────────────────────────────────────────────────────────────────────

class AdvancedScreenerOrchestrator:
    """Main API interface for all advanced screens"""

    ALL_SYMBOLS: List[str] = list(dict.fromkeys(NIFTY50 + NIFTY_NEXT50 + PSU_SYMBOLS))

    @classmethod
    def run_screen(cls, screen_type: str, universe: str = "nifty100", limit: int = 20) -> Dict[str, Any]:
        symbols = cls._get_universe(universe)

        if screen_type == "garp":
            results = QualityGrowthScreener.screen(symbols, limit)
        elif screen_type == "deep_value":
            results = DeepValueScreener.screen(symbols, limit)
        elif screen_type == "quality_compounder":
            results = HighQualityCompounders.screen(symbols, limit)
        elif screen_type == "turnaround":
            results = TurnaroundScreener.screen(symbols, limit)
        elif screen_type == "low_vol":
            results = LowVolatilityScreener.screen(symbols, limit)
        elif screen_type == "dividend":
            results = DividendYieldScreener.screen(symbols, limit)
        elif screen_type == "golden_cross":
            results = TechnicalSetupScreener.screen_golden_crossover(symbols)[:limit]
        elif screen_type == "oversold":
            results = TechnicalSetupScreener.screen_oversold_bounce(symbols)[:limit]
        elif screen_type == "52w_breakout":
            results = TechnicalSetupScreener.screen_52w_breakout(symbols)[:limit]
        elif screen_type == "earnings_momentum":
            results = EarningsMomentumScreener.screen(symbols, limit)
        else:
            return {"error": f"Unknown screen type: {screen_type}", "results": []}

        return {
            "screen_type": screen_type,
            "universe": universe,
            "total_screened": len(symbols),
            "results": results,
            "count": len(results),
            "generated_at": pd.Timestamp.now().isoformat(),
        }

    @classmethod
    def get_sector_analysis(cls, universe: str = "nifty100") -> Dict[str, Any]:
        symbols = cls._get_universe(universe)
        return SectorStrengthScreener.get_sector_performance(symbols)

    @classmethod
    def run_all_screens(cls, universe: str = "nifty100") -> Dict[str, Any]:
        """Run all screens and return combined results"""
        symbols = cls._get_universe(universe)
        return {
            "garp": QualityGrowthScreener.screen(symbols, 10),
            "deep_value": DeepValueScreener.screen(symbols, 10),
            "quality_compounder": HighQualityCompounders.screen(symbols, 10),
            "turnaround": TurnaroundScreener.screen(symbols, 10),
            "low_vol": LowVolatilityScreener.screen(symbols, 10),
            "dividend": DividendYieldScreener.screen(symbols, 10),
            "earnings_momentum": EarningsMomentumScreener.screen(symbols, 10),
            "golden_cross": TechnicalSetupScreener.screen_golden_crossover(symbols)[:10],
            "52w_breakout": TechnicalSetupScreener.screen_52w_breakout(symbols)[:10],
            "generated_at": pd.Timestamp.now().isoformat(),
        }

    @classmethod
    def _get_universe(cls, universe: str) -> List[str]:
        if universe == "nifty50":
            return NIFTY50
        elif universe == "nifty_next50":
            return NIFTY_NEXT50
        elif universe == "psu":
            return PSU_SYMBOLS
        elif universe == "nifty100":
            return list(dict.fromkeys(NIFTY50 + NIFTY_NEXT50))
        else:
            return cls.ALL_SYMBOLS


# ────────────────────────────────────────────────────────────────────────────
# STANDALONE UTILITY FUNCTIONS
# ────────────────────────────────────────────────────────────────────────────

def run_magic_formula_screen(symbols: List[str], limit: int = 20) -> List[Dict]:
    """Joel Greenblatt's Magic Formula: high ROIC + high earnings yield"""
    candidates = []
    for sym in symbols:
        try:
            fund = StockDataFetcher.get_fundamentals(sym)
            ta = StockDataFetcher.compute_technicals(StockDataFetcher.get_price_data(sym, "1y"))
            if not fund or not ta:
                continue
            pe = fund.get("pe_ratio") or 0
            roe = fund.get("roe") or 0
            ev_ebitda = fund.get("ev_ebitda") or 0
            if pe <= 0 or roe <= 0 or ev_ebitda <= 0:
                continue
            earnings_yield = 1 / pe * 100  # inverse PE = earnings yield
            candidates.append({
                "symbol": sym,
                "sector": SECTOR_MAP.get(sym, "Unknown"),
                "price": ta.get("price"),
                "pe": round(pe, 1),
                "earnings_yield": round(earnings_yield, 2),
                "roe": round(roe, 1),
                "ev_ebitda": round(ev_ebitda, 1),
                "screen": "MAGIC_FORMULA",
            })
        except Exception:
            pass

    # Rank by earnings yield percentile + ROIC percentile combined
    if not candidates:
        return []
    ey_sorted = sorted(candidates, key=lambda x: x["earnings_yield"], reverse=True)
    roe_sorted = sorted(candidates, key=lambda x: x["roe"], reverse=True)
    ey_rank = {c["symbol"]: i for i, c in enumerate(ey_sorted)}
    roe_rank = {c["symbol"]: i for i, c in enumerate(roe_sorted)}
    for c in candidates:
        c["magic_rank"] = ey_rank[c["symbol"]] + roe_rank[c["symbol"]]
    return sorted(candidates, key=lambda x: x["magic_rank"])[:limit]


def calculate_universe_heatmap(symbols: List[str] = None) -> Dict[str, Any]:
    """Return price change % grid for heatmap visualization"""
    if symbols is None:
        symbols = list(dict.fromkeys(NIFTY50 + NIFTY_NEXT50))
    results = []
    for sym in symbols:
        try:
            df = StockDataFetcher.get_price_data(sym, "1mo")
            ta = StockDataFetcher.compute_technicals(df)
            if ta:
                results.append({
                    "symbol": sym,
                    "sector": SECTOR_MAP.get(sym, "Unknown"),
                    "price": ta.get("price"),
                    "ret_1d": None,  # needs intraday
                    "ret_1w": None,
                    "ret_1m": ta.get("ret_1m"),
                    "ret_3m": ta.get("ret_3m"),
                    "volume_ratio": ta.get("vol_ratio"),
                    "rsi": ta.get("rsi"),
                })
        except Exception:
            pass
    return {"stocks": results, "total": len(results)}
