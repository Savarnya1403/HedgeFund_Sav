"""
Deep Fundamental Analysis Engine for Indian Listed Companies
Piotroski F-Score, Altman Z-Score, Beneish M-Score, DuPont, DCF, ROIC,
Working Capital Analysis, Quality Scoring, Comparable Valuation
Primary: yfinance | Secondary: Screener.in scraping
"""
from __future__ import annotations

import logging
import time
import warnings
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

try:
    import yfinance as yf
except ImportError:
    yf = None  # type: ignore

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────────

NIFTY100_PEERS: Dict[str, List[str]] = {
    "IT": ["TCS", "INFY", "HCLTECH", "WIPRO", "TECHM", "LTIM", "MPHASIS", "PERSISTENT"],
    "BANKING": ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "INDUSINDBK", "BANKBARODA", "PNB"],
    "PHARMA": ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "LUPIN", "AUROPHARMA", "BIOCON", "TORNTPHARM"],
    "FMCG": ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR", "MARICO", "COLPAL", "GODREJCP"],
    "AUTO": ["MARUTI", "TATAMOTORS", "BAJAJ-AUTO", "EICHERMOT", "HEROMOTOCO", "TVSMOTOR", "M&M", "ASHOKLEY"],
    "ENERGY": ["RELIANCE", "ONGC", "BPCL", "IOC", "GAIL", "POWERGRID", "NTPC", "COALINDIA"],
    "METALS": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "SAIL", "NMDC", "NATIONALUM", "HINDCOPPER"],
    "CEMENT": ["ULTRACEMCO", "GRASIM", "SHREECEM", "AMBUJACEM", "ACC", "DALMIACEMEN"],
    "INFRA": ["LT", "ADANIPORTS", "DLF", "SIEMENS", "ABB", "HAVELLS", "BHEL"],
    "NBFC": ["BAJFINANCE", "BAJAJFINSV", "CHOLAFIN", "MUTHOOTFIN", "LICHSGFIN"],
    "INSURANCE": ["HDFCLIFE", "SBILIFE", "ICICIGI", "NIACL"],
    "RETAIL": ["DMART", "TRENT", "VMART"],
    "CONSUMER": ["TITAN", "ASIANPAINT", "PIDILITIND", "BERGEPAINT", "KANSAINER"],
    "TELECOM": ["BHARTIARTL", "IDEA"],
}

SECTOR_MAP: Dict[str, str] = {
    "TCS": "IT", "INFY": "IT", "HCLTECH": "IT", "WIPRO": "IT", "TECHM": "IT",
    "LTIM": "IT", "MPHASIS": "IT", "PERSISTENT": "IT",
    "HDFCBANK": "BANKING", "ICICIBANK": "BANKING", "SBIN": "BANKING",
    "KOTAKBANK": "BANKING", "AXISBANK": "BANKING", "INDUSINDBK": "BANKING",
    "SUNPHARMA": "PHARMA", "DRREDDY": "PHARMA", "CIPLA": "PHARMA",
    "DIVISLAB": "PHARMA", "LUPIN": "PHARMA",
    "HINDUNILVR": "FMCG", "ITC": "FMCG", "NESTLEIND": "FMCG",
    "BRITANNIA": "FMCG", "DABUR": "FMCG", "MARICO": "FMCG",
    "MARUTI": "AUTO", "TATAMOTORS": "AUTO", "EICHERMOT": "AUTO",
    "HEROMOTOCO": "AUTO", "TVSMOTOR": "AUTO",
    "RELIANCE": "ENERGY", "ONGC": "ENERGY", "BPCL": "ENERGY", "NTPC": "ENERGY",
    "TATASTEEL": "METALS", "JSWSTEEL": "METALS", "HINDALCO": "METALS",
    "BAJFINANCE": "NBFC", "BAJAJFINSV": "NBFC", "CHOLAFIN": "NBFC",
    "LT": "INFRA", "ADANIPORTS": "INFRA", "DLF": "INFRA",
    "ULTRACEMCO": "CEMENT", "GRASIM": "CEMENT", "SHREECEM": "CEMENT",
    "HDFCLIFE": "INSURANCE", "SBILIFE": "INSURANCE",
    "TITAN": "CONSUMER", "ASIANPAINT": "CONSUMER", "PIDILITIND": "CONSUMER",
    "BHARTIARTL": "TELECOM",
}

BANKING_SECTORS = {"BANKING", "NBFC", "INSURANCE"}

_CACHE: Dict[str, Tuple[float, Any]] = {}
_CACHE_TTL = 3600  # seconds


def _cache_get(key: str) -> Optional[Any]:
    if key in _CACHE:
        ts, val = _CACHE[key]
        if time.time() - ts < _CACHE_TTL:
            return val
    return None


def _cache_set(key: str, val: Any) -> None:
    _CACHE[key] = (time.time(), val)


def _safe(val: Any, default: float = 0.0) -> float:
    """Safely convert a value to float, returning default if not possible."""
    try:
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return default
        return float(val)
    except Exception:
        return default


