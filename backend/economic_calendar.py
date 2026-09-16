"""
Economic Calendar & Events Engine for IndiaHedge Terminal
Real upcoming events: RBI policy, earnings, economic data releases,
corporate actions, index reconstitutions, F&O expiries
"""

from __future__ import annotations
import logging
import time
import re
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional
import warnings

import numpy as np
import pandas as pd
import requests
import yfinance as yf

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# NSE CALENDAR CLIENT
# ────────────────────────────────────────────────────────────────────────────

class NSECalendarClient:
    BASE = "https://www.nseindia.com"
    _session: Optional[requests.Session] = None
    _cache: Dict[str, Any] = {}
    _cache_ts: Dict[str, float] = {}
    CACHE_TTL = 3600  # 1 hour for calendar data

    NSE_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.nseindia.com/",
    }

    @classmethod
    def _get_session(cls) -> requests.Session:
        if cls._session is None:
            cls._session = requests.Session()
            cls._session.verify = False
            cls._session.headers.update(cls.NSE_HEADERS)
            try:
                cls._session.get(f"{cls.BASE}/", timeout=10)
            except Exception:
                pass
        return cls._session

    @classmethod
    def _cached(cls, key: str, ttl: int = None) -> Optional[Any]:
        ttl = ttl or cls.CACHE_TTL
        if key in cls._cache and (time.time() - cls._cache_ts.get(key, 0)) < ttl:
            return cls._cache[key]
        return None

    @classmethod
    def _store(cls, key: str, val: Any):
        cls._cache[key] = val
        cls._cache_ts[key] = time.time()

    @classmethod
    def get_trading_holidays(cls) -> List[Dict]:
        cached = cls._cached("holidays")
        if cached:
            return cached
        try:
            s = cls._get_session()
            r = s.get(f"{cls.BASE}/api/holiday-master?type=trading", timeout=15)
            if r.status_code == 200:
                data = r.json()
                holidays = []
                for segment, hlist in data.items():
                    if isinstance(hlist, list):
                        for h in hlist:
                            holidays.append({
                                "date": h.get("tradingDate", ""),
                                "day": h.get("weekDay", ""),
                                "description": h.get("description", ""),
                                "segment": segment,
                            })
                if holidays:
                    cls._store("holidays", holidays)
                    return holidays
        except Exception as e:
            logger.debug(f"NSE holidays: {e}")
        return []

    @classmethod
    def get_corporate_actions(cls, symbol: str = None) -> List[Dict]:
        key = f"corp_actions_{symbol or 'all'}"
        cached = cls._cached(key, 1800)
        if cached:
            return cached
        try:
            s = cls._get_session()
            url = f"{cls.BASE}/api/corporates-corporateActions?index=equities"
            r = s.get(url, timeout=15)
            if r.status_code == 200:
                data = r.json()
                actions = []
                if isinstance(data, list):
                    for item in data:
                        sym = item.get("symbol", "")
                        if symbol and sym.upper() != symbol.upper():
                            continue
                        actions.append({
                            "symbol": sym,
                            "company": item.get("companyName", ""),
                            "action_type": item.get("purpose", ""),
                            "ex_date": item.get("exDate", ""),
                            "record_date": item.get("recDate", ""),
                            "bc_start": item.get("bcStartDate", ""),
                            "bc_end": item.get("bcEndDate", ""),
                            "remarks": item.get("remarks", ""),
                        })
                cls._store(key, actions)
                return actions
        except Exception as e:
            logger.debug(f"Corp actions: {e}")
        return []

    @classmethod
    def get_upcoming_dividends(cls) -> List[Dict]:
        actions = cls.get_corporate_actions()
        today = datetime.now()
        dividends = []
        for a in actions:
            purpose = (a.get("action_type") or "").lower()
            if "div" in purpose or "interim" in purpose:
                ex_date_str = a.get("ex_date", "")
                try:
                    ex_date = datetime.strptime(ex_date_str, "%d-%b-%Y")
                    if ex_date >= today - timedelta(days=7):
                        a["days_to_ex"] = (ex_date - today).days
                        dividends.append(a)
                except Exception:
                    pass
        return sorted(dividends, key=lambda x: x.get("days_to_ex", 999))[:50]

    @classmethod
    def get_bonus_splits(cls) -> List[Dict]:
        actions = cls.get_corporate_actions()
        results = []
        today = datetime.now()
        for a in actions:
            purpose = (a.get("action_type") or "").lower()
            if "bonus" in purpose or "split" in purpose or "rights" in purpose:
                ex_date_str = a.get("ex_date", "")
                try:
                    ex_date = datetime.strptime(ex_date_str, "%d-%b-%Y")
                    if ex_date >= today - timedelta(days=7):
                        a["days_to_ex"] = (ex_date - today).days
                        results.append(a)
                except Exception:
                    pass
        return sorted(results, key=lambda x: x.get("days_to_ex", 999))[:30]

    @classmethod
    def get_fno_expiry_dates(cls) -> Dict[str, Any]:
        """NSE F&O expiry dates — NSE weekly (Thursday) and monthly"""
        today = datetime.now()
        expiries = []

        # Generate upcoming Thursday expiries (NIFTY weekly)
        d = today
        while d <= today + timedelta(days=90):
            if d.weekday() == 3:  # Thursday
                days_to = (d - today).days
                expiries.append({
                    "date": d.strftime("%Y-%m-%d"),
                    "day": d.strftime("%A"),
                    "type": "WEEKLY",
                    "indices": ["NIFTY"],
                    "days_to_expiry": days_to,
                    "is_monthly": d.month != (d + timedelta(7)).month,  # last Thursday of month
                })
            d += timedelta(1)

        # Monthly expiries for stocks (last Thursday of each month)
        monthly_expiries = []
        for month_offset in range(4):
            target_month_date = today + timedelta(days=30 * month_offset)
            year = target_month_date.year
            month = target_month_date.month
            # Find last Thursday
            last_day = date(year, month, 28) + timedelta(days=4 - date(year, month, 28).weekday())
            # Ensure it's in correct month
            while last_day.month != month:
                last_day -= timedelta(7)
            # Find last Thursday of month
            thursdays = [date(year, month, d) for d in range(1, 32)
                        if d <= 31 and date(year, month, min(d, 28)).month == month
                        and datetime(year, month, 1).weekday() == 0]  # simplified
            # Better approach
            d2 = date(year, month, 1)
            month_thurdays = []
            while d2.month == month:
                if d2.weekday() == 3:
                    month_thurdays.append(d2)
                d2 += timedelta(1)
            if month_thurdays:
                last_thu = month_thurdays[-1]
                days_to = (datetime(last_thu.year, last_thu.month, last_thu.day) - today).days
                if days_to >= 0:
                    monthly_expiries.append({
                        "date": last_thu.strftime("%Y-%m-%d"),
                        "month": last_thu.strftime("%B %Y"),
                        "type": "MONTHLY",
                        "indices": ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "STOCKS"],
                        "days_to_expiry": days_to,
                    })

        return {
            "weekly": [e for e in expiries if not e.get("is_monthly")][:8],
            "monthly": monthly_expiries,
            "next_expiry": expiries[0] if expiries else None,
            "generated_at": datetime.now().isoformat(),
        }


