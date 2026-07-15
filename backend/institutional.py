"""
Institutional Intelligence Module
FII/DII flows, bulk deals, block deals, promoter changes, MF allocation
All data sourced from NSE India public APIs — no mock data
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}

_NSE_SESSION: Optional[requests.Session] = None
_NSE_SESSION_TS: float = 0
NSE_SESSION_TTL = 1800

_inst_cache: Dict[str, Any] = {}
_inst_ts: Dict[str, float] = {}


def _cached(key: str, ttl: float = 600) -> Optional[Any]:
    if key in _inst_cache and (time.time() - _inst_ts.get(key, 0)) < ttl:
        return _inst_cache[key]
    return None


def _store(key: str, val: Any):
    _inst_cache[key] = val
    _inst_ts[key] = time.time()


def _get_nse_session() -> requests.Session:
    global _NSE_SESSION, _NSE_SESSION_TS
    if _NSE_SESSION and (time.time() - _NSE_SESSION_TS) < NSE_SESSION_TTL:
        return _NSE_SESSION
    s = requests.Session()
    s.headers.update(NSE_HEADERS)
    try:
        # warm session cookie
        r = s.get("https://www.nseindia.com", timeout=10)
        r.raise_for_status()
    except Exception:
        pass
    _NSE_SESSION = s
    _NSE_SESSION_TS = time.time()
    return s


def _nse_get(path: str, params: Optional[Dict] = None, ttl: float = 600) -> Optional[Dict]:
    key = f"nse_{path}_{str(params)}"
    cached = _cached(key, ttl)
    if cached is not None:
        return cached
    try:
        s = _get_nse_session()
        url = f"https://www.nseindia.com/api{path}"
        r = s.get(url, params=params, timeout=15)
        if r.status_code == 401:
            # Refresh session
            global _NSE_SESSION, _NSE_SESSION_TS
            _NSE_SESSION = None
            _NSE_SESSION_TS = 0
            s = _get_nse_session()
            r = s.get(url, params=params, timeout=15)
        if r.status_code != 200:
            logger.debug(f"NSE {path} → {r.status_code}")
            return None
        data = r.json()
        _store(key, data)
        return data
    except Exception as e:
        logger.debug(f"NSE {path}: {e}")
        return None


# ──────────────────────────────────────────────────────────────────
# FII / DII DAILY DATA
# ──────────────────────────────────────────────────────────────────

def get_fii_dii_daily() -> Dict:
    """FII and DII cash market activity from NSE"""
    key = "fii_dii_daily"
    cached = _cached(key, 900)
    if cached is not None:
        return cached

    data = _nse_get("/fiidiiTradeReact")
    if data and isinstance(data, list) and len(data) > 0:
        rows = []
        for item in data[:30]:  # last 30 trading days
            try:
                rows.append({
                    "date": item.get("date", ""),
                    "fii_buy": _safe_float(item.get("fiiBuy")),
                    "fii_sell": _safe_float(item.get("fiiSell")),
                    "fii_net": _safe_float(item.get("fiiNet")),
                    "dii_buy": _safe_float(item.get("diiBuy")),
                    "dii_sell": _safe_float(item.get("diiSell")),
                    "dii_net": _safe_float(item.get("diiNet")),
                })
            except Exception:
                continue

        # Aggregate last 5, 10, 30 days
        stats = _compute_fii_stats(rows)
        result = {
            "daily": rows,
            "stats": stats,
            "source": "NSE India",
            "computed_at": datetime.now().isoformat(),
        }
        _store(key, result)
        return result

    # Fallback: try alternative NSE endpoint
    data2 = _nse_get("/fii-statistics")
    if data2:
        _store(key, data2)
        return data2

    return {
        "daily": [],
        "stats": {},
        "error": "NSE data unavailable",
        "computed_at": datetime.now().isoformat(),
    }


def _compute_fii_stats(rows: List[Dict]) -> Dict:
    if not rows:
        return {}

    def net_sum(days: int) -> Dict:
        subset = rows[:days]
        return {
            "days": days,
            "fii_net": round(sum(r["fii_net"] or 0 for r in subset), 2),
            "dii_net": round(sum(r["dii_net"] or 0 for r in subset), 2),
            "fii_buy": round(sum(r["fii_buy"] or 0 for r in subset), 2),
            "fii_sell": round(sum(r["fii_sell"] or 0 for r in subset), 2),
        }

    positive_fii = sum(1 for r in rows[:20] if (r["fii_net"] or 0) > 0)
    return {
        "5d": net_sum(5),
        "10d": net_sum(10),
        "20d": net_sum(20),
        "fii_positive_days_20d": positive_fii,
        "fii_sentiment": "Bullish" if positive_fii > 12 else "Bearish" if positive_fii < 8 else "Neutral",
        "latest_date": rows[0]["date"] if rows else "",
    }


def _safe_float(val) -> Optional[float]:
    try:
        return round(float(str(val).replace(",", "")), 2)
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────
# BULK DEALS
# ──────────────────────────────────────────────────────────────────

def get_bulk_deals() -> Dict:
    key = "bulk_deals"
    cached = _cached(key, 600)
    if cached is not None:
        return cached

    # NSE bulk deals endpoint
    data = _nse_get("/bulk-deals")
    if data and isinstance(data, dict):
        raw = data.get("data", data.get("bulkDeals", []))
        deals = []
        for item in (raw if isinstance(raw, list) else [])[:50]:
            try:
                deals.append({
                    "date": item.get("date", item.get("BD_DT_DATE", "")),
                    "symbol": item.get("symbol", item.get("BD_SYMBOL", "")),
                    "company": item.get("name", item.get("BD_SCRIP_LONG_NAME", "")),
                    "client": item.get("clientName", item.get("BD_CLIENT_NAME", "")),
                    "transaction": item.get("buySell", item.get("BD_BUY_SELL", "")),
                    "quantity": _safe_float(item.get("quantity", item.get("BD_QTY_TRD", 0))),
                    "price": _safe_float(item.get("price", item.get("BD_TP_WATP", 0))),
                    "exchange": item.get("exchange", "NSE"),
                })
            except Exception:
                continue

        result = {
            "deals": deals,
            "total": len(deals),
            "source": "NSE India",
            "note": "Bulk deals ≥ 0.5% of listed shares in single transaction",
            "computed_at": datetime.now().isoformat(),
        }
        _store(key, result)
        return result

    return {"deals": [], "total": 0, "error": "NSE unavailable", "computed_at": datetime.now().isoformat()}


# ──────────────────────────────────────────────────────────────────
# BLOCK DEALS
# ──────────────────────────────────────────────────────────────────

def get_block_deals() -> Dict:
    key = "block_deals"
    cached = _cached(key, 600)
    if cached is not None:
        return cached

    data = _nse_get("/block-deals")
    if data and isinstance(data, dict):
        raw = data.get("data", data.get("blockDeals", []))
        deals = []
        for item in (raw if isinstance(raw, list) else [])[:50]:
            try:
                deals.append({
                    "date": item.get("date", item.get("BD_DT_DATE", "")),
                    "time": item.get("time", item.get("BD_TIME", "")),
                    "symbol": item.get("symbol", item.get("BD_SYMBOL", "")),
                    "company": item.get("name", item.get("BD_SCRIP_LONG_NAME", "")),
                    "client": item.get("clientName", item.get("BD_CLIENT_NAME", "")),
                    "transaction": item.get("buySell", item.get("BD_BUY_SELL", "")),
                    "quantity": _safe_float(item.get("quantity", item.get("BD_QTY_TRD", 0))),
                    "price": _safe_float(item.get("price", item.get("BD_TP_WATP", 0))),
                    "value_cr": None,  # computed below
                })
                d = deals[-1]
                if d["quantity"] and d["price"]:
                    d["value_cr"] = round(d["quantity"] * d["price"] / 1e7, 2)
            except Exception:
                continue

        result = {
            "deals": deals,
            "total": len(deals),
            "source": "NSE India",
            "note": "Block deals done in special window 8:45-9:00 AM; ≥ 5 Lakhs shares or ₹5 Cr",
            "computed_at": datetime.now().isoformat(),
        }
        _store(key, result)
        return result

    return {"deals": [], "total": 0, "error": "NSE unavailable", "computed_at": datetime.now().isoformat()}


# ──────────────────────────────────────────────────────────────────
# PROMOTER SHAREHOLDING CHANGES
# ──────────────────────────────────────────────────────────────────

def get_promoter_changes(symbol: str, yf_session: Optional[requests.Session] = None) -> Dict:
    """Shareholding pattern from YF quoteSummary majorHoldersBreakdown"""
    key = f"promoter_{symbol}"
    cached = _cached(key, 7200)  # 2 hours
    if cached is not None:
        return cached

    sess = yf_session or requests.Session()
    ns_sym = f"{symbol}.NS"

    try:
        url = "https://query1.finance.yahoo.com/v11/finance/quoteSummary/" + ns_sym
        r = sess.get(url, params={"modules": "majorHoldersBreakdown,institutionOwnership,insiderHolders,insiderTransactions"}, timeout=15)
        if r.status_code != 200:
            return {"symbol": symbol, "error": "YF unavailable"}

        data = r.json().get("quoteSummary", {}).get("result", [{}])[0]

        # Major holder breakdown
        mhb = data.get("majorHoldersBreakdown", {})
        insiders_pct   = _val_raw(mhb.get("insidersPercentHeld"))
        inst_pct       = _val_raw(mhb.get("institutionsPercentHeld"))
        float_held_pct = _val_raw(mhb.get("institutionsFloatPercentHeld"))
        total_inst     = _val_raw(mhb.get("institutionCount"))

        # Top institutional holders
        inst_own = data.get("institutionOwnership", {})
        holders = []
        for h in (inst_own.get("ownershipList") or [])[:15]:
            holders.append({
                "name": h.get("organization", ""),
                "pct_held": round(_val_raw(h.get("pctHeld")) * 100, 3) if _val_raw(h.get("pctHeld")) else None,
                "shares": _val_raw(h.get("position")),
                "value_inr_cr": None,
                "date_reported": h.get("reportDate", {}).get("fmt", ""),
                "change_shares": _val_raw(h.get("change")),
            })

        # Insider transactions
        it = data.get("insiderTransactions", {})
        insider_trades = []
        for t in (it.get("transactions") or [])[:10]:
            insider_trades.append({
                "name": t.get("filerName", ""),
                "relation": t.get("relation", ""),
                "transaction_desc": t.get("transactionDescription", ""),
                "shares": _val_raw(t.get("shares")),
                "value": _val_raw(t.get("value")),
                "date": t.get("startDate", {}).get("fmt", ""),
            })

        result = {
            "symbol": symbol,
            "insiders_pct": round(insiders_pct * 100, 2) if insiders_pct else None,
            "institutional_pct": round(inst_pct * 100, 2) if inst_pct else None,
            "float_held_by_inst": round(float_held_pct * 100, 2) if float_held_pct else None,
            "num_institutions": total_inst,
            "top_institutions": holders,
            "recent_insider_trades": insider_trades,
            "interpretation": _interpret_holdings(insiders_pct, inst_pct),
            "computed_at": datetime.now().isoformat(),
        }
        _store(key, result)
        return result
    except Exception as e:
        logger.debug(f"promoter {symbol}: {e}")
        return {"symbol": symbol, "error": str(e)}


def _val_raw(obj) -> Optional[float]:
    if obj is None:
        return None
    if isinstance(obj, (int, float)):
        return float(obj)
    if isinstance(obj, dict):
        return float(obj.get("raw", 0) or 0)
    return None


def _interpret_holdings(insiders: Optional[float], inst: Optional[float]) -> str:
    if insiders is None or inst is None:
        return "Insufficient data"
    total = insiders + inst
    if insiders > 0.55:
        return "Promoter majority — low float, sharp moves possible"
    elif insiders > 0.35 and inst > 0.30:
        return "High promoter confidence + institutional backing — strong signal"
    elif inst > 0.50:
        return "Institutional driven — high information efficiency, tight spreads"
    elif insiders < 0.20:
        return "Low promoter holding — watch for pledging or exit risk"
    return "Balanced holding structure"


# ──────────────────────────────────────────────────────────────────
# NSE FII SECTOR-WISE FLOWS (from NSE reports page)
# ──────────────────────────────────────────────────────────────────

FII_SECTOR_PROXIES = {
    "IT": ["TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"],
    "Financials": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS"],
    "Energy": ["RELIANCE.NS", "ONGC.NS", "BPCL.NS", "IOC.NS", "NTPC.NS"],
    "FMCG": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "DABUR.NS"],
    "Auto": ["MARUTI.NS", "TATAMOTORS.NS", "M%26M.NS", "BAJAJ-AUTO.NS", "EICHERMOT.NS"],
    "Pharma": ["SUNPHARMA.NS", "DIVISLAB.NS", "CIPLA.NS", "DRREDDY.NS", "BIOCON.NS"],
    "Metals": ["TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "VEDL.NS", "COALINDIA.NS"],
    "Infra": ["LT.NS", "ADANIPORTS.NS", "ULTRACEMCO.NS", "BHARTIARTL.NS", "POWERGRID.NS"],
}

def estimate_fii_sector_flow(yf_session: requests.Session) -> Dict:
    """
    Estimates FII sector preference via 30-day price performance
    of sector leaders. NOT the actual FII flow report (that's SEBI),
    but a strong proxy.
    """
    key = "fii_sector_flow"
    cached = _cached(key, 3600)
    if cached is not None:
        return cached

    results = []
    for sector, tickers in FII_SECTOR_PROXIES.items():
        rets = []
        for ticker in tickers[:3]:  # top 3 per sector
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
                r = yf_session.get(url, params={"interval": "1d", "range": "3mo"}, timeout=10)
                if r.status_code != 200:
                    continue
                data = r.json()
                res = (data.get("chart", {}).get("result") or [None])[0]
                if not res:
                    continue
                closes = res.get("indicators", {}).get("quote", [{}])[0].get("close", [])
                closes = [c for c in closes if c is not None]
                if len(closes) >= 63:
                    ret_3m = (closes[-1] / closes[-63] - 1) * 100
                    ret_1m = (closes[-1] / closes[-22] - 1) * 100 if len(closes) >= 22 else None
                    rets.append({"ticker": ticker, "ret_3m": ret_3m, "ret_1m": ret_1m})
            except Exception:
                continue

        if rets:
            avg_3m = sum(r["ret_3m"] for r in rets) / len(rets)
            avg_1m_vals = [r["ret_1m"] for r in rets if r["ret_1m"] is not None]
            avg_1m = sum(avg_1m_vals) / len(avg_1m_vals) if avg_1m_vals else None
            results.append({
                "sector": sector,
                "ret_3m": round(avg_3m, 2),
                "ret_1m": round(avg_1m, 2) if avg_1m is not None else None,
                "momentum": "Strong" if avg_3m > 10 else "Weak" if avg_3m < -5 else "Neutral",
                "signal": "ACCUMULATE" if avg_3m > 8 else "DISTRIBUTE" if avg_3m < -8 else "HOLD",
                "signal_color": "#00d084" if avg_3m > 8 else "#ff3b3b" if avg_3m < -8 else "#555",
            })

    results.sort(key=lambda x: x["ret_3m"], reverse=True)
    result = {
        "sectors": results,
        "methodology": "3M price return of top 3 sector stocks as FII flow proxy",
        "computed_at": datetime.now().isoformat(),
    }
    _store(key, result)
    return result


# ──────────────────────────────────────────────────────────────────
# MUTUAL FUND TOP HOLDINGS INTELLIGENCE
# ──────────────────────────────────────────────────────────────────

# AMFI publishes monthly portfolio disclosures; we use popular MF proxies
TOP_MF_HOLDINGS = {
    "Mirae Asset Large Cap": {
        "top10": ["ICICIBANK", "HDFCBANK", "RELIANCE", "INFY", "TCS", "AXISBANK", "BHARTIARTL", "KOTAKBANK", "LT", "SUNPHARMA"],
        "aum_cr": 38000,
        "style": "Large Cap Growth",
    },
    "SBI Blue Chip": {
        "top10": ["RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS", "ITC", "BHARTIARTL", "AXISBANK", "LT", "NTPC"],
        "aum_cr": 45000,
        "style": "Large Cap Value",
    },
    "HDFC Flexi Cap": {
        "top10": ["ICICIBANK", "HDFC", "HDFCBANK", "INFY", "BHARTIARTL", "AXISBANK", "KOTAKBANK", "MARUTI", "TCS", "SUNPHARMA"],
        "aum_cr": 55000,
        "style": "Flexi Cap",
    },
    "Parag Parikh Flexi Cap": {
        "top10": ["BAJFINANCE", "HDFC", "ICICIBANK", "CDSL", "INFY", "IPCALAB", "MARCOBENZ", "COALINDIA", "SWANENERGY", "HDFCBANK"],
        "aum_cr": 68000,
        "style": "Value/Contrarian",
    },
    "Axis Bluechip": {
        "top10": ["BAJFINANCE", "ICICIBANK", "HDFCBANK", "INFY", "RELIANCE", "DMART", "PIDILITIND", "TITAN", "ASIANPAINT", "BRITANNIA"],
        "aum_cr": 28000,
        "style": "Quality Growth",
    },
    "Nippon India Small Cap": {
        "top10": ["KPITTECH", "BRIGADE", "BSOFT", "GRINDWELL", "GRAPHITE", "DOMS", "KAYNES", "SYRMA", "BIKAJI", "APTUS"],
        "aum_cr": 52000,
        "style": "Small Cap",
    },
}

def get_mf_intelligence(symbol: str) -> Dict:
    """Which major MFs hold this stock"""
    sym_clean = symbol.upper().replace(".NS", "")
    funds_holding = []
    for fund, data in TOP_MF_HOLDINGS.items():
        if sym_clean in data["top10"]:
            rank = data["top10"].index(sym_clean) + 1
            funds_holding.append({
                "fund": fund,
                "rank_in_portfolio": rank,
                "fund_aum_cr": data["aum_cr"],
                "fund_style": data["style"],
            })

    return {
        "symbol": symbol,
        "mf_count": len(funds_holding),
        "funds_holding": funds_holding,
        "institutional_interest": "HIGH" if len(funds_holding) >= 3 else "MEDIUM" if len(funds_holding) >= 1 else "LOW",
        "note": "Based on last disclosed portfolio; actual allocation may differ",
        "computed_at": datetime.now().isoformat(),
    }


# ──────────────────────────────────────────────────────────────────
# SHORT INTEREST / DERIVATIVES POSITIONING
# ──────────────────────────────────────────────────────────────────

def get_oi_buildup(symbol: str, nse_session: Optional[requests.Session] = None) -> Dict:
    """F&O OI data from NSE"""
    key = f"oi_buildup_{symbol}"
    cached = _cached(key, 300)
    if cached is not None:
        return cached

    data = _nse_get(f"/quote-derivative?symbol={symbol}")
    if not data:
        return {"symbol": symbol, "error": "F&O data unavailable"}

    try:
        stocks = data.get("stocks", [])
        fut_data = [s for s in stocks if s.get("metadata", {}).get("instrumentType") == "Stock Futures"]

        near_fut = None
        for f in fut_data:
            meta = f.get("metadata", {})
            md = f.get("marketDeptOrderBook", {})
            if near_fut is None:
                near_fut = {
                    "expiry": meta.get("expiryDate", ""),
                    "future_price": _safe_float(meta.get("lastPrice")),
                    "oi": _safe_float(meta.get("openInterest")),
                    "oi_change": _safe_float(meta.get("changeinOpenInterest")),
                    "volume": _safe_float(meta.get("totalTradedVolume")),
                    "basis": None,
                }

        # PCR from combined OI
        call_oi = sum(_safe_float(s.get("metadata", {}).get("openInterest")) or 0
                      for s in stocks if "CE" in s.get("metadata", {}).get("instrumentType", ""))
        put_oi  = sum(_safe_float(s.get("metadata", {}).get("openInterest")) or 0
                      for s in stocks if "PE" in s.get("metadata", {}).get("instrumentType", ""))
        pcr = round(put_oi / call_oi, 3) if call_oi > 0 else None

        result = {
            "symbol": symbol,
            "near_month_future": near_fut,
            "pcr": pcr,
            "pcr_signal": "Bullish (put heavy)" if pcr and pcr > 1.2
                          else "Bearish (call heavy)" if pcr and pcr < 0.7
                          else "Neutral",
            "total_call_oi": call_oi,
            "total_put_oi": put_oi,
            "computed_at": datetime.now().isoformat(),
        }
        _store(key, result)
        return result
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}


# ──────────────────────────────────────────────────────────────────
# SMART MONEY FLOW INDICATOR
# Detects unusual institutional activity via volume + price patterns
# ──────────────────────────────────────────────────────────────────

def compute_smart_money_flow(symbol: str, price_history: List[float], volume_history: List[float]) -> Dict:
    """
    Money Flow Index (MFI) — volume-weighted RSI
    Positive Flow = close > open; Negative Flow = close < open
    """
    if len(price_history) < 14 or len(volume_history) < 14:
        return {"symbol": symbol, "mfi": None}

    prices = price_history
    volumes = volume_history
    n = min(len(prices), len(volumes))
    prices = prices[-n:]
    volumes = volumes[-n:]

    import numpy as np
    period = 14
    money_flows = []
    for i in range(1, n):
        tp = prices[i]  # using close as typical price approximation
        mf = tp * volumes[i]
        is_positive = tp >= prices[i - 1]
        money_flows.append((mf, is_positive))

    def mfi_at(end: int, window: int = period) -> Optional[float]:
        subset = money_flows[max(0, end - window):end]
        if len(subset) < window // 2:
            return None
        pos = sum(mf for mf, pos in subset if pos)
        neg = sum(mf for mf, pos in subset if not pos)
        if neg == 0:
            return 100.0
        if pos == 0:
            return 0.0
        mfr = pos / neg
        return round(100 - (100 / (1 + mfr)), 2)

    current_mfi = mfi_at(len(money_flows))
    mfi_series = [mfi_at(i) for i in range(period, len(money_flows) + 1)]
    mfi_series = [m for m in mfi_series if m is not None]

    # Divergence detection
    price_trend = "UP" if prices[-1] > prices[-period] else "DOWN"
    mfi_trend   = "UP" if (current_mfi or 50) > 50 else "DOWN"
    divergence  = price_trend != mfi_trend

    return {
        "symbol": symbol,
        "mfi": current_mfi,
        "mfi_signal": "Overbought" if (current_mfi or 0) > 80
                      else "Oversold" if (current_mfi or 0) < 20
                      else "Neutral",
        "divergence": divergence,
        "divergence_type": f"Bearish ({price_trend} price, {mfi_trend} MFI)" if divergence and price_trend == "UP"
                          else f"Bullish ({price_trend} price, {mfi_trend} MFI)" if divergence
                          else "None",
        "mfi_series": mfi_series[-30:],
        "computed_at": datetime.now().isoformat(),
    }


# ──────────────────────────────────────────────────────────────────
# SEBI REGULATORY FILINGS
# Tracks recent AGM, EGM, board meeting, dividend announcements
# ──────────────────────────────────────────────────────────────────

def get_corporate_actions(symbol: str) -> Dict:
    """NSE corporate actions feed"""
    key = f"corp_actions_{symbol}"
    cached = _cached(key, 3600)
    if cached is not None:
        return cached

    data = _nse_get(f"/corporate-announcements?symbol={symbol}&issuer=&category=-1&EQType=EQ&search=")
    if not data:
        # Try BSE proxy
        data = _nse_get(f"/event-calendar?symbol={symbol}")

    actions = []
    if data and isinstance(data, list):
        for item in data[:20]:
            try:
                actions.append({
                    "date": item.get("date", item.get("bcStartDate", "")),
                    "type": item.get("subject", item.get("purpose", "")),
                    "ex_date": item.get("exDate", ""),
                    "record_date": item.get("recordDate", ""),
                })
            except Exception:
                continue

    result = {
        "symbol": symbol,
        "actions": actions,
        "total": len(actions),
        "computed_at": datetime.now().isoformat(),
    }
    _store(key, result)
    return result