def _get_ticker_data(symbol: str) -> Tuple[Any, Dict, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Fetch yfinance Ticker and core financial statements."""
    ticker = yf.Ticker(f"{symbol}.NS")
    info = ticker.info or {}
    try:
        fin = ticker.financials
    except Exception:
        fin = pd.DataFrame()
    try:
        bs = ticker.balance_sheet
    except Exception:
        bs = pd.DataFrame()
    try:
        cf = ticker.cashflow
    except Exception:
        cf = pd.DataFrame()
    return ticker, info, fin, bs, cf


def _row(df: pd.DataFrame, *keys: str) -> pd.Series:
    """Find a row in a DataFrame by trying multiple possible key names."""
    if df is None or df.empty:
        return pd.Series(dtype=float)
    for key in keys:
        if key in df.index:
            return df.loc[key].astype(float)
    # Case-insensitive search
    lower_keys = {k.lower(): k for k in df.index}
    for key in keys:
        if key.lower() in lower_keys:
            return df.loc[lower_keys[key.lower()]].astype(float)
    return pd.Series(dtype=float)


def _col_val(series: pd.Series, col_idx: int = 0) -> float:
    """Get value at column index from a series (most recent = 0)."""
    if series is None or len(series) == 0:
        return 0.0
    cols = series.dropna()
    if len(cols) <= col_idx:
        return 0.0
    return _safe(cols.iloc[col_idx])


# ──────────────────────────────────────────────────────────────────
# SCREENER SCRAPER
# ──────────────────────────────────────────────────────────────────

class ScreenerScraper:
    """Scrape financial data from Screener.in for Indian-specific metrics."""

    BASE_URL = "https://www.screener.in/company/{symbol}/"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def _fetch_page(self, symbol: str) -> Optional[BeautifulSoup]:
        cache_key = f"screener_page_{symbol}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached
        try:
            url = self.BASE_URL.format(symbol=symbol)
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                _cache_set(cache_key, soup)
                return soup
            logger.warning("Screener returned %d for %s", resp.status_code, symbol)
        except Exception as exc:
            logger.warning("Screener fetch failed for %s: %s", symbol, exc)
        return None

    def _parse_number(self, text: str) -> Optional[float]:
        """Parse Indian number format (₹, Cr, L) to float."""
        if not text:
            return None
        text = text.strip().replace(",", "").replace("₹", "").replace("%", "")
        text = text.replace("Cr", "e7").replace("L", "e5")
        try:
            return float(text)
        except ValueError:
            return None

    def get_financial_data(self, symbol: str) -> Dict:
        """Fetch and parse 10-year financial data, ratios, and key metrics."""
        cache_key = f"screener_fin_{symbol}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        soup = self._fetch_page(symbol)
        if soup is None:
            return {"error": "Could not fetch Screener.in data", "symbol": symbol}

        result: Dict[str, Any] = {"symbol": symbol, "source": "screener.in"}

        # ── Ratios section ──
        ratios: Dict[str, Any] = {}
        try:
            ratio_ul = soup.find("ul", {"id": "top-ratios"})
            if ratio_ul:
                for li in ratio_ul.find_all("li"):
                    name_el = li.find("span", {"class": "name"})
                    val_el = li.find("span", {"class": "value"})
                    if name_el and val_el:
                        key = name_el.get_text(strip=True)
                        val = val_el.get_text(strip=True)
                        ratios[key] = val
        except Exception as exc:
            logger.debug("Ratio parse error: %s", exc)

        result["ratios_raw"] = ratios

        # Map common ratio names
        roe_keys = ["ROE", "Return on Equity", "Return on equity"]
        roce_keys = ["ROCE", "Return on capital employed"]
        de_keys = ["Debt to equity", "D/E Ratio", "Debt / Equity"]
        cr_keys = ["Current ratio", "Current Ratio"]
        pe_keys = ["PE Ratio", "Price to Earning", "P/E"]
        pb_keys = ["Price to Book value", "P/B Ratio", "PB Ratio"]

        def find_ratio(keys: List[str]) -> Optional[str]:
            for k in keys:
                if k in ratios:
                    return ratios[k]
            return None

        result["roe"] = find_ratio(roe_keys)
        result["roce"] = find_ratio(roce_keys)
        result["debt_to_equity"] = find_ratio(de_keys)
        result["current_ratio"] = find_ratio(cr_keys)
        result["pe_ratio"] = find_ratio(pe_keys)
        result["pb_ratio"] = find_ratio(pb_keys)

        # ── Annual P&L Table ──
        annual_data: Dict[str, List] = {}
        try:
            pl_section = soup.find("section", {"id": "profit-loss"})
            if pl_section:
                table = pl_section.find("table")
                if table:
                    headers_row = table.find("thead")
                    years: List[str] = []
                    if headers_row:
                        for th in headers_row.find_all("th"):
                            txt = th.get_text(strip=True)
                            if txt and txt != "":
                                years.append(txt)

                    for tr in table.find("tbody").find_all("tr"):
                        cells = tr.find_all("td")
                        if len(cells) > 1:
                            row_name = cells[0].get_text(strip=True)
                            values = []
                            for cell in cells[1:]:
                                txt = cell.get_text(strip=True)
                                values.append(self._parse_number(txt))
                            annual_data[row_name] = values

                    result["annual_years"] = years
                    result["annual_pl"] = annual_data
        except Exception as exc:
            logger.debug("Annual P&L parse error: %s", exc)

        # Extract key financials
        revenue_row = annual_data.get("Sales", annual_data.get("Revenue", []))
        profit_row = annual_data.get("Net Profit", annual_data.get("PAT", []))
        eps_row = annual_data.get("EPS in Rs", annual_data.get("EPS", []))

        result["revenue_history"] = [v for v in revenue_row if v is not None]
        result["profit_history"] = [v for v in profit_row if v is not None]
        result["eps_history"] = [v for v in eps_row if v is not None]

        # ── Balance Sheet Key Items ──
        try:
            bs_section = soup.find("section", {"id": "balance-sheet"})
            bs_data: Dict[str, List] = {}
            if bs_section:
                table = bs_section.find("table")
                if table and table.find("tbody"):
                    for tr in table.find("tbody").find_all("tr"):
                        cells = tr.find_all("td")
                        if len(cells) > 1:
                            row_name = cells[0].get_text(strip=True)
                            values = [self._parse_number(c.get_text(strip=True)) for c in cells[1:]]
                            bs_data[row_name] = values
            result["balance_sheet_data"] = bs_data
        except Exception as exc:
            logger.debug("Balance sheet parse error: %s", exc)

        # ── Cash Flow ──
        try:
            cf_section = soup.find("section", {"id": "cash-flow"})
            cf_data: Dict[str, List] = {}
            if cf_section:
                table = cf_section.find("table")
                if table and table.find("tbody"):
                    for tr in table.find("tbody").find_all("tr"):
                        cells = tr.find_all("td")
                        if len(cells) > 1:
                            row_name = cells[0].get_text(strip=True)
                            values = [self._parse_number(c.get_text(strip=True)) for c in cells[1:]]
                            cf_data[row_name] = values
            result["cash_flow_data"] = cf_data
        except Exception as exc:
            logger.debug("Cash flow parse error: %s", exc)

        _cache_set(cache_key, result)
        return result

    def get_quarterly_results(self, symbol: str) -> List[Dict]:
        """Fetch last 8 quarters of financial results."""
        cache_key = f"screener_qtr_{symbol}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        soup = self._fetch_page(symbol)
        if soup is None:
            return []

        quarters: List[Dict] = []
        try:
            qtr_section = soup.find("section", {"id": "quarters"})
            if qtr_section:
                table = qtr_section.find("table")
                if table:
                    headers_row = table.find("thead")
                    qtr_labels: List[str] = []
                    if headers_row:
                        for th in headers_row.find_all("th"):
                            txt = th.get_text(strip=True)
                            if txt:
                                qtr_labels.append(txt)

                    rows_data: Dict[str, List] = {}
                    if table.find("tbody"):
                        for tr in table.find("tbody").find_all("tr"):
                            cells = tr.find_all("td")
                            if len(cells) > 1:
                                row_name = cells[0].get_text(strip=True)
                                values = [self._parse_number(c.get_text(strip=True)) for c in cells[1:]]
                                rows_data[row_name] = values

                    # Transpose into list of quarter dicts (last 8)
                    num_qtrs = min(8, len(qtr_labels) - 1)
                    for i in range(num_qtrs):
                        q: Dict[str, Any] = {"quarter": qtr_labels[i + 1] if i + 1 < len(qtr_labels) else f"Q{i+1}"}
                        for metric, vals in rows_data.items():
                            if i < len(vals):
                                q[metric] = vals[i]
                        quarters.append(q)
        except Exception as exc:
            logger.debug("Quarterly parse error: %s", exc)

        _cache_set(cache_key, quarters)
        return quarters


# ──────────────────────────────────────────────────────────────────
# PIOTROSKI F-SCORE
# ──────────────────────────────────────────────────────────────────

class PiotroskiFScore:
    """
    9-point Piotroski F-Score assessing financial strength.
    Score 8-9: Strong, 5-7: Neutral, 0-4: Weak
    """

    def calculate(self, symbol: str) -> Dict:
        cache_key = f"piotroski_{symbol}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            ticker, info, fin, bs, cf = _get_ticker_data(symbol)
        except Exception as exc:
            return {"error": str(exc), "symbol": symbol}

        criteria: Dict[str, Any] = {}
        score = 0
        failed: List[str] = []

        try:
            # ── Profitability ──
            net_income = _row(fin, "Net Income", "Net Income From Continuing Operations")
            total_assets = _row(bs, "Total Assets")
            cfo = _row(cf, "Operating Cash Flow", "Total Cash From Operating Activities",
                       "Cash Flow From Continuing Operating Activities")

            ni_curr = _col_val(net_income, 0)
            ni_prev = _col_val(net_income, 1)
            ta_curr = _col_val(total_assets, 0)
            ta_prev = _col_val(total_assets, 1)
            cfo_curr = _col_val(cfo, 0)

            # F1: ROA > 0
            roa_curr = ni_curr / ta_curr if ta_curr != 0 else 0.0
            f1 = 1 if roa_curr > 0 else 0
            criteria["F1_ROA_positive"] = {
                "score": f1, "value": round(roa_curr, 4),
                "description": "ROA > 0 (profitable)"
            }
            score += f1
            if f1 == 0:
                failed.append("F1: ROA negative")

            # F2: Operating Cash Flow > 0
            f2 = 1 if cfo_curr > 0 else 0
            criteria["F2_CFO_positive"] = {
                "score": f2, "value": round(cfo_curr / 1e7, 2),
                "description": "Operating cash flow > 0"
            }
            score += f2
            if f2 == 0:
                failed.append("F2: CFO negative")

            # F3: ROA improving
            roa_prev = ni_prev / ta_prev if ta_prev != 0 else 0.0
            f3 = 1 if roa_curr > roa_prev else 0
            criteria["F3_ROA_improving"] = {
                "score": f3,
                "current_roa": round(roa_curr, 4),
                "prev_roa": round(roa_prev, 4),
                "description": "ROA improving YoY"
            }
            score += f3
            if f3 == 0:
                failed.append("F3: ROA declining")

            # F4: Accruals (quality of earnings) — lower is better
            accruals = (ni_curr - cfo_curr) / ta_curr if ta_curr != 0 else 0.0
            f4 = 1 if accruals < 0 else 0
            criteria["F4_accruals"] = {
                "score": f4, "value": round(accruals, 4),
                "description": "Accruals < 0 (cash earnings quality)"
            }
            score += f4
            if f4 == 0:
                failed.append("F4: High accruals (earnings quality concern)")

            # ── Leverage / Liquidity ──
            lt_debt = _row(bs, "Long Term Debt", "Long-Term Debt", "Long Term Debt And Capital Lease Obligation")
            curr_assets = _row(bs, "Current Assets", "Total Current Assets")
            curr_liab = _row(bs, "Current Liabilities", "Total Current Liabilities",
                             "Current Liabilities And Short Term Debt")
            shares = _row(bs, "Share Issued", "Common Stock Shares Outstanding")

            ltd_curr = _col_val(lt_debt, 0)
            ltd_prev = _col_val(lt_debt, 1)
            ca_curr = _col_val(curr_assets, 0)
            ca_prev = _col_val(curr_assets, 1)
            cl_curr = _col_val(curr_liab, 0)
            cl_prev = _col_val(curr_liab, 1)

            # F5: Long-term debt ratio decreasing
            ldr_curr = ltd_curr / ta_curr if ta_curr != 0 else 0.0
            ldr_prev = ltd_prev / ta_prev if ta_prev != 0 else 0.0
            f5 = 1 if ldr_curr <= ldr_prev else 0
            criteria["F5_leverage_decreasing"] = {
                "score": f5,
                "current_ldr": round(ldr_curr, 4),
                "prev_ldr": round(ldr_prev, 4),
                "description": "Long-term debt ratio not increasing"
            }
            score += f5
            if f5 == 0:
                failed.append("F5: Leverage increasing")

            # F6: Current ratio improving
            cr_curr = ca_curr / cl_curr if cl_curr != 0 else 0.0
            cr_prev = ca_prev / cl_prev if cl_prev != 0 else 0.0
            f6 = 1 if cr_curr > cr_prev else 0
            criteria["F6_current_ratio_improving"] = {
                "score": f6,
                "current_cr": round(cr_curr, 4),
                "prev_cr": round(cr_prev, 4),
                "description": "Current ratio improving YoY"
            }
            score += f6
            if f6 == 0:
                failed.append("F6: Liquidity deteriorating")

            # F7: No share dilution
            sh_curr = _col_val(shares, 0)
            sh_prev = _col_val(shares, 1)
            # Also try info
            if sh_curr == 0:
                sh_curr = _safe(info.get("sharesOutstanding", 0))
            f7 = 1 if sh_curr <= sh_prev or sh_prev == 0 else 0
            criteria["F7_no_dilution"] = {
                "score": f7,
                "shares_current": sh_curr,
                "shares_prev": sh_prev,
                "description": "No share dilution"
            }
            score += f7
            if f7 == 0:
                failed.append("F7: Share dilution occurred")

            # ── Operating Efficiency ──
            revenue = _row(fin, "Total Revenue", "Revenue")
            cogs = _row(fin, "Cost Of Revenue", "Cost of Goods Sold",
                        "Reconciled Cost Of Revenue")
            gross_profit = _row(fin, "Gross Profit")

            rev_curr = _col_val(revenue, 0)
            rev_prev = _col_val(revenue, 1)
            gp_curr = _col_val(gross_profit, 0)
            gp_prev = _col_val(gross_profit, 1)

            # F8: Gross margin improving
            gm_curr = gp_curr / rev_curr if rev_curr != 0 else 0.0
            gm_prev = gp_prev / rev_prev if rev_prev != 0 else 0.0
            f8 = 1 if gm_curr > gm_prev else 0
            criteria["F8_gross_margin_improving"] = {
                "score": f8,
                "current_gm": round(gm_curr, 4),
                "prev_gm": round(gm_prev, 4),
                "description": "Gross margin improving YoY"
            }
            score += f8
            if f8 == 0:
                failed.append("F8: Gross margin declining")

            # F9: Asset turnover improving
            at_curr = rev_curr / ta_curr if ta_curr != 0 else 0.0
            at_prev = rev_prev / ta_prev if ta_prev != 0 else 0.0
            f9 = 1 if at_curr > at_prev else 0
            criteria["F9_asset_turnover_improving"] = {
                "score": f9,
                "current_at": round(at_curr, 4),
                "prev_at": round(at_prev, 4),
                "description": "Asset turnover improving YoY"
            }
            score += f9
            if f9 == 0:
                failed.append("F9: Asset turnover declining")

        except Exception as exc:
            logger.warning("Piotroski calculation error for %s: %s", symbol, exc)
            return {"error": str(exc), "symbol": symbol, "score": score}

        if score >= 8:
            interpretation = "Strong"
        elif score >= 5:
            interpretation = "Neutral"
        else:
            interpretation = "Weak"

        result = {
            "symbol": symbol,
            "score": score,
            "max_score": 9,
            "interpretation": interpretation,
            "criteria": criteria,
            "failed_criteria": failed,
            "signal": "BUY" if score >= 7 else ("HOLD" if score >= 5 else "AVOID"),
        }
        _cache_set(cache_key, result)
        return result


# ──────────────────────────────────────────────────────────────────
# ALTMAN Z-SCORE
# ──────────────────────────────────────────────────────────────────

class AltmanZScore:
    """
    Original Altman Z-Score for public companies.
    Z'' model for banking/financial companies.
    """

    def calculate(self, symbol: str) -> Dict:
        cache_key = f"altman_{symbol}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            ticker, info, fin, bs, cf = _get_ticker_data(symbol)
        except Exception as exc:
            return {"error": str(exc), "symbol": symbol}

        is_bank = SECTOR_MAP.get(symbol, "") in BANKING_SECTORS
        sector = SECTOR_MAP.get(symbol, "Unknown")

        try:
            net_income = _row(fin, "Net Income", "Net Income From Continuing Operations")
            total_assets = _row(bs, "Total Assets")
            revenue = _row(fin, "Total Revenue", "Revenue")
            curr_assets = _row(bs, "Current Assets", "Total Current Assets")
            curr_liab = _row(bs, "Current Liabilities", "Total Current Liabilities",
                             "Current Liabilities And Short Term Debt")
            total_equity = _row(bs, "Stockholders Equity", "Total Equity Gross Minority Interest",
                                "Common Stock Equity")
            retained_earnings = _row(bs, "Retained Earnings")
            ebit_row = _row(fin, "EBIT", "Operating Income", "Operating Income Loss")
            total_debt = _row(bs, "Total Debt", "Long Term Debt And Capital Lease Obligation")

            ta = _col_val(total_assets, 0)
            if ta == 0:
                return {"error": "No total assets data", "symbol": symbol}

            wc = _col_val(curr_assets, 0) - _col_val(curr_liab, 0)
            re = _col_val(retained_earnings, 0)
            ebit = _col_val(ebit_row, 0)
            rev = _col_val(revenue, 0)
            market_cap = _safe(info.get("marketCap", 0))
            total_liab = ta - _col_val(total_equity, 0)

            T1 = wc / ta if ta else 0.0
            T2 = re / ta if ta else 0.0
            T3 = ebit / ta if ta else 0.0
            T4 = market_cap / total_liab if total_liab != 0 else 0.0
            T5 = rev / ta if ta else 0.0

            if not is_bank:
                # Original Altman Z-Score
                z_score = 1.2 * T1 + 1.4 * T2 + 3.3 * T3 + 0.6 * T4 + 1.0 * T5

                if z_score > 2.99:
                    zone = "Safe Zone"
                    distress_prob = "Low"
                    color = "green"
                elif z_score > 1.81:
                    zone = "Grey Zone"
                    distress_prob = "Moderate"
                    color = "yellow"
                else:
                    zone = "Distress Zone"
                    distress_prob = "High"
                    color = "red"

                model = "Original Altman Z-Score (Public Companies)"
                thresholds = {"safe": 2.99, "grey_upper": 2.99, "grey_lower": 1.81, "distress": 1.81}
            else:
                # Altman Z'' model for non-manufacturing / financial companies
                z_score = 6.56 * T1 + 3.26 * T2 + 6.72 * T3 + 1.05 * T4

                if z_score > 2.6:
                    zone = "Safe Zone"
                    distress_prob = "Low"
                    color = "green"
                elif z_score > 1.1:
                    zone = "Grey Zone"
                    distress_prob = "Moderate"
                    color = "yellow"
                else:
                    zone = "Distress Zone"
                    distress_prob = "High"
                    color = "red"

                model = "Altman Z''-Score (Non-Manufacturing / Banks)"
                thresholds = {"safe": 2.6, "grey_upper": 2.6, "grey_lower": 1.1, "distress": 1.1}

        except Exception as exc:
            logger.warning("Altman Z calc error for %s: %s", symbol, exc)
            return {"error": str(exc), "symbol": symbol}

        result = {
            "symbol": symbol,
            "sector": sector,
            "model": model,
            "z_score": round(z_score, 4),
            "zone": zone,
            "distress_probability": distress_prob,
            "color": color,
            "components": {
                "T1_working_capital_ratio": round(T1, 4),
                "T2_retained_earnings_ratio": round(T2, 4),
                "T3_ebit_ratio": round(T3, 4),
                "T4_market_cap_to_liabilities": round(T4, 4),
                "T5_revenue_ratio": round(T5, 4) if not is_bank else "N/A (Z'' model)",
            },
            "thresholds": thresholds,
        }
        _cache_set(cache_key, result)
        return result


# ──────────────────────────────────────────────────────────────────
# BENEISH M-SCORE
# ──────────────────────────────────────────────────────────────────

class BeneishMScore:
    """
    Beneish M-Score for earnings manipulation detection.
    Score > -1.78 suggests likely manipulator.
    """

    def calculate(self, symbol: str) -> Dict:
        cache_key = f"beneish_{symbol}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            ticker, info, fin, bs, cf = _get_ticker_data(symbol)
        except Exception as exc:
            return {"error": str(exc), "symbol": symbol}

        try:
            revenue = _row(fin, "Total Revenue", "Revenue")
            receivables = _row(bs, "Receivables", "Accounts Receivable", "Net Receivables")
            cogs = _row(fin, "Cost Of Revenue", "Reconciled Cost Of Revenue")
            gross_profit = _row(fin, "Gross Profit")
            total_assets = _row(bs, "Total Assets")
            ppe = _row(bs, "Net PPE", "Net Property Plant Equipment",
                       "Properties Plant And Equipment Net")
            depreciation = _row(cf, "Depreciation And Amortization",
                                "Depreciation Amortization Depletion",
                                "Depreciation")
            sga = _row(fin, "Selling General And Administrative",
                       "Selling General Administrative", "General And Administrative Expense")
            total_debt = _row(bs, "Total Debt")
            total_equity = _row(bs, "Common Stock Equity", "Stockholders Equity",
                                "Total Equity Gross Minority Interest")
            net_income = _row(fin, "Net Income", "Net Income From Continuing Operations")
            cfo = _row(cf, "Operating Cash Flow", "Total Cash From Operating Activities",
                       "Cash Flow From Continuing Operating Activities")
            curr_assets = _row(bs, "Current Assets", "Total Current Assets")
            curr_liab = _row(bs, "Current Liabilities", "Total Current Liabilities")

            # Current year = col 0, prior year = col 1
            def v(series: pd.Series, yr: int) -> float:
                return _col_val(series, yr)

            rev_t = v(revenue, 0)
            rev_t1 = v(revenue, 1)
            rec_t = v(receivables, 0)
            rec_t1 = v(receivables, 1)
            cogs_t = v(cogs, 0)
            cogs_t1 = v(cogs, 1)
            gp_t = v(gross_profit, 0)
            gp_t1 = v(gross_profit, 1)
            ta_t = v(total_assets, 0)
            ta_t1 = v(total_assets, 1)
            ppe_t = v(ppe, 0)
            ppe_t1 = v(ppe, 1)
            dep_t = abs(v(depreciation, 0))
            dep_t1 = abs(v(depreciation, 1))
            sga_t = v(sga, 0)
            sga_t1 = v(sga, 1)
            debt_t = v(total_debt, 0)
            debt_t1 = v(total_debt, 1)
            eq_t = v(total_equity, 0)
            eq_t1 = v(total_equity, 1)
            ni_t = v(net_income, 0)
            cfo_t = v(cfo, 0)
            ca_t = v(curr_assets, 0)
            cl_t = v(curr_liab, 0)

            eps = 1e-9  # avoid division by zero

            # DSRI: Days Sales Receivable Index
            dsri = ((rec_t / (rev_t + eps)) / (rec_t1 / (rev_t1 + eps))) if rev_t1 != 0 else 1.0

            # GMI: Gross Margin Index
            gm_t = gp_t / (rev_t + eps)
            gm_t1 = gp_t1 / (rev_t1 + eps)
            gmi = gm_t1 / (gm_t + eps) if gm_t != 0 else 1.0

            # AQI: Asset Quality Index
            # Non-current assets excluding PP&E / total assets
            nca_t = ta_t - ca_t - ppe_t
            nca_t1 = ta_t1 - v(curr_assets, 1) - ppe_t1
            aqi = (nca_t / (ta_t + eps)) / ((nca_t1 / (ta_t1 + eps)) + eps) if ta_t1 != 0 else 1.0

            # SGI: Sales Growth Index
            sgi = rev_t / (rev_t1 + eps) if rev_t1 != 0 else 1.0

            # DEPI: Depreciation Index
            depr_rate_t = dep_t / (dep_t + ppe_t + eps)
            depr_rate_t1 = dep_t1 / (dep_t1 + ppe_t1 + eps)
            depi = depr_rate_t1 / (depr_rate_t + eps) if depr_rate_t != 0 else 1.0

            # SGAI: SGA Index
            sgai = (sga_t / (rev_t + eps)) / ((sga_t1 / (rev_t1 + eps)) + eps) if sga_t1 != 0 and rev_t1 != 0 else 1.0

            # LVGI: Leverage Index
            lev_t = (debt_t) / (ta_t + eps)
            lev_t1 = (debt_t1) / (ta_t1 + eps)
            lvgi = lev_t / (lev_t1 + eps) if lev_t1 != 0 else 1.0

            # TATA: Total Accruals to Total Assets
            tata = (ni_t - cfo_t) / (ta_t + eps)

            # M-Score
            m_score = (
                -4.84
                + 0.920 * dsri
                + 0.528 * gmi
                + 0.404 * aqi
                + 0.892 * sgi
                + 0.115 * depi
                - 0.172 * sgai
                + 4.679 * tata
                - 0.327 * lvgi
            )

        except Exception as exc:
            logger.warning("Beneish calc error for %s: %s", symbol, exc)
            return {"error": str(exc), "symbol": symbol}

        if m_score > -1.78:
            risk = "HIGH — Likely Manipulator"
            flag = True
        elif m_score > -2.22:
            risk = "MODERATE — Possible Manipulation"
            flag = False
        else:
            risk = "LOW — Likely Non-Manipulator"
            flag = False

        result = {
            "symbol": symbol,
            "m_score": round(m_score, 4),
            "threshold": -1.78,
            "risk_classification": risk,
            "manipulation_flag": flag,
            "indices": {
                "DSRI": round(dsri, 4),
                "GMI": round(gmi, 4),
                "AQI": round(aqi, 4),
                "SGI": round(sgi, 4),
                "DEPI": round(depi, 4),
                "SGAI": round(sgai, 4),
                "LVGI": round(lvgi, 4),
                "TATA": round(tata, 4),
            },
            "interpretation": {
                "DSRI": "High = Receivables growing faster than sales (revenue inflation risk)" if dsri > 1.5 else "Normal",
                "GMI": "High = Gross margin deteriorating (manipulation incentive)" if gmi > 1.2 else "Normal",
                "AQI": "High = Asset quality declining" if aqi > 1.25 else "Normal",
                "SGI": "High = Revenue growing fast (growth pressure)" if sgi > 1.6 else "Normal",
                "DEPI": "High = Depreciation slowing down (earnings boost)" if depi > 1.1 else "Normal",
                "SGAI": "High = SGA growing faster than sales" if sgai > 1.1 else "Normal",
                "LVGI": "High = Leverage increasing" if lvgi > 1.1 else "Normal",
                "TATA": "High = Large accruals relative to assets" if tata > 0.05 else "Normal",
            },
        }
        _cache_set(cache_key, result)
        return result


# ──────────────────────────────────────────────────────────────────
# DUPONT ANALYSIS
# ──────────────────────────────────────────────────────────────────

class DuPontAnalysis:
    """
    Three-factor and Five-factor DuPont decomposition of ROE.
    Identifies the primary driver of return on equity changes.
    """

    def calculate(self, symbol: str) -> Dict:
        cache_key = f"dupont_{symbol}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            ticker, info, fin, bs, cf = _get_ticker_data(symbol)
        except Exception as exc:
            return {"error": str(exc), "symbol": symbol}

        years_data: List[Dict] = []
        try:
            net_income = _row(fin, "Net Income", "Net Income From Continuing Operations")
            revenue = _row(fin, "Total Revenue", "Revenue")
            total_assets = _row(bs, "Total Assets")
            total_equity = _row(bs, "Common Stock Equity", "Stockholders Equity",
                                "Total Equity Gross Minority Interest")
            ebit_row = _row(fin, "EBIT", "Operating Income", "Operating Income Loss")
            ebt_row = _row(fin, "Pretax Income", "Income Before Tax",
                           "Pretax Income Loss Adjustment")

            num_years = min(len(net_income.dropna()), len(revenue.dropna()),
                            len(total_assets.dropna()), len(total_equity.dropna()), 3)

            for i in range(num_years):
                ni = _col_val(net_income, i)
                rev = _col_val(revenue, i)
                ta = _col_val(total_assets, i)
                eq = _col_val(total_equity, i)
                ebit = _col_val(ebit_row, i)
                ebt = _col_val(ebt_row, i)

                if rev == 0 or ta == 0 or eq == 0:
                    continue

                # 3-Factor DuPont
                npm = ni / rev  # Net Profit Margin
                at = rev / ta   # Asset Turnover
                em = ta / eq    # Equity Multiplier (Financial Leverage)
                roe_3f = npm * at * em

                # 5-Factor DuPont
                tax_burden = ni / ebt if ebt != 0 else 0.0    # Tax Burden
                int_burden = ebt / ebit if ebit != 0 else 0.0  # Interest Burden
                op_margin = ebit / rev                          # Operating Margin
                # asset turnover already calculated
                fin_lev = em                                    # Financial Leverage

                roe_5f = tax_burden * int_burden * op_margin * at * fin_lev

                # Try to get year label
                try:
                    year_label = str(net_income.index[i].year) if hasattr(net_income.index[i], "year") else f"Year-{i}"
                except Exception:
                    year_label = f"Year-{i}"

                years_data.append({
                    "year": year_label,
                    "three_factor": {
                        "roe": round(roe_3f * 100, 2),
                        "net_profit_margin_pct": round(npm * 100, 2),
                        "asset_turnover": round(at, 4),
                        "equity_multiplier": round(em, 4),
                    },
                    "five_factor": {
                        "roe": round(roe_5f * 100, 2),
                        "tax_burden": round(tax_burden, 4),
                        "interest_burden": round(int_burden, 4),
                        "operating_margin_pct": round(op_margin * 100, 2),
                        "asset_turnover": round(at, 4),
                        "financial_leverage": round(fin_lev, 4),
                    },
                })

        except Exception as exc:
            logger.warning("DuPont calc error for %s: %s", symbol, exc)
            return {"error": str(exc), "symbol": symbol}

        # Identify key driver
        key_driver = "Insufficient data"
        if len(years_data) >= 2:
            latest = years_data[0]["three_factor"]
            prev = years_data[1]["three_factor"]
            roe_change = latest["roe"] - prev["roe"]

            npm_contribution = (latest["net_profit_margin_pct"] - prev["net_profit_margin_pct"])
            at_contribution = (latest["asset_turnover"] - prev["asset_turnover"]) * prev["net_profit_margin_pct"] * prev["equity_multiplier"]
            lev_contribution = (latest["equity_multiplier"] - prev["equity_multiplier"]) * prev["net_profit_margin_pct"] * prev["asset_turnover"]

            drivers = {
                "Margin Expansion/Contraction": abs(npm_contribution),
                "Asset Utilization Change": abs(at_contribution),
                "Leverage Change": abs(lev_contribution),
            }
            key_driver = max(drivers, key=drivers.get)  # type: ignore

            if roe_change > 0:
                driver_direction = f"ROE improved by {round(abs(roe_change), 2)}% — driven by {key_driver}"
            else:
                driver_direction = f"ROE declined by {round(abs(roe_change), 2)}% — dragged by {key_driver}"
        else:
            driver_direction = "Insufficient years for trend analysis"

        result = {
            "symbol": symbol,
            "yearly_decomposition": years_data,
            "key_driver": key_driver,
            "driver_analysis": driver_direction,
        }
        _cache_set(cache_key, result)
        return result


# ──────────────────────────────────────────────────────────────────
# DCF VALUATION
# ──────────────────────────────────────────────────────────────────

class DCFValuation:
    """
    Discounted Cash Flow intrinsic value calculation.
    Two-stage model: explicit 10-year FCF projection + terminal value.
    """

    RISK_FREE_RATE = 0.065  # India 10Y G-Sec approximation
    EQUITY_RISK_PREMIUM = 0.06  # India ERP

    def calculate(self, symbol: str, wacc: Optional[float] = None,
                  terminal_growth: float = 0.05) -> Dict:
        cache_key = f"dcf_{symbol}_{wacc}_{terminal_growth}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            ticker, info, fin, bs, cf = _get_ticker_data(symbol)
        except Exception as exc:
            return {"error": str(exc), "symbol": symbol}

        try:
            cfo = _row(cf, "Operating Cash Flow", "Total Cash From Operating Activities",
                       "Cash Flow From Continuing Operating Activities")
            capex = _row(cf, "Capital Expenditure", "Purchase Of Property Plant And Equipment",
                         "Capital Expenditures")
            net_income = _row(fin, "Net Income", "Net Income From Continuing Operations")
            revenue = _row(fin, "Total Revenue", "Revenue")
            total_debt = _row(bs, "Total Debt", "Long Term Debt And Capital Lease Obligation")
            cash = _row(bs, "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments")
            total_equity = _row(bs, "Common Stock Equity", "Stockholders Equity",
                                "Total Equity Gross Minority Interest")

            # FCF history
            fcf_history: List[float] = []
            num_years = min(len(cfo.dropna()), len(capex.dropna()), 5)
            for i in range(num_years):
                cfo_val = _col_val(cfo, i)
                cap_val = abs(_col_val(capex, i))  # capex is usually negative
                fcf = cfo_val - cap_val
                fcf_history.append(fcf)

            if len(fcf_history) < 2:
                return {"error": "Insufficient FCF history for DCF", "symbol": symbol}

            # Estimate FCF growth rate via geometric mean
            positive_fcfs = [f for f in fcf_history if f > 0]
            if len(positive_fcfs) >= 2:
                cagr = (positive_fcfs[0] / positive_fcfs[-1]) ** (1 / (len(positive_fcfs) - 1)) - 1
                # Cap growth rate to reasonable range
                fcf_growth = max(min(cagr, 0.30), -0.10)
            else:
                fcf_growth = 0.08  # default conservative

            # Estimate WACC if not provided
            if wacc is None:
                beta = _safe(info.get("beta", 1.0))
                if beta <= 0:
                    beta = 1.0
                cost_of_equity = self.RISK_FREE_RATE + beta * self.EQUITY_RISK_PREMIUM

                debt_val = _col_val(total_debt, 0)
                equity_val = _safe(info.get("marketCap", 0))
                if equity_val == 0:
                    equity_val = _col_val(total_equity, 0)

                total_capital = debt_val + equity_val
                if total_capital > 0:
                    weight_equity = equity_val / total_capital
                    weight_debt = debt_val / total_capital
                    # Approx cost of debt from interest expense
                    interest_exp = _row(fin, "Interest Expense",
                                        "Interest Expense Non Operating")
                    int_exp = abs(_col_val(interest_exp, 0))
                    cost_of_debt = int_exp / debt_val if debt_val > 0 else 0.08
                    cost_of_debt = min(cost_of_debt, 0.15)  # cap at 15%
                    tax_rate = 0.25  # India corporate tax rate
                    wacc = weight_equity * cost_of_equity + weight_debt * cost_of_debt * (1 - tax_rate)
                else:
                    wacc = cost_of_equity

                wacc = max(min(wacc, 0.20), 0.08)  # clamp to [8%, 20%]

            # Stage 1: Project FCF for 10 years
            # Fade growth rate from fcf_growth toward terminal_growth over 10 years
            base_fcf = fcf_history[0]
            projected_fcfs: List[float] = []
            for yr in range(1, 11):
                fade_factor = yr / 10.0
                year_growth = fcf_growth * (1 - fade_factor) + terminal_growth * fade_factor
                if yr == 1:
                    proj = base_fcf * (1 + year_growth)
                else:
                    proj = projected_fcfs[-1] * (1 + year_growth)
                projected_fcfs.append(proj)

            # Stage 2: Terminal value (Gordon Growth)
            if wacc <= terminal_growth:
                terminal_growth = wacc - 0.01

            terminal_value = projected_fcfs[-1] * (1 + terminal_growth) / (wacc - terminal_growth)

            # Discount all to PV
            pv_fcfs: List[float] = []
            for yr, fcf_val in enumerate(projected_fcfs, 1):
                pv = fcf_val / ((1 + wacc) ** yr)
                pv_fcfs.append(pv)

            pv_terminal = terminal_value / ((1 + wacc) ** 10)
            total_pv = sum(pv_fcfs) + pv_terminal

            # Bridge to equity value
            debt_val = _col_val(total_debt, 0)
            cash_val = _col_val(cash, 0)
            shares = _safe(info.get("sharesOutstanding", 0))
            if shares == 0:
                shares = 1e7  # fallback

            equity_value = total_pv - debt_val + cash_val
            intrinsic_per_share = equity_value / shares

            current_price = _safe(info.get("currentPrice", info.get("regularMarketPrice", 0)))
            if current_price > 0:
                margin_of_safety = (intrinsic_per_share - current_price) / intrinsic_per_share * 100
            else:
                margin_of_safety = None

            # Sensitivity table: WACC ±2%, growth ±1%
            sensitivity: Dict[str, Dict] = {}
            for wacc_adj in [-0.02, -0.01, 0.0, +0.01, +0.02]:
                wacc_key = f"WACC_{round((wacc + wacc_adj) * 100, 1)}%"
                sensitivity[wacc_key] = {}
                for g_adj in [-0.01, 0.0, +0.01]:
                    g_key = f"g_{round((terminal_growth + g_adj) * 100, 1)}%"
                    w = wacc + wacc_adj
                    g = terminal_growth + g_adj
                    if w <= g:
                        sensitivity[wacc_key][g_key] = "N/A"
                        continue
                    tv = projected_fcfs[-1] * (1 + g) / (w - g)
                    pvs = sum(f / ((1 + w) ** yr) for yr, f in enumerate(projected_fcfs, 1))
                    pvt = tv / ((1 + w) ** 10)
                    ev = pvs + pvt - debt_val + cash_val
                    sensitivity[wacc_key][g_key] = round(ev / shares, 2)

            # Scenarios
            scenarios = {
                "bear": {
                    "growth_assumption": f"{round(max(fcf_growth * 0.5, -0.05) * 100, 1)}%",
                    "wacc": f"{round(wacc * 1.02 * 100, 1)}%",
                },
                "base": {
                    "growth_assumption": f"{round(fcf_growth * 100, 1)}%",
                    "wacc": f"{round(wacc * 100, 1)}%",
                    "intrinsic_value": round(intrinsic_per_share, 2),
                },
                "bull": {
                    "growth_assumption": f"{round(min(fcf_growth * 1.5, 0.35) * 100, 1)}%",
                    "wacc": f"{round(wacc * 0.98 * 100, 1)}%",
                },
            }

            # Bear scenario
            w_bear = wacc * 1.02
            g_bear = max(fcf_growth * 0.5, -0.05)
            pv_bear = sum(base_fcf * (1 + g_bear) ** yr / ((1 + w_bear) ** yr) for yr in range(1, 11))
            tv_bear = base_fcf * (1 + g_bear) ** 10 * (1 + terminal_growth) / (w_bear - terminal_growth)
            scenarios["bear"]["intrinsic_value"] = round((pv_bear + tv_bear / (1 + w_bear) ** 10 - debt_val + cash_val) / shares, 2)

            # Bull scenario
            w_bull = wacc * 0.98
            g_bull = min(fcf_growth * 1.5, 0.35)
            pv_bull = sum(base_fcf * (1 + g_bull) ** yr / ((1 + w_bull) ** yr) for yr in range(1, 11))
            tv_bull = base_fcf * (1 + g_bull) ** 10 * (1 + terminal_growth) / (w_bull - terminal_growth)
            scenarios["bull"]["intrinsic_value"] = round((pv_bull + tv_bull / (1 + w_bull) ** 10 - debt_val + cash_val) / shares, 2)

        except Exception as exc:
            logger.warning("DCF calc error for %s: %s", symbol, exc)
            return {"error": str(exc), "symbol": symbol}

        result = {
            "symbol": symbol,
            "intrinsic_value_per_share": round(intrinsic_per_share, 2),
            "current_price": round(current_price, 2),
            "margin_of_safety_pct": round(margin_of_safety, 2) if margin_of_safety is not None else None,
            "upside_downside": "Undervalued" if (margin_of_safety or 0) > 20 else (
                "Overvalued" if (margin_of_safety or 0) < -10 else "Fairly Valued"),
            "assumptions": {
                "wacc_pct": round(wacc * 100, 2),
                "terminal_growth_pct": round(terminal_growth * 100, 2),
                "fcf_growth_stage1_pct": round(fcf_growth * 100, 2),
                "projection_years": 10,
            },
            "fcf_history_cr": [round(f / 1e7, 2) for f in fcf_history],
            "projected_fcfs_cr": [round(f / 1e7, 2) for f in projected_fcfs],
            "pv_breakdown": {
                "pv_fcf_stage1_cr": round(sum(pv_fcfs) / 1e7, 2),
                "pv_terminal_cr": round(pv_terminal / 1e7, 2),
                "total_enterprise_value_cr": round(total_pv / 1e7, 2),
                "less_debt_cr": round(debt_val / 1e7, 2),
                "plus_cash_cr": round(cash_val / 1e7, 2),
                "equity_value_cr": round(equity_value / 1e7, 2),
            },
            "sensitivity_table": sensitivity,
            "scenarios": scenarios,
        }
        _cache_set(cache_key, result)
        return result


# ──────────────────────────────────────────────────────────────────
# ROIC ANALYSIS
# ──────────────────────────────────────────────────────────────────

class ROICAnalysis:
    """
    Return on Invested Capital — measures true value creation.
    ROIC > WACC = Value creation; ROIC < WACC = Value destruction.
    """

    def calculate(self, symbol: str) -> Dict:
        cache_key = f"roic_{symbol}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            ticker, info, fin, bs, cf = _get_ticker_data(symbol)
        except Exception as exc:
            return {"error": str(exc), "symbol": symbol}

        try:
            ebit_row = _row(fin, "EBIT", "Operating Income", "Operating Income Loss")
            tax_expense = _row(fin, "Tax Provision", "Income Tax Expense",
                               "Tax Provision Non Operating")
            pretax_income = _row(fin, "Pretax Income", "Income Before Tax")
            total_debt = _row(bs, "Total Debt", "Long Term Debt And Capital Lease Obligation")
            total_equity = _row(bs, "Common Stock Equity", "Stockholders Equity",
                                "Total Equity Gross Minority Interest")
            cash = _row(bs, "Cash And Cash Equivalents",
                        "Cash Cash Equivalents And Short Term Investments")

            roic_trend: List[Dict] = []
            eva_trend: List[Dict] = []

            beta = _safe(info.get("beta", 1.0))
            if beta <= 0:
                beta = 1.0
            estimated_wacc = 0.065 + beta * 0.06

            num_years = min(len(ebit_row.dropna()), 3)
            for i in range(num_years):
                ebit = _col_val(ebit_row, i)
                tax_exp = abs(_col_val(tax_expense, i))
                pre_tax = _col_val(pretax_income, i)
                debt = _col_val(total_debt, i)
                equity = _col_val(total_equity, i)
                cash_val = _col_val(cash, i)

                # Effective tax rate
                eff_tax = tax_exp / pre_tax if pre_tax > 0 else 0.25

                nopat = ebit * (1 - eff_tax)
                invested_capital = equity + debt - cash_val

                roic = nopat / invested_capital if invested_capital != 0 else 0.0
                eva = nopat - estimated_wacc * invested_capital

                try:
                    year_label = str(ebit_row.index[i].year) if hasattr(ebit_row.index[i], "year") else f"Year-{i}"
                except Exception:
                    year_label = f"Year-{i}"

                roic_trend.append({
                    "year": year_label,
                    "roic_pct": round(roic * 100, 2),
                    "nopat_cr": round(nopat / 1e7, 2),
                    "invested_capital_cr": round(invested_capital / 1e7, 2),
                    "effective_tax_rate_pct": round(eff_tax * 100, 2),
                })
                eva_trend.append({
                    "year": year_label,
                    "eva_cr": round(eva / 1e7, 2),
                    "roic_wacc_spread_pct": round((roic - estimated_wacc) * 100, 2),
                    "value_creation": "YES" if roic > estimated_wacc else "NO",
                })

        except Exception as exc:
            logger.warning("ROIC calc error for %s: %s", symbol, exc)
            return {"error": str(exc), "symbol": symbol}

        latest_roic = roic_trend[0]["roic_pct"] if roic_trend else 0.0
        latest_eva = eva_trend[0]["eva_cr"] if eva_trend else 0.0
        spread = eva_trend[0]["roic_wacc_spread_pct"] if eva_trend else 0.0

        result = {
            "symbol": symbol,
            "latest_roic_pct": latest_roic,
            "estimated_wacc_pct": round(estimated_wacc * 100, 2),
            "roic_wacc_spread_pct": spread,
            "value_creation": latest_roic > estimated_wacc * 100,
            "latest_eva_cr": latest_eva,
            "roic_trend": roic_trend,
            "eva_trend": eva_trend,
            "interpretation": (
                f"ROIC of {latest_roic}% is {'ABOVE' if latest_roic > estimated_wacc * 100 else 'BELOW'} "
                f"estimated WACC of {round(estimated_wacc * 100, 2)}%, indicating "
                f"{'value creation' if latest_roic > estimated_wacc * 100 else 'value destruction'}."
            ),
        }
        _cache_set(cache_key, result)
        return result


# ──────────────────────────────────────────────────────────────────
# WORKING CAPITAL ANALYSIS
# ──────────────────────────────────────────────────────────────────

class WorkingCapitalAnalysis:
    """
    Cash Conversion Cycle and working capital efficiency analysis.
    Negative CCC = Competitive advantage (receives cash before paying suppliers).
    """

    def calculate(self, symbol: str) -> Dict:
        cache_key = f"wc_{symbol}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            ticker, info, fin, bs, cf = _get_ticker_data(symbol)
        except Exception as exc:
            return {"error": str(exc), "symbol": symbol}

        try:
            revenue = _row(fin, "Total Revenue", "Revenue")
            cogs = _row(fin, "Cost Of Revenue", "Reconciled Cost Of Revenue")
            receivables = _row(bs, "Receivables", "Accounts Receivable", "Net Receivables",
                               "Gross Accounts Receivable")
            inventory = _row(bs, "Inventory", "Finished Goods", "Inventories")
            payables = _row(bs, "Accounts Payable", "Payables")
            curr_assets = _row(bs, "Current Assets", "Total Current Assets")
            curr_liab = _row(bs, "Current Liabilities", "Total Current Liabilities")

            trends: List[Dict] = []
            num_years = min(len(revenue.dropna()), len(cogs.dropna()),
                            len(receivables.dropna()), 3)

            for i in range(num_years):
                rev = _col_val(revenue, i)
                cog = _col_val(cogs, i)
                rec = _col_val(receivables, i)
                inv = _col_val(inventory, i)
                pay = _col_val(payables, i)
                ca = _col_val(curr_assets, i)
                cl = _col_val(curr_liab, i)

                # Days metrics
                dso = (rec / rev * 365) if rev > 0 else 0.0   # Days Sales Outstanding
                dio = (inv / cog * 365) if cog > 0 else 0.0   # Days Inventory Outstanding
                dpo = (pay / cog * 365) if cog > 0 else 0.0   # Days Payable Outstanding
                ccc = dio + dso - dpo                           # Cash Conversion Cycle
                nwc = ca - cl                                   # Net Working Capital

                try:
                    year_label = str(revenue.index[i].year) if hasattr(revenue.index[i], "year") else f"Year-{i}"
                except Exception:
                    year_label = f"Year-{i}"

                trends.append({
                    "year": year_label,
                    "dso_days": round(dso, 1),
                    "dio_days": round(dio, 1),
                    "dpo_days": round(dpo, 1),
                    "ccc_days": round(ccc, 1),
                    "nwc_cr": round(nwc / 1e7, 2),
                    "current_ratio": round(ca / cl, 2) if cl > 0 else None,
                })

        except Exception as exc:
            logger.warning("WC calc error for %s: %s", symbol, exc)
            return {"error": str(exc), "symbol": symbol}

        # Trend analysis
        ccc_direction = "Stable"
        nwc_change = None
        if len(trends) >= 2:
            ccc_change = trends[0]["ccc_days"] - trends[1]["ccc_days"]
            nwc_change = trends[0]["nwc_cr"] - trends[1]["nwc_cr"]
            if ccc_change < -5:
                ccc_direction = "Improving (shorter cycle)"
            elif ccc_change > 5:
                ccc_direction = "Deteriorating (longer cycle)"
            else:
                ccc_direction = "Stable"

        latest = trends[0] if trends else {}
        ccc = latest.get("ccc_days", 0)

        result = {
            "symbol": symbol,
            "latest": latest,
            "trend": trends,
            "ccc_direction": ccc_direction,
            "nwc_change_cr": round(nwc_change, 2) if nwc_change is not None else None,
            "competitive_advantage": ccc < 0,
            "interpretation": (
                f"CCC of {ccc} days — "
                + ("Negative CCC: receives customer cash before paying suppliers (like DMart) — strong advantage"
                   if ccc < 0
                   else f"Positive CCC: capital tied up in operations for {round(ccc)} days")
            ),
        }
        _cache_set(cache_key, result)
        return result


# ──────────────────────────────────────────────────────────────────
# QUALITY SCORING
# ──────────────────────────────────────────────────────────────────

class QualityScoring:
    """
    Comprehensive quality score (0-100) across four dimensions.
    """

    def calculate(self, symbol: str) -> Dict:
        cache_key = f"quality_{symbol}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            ticker, info, fin, bs, cf = _get_ticker_data(symbol)
        except Exception as exc:
            return {"error": str(exc), "symbol": symbol}

        scores: Dict[str, float] = {}

        # ── 1. Earnings Quality (25%) ──
        try:
            piotroski = PiotroskiFScore().calculate(symbol)
            pio_score = piotroski.get("score", 0)
            eq_from_pio = (pio_score / 9) * 100 * 0.5  # 50% weight

            net_income = _row(fin, "Net Income", "Net Income From Continuing Operations")
            cfo = _row(cf, "Operating Cash Flow", "Total Cash From Operating Activities",
                       "Cash Flow From Continuing Operating Activities")
            ni_curr = _col_val(net_income, 0)
            cfo_curr = _col_val(cfo, 0)

            cfo_ni_ratio = cfo_curr / ni_curr if ni_curr > 0 else 0.0
            eq_from_cfo = min(max(cfo_ni_ratio, 0), 2) / 2 * 100 * 0.5  # 50% weight, ratio>2=perfect

            scores["earnings_quality"] = eq_from_pio + eq_from_cfo
        except Exception:
            scores["earnings_quality"] = 50.0

        # ── 2. Balance Sheet Strength (25%) ──
        try:
            total_debt = _row(bs, "Total Debt", "Long Term Debt And Capital Lease Obligation")
            total_equity = _row(bs, "Common Stock Equity", "Stockholders Equity",
                                "Total Equity Gross Minority Interest")
            curr_assets = _row(bs, "Current Assets", "Total Current Assets")
            curr_liab = _row(bs, "Current Liabilities", "Total Current Liabilities")
            ebit_row = _row(fin, "EBIT", "Operating Income", "Operating Income Loss")
            interest_exp = _row(fin, "Interest Expense", "Interest Expense Non Operating")

            debt = _col_val(total_debt, 0)
            equity = _col_val(total_equity, 0)
            ca = _col_val(curr_assets, 0)
            cl = _col_val(curr_liab, 0)
            ebit = _col_val(ebit_row, 0)
            int_exp = abs(_col_val(interest_exp, 0))

            de_ratio = debt / equity if equity > 0 else 10.0
            cr = ca / cl if cl > 0 else 0.0
            int_cov = ebit / int_exp if int_exp > 0 else 10.0

            # Score components
            de_score = max(0, 100 - de_ratio * 20)  # 0 D/E = 100, 5 D/E = 0
            cr_score = min(cr * 40, 100)              # CR of 2.5+ = 100
            ic_score = min(int_cov * 5, 100)          # IC of 20+ = 100

            scores["balance_sheet_strength"] = (de_score * 0.4 + cr_score * 0.3 + ic_score * 0.3)
        except Exception:
            scores["balance_sheet_strength"] = 50.0

        # ── 3. Capital Allocation (25%) ──
        try:
            roic_data = ROICAnalysis().calculate(symbol)
            roic_score = min(max(roic_data.get("latest_roic_pct", 0) * 2, 0), 100) * 0.5

            cfo_series = _row(cf, "Operating Cash Flow", "Total Cash From Operating Activities",
                              "Cash Flow From Continuing Operating Activities")
            capex_series = _row(cf, "Capital Expenditure",
                                "Purchase Of Property Plant And Equipment")
            fcf_positive_count = sum(
                1 for i in range(min(3, len(cfo_series.dropna())))
                if _col_val(cfo_series, i) - abs(_col_val(capex_series, i)) > 0
            )
            fcf_score = (fcf_positive_count / 3) * 100 * 0.5

            scores["capital_allocation"] = roic_score + fcf_score
        except Exception:
            scores["capital_allocation"] = 50.0

        # ── 4. Management Track Record (25%) ──
        try:
            revenue = _row(fin, "Total Revenue", "Revenue")
            net_income = _row(fin, "Net Income", "Net Income From Continuing Operations")
            num_years = min(len(revenue.dropna()), len(net_income.dropna()), 3)

            if num_years >= 2:
                rev_vals = [_col_val(revenue, i) for i in range(num_years)]
                ni_vals = [_col_val(net_income, i) for i in range(num_years)]

                # Revenue CAGR (most recent vs oldest)
                if rev_vals[-1] > 0 and rev_vals[0] > 0:
                    rev_cagr = (rev_vals[0] / rev_vals[-1]) ** (1 / (num_years - 1)) - 1
                else:
                    rev_cagr = 0.0

                # NI consistency (all positive?)
                ni_positive_count = sum(1 for n in ni_vals if n > 0)

                rev_cagr_score = min(max(rev_cagr * 200, 0), 100) * 0.5  # 50% CAGR
                ni_consistency_score = (ni_positive_count / num_years) * 100 * 0.5

                scores["management_track_record"] = rev_cagr_score + ni_consistency_score
            else:
                scores["management_track_record"] = 50.0
        except Exception:
            scores["management_track_record"] = 50.0

        # ── Composite Score ──
        composite = (
            scores.get("earnings_quality", 50) * 0.25
            + scores.get("balance_sheet_strength", 50) * 0.25
            + scores.get("capital_allocation", 50) * 0.25
            + scores.get("management_track_record", 50) * 0.25
        )

        if composite >= 75:
            rating = "Excellent"
        elif composite >= 60:
            rating = "Good"
        elif composite >= 45:
            rating = "Average"
        elif composite >= 30:
            rating = "Below Average"
        else:
            rating = "Poor"

        result = {
            "symbol": symbol,
            "composite_quality_score": round(composite, 1),
            "rating": rating,
            "component_scores": {
                "earnings_quality_25pct": round(scores.get("earnings_quality", 50), 1),
                "balance_sheet_strength_25pct": round(scores.get("balance_sheet_strength", 50), 1),
                "capital_allocation_25pct": round(scores.get("capital_allocation", 50), 1),
                "management_track_record_25pct": round(scores.get("management_track_record", 50), 1),
            },
        }
        _cache_set(cache_key, result)
        return result


# ──────────────────────────────────────────────────────────────────
# COMPARABLE VALUATION
# ──────────────────────────────────────────────────────────────────

class ComparableValuation:
    """
    Relative valuation vs sector peers from NIFTY 100 universe.
    """

    def _get_peer_metrics(self, peer_symbol: str) -> Optional[Dict]:
        try:
            ticker = yf.Ticker(f"{peer_symbol}.NS")
            info = ticker.info or {}
            if not info:
                return None

            market_cap = _safe(info.get("marketCap", 0))
            if market_cap == 0:
                return None

            return {
                "symbol": peer_symbol,
                "pe": _safe(info.get("trailingPE", info.get("forwardPE", 0))),
                "pb": _safe(info.get("priceToBook", 0)),
                "ev_ebitda": _safe(info.get("enterpriseToEbitda", 0)),
                "ev_revenue": _safe(info.get("enterpriseToRevenue", 0)),
                "market_cap_cr": round(market_cap / 1e7, 0),
                "forward_pe": _safe(info.get("forwardPE", 0)),
                "peg": _safe(info.get("pegRatio", 0)),
                "dividend_yield": _safe(info.get("dividendYield", 0)) * 100,
            }
        except Exception:
            return None

    def calculate(self, symbol: str) -> Dict:
        cache_key = f"comparable_{symbol}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        sector = SECTOR_MAP.get(symbol, "Unknown")
        peers = NIFTY100_PEERS.get(sector, [])
        if not peers:
            # Try to find any peers
            for sec, members in NIFTY100_PEERS.items():
                if symbol in members:
                    peers = members
                    sector = sec
                    break

        # Get target company metrics
        target_metrics = self._get_peer_metrics(symbol)
        if target_metrics is None:
            return {"error": f"Could not fetch metrics for {symbol}", "symbol": symbol}

        # Get peer metrics (exclude target itself)
        peer_data: List[Dict] = []
        for p in peers:
            if p == symbol:
                continue
            m = self._get_peer_metrics(p)
            if m:
                peer_data.append(m)

        if not peer_data:
            return {
                "symbol": symbol, "sector": sector,
                "error": "No peer data available",
                "target_metrics": target_metrics,
            }

        # Calculate sector medians
        def safe_median(key: str) -> float:
            vals = [d[key] for d in peer_data if d.get(key, 0) > 0]
            return float(np.median(vals)) if vals else 0.0

        def percentile_rank(val: float, key: str) -> float:
            vals = sorted([d[key] for d in peer_data if d.get(key, 0) > 0])
            if not vals:
                return 50.0
            below = sum(1 for v in vals if v < val)
            return round(below / len(vals) * 100, 1)

        sector_medians = {
            "pe": safe_median("pe"),
            "pb": safe_median("pb"),
            "ev_ebitda": safe_median("ev_ebitda"),
            "ev_revenue": safe_median("ev_revenue"),
            "forward_pe": safe_median("forward_pe"),
            "peg": safe_median("peg"),
        }

        # Premium/discount vs sector median
        premium_discount: Dict[str, Any] = {}
        for metric in ["pe", "pb", "ev_ebitda", "ev_revenue"]:
            target_val = target_metrics.get(metric, 0)
            sector_val = sector_medians.get(metric, 0)
            if sector_val > 0 and target_val > 0:
                prem = (target_val - sector_val) / sector_val * 100
                premium_discount[metric] = {
                    "target": target_val,
                    "sector_median": sector_val,
                    "premium_discount_pct": round(prem, 1),
                    "assessment": "Premium" if prem > 10 else ("Discount" if prem < -10 else "In-line"),
                    "percentile": percentile_rank(target_val, metric),
                }

        # Overall valuation signal
        premiums = [v["premium_discount_pct"] for v in premium_discount.values()
                    if isinstance(v, dict) and "premium_discount_pct" in v]
        avg_premium = np.mean(premiums) if premiums else 0.0

        if avg_premium > 25:
            valuation_signal = "EXPENSIVE — significant premium to sector"
        elif avg_premium > 10:
            valuation_signal = "SLIGHTLY EXPENSIVE — above sector median"
        elif avg_premium > -10:
            valuation_signal = "FAIRLY VALUED — in-line with sector"
        elif avg_premium > -25:
            valuation_signal = "ATTRACTIVE — below sector median"
        else:
            valuation_signal = "DEEPLY DISCOUNTED — may signal risk or opportunity"

        result = {
            "symbol": symbol,
            "sector": sector,
            "target_metrics": target_metrics,
            "sector_medians": sector_medians,
            "premium_discount_analysis": premium_discount,
            "average_premium_discount_pct": round(avg_premium, 1),
            "valuation_signal": valuation_signal,
            "peers_compared": [p["symbol"] for p in peer_data],
            "peer_table": peer_data,
        }
        _cache_set(cache_key, result)
        return result


# ──────────────────────────────────────────────────────────────────
# FUNDAMENTAL DASHBOARD (Main API Interface)
# ──────────────────────────────────────────────────────────────────

class FundamentalDashboard:
    """
    Main API interface — orchestrates all fundamental analyses and
    produces an overall fundamental score with investment thesis.
    """

    def __init__(self) -> None:
        self.screener = ScreenerScraper()
        self.piotroski = PiotroskiFScore()
        self.altman = AltmanZScore()
        self.beneish = BeneishMScore()
        self.dupont = DuPontAnalysis()
        self.dcf = DCFValuation()
        self.roic = ROICAnalysis()
        self.wc = WorkingCapitalAnalysis()
        self.quality = QualityScoring()
        self.comparable = ComparableValuation()

    def _safe_run(self, name: str, fn, *args, **kwargs) -> Dict:
        """Run an analysis function and catch all exceptions."""
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            logger.warning("%s failed: %s", name, exc)
            return {"error": str(exc)}

    def _generate_investment_thesis(
        self,
        symbol: str,
        info: Dict,
        piotroski: Dict,
        altman: Dict,
        beneish: Dict,
        dcf: Dict,
        roic: Dict,
        quality: Dict,
        comparable: Dict,
    ) -> str:
        """Generate a concise investment thesis based on all analyses."""
        parts: List[str] = []

        company_name = info.get("longName", symbol)
        sector = SECTOR_MAP.get(symbol, "Unknown")
        parts.append(f"{company_name} ({symbol}) — {sector} sector.")

        # Quality
        q_score = quality.get("composite_quality_score", 50)
        q_rating = quality.get("rating", "Average")
        parts.append(f"Quality Rating: {q_rating} ({q_score}/100).")

        # Financial health
        pio_score = piotroski.get("score", 0)
        pio_interp = piotroski.get("interpretation", "Unknown")
        parts.append(f"Piotroski F-Score: {pio_score}/9 ({pio_interp} financial health).")

        # Distress risk
        zone = altman.get("zone", "Unknown")
        z_score = altman.get("z_score", 0)
        parts.append(f"Altman Z-Score: {z_score} ({zone}).")

        # Value
        intrinsic = dcf.get("intrinsic_value_per_share")
        current = dcf.get("current_price")
        mos = dcf.get("margin_of_safety_pct")
        if intrinsic and current and intrinsic > 0:
            updown = "undervalued" if (mos or 0) > 15 else ("overvalued" if (mos or 0) < -15 else "fairly valued")
            parts.append(f"DCF Intrinsic Value: ₹{intrinsic} vs Current ₹{current} — {updown} (MoS: {mos}%).")

        # ROIC
        roic_val = roic.get("latest_roic_pct", 0)
        wacc_val = roic.get("estimated_wacc_pct", 0)
        value_creation = roic.get("value_creation", False)
        parts.append(f"ROIC: {roic_val}% vs WACC: {wacc_val}% — {'value creating' if value_creation else 'value destroying'}.")

        # Comparable
        val_signal = comparable.get("valuation_signal", "")
        if val_signal:
            parts.append(f"Peer Comparison: {val_signal}.")

        return " ".join(parts)

    def _identify_red_flags(
        self,
        beneish: Dict,
        altman: Dict,
        piotroski: Dict,
        wc: Dict,
        quality: Dict,
    ) -> List[str]:
        flags: List[str] = []

        # Beneish manipulation
        if beneish.get("manipulation_flag"):
            flags.append(f"EARNINGS MANIPULATION RISK: Beneish M-Score of {beneish.get('m_score')} > -1.78 threshold")

        # Distress
        if altman.get("zone") == "Distress Zone":
            flags.append(f"DISTRESS RISK: Altman Z-Score of {altman.get('z_score')} indicates financial distress")

        # Weak financials
        pio_score = piotroski.get("score", 9)
        if pio_score <= 3:
            flags.append(f"WEAK FUNDAMENTALS: Piotroski F-Score only {pio_score}/9 — multiple financial concerns")

        failed = piotroski.get("failed_criteria", [])
        for f in failed:
            if "dilution" in f.lower():
                flags.append("SHARE DILUTION: Shares outstanding increased — potential value dilution")
            if "leverage" in f.lower():
                flags.append("RISING LEVERAGE: Long-term debt ratio increasing")

        # Quality
        q_score = quality.get("composite_quality_score", 50)
        if q_score < 35:
            flags.append(f"LOW QUALITY: Overall quality score of {q_score}/100 — concerns across multiple dimensions")

        # Working capital
        ccc = wc.get("latest", {}).get("ccc_days", 0)
        if wc.get("ccc_direction") == "Deteriorating (longer cycle)" and ccc > 90:
            flags.append(f"WORKING CAPITAL STRESS: CCC of {ccc} days deteriorating — cash cycle under pressure")

        # Beneish index-specific flags
        indices = beneish.get("indices", {})
        if indices.get("DSRI", 0) > 1.8:
            flags.append("RECEIVABLES SPIKE: DSRI > 1.8 — receivables growing much faster than revenue")
        if indices.get("TATA", 0) > 0.1:
            flags.append("HIGH ACCRUALS: TATA > 0.1 — large non-cash earnings component")

        return flags

    def get_full_analysis(self, symbol: str) -> Dict:
        """Run all analyses and return comprehensive fundamental assessment."""
        symbol = symbol.upper()
        cache_key = f"fundamental_full_{symbol}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        logger.info("Running full fundamental analysis for %s", symbol)

        # Fetch basic info
        try:
            ticker, info, fin, bs, cf = _get_ticker_data(symbol)
        except Exception as exc:
            return {"error": f"Cannot fetch data for {symbol}: {exc}", "symbol": symbol}

        # Run all analyses
        piotroski = self._safe_run("Piotroski", self.piotroski.calculate, symbol)
        altman = self._safe_run("Altman", self.altman.calculate, symbol)
        beneish = self._safe_run("Beneish", self.beneish.calculate, symbol)
        dupont = self._safe_run("DuPont", self.dupont.calculate, symbol)
        dcf = self._safe_run("DCF", self.dcf.calculate, symbol)
        roic = self._safe_run("ROIC", self.roic.calculate, symbol)
        wc = self._safe_run("WorkingCapital", self.wc.calculate, symbol)
        quality = self._safe_run("Quality", self.quality.calculate, symbol)
        comparable = self._safe_run("Comparable", self.comparable.calculate, symbol)
        screener = self._safe_run("Screener", self.screener.get_financial_data, symbol)
        quarterly = self._safe_run("Quarterly", self.screener.get_quarterly_results, symbol)

        # Overall fundamental score (weighted composite)
        weights = {
            "piotroski": 0.15,
            "altman": 0.15,
            "quality": 0.25,
            "roic": 0.20,
            "dcf": 0.15,
            "beneish": 0.10,
        }
        component_scores: Dict[str, float] = {}

        # Piotroski (0-9 → 0-100)
        component_scores["piotroski"] = (piotroski.get("score", 5) / 9) * 100

        # Altman (zone → score)
        altman_zone = altman.get("zone", "Grey Zone")
        component_scores["altman"] = {"Safe Zone": 85, "Grey Zone": 50, "Distress Zone": 15}.get(altman_zone, 50)

        # Quality composite
        component_scores["quality"] = quality.get("composite_quality_score", 50)

        # ROIC (ROIC/WACC ratio → score)
        roic_pct = roic.get("latest_roic_pct", 10)
        wacc_pct = roic.get("estimated_wacc_pct", 12)
        roic_ratio = roic_pct / wacc_pct if wacc_pct > 0 else 1.0
        component_scores["roic"] = min(max(roic_ratio * 50, 0), 100)

        # DCF (margin of safety → score)
        mos = dcf.get("margin_of_safety_pct", 0) or 0
        component_scores["dcf"] = min(max(50 + mos, 0), 100)

        # Beneish (no manipulation = 80, manipulation flag = 20)
        component_scores["beneish"] = 20 if beneish.get("manipulation_flag") else 80

        overall_score = sum(component_scores[k] * weights[k] for k in weights)

        if overall_score >= 75:
            fundamental_rating = "STRONG BUY"
        elif overall_score >= 60:
            fundamental_rating = "BUY"
        elif overall_score >= 45:
            fundamental_rating = "HOLD"
        elif overall_score >= 30:
            fundamental_rating = "REDUCE"
        else:
            fundamental_rating = "SELL"

        # Investment thesis
        investment_thesis = self._generate_investment_thesis(
            symbol, info, piotroski, altman, beneish, dcf, roic, quality, comparable
        )

        # Red flags
        red_flags = self._identify_red_flags(beneish, altman, piotroski, wc, quality)

        # Key metrics snapshot
        current_price = _safe(info.get("currentPrice", info.get("regularMarketPrice", 0)))
        market_cap = _safe(info.get("marketCap", 0))

        key_metrics = {
            "company_name": info.get("longName", symbol),
            "sector": SECTOR_MAP.get(symbol, info.get("sector", "Unknown")),
            "current_price": current_price,
            "market_cap_cr": round(market_cap / 1e7, 0),
            "pe_ttm": _safe(info.get("trailingPE", 0)),
            "forward_pe": _safe(info.get("forwardPE", 0)),
            "pb_ratio": _safe(info.get("priceToBook", 0)),
            "ev_ebitda": _safe(info.get("enterpriseToEbitda", 0)),
            "roe_pct": _safe(info.get("returnOnEquity", 0)) * 100,
            "roa_pct": _safe(info.get("returnOnAssets", 0)) * 100,
            "revenue_growth_pct": _safe(info.get("revenueGrowth", 0)) * 100,
            "earnings_growth_pct": _safe(info.get("earningsGrowth", 0)) * 100,
            "profit_margin_pct": _safe(info.get("profitMargins", 0)) * 100,
            "debt_to_equity": _safe(info.get("debtToEquity", 0)) / 100,  # yfinance returns in %
            "dividend_yield_pct": _safe(info.get("dividendYield", 0)) * 100,
            "beta": _safe(info.get("beta", 1.0)),
            "52w_high": _safe(info.get("fiftyTwoWeekHigh", 0)),
            "52w_low": _safe(info.get("fiftyTwoWeekLow", 0)),
            "shares_outstanding_cr": round(_safe(info.get("sharesOutstanding", 0)) / 1e7, 2),
        }

        result = {
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "overall_fundamental_score": round(overall_score, 1),
            "fundamental_rating": fundamental_rating,
            "component_scores": component_scores,
            "investment_thesis": investment_thesis,
            "red_flags": red_flags,
            "key_metrics": key_metrics,
            "analyses": {
                "piotroski_fscore": piotroski,
                "altman_zscore": altman,
                "beneish_mscore": beneish,
                "dupont_analysis": dupont,
                "dcf_valuation": dcf,
                "roic_analysis": roic,
                "working_capital": wc,
                "quality_scoring": quality,
                "comparable_valuation": comparable,
                "screener_data": screener,
                "quarterly_results": quarterly,
            },
        }

        _cache_set(f"fundamental_full_{symbol}", result)
        return result


# ──────────────────────────────────────────────────────────────────
# CONVENIENCE FUNCTIONS (for FastAPI endpoints)
# ──────────────────────────────────────────────────────────────────

_dashboard = FundamentalDashboard()


def get_fundamental_analysis(symbol: str) -> Dict:
    """Full fundamental analysis — primary entry point."""
    return _dashboard.get_full_analysis(symbol)


def get_piotroski(symbol: str) -> Dict:
    return PiotroskiFScore().calculate(symbol)


def get_altman_z(symbol: str) -> Dict:
    return AltmanZScore().calculate(symbol)


def get_beneish_m(symbol: str) -> Dict:
    return BeneishMScore().calculate(symbol)


def get_dcf(symbol: str, wacc: Optional[float] = None,
            terminal_growth: float = 0.05) -> Dict:
    return DCFValuation().calculate(symbol, wacc=wacc, terminal_growth=terminal_growth)


def get_roic(symbol: str) -> Dict:
    return ROICAnalysis().calculate(symbol)


def get_quality_score(symbol: str) -> Dict:
    return QualityScoring().calculate(symbol)


def get_comparable_valuation(symbol: str) -> Dict:
    return ComparableValuation().calculate(symbol)


def get_screener_data(symbol: str) -> Dict:
    return ScreenerScraper().get_financial_data(symbol)


def get_working_capital(symbol: str) -> Dict:
    return WorkingCapitalAnalysis().calculate(symbol)


def get_dupont(symbol: str) -> Dict:
    return DuPontAnalysis().calculate(symbol)