# ────────────────────────────────────────────────────────────────────────────
# EARNINGS CALENDAR (via yfinance)
# ────────────────────────────────────────────────────────────────────────────

class EarningsCalendar:
    _cache: Dict[str, Any] = {}
    _cache_ts: Dict[str, float] = {}

    NIFTY50 = [
        "RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","HINDUNILVR","BAJFINANCE",
        "BHARTIARTL","SBIN","KOTAKBANK","ITC","LT","AXISBANK","TITAN","ASIANPAINT",
        "MARUTI","ULTRACEMCO","WIPRO","HCLTECH","NESTLEIND","ADANIENT","ADANIPORTS",
        "POWERGRID","NTPC","ONGC","COALINDIA","GRASIM","BAJAJFINSV","TATASTEEL",
        "JSWSTEEL","HDFCLIFE","SBILIFE","DIVISLAB","CIPLA","DRREDDY","SUNPHARMA",
        "TECHM","INDUSINDBK","BPCL","EICHERMOT","BRITANNIA","HINDALCO","TATAMOTORS",
        "APOLLOHOSP","HEROMOTOCO","MM","SHREECEM","TATACONSUM","PIDILITIND","LTIM",
    ]

    YF_OVERRIDES = {"MM": "M%26M.NS", "BAJAJ-AUTO": "BAJAJ-AUTO.NS"}

    @classmethod
    def get_earnings_dates(cls, symbols: List[str] = None) -> List[Dict]:
        if symbols is None:
            symbols = cls.NIFTY50
        cached = cls._cache.get("earnings_all")
        if cached and (time.time() - cls._cache_ts.get("earnings_all", 0)) < 7200:
            return cached

        results = []
        today = datetime.now()
        for sym in symbols:
            try:
                yf_sym = cls.YF_OVERRIDES.get(sym, f"{sym}.NS")
                ticker = yf.Ticker(yf_sym)
                cal = ticker.calendar
                if cal is None:
                    continue

                # calendar can be a dict or DataFrame
                if isinstance(cal, dict):
                    earnings_date = cal.get("Earnings Date", [])
                    if isinstance(earnings_date, list) and earnings_date:
                        ed = earnings_date[0]
                    elif earnings_date:
                        ed = earnings_date
                    else:
                        continue
                elif hasattr(cal, 'columns'):
                    if 'Earnings Date' in cal.columns:
                        ed = cal['Earnings Date'].iloc[0] if not cal.empty else None
                    else:
                        continue
                else:
                    continue

                if ed is None:
                    continue

                # Convert to datetime
                if hasattr(ed, 'timestamp'):
                    ed_dt = datetime.fromtimestamp(ed.timestamp())
                elif isinstance(ed, str):
                    try:
                        ed_dt = datetime.strptime(ed, "%Y-%m-%d")
                    except Exception:
                        continue
                else:
                    continue

                days_to = (ed_dt - today).days
                info = ticker.info or {}
                results.append({
                    "symbol": sym,
                    "company": info.get("longName", sym),
                    "earnings_date": ed_dt.strftime("%Y-%m-%d"),
                    "days_to_earnings": days_to,
                    "eps_estimate": info.get("forwardEps"),
                    "eps_actual_last": info.get("trailingEps"),
                    "revenue_estimate": info.get("revenueEstimate"),
                    "market_cap_cr": round(info.get("marketCap", 0) / 1e7, 0) if info.get("marketCap") else None,
                    "sector": info.get("sector", ""),
                })
            except Exception as e:
                logger.debug(f"Earnings date {sym}: {e}")

        results.sort(key=lambda x: x.get("days_to_earnings", 999))
        cls._cache["earnings_all"] = results
        cls._cache_ts["earnings_all"] = time.time()
        return results

    @classmethod
    def get_historical_earnings(cls, symbol: str) -> Dict[str, Any]:
        """Earnings history with surprise analysis"""
        try:
            yf_sym = cls.YF_OVERRIDES.get(symbol, f"{symbol}.NS")
            ticker = yf.Ticker(yf_sym)
            hist = ticker.earnings_history
            quarterly = ticker.quarterly_financials

            earnings_history = []
            if hist is not None and not hist.empty:
                for idx, row in hist.iterrows():
                    eps_est = row.get("epsEstimate")
                    eps_actual = row.get("epsActual")
                    surprise = None
                    surprise_pct = None
                    if eps_est and eps_actual and eps_est != 0:
                        surprise = eps_actual - eps_est
                        surprise_pct = (surprise / abs(eps_est)) * 100

                    earnings_history.append({
                        "date": str(idx)[:10],
                        "eps_estimate": float(eps_est) if eps_est else None,
                        "eps_actual": float(eps_actual) if eps_actual else None,
                        "surprise": round(float(surprise), 2) if surprise else None,
                        "surprise_pct": round(float(surprise_pct), 1) if surprise_pct else None,
                        "beat": surprise > 0 if surprise else None,
                    })

            # Average surprise
            surprises = [e["surprise_pct"] for e in earnings_history if e.get("surprise_pct") is not None]
            avg_surprise = np.mean(surprises) if surprises else None
            beat_rate = (sum(1 for e in earnings_history if e.get("beat")) / len(earnings_history) * 100) if earnings_history else None

            return {
                "symbol": symbol,
                "history": earnings_history[-8:],  # last 8 quarters
                "avg_surprise_pct": round(float(avg_surprise), 1) if avg_surprise else None,
                "beat_rate_pct": round(float(beat_rate), 1) if beat_rate else None,
                "consecutive_beats": cls._count_consecutive_beats(earnings_history),
            }
        except Exception as e:
            logger.debug(f"EarningsHistory {symbol}: {e}")
            return {"symbol": symbol, "history": [], "error": str(e)}

    @staticmethod
    def _count_consecutive_beats(history: List[Dict]) -> int:
        count = 0
        for e in reversed(history):
            if e.get("beat"):
                count += 1
            else:
                break
        return count


