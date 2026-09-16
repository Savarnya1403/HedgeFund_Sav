"""
Order Flow Analysis — Citadel-Grade Market Microstructure Intelligence
Cumulative delta, smart money flow, dark pool proxy, liquidity metrics, seasonality
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Any
from math import log, sqrt, exp, erf, pi


# ── ORDER FLOW ─────────────────────────────────────────────────────

def compute_order_flow(df: pd.DataFrame) -> Dict[str, Any]:
    """Tick-rule order flow decomposition from daily OHLCV."""
    if df is None or len(df) < 20:
        return {"error": "Insufficient data"}

    df = df.copy()
    df["close_diff"] = df["Close"].diff()
    df["tick_dir"] = np.where(df["close_diff"] > 0, 1, np.where(df["close_diff"] < 0, -1, 0))
    df["tick_dir"] = df["tick_dir"].replace(0, np.nan).ffill().fillna(1)

    df["buy_vol"] = np.where(df["tick_dir"] > 0, df["Volume"], 0)
    df["sell_vol"] = np.where(df["tick_dir"] < 0, df["Volume"], 0)
    df["volume_delta"] = df["buy_vol"] - df["sell_vol"]
    df["cum_delta"] = df["volume_delta"].cumsum()

    # Delta divergence
    price_dir = np.sign(df["Close"].iloc[-1] - df["Close"].iloc[-20])
    delta_dir = np.sign(df["cum_delta"].iloc[-1] - df["cum_delta"].iloc[-20])
    if price_dir > 0 and delta_dir < 0:
        divergence = "bearish"
    elif price_dir < 0 and delta_dir > 0:
        divergence = "bullish"
    else:
        divergence = "none"

    # Buying pressure (20-day)
    recent = df.tail(20)
    total_vol = recent["Volume"].sum()
    buy_pressure = recent["buy_vol"].sum() / total_vol if total_vol > 0 else 0.5

    # Smart money flow — large volume bars closing in upper half = bullish institutional
    high_vol_thresh = df["Volume"].quantile(0.75)
    large_bars = df[df["Volume"] > high_vol_thresh].tail(30)
    if len(large_bars) > 0:
        close_pct = (large_bars["Close"] - large_bars["Low"]) / (large_bars["High"] - large_bars["Low"] + 1e-9)
        score = float(close_pct.mean())
        smart_flow = "bullish" if score > 0.6 else "bearish" if score < 0.4 else "neutral"
    else:
        score, smart_flow = 0.5, "neutral"

    # OBV trend
    df["obv"] = (np.sign(df["Close"].diff()) * df["Volume"]).cumsum()
    obv_slope = float(np.polyfit(range(20), df["obv"].tail(20).values, 1)[0])
    obv_trend = "rising" if obv_slope > 0 else "falling"

    # VWAP 20-day deviation
    df["typ"] = (df["High"] + df["Low"] + df["Close"]) / 3
    vwap_20 = float((df["typ"].tail(20) * df["Volume"].tail(20)).sum() / (df["Volume"].tail(20).sum() + 1))
    vwap_dev = (float(df["Close"].iloc[-1]) - vwap_20) / vwap_20 * 100

    # Volume imbalance (last 5 bars)
    r5 = df.tail(5)
    vol_imbalance = float((r5["buy_vol"].sum() - r5["sell_vol"].sum()) / (r5["Volume"].sum() + 1))

    # Chart time series (last 60 bars)
    chart_data = []
    for idx, row in df.tail(60).iterrows():
        chart_data.append({
            "date": str(idx.date()) if hasattr(idx, "date") else str(idx),
            "buy_vol": float(row["buy_vol"]),
            "sell_vol": float(row["sell_vol"]),
            "cum_delta": float(row["cum_delta"]),
            "obv": float(row["obv"]),
            "price": float(row["Close"]),
            "volume": float(row["Volume"]),
        })

    overall_signal = (
        "bullish" if buy_pressure > 0.57 and smart_flow == "bullish" else
        "bearish" if buy_pressure < 0.43 and smart_flow == "bearish" else
        "neutral"
    )

    return {
        "buying_pressure_ratio": round(buy_pressure, 4),
        "selling_pressure_ratio": round(1 - buy_pressure, 4),
        "cumulative_delta": round(float(df["cum_delta"].iloc[-1]), 0),
        "delta_divergence": divergence,
        "smart_money_flow": smart_flow,
        "smart_money_score": round(score, 3),
        "obv_trend": obv_trend,
        "vwap_20d": round(vwap_20, 2),
        "vwap_deviation_pct": round(vwap_dev, 2),
        "volume_imbalance": round(vol_imbalance, 3),
        "signal": overall_signal,
        "chart_data": chart_data,
    }


# ── DARK POOL PROXY ────────────────────────────────────────────────

def compute_dark_pool_proxy(df: pd.DataFrame, symbol: str) -> Dict[str, Any]:
    """Institutional absorption proxy: large volume + small price impact = dark pool prints."""
    if df is None or len(df) < 30:
        return {"error": "Insufficient data"}

    df = df.copy()
    avg_vol = float(df["Volume"].mean())
    avg_range = float((df["High"] - df["Low"]).mean())

    df["vol_ratio"] = df["Volume"] / (avg_vol + 1)
    df["range_ratio"] = (df["High"] - df["Low"]) / (avg_range + 0.01)
    df["absorption_score"] = df["vol_ratio"] / (df["range_ratio"] + 0.1)

    dark_pool_days = df[df["absorption_score"] > 2.5].tail(20)

    events = []
    for idx, row in dark_pool_days.iterrows():
        events.append({
            "date": str(idx.date()) if hasattr(idx, "date") else str(idx),
            "price": round(float(row["Close"]), 2),
            "volume": int(row["Volume"]),
            "vol_ratio": round(float(row["vol_ratio"]), 2),
            "absorption_score": round(float(row["absorption_score"]), 2),
            "direction": "buy" if row["Close"] > row["Open"] else "sell",
        })

    if len(dark_pool_days) > 0:
        buy_days = int((dark_pool_days["Close"] > dark_pool_days["Open"]).sum())
        net_dir = "accumulation" if buy_days > len(dark_pool_days) / 2 else "distribution"
    else:
        net_dir = "neutral"

    return {
        "symbol": symbol.upper(),
        "absorption_events": events,
        "event_count_20d": len(events),
        "net_direction": net_dir,
        "avg_absorption_score": round(float(df["absorption_score"].tail(20).mean()), 2),
        "interpretation": f"Institutional {net_dir} — large-volume, low-impact bars detected",
    }


# ── SEASONALITY / INTRADAY PATTERNS ───────────────────────────────

def compute_seasonality(df: pd.DataFrame) -> Dict[str, Any]:
    """Day-of-week and monthly seasonality from daily returns."""
    if df is None or len(df) < 60:
        return {"error": "Insufficient data for seasonality analysis"}

    df = df.copy()
    df["return"] = df["Close"].pct_change()
    idx_dt = pd.to_datetime(df.index)
    df["dow"] = idx_dt.dayofweek
    df["month"] = idx_dt.month
    df["week_of_month"] = (idx_dt.day - 1) // 7

    dow_map = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri"}
    dow_stats = {}
    for d in range(5):
        data = df[df["dow"] == d]["return"].dropna()
        if len(data) > 0:
            dow_stats[dow_map[d]] = {
                "mean_pct": round(float(data.mean() * 100), 3),
                "win_rate": round(float((data > 0).mean() * 100), 1),
                "n": int(len(data)),
            }

    month_map = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
                 7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}
    month_stats = {}
    for m in range(1, 13):
        data = df[df["month"] == m]["return"].dropna()
        if len(data) > 0:
            month_stats[month_map[m]] = {
                "mean_pct": round(float(data.mean() * 100), 3),
                "win_rate": round(float((data > 0).mean() * 100), 1),
                "n": int(len(data)),
            }

    best_day = max(dow_stats, key=lambda k: dow_stats[k]["mean_pct"]) if dow_stats else "N/A"
    worst_day = min(dow_stats, key=lambda k: dow_stats[k]["mean_pct"]) if dow_stats else "N/A"
    best_month = max(month_stats, key=lambda k: month_stats[k]["mean_pct"]) if month_stats else "N/A"
    worst_month = min(month_stats, key=lambda k: month_stats[k]["mean_pct"]) if month_stats else "N/A"

    expiry_week = df[df["week_of_month"] == 3]["return"].dropna()

    return {
        "day_of_week": dow_stats,
        "monthly": month_stats,
        "best_day": best_day,
        "worst_day": worst_day,
        "best_month": best_month,
        "worst_month": worst_month,
        "expiry_week_return_pct": round(float(expiry_week.mean() * 100), 3) if len(expiry_week) > 0 else 0,
        "expiry_week_win_rate": round(float((expiry_week > 0).mean() * 100), 1) if len(expiry_week) > 0 else 0,
    }


# ── LIQUIDITY METRICS ──────────────────────────────────────────────

def compute_liquidity_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    """Amihud illiquidity, Roll spread, Corwin-Schultz spread, price impact."""
    if df is None or len(df) < 30:
        return {"error": "Insufficient data"}

    df = df.copy()
    df["ret_abs"] = df["Close"].pct_change().abs()
    df["dollar_vol"] = df["Close"] * df["Volume"]

    # Amihud illiquidity
    amihud = float((df["ret_abs"] / (df["dollar_vol"] + 1)).mean() * 1e6)

    # Roll's effective spread
    price_chg = df["Close"].diff().dropna()
    cov = float(price_chg.autocorr(lag=1))
    roll_spread = 2 * sqrt(max(-cov, 0)) if cov < 0 else 0
    roll_bps = round(roll_spread / float(df["Close"].mean()) * 10000, 2)

    # Corwin-Schultz high-low spread
    log_hl = np.log(df["High"] / df["Low"])
    alpha = (sqrt(2) - 1) / (3 - 2 * sqrt(2)) * float(log_hl.mean())
    cs_spread = (2 * (exp(alpha) - 1) / (1 + exp(alpha))) * 100

    # Avg dollar volume (liquidity proxy)
    avg_dv = float(df["dollar_vol"].mean())

    # Liquidity score 0-100
    amihud_norm = min(50, amihud * 20)
    roll_norm = min(30, roll_bps / 3)
    dv_score = min(20, (avg_dv / 1e8) * 20)
    score = max(0, min(100, 100 - amihud_norm - roll_norm + dv_score))
    grade = "A" if score > 80 else "B" if score > 60 else "C" if score > 40 else "D"

    return {
        "amihud_illiquidity": round(amihud, 6),
        "roll_spread_bps": roll_bps,
        "cs_spread_pct": round(cs_spread, 4),
        "avg_dollar_volume_cr": round(avg_dv / 1e7, 2),
        "liquidity_score": round(score, 1),
        "liquidity_grade": grade,
        "interpretation": (
            "Highly liquid — institutional-grade, minimal impact cost" if score > 80 else
            "Good liquidity — manageable impact for large trades" if score > 60 else
            "Moderate liquidity — expect some impact on large orders" if score > 40 else
            "Illiquid — significant impact cost, size carefully"
        ),
    }


# ── KALMAN FILTER PAIRS ────────────────────────────────────────────

def kalman_filter_pairs(y: np.ndarray, x: np.ndarray) -> Dict[str, Any]:
    """
    Dynamic hedge ratio via Kalman filter (far superior to static OLS).
    State: [beta (hedge ratio), alpha (intercept)]
    """
    n = len(y)
    if n < 30:
        return {"error": "Insufficient data for Kalman estimation"}

    delta = 1e-4
    Vw = delta / (1 - delta) * np.eye(2)
    Ve = 0.001

    theta = np.zeros((n, 2))
    P = np.zeros((n, 2, 2))
    P[0] = np.eye(2)

    # Bootstrap with OLS
    A_init = np.column_stack([x[:20], np.ones(20)])
    theta[0], _, _, _ = np.linalg.lstsq(A_init, y[:20], rcond=None)

    spread = np.zeros(n)
    innovations = np.zeros(n)

    for t in range(1, n):
        theta_pred = theta[t - 1]
        P_pred = P[t - 1] + Vw

        F = np.array([x[t], 1.0])
        y_hat = float(F @ theta_pred)
        innovations[t] = y[t] - y_hat

        S = float(F @ P_pred @ F) + Ve
        K_gain = P_pred @ F / S

        theta[t] = theta_pred + K_gain * innovations[t]
        P[t] = (np.eye(2) - np.outer(K_gain, F)) @ P_pred
        spread[t] = y[t] - theta[t, 0] * x[t] - theta[t, 1]

    spread_series = spread[30:]
    mean_s = float(np.mean(spread_series))
    std_s = float(np.std(spread_series))
    z = (float(spread[-1]) - mean_s) / (std_s + 1e-9)

    if z < -2.0:
        signal = "enter_long_spread"
    elif z > 2.0:
        signal = "enter_short_spread"
    elif -0.5 < z < 0:
        signal = "exit_long"
    elif 0 < z < 0.5:
        signal = "exit_short"
    else:
        signal = "hold"

    return {
        "hedge_ratio": round(float(theta[-1, 0]), 4),
        "intercept": round(float(theta[-1, 1]), 4),
        "hedge_ratio_history": [round(float(h), 4) for h in theta[-60:, 0]],
        "spread": [round(float(s), 4) for s in spread[-60:]],
        "spread_mean": round(mean_s, 4),
        "spread_std": round(std_s, 4),
        "z_score": round(z, 3),
        "signal": signal,
        "half_life_days": round(float(-np.log(2) / np.log(abs(np.corrcoef(spread_series[:-1], spread_series[1:])[0, 1]) + 1e-9)), 1) if len(spread_series) > 5 else None,
    }