# ────────────────────────────────────────────────────────────────────────────
# RBI & MACRO EVENTS
# ────────────────────────────────────────────────────────────────────────────

class RBIEventsCalendar:
    """RBI Monetary Policy Committee (MPC) meeting schedule and decisions"""

    # RBI MPC typically meets 6 times per year (bi-monthly)
    # Known 2025-2026 dates based on RBI schedule patterns
    MPC_SCHEDULE_2025_2026 = [
        {"date": "2025-08-05", "type": "MPC_MEETING", "description": "RBI MPC Meeting - August 2025"},
        {"date": "2025-10-07", "type": "MPC_MEETING", "description": "RBI MPC Meeting - October 2025"},
        {"date": "2025-12-05", "type": "MPC_MEETING", "description": "RBI MPC Meeting - December 2025"},
        {"date": "2026-02-05", "type": "MPC_MEETING", "description": "RBI MPC Meeting - February 2026"},
        {"date": "2026-04-07", "type": "MPC_MEETING", "description": "RBI MPC Meeting - April 2026"},
        {"date": "2026-06-05", "type": "MPC_MEETING", "description": "RBI MPC Meeting - June 2026"},
        {"date": "2026-08-06", "type": "MPC_MEETING", "description": "RBI MPC Meeting - August 2026"},
        {"date": "2026-10-06", "type": "MPC_MEETING", "description": "RBI MPC Meeting - October 2026"},
    ]

    # GST Council meetings (approximate, quarterly)
    GST_SCHEDULE = [
        {"date": "2025-08-02", "type": "GST_COUNCIL", "description": "GST Council Meeting"},
        {"date": "2025-11-01", "type": "GST_COUNCIL", "description": "GST Council Meeting"},
        {"date": "2026-02-01", "type": "GST_COUNCIL", "description": "GST Council Meeting"},
    ]

    # Union Budget
    BUDGET_SCHEDULE = [
        {"date": "2026-02-01", "type": "UNION_BUDGET", "description": "Union Budget 2026-27 Presentation", "importance": "CRITICAL"},
    ]

    @classmethod
    def get_upcoming_macro_events(cls, days_ahead: int = 90) -> List[Dict]:
        today = datetime.now()
        cutoff = today + timedelta(days=days_ahead)
        events = []

        all_events = cls.MPC_SCHEDULE_2025_2026 + cls.GST_SCHEDULE + cls.BUDGET_SCHEDULE
        for evt in all_events:
            try:
                evt_date = datetime.strptime(evt["date"], "%Y-%m-%d")
                if today - timedelta(1) <= evt_date <= cutoff:
                    events.append({
                        **evt,
                        "days_to_event": (evt_date - today).days,
                        "importance": evt.get("importance", "HIGH"),
                    })
            except Exception:
                pass

        # Add US Fed events (approximate)
        fed_events = cls._get_fed_calendar(today, cutoff)
        events.extend(fed_events)

        return sorted(events, key=lambda x: x.get("days_to_event", 999))

    @staticmethod
    def _get_fed_calendar(today: datetime, cutoff: datetime) -> List[Dict]:
        """Approximate Fed FOMC dates"""
        # FOMC meets approximately 8 times per year
        approx_fomc_dates = [
            "2025-07-30", "2025-09-17", "2025-11-07", "2025-12-17",
            "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
            "2026-07-29", "2026-09-16",
        ]
        events = []
        for d_str in approx_fomc_dates:
            try:
                evt_date = datetime.strptime(d_str, "%Y-%m-%d")
                if today - timedelta(1) <= evt_date <= cutoff:
                    events.append({
                        "date": d_str,
                        "type": "FED_FOMC",
                        "description": "US Fed FOMC Meeting - Rate Decision",
                        "days_to_event": (evt_date - today).days,
                        "importance": "HIGH",
                        "impact_on_india": "FII flows, USD/INR, global risk appetite",
                    })
            except Exception:
                pass
        return events

    @classmethod
    def get_economic_data_releases(cls) -> List[Dict]:
        """Upcoming Indian economic data releases"""
        today = datetime.now()
        # Approximate monthly release schedule for India
        events = []

        # CPI India - released around 12th of each month
        # WPI India - released around 14th of each month
        # IIP - released around 12th with 2 month lag
        for month_offset in range(3):
            target = today + timedelta(days=30 * month_offset)
            year = target.year
            month = target.month

            # CPI release: ~12th of month
            cpi_date = datetime(year, month, 12)
            if cpi_date >= today:
                events.append({
                    "date": cpi_date.strftime("%Y-%m-%d"),
                    "type": "INDIA_CPI",
                    "description": f"India CPI Inflation Data - {cpi_date.strftime('%B %Y')}",
                    "days_to_event": (cpi_date - today).days,
                    "importance": "HIGH",
                    "impact": "Monetary policy expectations, rate-sensitive sectors",
                })

            # WPI release: ~14th of month
            wpi_date = datetime(year, month, 14)
            if wpi_date >= today:
                events.append({
                    "date": wpi_date.strftime("%Y-%m-%d"),
                    "type": "INDIA_WPI",
                    "description": f"India WPI Inflation Data - {wpi_date.strftime('%B %Y')}",
                    "days_to_event": (wpi_date - today).days,
                    "importance": "MEDIUM",
                })

            # IIP: ~12th with 2 month lag
            iip_date = datetime(year, month, 12)
            if iip_date >= today:
                lag_month = (month - 2) if month > 2 else (12 + month - 2)
                events.append({
                    "date": iip_date.strftime("%Y-%m-%d"),
                    "type": "INDIA_IIP",
                    "description": f"India IIP Industrial Production - {iip_date.strftime('%B %Y')}",
                    "days_to_event": (iip_date - today).days,
                    "importance": "MEDIUM",
                })

        # GDP quarterly (every 3 months, released with lag)
        for quarter_offset in range(2):
            # GDP released ~28th of month after quarter end
            q_month = ((today.month - 1) // 3 + 1 + quarter_offset) * 3
            if q_month > 12:
                q_month -= 12
            release_month = (q_month % 12) + 2
            release_year = today.year + (1 if release_month < today.month else 0)
            gdp_date = datetime(release_year, max(1, min(12, release_month)), 28)
            if gdp_date >= today:
                events.append({
                    "date": gdp_date.strftime("%Y-%m-%d"),
                    "type": "INDIA_GDP",
                    "description": "India GDP Quarterly Data",
                    "days_to_event": (gdp_date - today).days,
                    "importance": "CRITICAL",
                    "impact": "Market sentiment, all sectors",
                })

        return sorted(events, key=lambda x: x.get("days_to_event", 999))


# ────────────────────────────────────────────────────────────────────────────
# DIVIDEND & CORPORATE EVENT TRACKER
# ────────────────────────────────────────────────────────────────────────────

class DividendTracker:
    """Track dividend income opportunities"""

    @classmethod
    def get_high_yield_upcoming(cls, min_yield: float = 1.5) -> List[Dict]:
        """Upcoming ex-dividend dates for high yield stocks"""
        nse_client = NSECalendarClient()
        corp_actions = NSECalendarClient.get_corporate_actions()
        today = datetime.now()

        results = []
        for action in corp_actions:
            purpose = (action.get("action_type") or "").lower()
            if "div" not in purpose and "interim" not in purpose:
                continue

            ex_date_str = action.get("ex_date", "")
            try:
                ex_date = datetime.strptime(ex_date_str, "%d-%b-%Y")
            except Exception:
                continue

            days_to = (ex_date - today).days
            if days_to < -5 or days_to > 60:
                continue

            sym = action.get("symbol", "")
            # Try to get dividend amount from remarks
            remarks = action.get("remarks", "")
            div_amount = cls._parse_dividend_amount(remarks)

            # Get current price for yield calculation
            try:
                ticker = yf.Ticker(f"{sym}.NS")
                price = ticker.info.get("regularMarketPrice", 0)
                div_yield = (div_amount / price * 100) if (div_amount and price > 0) else None
            except Exception:
                price = None
                div_yield = None

            if min_yield and div_yield and div_yield < min_yield:
                continue

            results.append({
                "symbol": sym,
                "company": action.get("company", ""),
                "action_type": purpose.upper(),
                "ex_date": ex_date.strftime("%Y-%m-%d"),
                "days_to_ex_date": days_to,
                "record_date": action.get("record_date", ""),
                "dividend_amount": div_amount,
                "current_price": price,
                "dividend_yield_pct": round(div_yield, 2) if div_yield else None,
                "remarks": remarks,
            })

        return sorted(results, key=lambda x: x["days_to_ex_date"])

    @staticmethod
    def _parse_dividend_amount(remarks: str) -> Optional[float]:
        if not remarks:
            return None
        patterns = [
            r"rs\.?\s*([\d.]+)",
            r"₹\s*([\d.]+)",
            r"inr\s*([\d.]+)",
            r"([\d.]+)\s*per\s*share",
            r"([\d.]+)\s*ps",
        ]
        for pattern in patterns:
            match = re.search(pattern, remarks.lower())
            if match:
                try:
                    return float(match.group(1))
                except Exception:
                    pass
        return None


# ────────────────────────────────────────────────────────────────────────────
# IPO CALENDAR
# ────────────────────────────────────────────────────────────────────────────

class IPOCalendar:
    """IPO pipeline and listing data"""

    @classmethod
    def get_upcoming_ipos(cls) -> List[Dict]:
        """Fetch upcoming IPO data from NSE"""
        try:
            session = NSECalendarClient._get_session()
            r = session.get("https://www.nseindia.com/api/ipo-current", timeout=10)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    return [{
                        "company": ipo.get("companyName", ""),
                        "open_date": ipo.get("openDate", ""),
                        "close_date": ipo.get("closeDate", ""),
                        "issue_price_min": ipo.get("minBidPrice"),
                        "issue_price_max": ipo.get("maxBidPrice"),
                        "lot_size": ipo.get("bidLot"),
                        "issue_size": ipo.get("totalIssueSize"),
                        "listing_date": ipo.get("listingDate", ""),
                        "category": "MAINBOARD",
                    } for ipo in data]
        except Exception as e:
            logger.debug(f"IPO fetch: {e}")

        return []

    @classmethod
    def get_recent_listings(cls) -> List[Dict]:
        """Recently listed IPOs with listing day performance"""
        try:
            session = NSECalendarClient._get_session()
            r = session.get("https://www.nseindia.com/api/ipo-recent", timeout=10)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    return [{
                        "company": ipo.get("companyName", ""),
                        "symbol": ipo.get("symbol", ""),
                        "listing_date": ipo.get("listingDate", ""),
                        "issue_price": ipo.get("issuePrice"),
                        "listing_price": ipo.get("listingPrice"),
                        "listing_gain_pct": cls._calc_gain(ipo.get("issuePrice"), ipo.get("listingPrice")),
                        "current_price": ipo.get("lastPrice"),
                        "gain_from_issue": cls._calc_gain(ipo.get("issuePrice"), ipo.get("lastPrice")),
                    } for ipo in data]
        except Exception as e:
            logger.debug(f"Recent listings: {e}")
        return []

    @staticmethod
    def _calc_gain(issue: Any, current: Any) -> Optional[float]:
        try:
            issue_f = float(issue)
            current_f = float(current)
            if issue_f > 0:
                return round((current_f / issue_f - 1) * 100, 2)
        except Exception:
            pass
        return None


# ────────────────────────────────────────────────────────────────────────────
# NIFTY INDEX RECONSTITUTION TRACKER
# ────────────────────────────────────────────────────────────────────────────

class IndexReconstitutionTracker:
    """Track NIFTY index changes — inclusions/exclusions create trading opportunities"""

    @classmethod
    def get_rebalance_schedule(cls) -> List[Dict]:
        """NIFTY 50/100/Midcap rebalance schedule (semi-annual)"""
        today = datetime.now()
        # NSE rebalances NIFTY indices semi-annually in March and September
        rebalance_dates = []
        for year in [today.year, today.year + 1]:
            # March rebalance (effective last Friday of March / first Friday of April)
            march_date = datetime(year, 3, 28)
            while march_date.weekday() != 4:
                march_date += timedelta(1)
            if march_date >= today:
                rebalance_dates.append({
                    "date": march_date.strftime("%Y-%m-%d"),
                    "type": "INDEX_REBALANCE",
                    "description": f"NIFTY Semi-Annual Rebalance - March {year}",
                    "indices": ["NIFTY 50", "NIFTY NEXT 50", "NIFTY 100", "NIFTY 200", "NIFTY 500"],
                    "days_to_event": (march_date - today).days,
                    "importance": "HIGH",
                    "opportunity": "Stocks being added see forced buying from index funds; removed stocks see selling",
                })

            # September rebalance
            sep_date = datetime(year, 9, 26)
            while sep_date.weekday() != 4:
                sep_date += timedelta(1)
            if sep_date >= today:
                rebalance_dates.append({
                    "date": sep_date.strftime("%Y-%m-%d"),
                    "type": "INDEX_REBALANCE",
                    "description": f"NIFTY Semi-Annual Rebalance - September {year}",
                    "indices": ["NIFTY 50", "NIFTY NEXT 50", "NIFTY 100", "NIFTY 200", "NIFTY 500"],
                    "days_to_event": (sep_date - today).days,
                    "importance": "HIGH",
                    "opportunity": "Stocks being added see forced buying from index funds; removed stocks see selling",
                })

        return sorted(rebalance_dates, key=lambda x: x["days_to_event"])[:4]


# ────────────────────────────────────────────────────────────────────────────
# MARKET EVENTS AGGREGATOR
# ────────────────────────────────────────────────────────────────────────────

class MarketEventsCalendar:
    """Master calendar aggregating all market events"""

    _cache: Dict[str, Any] = {}
    _cache_ts: Dict[str, float] = {}

    @classmethod
    def get_full_calendar(cls, days_ahead: int = 30) -> Dict[str, Any]:
        key = f"full_calendar_{days_ahead}"
        if key in cls._cache and (time.time() - cls._cache_ts.get(key, 0)) < 1800:
            return cls._cache[key]

        today = datetime.now()
        all_events = []

        # RBI and macro events
        try:
            macro_events = RBIEventsCalendar.get_upcoming_macro_events(days_ahead)
            all_events.extend(macro_events)
        except Exception as e:
            logger.debug(f"Macro events: {e}")

        # Economic data releases
        try:
            economic_events = RBIEventsCalendar.get_economic_data_releases()
            upcoming_eco = [e for e in economic_events if 0 <= e.get("days_to_event", 999) <= days_ahead]
            all_events.extend(upcoming_eco)
        except Exception as e:
            logger.debug(f"Economic events: {e}")

        # F&O expiry
        try:
            fno_expiries = NSECalendarClient.get_fno_expiry_dates()
            for exp in fno_expiries.get("weekly", [])[:4]:
                exp["type"] = "FNO_EXPIRY"
                exp["description"] = f"F&O Weekly Expiry - {exp.get('date', '')}"
                exp["importance"] = "MEDIUM"
                all_events.append(exp)
            for exp in fno_expiries.get("monthly", [])[:2]:
                exp["type"] = "FNO_MONTHLY_EXPIRY"
                exp["description"] = f"F&O Monthly Expiry - {exp.get('month', '')}"
                exp["importance"] = "HIGH"
                all_events.append(exp)
        except Exception as e:
            logger.debug(f"F&O expiry: {e}")

        # Corporate actions (ex-dividends)
        try:
            dividends = DividendTracker.get_high_yield_upcoming(min_yield=1.0)
            for div in dividends[:15]:
                all_events.append({
                    "date": div.get("ex_date", ""),
                    "type": "EX_DIVIDEND",
                    "description": f"{div.get('company', div.get('symbol'))} Ex-Dividend",
                    "days_to_event": div.get("days_to_ex_date", 999),
                    "importance": "LOW",
                    "details": div,
                })
        except Exception as e:
            logger.debug(f"Dividends: {e}")

        # Trading holidays
        try:
            holidays = NSECalendarClient.get_trading_holidays()
            today_year = today.year
            for h in holidays:
                try:
                    h_date = datetime.strptime(h.get("date", ""), "%d-%b-%Y")
                    if today <= h_date <= today + timedelta(days=days_ahead):
                        all_events.append({
                            "date": h_date.strftime("%Y-%m-%d"),
                            "type": "MARKET_HOLIDAY",
                            "description": f"Market Holiday: {h.get('description', '')}",
                            "days_to_event": (h_date - today).days,
                            "importance": "HIGH",
                        })
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Holidays: {e}")

        # Index rebalance
        try:
            rebalances = IndexReconstitutionTracker.get_rebalance_schedule()
            for r in rebalances:
                if r.get("days_to_event", 999) <= days_ahead:
                    all_events.append(r)
        except Exception as e:
            logger.debug(f"Rebalance: {e}")

        # Upcoming IPOs
        try:
            ipos = IPOCalendar.get_upcoming_ipos()
            for ipo in ipos[:5]:
                today_str = today.strftime("%Y-%m-%d")
                all_events.append({
                    "date": ipo.get("open_date", ""),
                    "type": "IPO_OPEN",
                    "description": f"IPO Opens: {ipo.get('company', '')}",
                    "days_to_event": 0,
                    "importance": "MEDIUM",
                    "details": ipo,
                })
        except Exception as e:
            logger.debug(f"IPOs: {e}")

        # Deduplicate events by (date, type, description)
        seen_keys = set()
        deduped_events = []
        for evt in all_events:
            key = (evt.get("date", ""), evt.get("type", ""), evt.get("description", ""))
            if key not in seen_keys:
                seen_keys.add(key)
                deduped_events.append(evt)
        all_events = deduped_events

        # Sort all events
        all_events_sorted = sorted(
            [e for e in all_events if isinstance(e.get("days_to_event"), (int, float)) and e["days_to_event"] >= 0],
            key=lambda x: x.get("days_to_event", 999)
        )

        # Group by date
        grouped = {}
        for evt in all_events_sorted:
            date_key = evt.get("date", "unknown")
            grouped.setdefault(date_key, []).append(evt)

        result = {
            "events": all_events_sorted,
            "grouped_by_date": grouped,
            "total_events": len(all_events_sorted),
            "critical_events": [e for e in all_events_sorted if e.get("importance") == "CRITICAL"],
            "next_7_days": [e for e in all_events_sorted if 0 <= e.get("days_to_event", 999) <= 7],
            "generated_at": datetime.now().isoformat(),
        }

        cls._cache[key] = result
        cls._cache_ts[key] = time.time()
        return result

    @classmethod
    def get_stock_events(cls, symbol: str) -> Dict[str, Any]:
        """All upcoming events for a specific stock"""
        try:
            # Earnings
            earnings = EarningsCalendar.get_historical_earnings(symbol)
            upcoming_earnings = EarningsCalendar.get_earnings_dates([symbol])

            # Corporate actions
            corp_actions = NSECalendarClient.get_corporate_actions(symbol)
            today = datetime.now()
            upcoming_actions = []
            for action in corp_actions:
                ex_date_str = action.get("ex_date", "")
                try:
                    ex_date = datetime.strptime(ex_date_str, "%d-%b-%Y")
                    if ex_date >= today - timedelta(1):
                        action["days_to_event"] = (ex_date - today).days
                        upcoming_actions.append(action)
                except Exception:
                    pass

            return {
                "symbol": symbol,
                "earnings": {
                    "upcoming": upcoming_earnings[0] if upcoming_earnings else None,
                    "history": earnings.get("history", []),
                    "avg_surprise": earnings.get("avg_surprise_pct"),
                    "beat_rate": earnings.get("beat_rate_pct"),
                    "consecutive_beats": earnings.get("consecutive_beats", 0),
                },
                "corporate_actions": sorted(upcoming_actions, key=lambda x: x.get("days_to_event", 999))[:10],
            }
        except Exception as e:
            logger.error(f"Stock events {symbol}: {e}")
            return {"symbol": symbol, "error": str(e)}
