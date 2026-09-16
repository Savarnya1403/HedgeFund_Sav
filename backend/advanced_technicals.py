"""
Advanced Technical Analysis Engine
Indian Hedge Fund Intelligence System
All indicators implemented from scratch using NumPy/Pandas/SciPy.
No 'ta' library dependency.
"""

import warnings
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf
from scipy import stats
from scipy.signal import argrelextrema

warnings.filterwarnings("ignore")


# ─────────────────────────────────────────────────────────────────────────────
# HELPER UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def _true_range(df: pd.DataFrame) -> pd.Series:
    """Wilder's True Range."""
    high = df["High"]
    low = df["Low"]
    prev_close = df["Close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range using Wilder smoothing."""
    tr = _true_range(df)
    atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return atr


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def calculate_pivot_points(high: float, low: float, close: float) -> dict:
    """Classic, Fibonacci, and Camarilla pivot points."""
    # Classic
    pp = (high + low + close) / 3
    r1_c = 2 * pp - low
    s1_c = 2 * pp - high
    r2_c = pp + (high - low)
    s2_c = pp - (high - low)
    r3_c = high + 2 * (pp - low)
    s3_c = low - 2 * (high - pp)

    # Fibonacci
    rng = high - low
    r1_f = pp + 0.382 * rng
    r2_f = pp + 0.618 * rng
    r3_f = pp + 1.000 * rng
    s1_f = pp - 0.382 * rng
    s2_f = pp - 0.618 * rng
    s3_f = pp - 1.000 * rng

    # Camarilla
    r1_ca = close + rng * 1.1 / 12
    r2_ca = close + rng * 1.1 / 6
    r3_ca = close + rng * 1.1 / 4
    r4_ca = close + rng * 1.1 / 2
    s1_ca = close - rng * 1.1 / 12
    s2_ca = close - rng * 1.1 / 6
    s3_ca = close - rng * 1.1 / 4
    s4_ca = close - rng * 1.1 / 2

    return {
        "classic": {"PP": pp, "R1": r1_c, "R2": r2_c, "R3": r3_c,
                    "S1": s1_c, "S2": s2_c, "S3": s3_c},
        "fibonacci": {"PP": pp, "R1": r1_f, "R2": r2_f, "R3": r3_f,
                      "S1": s1_f, "S2": s2_f, "S3": s3_f},
        "camarilla": {"R1": r1_ca, "R2": r2_ca, "R3": r3_ca, "R4": r4_ca,
                      "S1": s1_ca, "S2": s2_ca, "S3": s3_ca, "S4": s4_ca},
    }


def calculate_support_resistance(df: pd.DataFrame, n_levels: int = 5) -> dict:
    """Swing high/low based support and resistance."""
    close = df["Close"].values
    highs = df["High"].values
    lows = df["Low"].values

    # Find local maxima and minima
    order = 5
    hi_idx = argrelextrema(highs, np.greater_equal, order=order)[0]
    lo_idx = argrelextrema(lows, np.less_equal, order=order)[0]

    resistance_levels = sorted(highs[hi_idx], reverse=True)[:n_levels]
    support_levels = sorted(lows[lo_idx])[:n_levels]

    current = close[-1]
    nearest_res = min([r for r in resistance_levels if r > current], default=None)
    nearest_sup = max([s for s in support_levels if s < current], default=None)

    return {
        "resistance_levels": [round(r, 2) for r in resistance_levels],
        "support_levels": [round(s, 2) for s in support_levels],
        "nearest_resistance": round(nearest_res, 2) if nearest_res else None,
        "nearest_support": round(nearest_sup, 2) if nearest_sup else None,
        "current_price": round(current, 2),
    }


def calculate_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """Heikin Ashi candles."""
    ha = df.copy()
    ha["HA_Close"] = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4
    ha["HA_Open"] = (df["Open"].shift(1) + df["Close"].shift(1)) / 2
    ha["HA_Open"].iloc[0] = (df["Open"].iloc[0] + df["Close"].iloc[0]) / 2
    # Propagate HA_Open forward
    for i in range(1, len(ha)):
        ha["HA_Open"].iloc[i] = (ha["HA_Open"].iloc[i - 1] + ha["HA_Close"].iloc[i - 1]) / 2
    ha["HA_High"] = ha[["High", "HA_Open", "HA_Close"]].max(axis=1)
    ha["HA_Low"] = ha[["Low", "HA_Open", "HA_Close"]].min(axis=1)
    return ha[["HA_Open", "HA_High", "HA_Low", "HA_Close"]]


def calculate_renko(df: pd.DataFrame, brick_size: float = None) -> list:
    """Renko bricks. ATR-based brick size if not provided."""
    if brick_size is None:
        atr_val = _atr(df, 14).dropna().iloc[-1]
        brick_size = round(atr_val, 2)

    close = df["Close"].values
    bricks = []
    if len(close) == 0:
        return bricks

    ref = close[0]
    for price in close[1:]:
        while price >= ref + brick_size:
            bricks.append({"open": ref, "close": ref + brick_size, "direction": "up"})
            ref += brick_size
        while price <= ref - brick_size:
            bricks.append({"open": ref, "close": ref - brick_size, "direction": "down"})
            ref -= brick_size
    return bricks


def calculate_linear_regression_channel(df: pd.DataFrame, period: int = 50) -> dict:
    """Linear regression channel over the last `period` bars."""
    close = df["Close"].values[-period:]
    x = np.arange(len(close))
    slope, intercept, r_val, _, std_err = stats.linregress(x, close)
    fitted = slope * x + intercept
    residuals = close - fitted
    std_dev = np.std(residuals)

    upper_1 = fitted + std_dev
    lower_1 = fitted - std_dev
    upper_2 = fitted + 2 * std_dev
    lower_2 = fitted - 2 * std_dev

    return {
        "slope": round(slope, 4),
        "intercept": round(intercept, 4),
        "r_squared": round(r_val ** 2, 4),
        "std_error": round(std_err, 4),
        "channel_upper_1sd": round(upper_1[-1], 2),
        "channel_lower_1sd": round(lower_1[-1], 2),
        "channel_upper_2sd": round(upper_2[-1], 2),
        "channel_lower_2sd": round(lower_2[-1], 2),
        "midline_current": round(fitted[-1], 2),
        "trend_direction": "UP" if slope > 0 else "DOWN",
        "fitted_values": [round(v, 2) for v in fitted.tolist()],
    }


def calculate_standard_deviation_channel(df: pd.DataFrame, period: int = 20) -> dict:
    """Standard deviation channel (Keltner-style but purely std-based)."""
    close = df["Close"].tail(period)
    mid = close.mean()
    std = close.std()
    return {
        "midline": round(mid, 2),
        "upper_1sd": round(mid + std, 2),
        "upper_2sd": round(mid + 2 * std, 2),
        "lower_1sd": round(mid - std, 2),
        "lower_2sd": round(mid - 2 * std, 2),
        "current_z_score": round((close.iloc[-1] - mid) / std, 3) if std else 0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ICHIMOKU CLOUD
# ─────────────────────────────────────────────────────────────────────────────

class IchimokuCloud:
    """Full Ichimoku Kinko Hyo implementation."""

    @staticmethod
    def _midpoint(series_high: pd.Series, series_low: pd.Series, period: int) -> pd.Series:
        return (series_high.rolling(period).max() + series_low.rolling(period).min()) / 2

    def calculate(self, df: pd.DataFrame) -> dict:
        high = df["High"]
        low = df["Low"]
        close = df["Close"]

        tenkan = self._midpoint(high, low, 9)
        kijun = self._midpoint(high, low, 26)
        span_a = ((tenkan + kijun) / 2).shift(26)
        span_b = self._midpoint(high, low, 52).shift(26)
        chikou = close.shift(-26)

        cloud_color = np.where(span_a > span_b, "green", "red")

        return {
            "tenkan_sen": tenkan.round(2).tolist(),
            "kijun_sen": kijun.round(2).tolist(),
            "senkou_span_a": span_a.round(2).tolist(),
            "senkou_span_b": span_b.round(2).tolist(),
            "chikou_span": chikou.round(2).tolist(),
            "cloud_color": cloud_color.tolist(),
            "current": {
                "tenkan": round(tenkan.iloc[-1], 2) if not np.isnan(tenkan.iloc[-1]) else None,
                "kijun": round(kijun.iloc[-1], 2) if not np.isnan(kijun.iloc[-1]) else None,
                "span_a": round(span_a.iloc[-27], 2) if len(span_a.dropna()) > 27 else None,
                "span_b": round(span_b.iloc[-27], 2) if len(span_b.dropna()) > 27 else None,
                "cloud_color": cloud_color[-27] if len(cloud_color) > 27 else None,
            },
        }

    def get_signals(self, df: pd.DataFrame) -> dict:
        high = df["High"]
        low = df["Low"]
        close = df["Close"]

        tenkan = self._midpoint(high, low, 9)
        kijun = self._midpoint(high, low, 26)
        span_a = ((tenkan + kijun) / 2).shift(26)
        span_b = self._midpoint(high, low, 52).shift(26)
        chikou = close.shift(-26)

        # Current cloud boundaries (current bar is 26 bars ago in forward projection)
        cloud_top = span_a.combine(span_b, max)
        cloud_bot = span_a.combine(span_b, min)

        price_now = close.iloc[-1]
        cloud_top_now = cloud_top.iloc[-27] if len(cloud_top.dropna()) > 27 else None
        cloud_bot_now = cloud_bot.iloc[-27] if len(cloud_bot.dropna()) > 27 else None

        # Price vs cloud
        if cloud_top_now and cloud_bot_now:
            if price_now > cloud_top_now:
                price_position = "ABOVE_CLOUD"
            elif price_now < cloud_bot_now:
                price_position = "BELOW_CLOUD"
            else:
                price_position = "INSIDE_CLOUD"
        else:
            price_position = "UNKNOWN"

        # TK Cross
        tk_cross = "NEUTRAL"
        if len(tenkan.dropna()) >= 2 and len(kijun.dropna()) >= 2:
            if tenkan.iloc[-2] <= kijun.iloc[-2] and tenkan.iloc[-1] > kijun.iloc[-1]:
                tk_cross = "BULLISH_TK_CROSS"
            elif tenkan.iloc[-2] >= kijun.iloc[-2] and tenkan.iloc[-1] < kijun.iloc[-1]:
                tk_cross = "BEARISH_TK_CROSS"

        # Cloud twist (future cloud flip)
        future_twist = "NONE"
        if len(span_a.dropna()) >= 2 and len(span_b.dropna()) >= 2:
            recent_a = span_a.dropna().iloc[-1]
            recent_b = span_b.dropna().iloc[-1]
            prev_a = span_a.dropna().iloc[-2]
            prev_b = span_b.dropna().iloc[-2]
            if prev_a <= prev_b and recent_a > recent_b:
                future_twist = "BULLISH_KUMO_TWIST"
            elif prev_a >= prev_b and recent_a < recent_b:
                future_twist = "BEARISH_KUMO_TWIST"

        # Chikou confirmation
        chikou_signal = "NEUTRAL"
        if len(chikou.dropna()) >= 1:
            ck_price = chikou.dropna().iloc[-1]
            past_close = close.iloc[-27] if len(close) > 27 else close.iloc[0]
            chikou_signal = "BULLISH" if ck_price > past_close else "BEARISH"

        # Signal strength score 0-10
        score = 5
        if price_position == "ABOVE_CLOUD":
            score += 2
        elif price_position == "BELOW_CLOUD":
            score -= 2
        if tk_cross == "BULLISH_TK_CROSS":
            score += 1
        elif tk_cross == "BEARISH_TK_CROSS":
            score -= 1
        if future_twist == "BULLISH_KUMO_TWIST":
            score += 1
        elif future_twist == "BEARISH_KUMO_TWIST":
            score -= 1
        if chikou_signal == "BULLISH":
            score += 1
        elif chikou_signal == "BEARISH":
            score -= 1
        score = max(0, min(10, score))

        return {
            "price_position": price_position,
            "tk_cross": tk_cross,
            "cloud_twist": future_twist,
            "chikou_confirmation": chikou_signal,
            "signal_strength": score,
            "overall_signal": "BULLISH" if score >= 7 else ("BEARISH" if score <= 3 else "NEUTRAL"),
        }


# ─────────────────────────────────────────────────────────────────────────────
# SUPERTREND
# ─────────────────────────────────────────────────────────────────────────────

class SupertrendIndicator:
    """Supertrend based on ATR bands."""

    def calculate(self, df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> dict:
        hl2 = (df["High"] + df["Low"]) / 2
        atr = _atr(df, period)
        upper_band = hl2 + multiplier * atr
        lower_band = hl2 - multiplier * atr
        close = df["Close"]

        supertrend = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(index=df.index, dtype=int)  # 1 = UP, -1 = DOWN

        final_upper = upper_band.copy()
        final_lower = lower_band.copy()

        for i in range(1, len(df)):
            # Upper band
            if upper_band.iloc[i] < final_upper.iloc[i - 1] or close.iloc[i - 1] > final_upper.iloc[i - 1]:
                final_upper.iloc[i] = upper_band.iloc[i]
            else:
                final_upper.iloc[i] = final_upper.iloc[i - 1]

            # Lower band
            if lower_band.iloc[i] > final_lower.iloc[i - 1] or close.iloc[i - 1] < final_lower.iloc[i - 1]:
                final_lower.iloc[i] = lower_band.iloc[i]
            else:
                final_lower.iloc[i] = final_lower.iloc[i - 1]

            # Direction
            if i == 1:
                direction.iloc[i] = 1
            elif supertrend.iloc[i - 1] == final_upper.iloc[i - 1]:
                direction.iloc[i] = -1 if close.iloc[i] > final_upper.iloc[i] else 1
            else:
                direction.iloc[i] = 1 if close.iloc[i] < final_lower.iloc[i] else -1

            supertrend.iloc[i] = final_lower.iloc[i] if direction.iloc[i] == -1 else final_upper.iloc[i]

        # Find flip points
        flip_points = []
        for i in range(1, len(direction)):
            if direction.iloc[i] != direction.iloc[i - 1] and not np.isnan(direction.iloc[i]):
                flip_points.append({
                    "date": str(df.index[i].date()) if hasattr(df.index[i], 'date') else str(df.index[i]),
                    "price": round(close.iloc[i], 2),
                    "signal": "BUY" if direction.iloc[i] == -1 else "SELL",
                })

        current_dir = direction.iloc[-1]
        return {
            "supertrend_values": [round(v, 2) if not np.isnan(v) else None for v in supertrend.tolist()],
            "direction": ["UP" if d == -1 else "DOWN" for d in direction.tolist()],
            "current_direction": "UP" if current_dir == -1 else "DOWN",
            "current_supertrend": round(supertrend.iloc[-1], 2) if not np.isnan(supertrend.iloc[-1]) else None,
            "upper_band": [round(v, 2) if not np.isnan(v) else None for v in final_upper.tolist()],
            "lower_band": [round(v, 2) if not np.isnan(v) else None for v in final_lower.tolist()],
            "flip_points": flip_points[-10:],
        }

    def get_signals(self, df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> dict:
        result = self.calculate(df, period, multiplier)
        current_dir = result["current_direction"]
        flip_pts = result["flip_points"]

        # Most recent flip
        latest_flip = flip_pts[-1] if flip_pts else None
        signal = "NEUTRAL"
        if latest_flip:
            bars_since_flip = len(df) - 1
            for i, idx in enumerate(df.index):
                if str(idx.date()) if hasattr(idx, 'date') else str(idx) == latest_flip["date"]:
                    bars_since_flip = len(df) - 1 - i
                    break
            if bars_since_flip <= 3:
                signal = "BUY" if latest_flip["signal"] == "BUY" else "SELL"

        return {
            "current_trend": current_dir,
            "signal": signal,
            "recent_flips": flip_pts[-5:],
            "support_resistance": result["current_supertrend"],
            "description": f"Supertrend is {'bullish' if current_dir == 'UP' else 'bearish'}. "
                           f"Current level: {result['current_supertrend']}",
        }


# ─────────────────────────────────────────────────────────────────────────────
# VWAP CALCULATOR
# ─────────────────────────────────────────────────────────────────────────────

class VWAPCalculator:
    """VWAP and Anchored VWAP calculations."""

    def calculate_intraday_vwap(self, df: pd.DataFrame) -> dict:
        typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
        cum_pv = (typical_price * df["Volume"]).cumsum()
        cum_vol = df["Volume"].cumsum()
        vwap = cum_pv / cum_vol

        # SD bands
        squared_diff = ((typical_price - vwap) ** 2 * df["Volume"]).cumsum()
        variance = squared_diff / cum_vol
        std = np.sqrt(variance)

        current_vwap = vwap.iloc[-1]
        current_price = df["Close"].iloc[-1]
        current_std = std.iloc[-1]

        if current_price > current_vwap + 2 * current_std:
            position = "EXTREMELY_OVERBOUGHT"
        elif current_price > current_vwap + current_std:
            position = "OVERBOUGHT"
        elif current_price > current_vwap:
            position = "ABOVE_VWAP"
        elif current_price < current_vwap - 2 * current_std:
            position = "EXTREMELY_OVERSOLD"
        elif current_price < current_vwap - current_std:
            position = "OVERSOLD"
        else:
            position = "BELOW_VWAP"

        return {
            "vwap": [round(v, 2) if not np.isnan(v) else None for v in vwap.tolist()],
            "upper_1sd": [round(v + s, 2) if not np.isnan(v + s) else None for v, s in zip(vwap, std)],
            "upper_2sd": [round(v + 2 * s, 2) if not np.isnan(v + 2 * s) else None for v, s in zip(vwap, std)],
            "lower_1sd": [round(v - s, 2) if not np.isnan(v - s) else None for v, s in zip(vwap, std)],
            "lower_2sd": [round(v - 2 * s, 2) if not np.isnan(v - 2 * s) else None for v, s in zip(vwap, std)],
            "current_vwap": round(current_vwap, 2),
            "current_std": round(current_std, 2),
            "price_position": position,
            "deviation_pct": round((current_price - current_vwap) / current_vwap * 100, 3),
        }

    def calculate_anchored_vwap(self, df: pd.DataFrame, anchor_date: str) -> dict:
        """VWAP anchored from a specific date."""
        try:
            anchor_dt = pd.Timestamp(anchor_date)
        except Exception:
            return {"error": f"Invalid anchor_date: {anchor_date}"}

        mask = df.index >= anchor_dt
        if mask.sum() == 0:
            return {"error": "No data from anchor_date onwards"}

        anchored_df = df[mask].copy()
        typical_price = (anchored_df["High"] + anchored_df["Low"] + anchored_df["Close"]) / 3
        cum_pv = (typical_price * anchored_df["Volume"]).cumsum()
        cum_vol = anchored_df["Volume"].cumsum()
        avwap = cum_pv / cum_vol

        current_avwap = avwap.iloc[-1]
        current_price = anchored_df["Close"].iloc[-1]

        return {
            "anchor_date": anchor_date,
            "anchored_vwap": [round(v, 2) for v in avwap.tolist()],
            "current_avwap": round(current_avwap, 2),
            "current_price": round(current_price, 2),
            "price_vs_avwap": "ABOVE" if current_price > current_avwap else "BELOW",
            "deviation_pct": round((current_price - current_avwap) / current_avwap * 100, 3),
            "dates": [str(d.date()) if hasattr(d, 'date') else str(d) for d in anchored_df.index],
        }


# ─────────────────────────────────────────────────────────────────────────────
# VOLUME PROFILE
# ─────────────────────────────────────────────────────────────────────────────

class VolumeProfile:
    """Volume at Price analysis."""

    def calculate(self, df: pd.DataFrame, n_bins: int = 50) -> dict:
        price_min = df["Low"].min()
        price_max = df["High"].max()
        bins = np.linspace(price_min, price_max, n_bins + 1)
        bin_centers = (bins[:-1] + bins[1:]) / 2
        vol_at_price = np.zeros(n_bins)

        for _, row in df.iterrows():
            bar_low, bar_high, bar_vol = row["Low"], row["High"], row["Volume"]
            if bar_high == bar_low:
                continue
            for i in range(n_bins):
                overlap_low = max(bar_low, bins[i])
                overlap_high = min(bar_high, bins[i + 1])
                if overlap_high > overlap_low:
                    proportion = (overlap_high - overlap_low) / (bar_high - bar_low)
                    vol_at_price[i] += bar_vol * proportion

        poc_idx = np.argmax(vol_at_price)
        poc_price = bin_centers[poc_idx]

        # Value area (70% of volume)
        total_vol = vol_at_price.sum()
        target_vol = total_vol * 0.70
        sorted_idx = np.argsort(vol_at_price)[::-1]
        running_vol = 0
        value_area_idx = []
        for idx in sorted_idx:
            running_vol += vol_at_price[idx]
            value_area_idx.append(idx)
            if running_vol >= target_vol:
                break

        vah = bin_centers[max(value_area_idx)]
        val = bin_centers[min(value_area_idx)]

        # HVN/LVN (top/bottom 20% bins by volume)
        threshold_high = np.percentile(vol_at_price[vol_at_price > 0], 80)
        threshold_low = np.percentile(vol_at_price[vol_at_price > 0], 20)
        hvn = [round(bin_centers[i], 2) for i in range(n_bins) if vol_at_price[i] >= threshold_high]
        lvn = [round(bin_centers[i], 2) for i in range(n_bins) if vol_at_price[i] <= threshold_low and vol_at_price[i] > 0]

        return {
            "price_levels": [round(p, 2) for p in bin_centers.tolist()],
            "volume_at_price": [round(v, 0) for v in vol_at_price.tolist()],
            "poc": round(poc_price, 2),
            "vah": round(vah, 2),
            "val": round(val, 2),
            "value_area_volume_pct": 70.0,
            "hvn": hvn,
            "lvn": lvn,
            "total_volume": round(total_vol, 0),
        }

    def get_support_resistance(self, df: pd.DataFrame) -> dict:
        profile = self.calculate(df)
        current_price = df["Close"].iloc[-1]
        poc = profile["poc"]
        hvn = profile["hvn"]
        vah = profile["vah"]
        val = profile["val"]

        support_hvn = sorted([h for h in hvn if h < current_price], reverse=True)
        resistance_hvn = sorted([h for h in hvn if h > current_price])

        return {
            "poc": poc,
            "poc_relation": "SUPPORT" if poc < current_price else "RESISTANCE",
            "value_area_high": vah,
            "value_area_low": val,
            "nearest_support_hvn": support_hvn[0] if support_hvn else None,
            "nearest_resistance_hvn": resistance_hvn[0] if resistance_hvn else None,
            "all_support_hvn": support_hvn[:5],
            "all_resistance_hvn": resistance_hvn[:5],
        }


# ─────────────────────────────────────────────────────────────────────────────
# FIBONACCI ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

class FibonacciAnalysis:
    """Fibonacci retracements, extensions, and time zones."""

    RETRACEMENT_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    EXTENSION_LEVELS = [1.272, 1.414, 1.618, 2.0, 2.618]

    def calculate_retracements(self, df: pd.DataFrame, lookback: int = 60) -> dict:
        window = df.tail(lookback)
        swing_high = window["High"].max()
        swing_low = window["Low"].min()
        current = df["Close"].iloc[-1]
        rng = swing_high - swing_low

        # Determine trend direction (is price retracing from high or low?)
        high_idx = window["High"].idxmax()
        low_idx = window["Low"].idxmin()
        trend_up = window.index.get_loc(high_idx) > window.index.get_loc(low_idx)

        if trend_up:
            # Retracements from high back down (bearish retracement from swing high)
            base = swing_high
            direction = -1
        else:
            base = swing_low
            direction = 1

        ret_levels = {}
        for lvl in self.RETRACEMENT_LEVELS:
            price = swing_high - lvl * rng if trend_up else swing_low + lvl * rng
            dist = abs(current - price)
            ret_levels[f"{lvl:.3f}"] = {
                "price": round(price, 2),
                "distance_from_current": round(dist, 2),
                "distance_pct": round(dist / current * 100, 3),
                "role": "SUPPORT" if price < current else "RESISTANCE",
            }

        ext_levels = {}
        for lvl in self.EXTENSION_LEVELS:
            price = swing_low - lvl * rng if trend_up else swing_high + lvl * rng
            dist = abs(current - price)
            ext_levels[f"{lvl:.3f}"] = {
                "price": round(price, 2),
                "distance_from_current": round(dist, 2),
                "distance_pct": round(dist / current * 100, 3),
            }

        # Nearest support and resistance fib levels
        support_candidates = [(k, v) for k, v in ret_levels.items() if v["role"] == "SUPPORT"]
        resistance_candidates = [(k, v) for k, v in ret_levels.items() if v["role"] == "RESISTANCE"]

        nearest_support = min(support_candidates, key=lambda x: x[1]["distance_from_current"])[1] if support_candidates else None
        nearest_resistance = min(resistance_candidates, key=lambda x: x[1]["distance_from_current"])[1] if resistance_candidates else None

        return {
            "swing_high": round(swing_high, 2),
            "swing_low": round(swing_low, 2),
            "trend_direction": "UP" if trend_up else "DOWN",
            "retracements": ret_levels,
            "extensions": ext_levels,
            "nearest_support": nearest_support,
            "nearest_resistance": nearest_resistance,
            "current_price": round(current, 2),
        }

    def calculate_fib_time_zones(self, df: pd.DataFrame) -> list:
        """Fibonacci time zones: 1, 2, 3, 5, 8, 13, 21, 34, 55 bars after major swing."""
        fib_numbers = [1, 2, 3, 5, 8, 13, 21, 34, 55]
        close = df["Close"]
        # Detect the most recent significant swing (largest move in last 60 bars)
        window = 60
        data = close.tail(window)
        max_idx = data.idxmax()
        min_idx = data.idxmin()

        # Pick the more recent one as anchor
        if df.index.get_loc(max_idx) > df.index.get_loc(min_idx):
            anchor_pos = df.index.get_loc(max_idx)
            swing_type = "HIGH"
        else:
            anchor_pos = df.index.get_loc(min_idx)
            swing_type = "LOW"

        time_zones = []
        for fib in fib_numbers:
            future_pos = anchor_pos + fib
            if future_pos < len(df):
                date_str = str(df.index[future_pos].date()) if hasattr(df.index[future_pos], 'date') else str(df.index[future_pos])
                price_at = round(df["Close"].iloc[future_pos], 2)
                time_zones.append({"fib": fib, "bar_index": future_pos, "date": date_str, "close": price_at, "status": "PAST"})
            else:
                time_zones.append({"fib": fib, "bar_index": future_pos, "date": "FUTURE", "close": None, "status": "UPCOMING"})

        return {
            "anchor_swing": swing_type,
            "anchor_position": anchor_pos,
            "anchor_date": str(df.index[anchor_pos].date()) if hasattr(df.index[anchor_pos], 'date') else str(df.index[anchor_pos]),
            "time_zones": time_zones,
        }


# ─────────────────────────────────────────────────────────────────────────────
# CANDLESTICK PATTERNS
# ─────────────────────────────────────────────────────────────────────────────

class CandlePatterns:
    """20+ candlestick pattern detection from raw OHLC math."""

    def _body(self, o, c):
        return abs(c - o)

    def _range(self, h, l):
        return h - l

    def _upper_shadow(self, o, h, c):
        return h - max(o, c)

    def _lower_shadow(self, o, l, c):
        return min(o, c) - l

    def _is_bullish(self, o, c):
        return c > o

    def detect_all(self, df: pd.DataFrame) -> dict:
        opens = df["Open"].values
        highs = df["High"].values
        lows = df["Low"].values
        closes = df["Close"].values
        n = len(df)
        dates = [str(df.index[i].date()) if hasattr(df.index[i], 'date') else str(df.index[i]) for i in range(n)]

        patterns = []

        for i in range(2, n):
            o, h, l, c = opens[i], highs[i], lows[i], closes[i]
            po, ph, pl, pc = opens[i - 1], highs[i - 1], lows[i - 1], closes[i - 1]
            ppo, pph, ppl, ppc = opens[i - 2], highs[i - 2], lows[i - 2], closes[i - 2]

            body = self._body(o, c)
            rng = self._range(h, l)
            upper = self._upper_shadow(o, h, c)
            lower = self._lower_shadow(o, l, c)
            prev_body = self._body(po, pc)
            prev_rng = self._range(ph, pl)

            if rng == 0:
                continue

            # DOJI
            if body / rng < 0.1:
                patterns.append({"name": "Doji", "type": "NEUTRAL", "confidence": 0.7,
                                  "bar_index": i, "date": dates[i]})

            # MARUBOZU (full body, no shadows)
            if body / rng > 0.95:
                direction = "BULLISH" if self._is_bullish(o, c) else "BEARISH"
                patterns.append({"name": "Marubozu", "type": direction, "confidence": 0.8,
                                  "bar_index": i, "date": dates[i]})

            # SPINNING TOP
            if body / rng < 0.3 and upper > body and lower > body:
                patterns.append({"name": "SpinningTop", "type": "NEUTRAL", "confidence": 0.6,
                                  "bar_index": i, "date": dates[i]})

            # HAMMER (bullish reversal at downtrend bottom)
            if (lower > 2 * body and upper < 0.3 * body and
                    body / rng < 0.35 and self._is_bullish(o, c)):
                patterns.append({"name": "Hammer", "type": "BULLISH", "confidence": 0.75,
                                  "bar_index": i, "date": dates[i]})

            # SHOOTING STAR (bearish reversal)
            if (upper > 2 * body and lower < 0.3 * body and
                    body / rng < 0.35 and not self._is_bullish(o, c)):
                patterns.append({"name": "ShootingStar", "type": "BEARISH", "confidence": 0.75,
                                  "bar_index": i, "date": dates[i]})

            # PIN BAR (long tail, small body at opposite end)
            if lower > 2.5 * body and upper < 0.5 * lower:
                patterns.append({"name": "PinBar_Bullish", "type": "BULLISH", "confidence": 0.7,
                                  "bar_index": i, "date": dates[i]})
            if upper > 2.5 * body and lower < 0.5 * upper:
                patterns.append({"name": "PinBar_Bearish", "type": "BEARISH", "confidence": 0.7,
                                  "bar_index": i, "date": dates[i]})

            # BULLISH ENGULFING
            if (not self._is_bullish(po, pc) and self._is_bullish(o, c) and
                    o < pc and c > po and body > prev_body):
                patterns.append({"name": "BullishEngulfing", "type": "BULLISH", "confidence": 0.85,
                                  "bar_index": i, "date": dates[i]})

            # BEARISH ENGULFING
            if (self._is_bullish(po, pc) and not self._is_bullish(o, c) and
                    o > pc and c < po and body > prev_body):
                patterns.append({"name": "BearishEngulfing", "type": "BEARISH", "confidence": 0.85,
                                  "bar_index": i, "date": dates[i]})

            # HARAMI (body inside previous body)
            if self._is_bullish(po, pc) and not self._is_bullish(o, c) and o < pc and c > po:
                if body < prev_body * 0.6:
                    patterns.append({"name": "BearishHarami", "type": "BEARISH", "confidence": 0.65,
                                      "bar_index": i, "date": dates[i]})
            if not self._is_bullish(po, pc) and self._is_bullish(o, c) and o > pc and c < po:
                if body < prev_body * 0.6:
                    patterns.append({"name": "BullishHarami", "type": "BULLISH", "confidence": 0.65,
                                      "bar_index": i, "date": dates[i]})

            # PIERCING PATTERN (2-candle bullish reversal)
            if (not self._is_bullish(po, pc) and self._is_bullish(o, c) and
                    o < pl and c > (po + pc) / 2 and c < po):
                patterns.append({"name": "PiercingPattern", "type": "BULLISH", "confidence": 0.78,
                                  "bar_index": i, "date": dates[i]})

            # DARK CLOUD COVER (2-candle bearish reversal)
            if (self._is_bullish(po, pc) and not self._is_bullish(o, c) and
                    o > ph and c < (po + pc) / 2 and c > po):
                patterns.append({"name": "DarkCloudCover", "type": "BEARISH", "confidence": 0.78,
                                  "bar_index": i, "date": dates[i]})

            # INSIDE BAR (current high < prev high and current low > prev low)
            if h < ph and l > pl:
                patterns.append({"name": "InsideBar", "type": "NEUTRAL", "confidence": 0.65,
                                  "bar_index": i, "date": dates[i]})

            # OUTSIDE BAR (current range engulfs previous)
            if h > ph and l < pl:
                direction = "BULLISH" if self._is_bullish(o, c) else "BEARISH"
                patterns.append({"name": "OutsideBar", "type": direction, "confidence": 0.70,
                                  "bar_index": i, "date": dates[i]})

            # MORNING STAR (3-candle bullish reversal)
            if (not self._is_bullish(ppo, ppc) and
                    self._body(ppo, ppc) > 0.5 * self._range(pph, ppl) and
                    self._body(po, pc) < 0.3 * self._body(ppo, ppc) and
                    self._is_bullish(o, c) and c > (ppo + ppc) / 2):
                patterns.append({"name": "MorningStar", "type": "BULLISH", "confidence": 0.88,
                                  "bar_index": i, "date": dates[i]})

            # EVENING STAR (3-candle bearish reversal)
            if (self._is_bullish(ppo, ppc) and
                    self._body(ppo, ppc) > 0.5 * self._range(pph, ppl) and
                    self._body(po, pc) < 0.3 * self._body(ppo, ppc) and
                    not self._is_bullish(o, c) and c < (ppo + ppc) / 2):
                patterns.append({"name": "EveningStar", "type": "BEARISH", "confidence": 0.88,
                                  "bar_index": i, "date": dates[i]})

            # THREE WHITE SOLDIERS
            if i >= 3:
                o3, h3, l3, c3 = opens[i - 2], highs[i - 2], lows[i - 2], closes[i - 2]
                o2, h2, l2, c2 = opens[i - 1], highs[i - 1], lows[i - 1], closes[i - 1]
                o1, h1, l1, c1 = opens[i], highs[i], lows[i], closes[i]
                if (self._is_bullish(o3, c3) and self._is_bullish(o2, c2) and
                        self._is_bullish(o1, c1) and c3 < c2 < c1 and
                        o2 > o3 and o1 > o2):
                    patterns.append({"name": "ThreeWhiteSoldiers", "type": "BULLISH", "confidence": 0.90,
                                      "bar_index": i, "date": dates[i]})

            # THREE BLACK CROWS
            if i >= 3:
                o3, h3, l3, c3 = opens[i - 2], highs[i - 2], lows[i - 2], closes[i - 2]
                o2, h2, l2, c2 = opens[i - 1], highs[i - 1], lows[i - 1], closes[i - 1]
                o1, h1, l1, c1 = opens[i], highs[i], lows[i], closes[i]
                if (not self._is_bullish(o3, c3) and not self._is_bullish(o2, c2) and
                        not self._is_bullish(o1, c1) and c3 > c2 > c1 and
                        o2 < o3 and o1 < o2):
                    patterns.append({"name": "ThreeBlackCrows", "type": "BEARISH", "confidence": 0.90,
                                      "bar_index": i, "date": dates[i]})

            # THREE INSIDE UP
            if (not self._is_bullish(ppo, ppc) and self._body(po, pc) < self._body(ppo, ppc) * 0.6 and
                    po > ppc and pc < ppo and self._is_bullish(o, c) and c > ppo):
                patterns.append({"name": "ThreeInsideUp", "type": "BULLISH", "confidence": 0.82,
                                  "bar_index": i, "date": dates[i]})

            # THREE INSIDE DOWN
            if (self._is_bullish(ppo, ppc) and self._body(po, pc) < self._body(ppo, ppc) * 0.6 and
                    po < ppc and pc > ppo and not self._is_bullish(o, c) and c < ppo):
                patterns.append({"name": "ThreeInsideDown", "type": "BEARISH", "confidence": 0.82,
                                  "bar_index": i, "date": dates[i]})

            # TWO CROWS (bearish)
            if (self._is_bullish(ppo, ppc) and not self._is_bullish(po, pc) and
                    not self._is_bullish(o, c) and po > ppc and o > po and c < po):
                patterns.append({"name": "TwoCrows", "type": "BEARISH", "confidence": 0.75,
                                  "bar_index": i, "date": dates[i]})

        # Filter to last 30 bars only
        recent = [p for p in patterns if p["bar_index"] >= n - 30]
        bullish = [p for p in recent if p["type"] == "BULLISH"]
        bearish = [p for p in recent if p["type"] == "BEARISH"]

        return {
            "all_patterns": recent,
            "bullish_patterns": bullish,
            "bearish_patterns": bearish,
            "neutral_patterns": [p for p in recent if p["type"] == "NEUTRAL"],
            "total_bullish": len(bullish),
            "total_bearish": len(bearish),
            "bias": "BULLISH" if len(bullish) > len(bearish) else ("BEARISH" if len(bearish) > len(bullish) else "NEUTRAL"),
            "last_pattern": recent[-1] if recent else None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# WYCKOFF ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

class WyckoffAnalysis:
    """Wyckoff Method: Accumulation and Distribution phase identification."""

    def _volume_ma(self, df: pd.DataFrame, period: int = 20) -> pd.Series:
        return df["Volume"].rolling(period).mean()

    def _price_spread(self, df: pd.DataFrame) -> pd.Series:
        return df["High"] - df["Low"]

    def analyze(self, df: pd.DataFrame) -> dict:
        close = df["Close"]
        volume = df["Volume"]
        high = df["High"]
        low = df["Low"]
        n = len(df)

        vol_ma = self._volume_ma(df)
        spread = self._price_spread(df)

        # Price trend analysis
        sma_50 = _sma(close, 50)
        sma_200 = _sma(close, 200)

        # Effort vs Result analysis
        # High volume bars with small price spread = absorption (accumulation/distribution)
        effort_vs_result = []
        for i in range(20, n):
            vol_ratio = volume.iloc[i] / vol_ma.iloc[i] if vol_ma.iloc[i] > 0 else 1
            price_move = abs(close.iloc[i] - close.iloc[i - 1]) / close.iloc[i - 1] * 100
            if vol_ratio > 1.5 and price_move < 0.3:
                effort_vs_result.append({
                    "date": str(df.index[i].date()) if hasattr(df.index[i], 'date') else str(df.index[i]),
                    "type": "ABSORPTION",
                    "vol_ratio": round(vol_ratio, 2),
                    "price_move_pct": round(price_move, 3),
                })

        # Identify potential Selling Climax (SC) or Buying Climax (BC)
        # SC: large bar down on high volume at the bottom
        # BC: large bar up on high volume at the top
        climax_events = []
        for i in range(5, n):
            vol_ratio = volume.iloc[i] / vol_ma.iloc[i] if vol_ma.iloc[i] > 0 else 1
            bar_range = spread.iloc[i]
            avg_range = spread.rolling(20).mean().iloc[i]
            is_range_extreme = bar_range > 1.5 * avg_range if not np.isnan(avg_range) else False

            if vol_ratio > 2.0 and is_range_extreme:
                direction = "DOWN" if close.iloc[i] < close.iloc[i - 1] else "UP"
                climax_events.append({
                    "date": str(df.index[i].date()) if hasattr(df.index[i], 'date') else str(df.index[i]),
                    "type": "SELLING_CLIMAX" if direction == "DOWN" else "BUYING_CLIMAX",
                    "vol_ratio": round(vol_ratio, 2),
                })

        # Determine current Wyckoff phase
        current_price = close.iloc[-1]
        recent_high = high.tail(60).max()
        recent_low = low.tail(60).min()
        price_position = (current_price - recent_low) / (recent_high - recent_low) if recent_high != recent_low else 0.5

        # Volume trend in recent 20 bars vs prior 20 bars
        recent_vol = volume.tail(20).mean()
        prior_vol = volume.iloc[-40:-20].mean() if n > 40 else volume.mean()
        vol_trend = "INCREASING" if recent_vol > prior_vol else "DECREASING"

        # Price direction in recent 20 bars
        price_change_20 = (current_price - close.iloc[-20]) / close.iloc[-20] * 100 if n > 20 else 0

        # Phase assessment
        if price_position < 0.3 and vol_trend == "DECREASING" and price_change_20 > -3:
            phase = "ACCUMULATION_PHASE_B_or_C"
            composite_man = "PROFESSIONAL_BUYING_LIKELY"
        elif price_position < 0.3 and price_change_20 < -5:
            phase = "ACCUMULATION_PHASE_A_SELLING_CLIMAX"
            composite_man = "PROFESSIONAL_ACCUMULATION_STARTING"
        elif price_position > 0.7 and vol_trend == "DECREASING" and price_change_20 < 3:
            phase = "DISTRIBUTION_PHASE_B_or_C"
            composite_man = "PROFESSIONAL_SELLING_LIKELY"
        elif price_position > 0.7 and price_change_20 > 5:
            phase = "DISTRIBUTION_PHASE_A_BUYING_CLIMAX"
            composite_man = "PROFESSIONAL_DISTRIBUTION_STARTING"
        elif 0.3 <= price_position <= 0.7 and price_change_20 > 5:
            phase = "MARKUP_PHASE_E"
            composite_man = "MARKDOWN_OR_MARKUP_IN_PROGRESS"
        elif 0.3 <= price_position <= 0.7 and price_change_20 < -5:
            phase = "MARKDOWN_PHASE"
            composite_man = "MARKDOWN_IN_PROGRESS"
        else:
            phase = "RANGING_CAUSE_BUILDING"
            composite_man = "INDETERMINATE"

        # SOS (Sign of Strength) and LPS (Last Point of Support) detection
        sos_signal = None
        if n > 3:
            last_3_closes = close.tail(3).values
            last_3_vols = volume.tail(3).values
            if (last_3_closes[-1] > last_3_closes[-2] > last_3_closes[-3] and
                    last_3_vols[-1] > last_3_vols[-2] and
                    last_3_closes[-1] > recent_high * 0.97):
                sos_signal = "POTENTIAL_SOS_BREAKOUT"

        return {
            "current_phase": phase,
            "composite_man_signal": composite_man,
            "price_position_in_range": round(price_position, 3),
            "volume_trend": vol_trend,
            "price_change_20d_pct": round(price_change_20, 2),
            "effort_vs_result_signals": effort_vs_result[-5:],
            "climax_events": climax_events[-5:],
            "sos_signal": sos_signal,
            "recent_high": round(recent_high, 2),
            "recent_low": round(recent_low, 2),
            "sma50_current": round(sma_50.iloc[-1], 2) if not sma_50.isna().iloc[-1] else None,
            "sma200_current": round(sma_200.iloc[-1], 2) if not sma_200.isna().iloc[-1] else None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# ELLIOTT WAVE DETECTOR
# ─────────────────────────────────────────────────────────────────────────────

class ElliottWaveDetector:
    """Elliott Wave detection via ZigZag pivots."""

    def _zigzag(self, close: np.ndarray, min_pct: float = 0.05) -> list:
        """ZigZag algorithm: finds pivots with minimum % deviation."""
        pivots = []
        direction = None
        last_pivot_price = close[0]
        last_pivot_idx = 0

        for i in range(1, len(close)):
            change = (close[i] - last_pivot_price) / last_pivot_price

            if direction is None:
                if abs(change) >= min_pct:
                    direction = 1 if change > 0 else -1
                    pivots.append({"idx": last_pivot_idx, "price": last_pivot_price,
                                   "type": "LOW" if direction == 1 else "HIGH"})
            elif direction == 1:  # Was going up
                if change <= -min_pct:
                    # Reversal down
                    pivots.append({"idx": i - 1 if i > 0 else i, "price": max(close[last_pivot_idx:i]),
                                   "type": "HIGH"})
                    last_pivot_idx = i
                    last_pivot_price = close[i]
                    direction = -1
                elif close[i] > last_pivot_price:
                    # Extend the pivot
                    last_pivot_price = close[i]
                    last_pivot_idx = i
            elif direction == -1:  # Was going down
                if change >= min_pct:
                    # Reversal up
                    pivots.append({"idx": i - 1 if i > 0 else i, "price": min(close[last_pivot_idx:i]),
                                   "type": "LOW"})
                    last_pivot_idx = i
                    last_pivot_price = close[i]
                    direction = 1
                elif close[i] < last_pivot_price:
                    last_pivot_price = close[i]
                    last_pivot_idx = i

        # Add final pivot
        if last_pivot_idx < len(close) - 1:
            pivots.append({"idx": len(close) - 1, "price": close[-1], "type": "END"})

        return pivots

    def detect_waves(self, df: pd.DataFrame) -> dict:
        close = df["Close"].values
        min_pct = 0.03  # 3% minimum swing

        pivots = self._zigzag(close, min_pct)

        if len(pivots) < 8:
            return {
                "wave_count": None,
                "pivots": pivots,
                "confidence": 0,
                "message": "Insufficient pivots for Elliott Wave analysis. Need at least 8.",
            }

        # Label the last complete set
        # Try to identify 5-wave impulse in the last pivots
        last_pivots = pivots[-9:]  # take last 9 pivots for analysis

        wave_labels = []
        fib_ratios = {}

        # Check if alternating low-high-low-high pattern (bullish impulse)
        types = [p["type"] for p in last_pivots]
        prices = [p["price"] for p in last_pivots]

        # Simplified labeling: assign wave numbers
        labels = ["W1", "W2", "W3", "W4", "W5", "WA", "WB", "WC"]
        for j, pivot in enumerate(last_pivots[:8]):
            wave_labels.append({
                "wave": labels[j] if j < len(labels) else f"W{j}",
                "price": round(pivot["price"], 2),
                "idx": pivot["idx"],
            })

        # Fibonacci ratios between waves
        if len(prices) >= 6:
            w1 = abs(prices[1] - prices[0])
            w2 = abs(prices[2] - prices[1])
            w3 = abs(prices[3] - prices[2])
            w4 = abs(prices[4] - prices[3])
            w5 = abs(prices[5] - prices[4]) if len(prices) > 5 else None

            fib_ratios = {
                "w2_retraces_w1": round(w2 / w1, 3) if w1 else None,
                "w3_vs_w1": round(w3 / w1, 3) if w1 else None,
                "w4_retraces_w3": round(w4 / w3, 3) if w3 else None,
                "w5_vs_w1": round(w5 / w1, 3) if w5 and w1 else None,
                "ideal_w3_extension": 1.618,
                "ideal_w2_retrace": 0.618,
            }

        # Current wave assessment
        current_price = close[-1]
        if wave_labels:
            last_wave = wave_labels[-1]
            if last_wave["price"] < current_price:
                current_wave = "Possible W3 or W5 extension"
                projection = round(last_wave["price"] * 1.618, 2)
            else:
                current_wave = "Possible correction"
                projection = round(last_wave["price"] * 0.618, 2)
        else:
            current_wave = "Undetermined"
            projection = None

        # Confidence based on pivot count and fib alignment
        confidence = min(0.85, 0.5 + len(pivots) * 0.02)

        return {
            "wave_labels": wave_labels,
            "fib_ratios": fib_ratios,
            "total_pivots_detected": len(pivots),
            "current_wave_assessment": current_wave,
            "price_projection": projection,
            "confidence": round(confidence, 2),
            "pivots_last_10": pivots[-10:],
        }


# ─────────────────────────────────────────────────────────────────────────────
# MARKET MICROSTRUCTURE
# ─────────────────────────────────────────────────────────────────────────────

class MarketMicrostructure:
    """Microstructure metrics: Amihud, Kyle lambda, Roll spread, Volume clock."""

    def calculate_amihud_illiquidity(self, df: pd.DataFrame) -> float:
        """Amihud illiquidity ratio = mean(|return| / volume_in_crores)."""
        returns = df["Close"].pct_change().abs().dropna()
        volume_crores = df["Volume"].iloc[1:] * df["Close"].iloc[1:].values / 1e7  # crores
        volume_crores = volume_crores.replace(0, np.nan)
        amihud = (returns.values / volume_crores.values)
        amihud = amihud[np.isfinite(amihud)]
        return round(float(np.mean(amihud)) * 1e6, 6)  # scale for readability

    def calculate_kyle_lambda(self, df: pd.DataFrame) -> float:
        """Kyle lambda: price impact per unit order flow. Proxy using volume signed by direction."""
        price_change = df["Close"].diff()
        signed_vol = df["Volume"] * np.sign(price_change)
        signed_vol = signed_vol.replace(0, np.nan).dropna()
        price_change = price_change.reindex(signed_vol.index)

        if len(signed_vol) < 10:
            return 0.0
        try:
            slope, _, _, _, _ = stats.linregress(signed_vol.values, price_change.values)
            return round(float(slope), 8)
        except Exception:
            return 0.0

    def calculate_bid_ask_proxy(self, df: pd.DataFrame) -> float:
        """Roll's spread estimator: 2 * sqrt(-Cov(r_t, r_{t-1}))."""
        returns = df["Close"].pct_change().dropna()
        if len(returns) < 2:
            return 0.0
        cov = np.cov(returns.values[1:], returns.values[:-1])[0, 1]
        if cov < 0:
            roll_spread = 2 * np.sqrt(-cov)
        else:
            roll_spread = 0.0
        return round(roll_spread * 100, 4)  # percent

    def calculate_volume_clock(self, df: pd.DataFrame, n_buckets: int = 10) -> dict:
        """Volume-weighted time: identify high-activity periods."""
        if df.empty:
            return {}

        total_vol = df["Volume"].sum()
        bucket_size = len(df) // n_buckets

        buckets = []
        for i in range(n_buckets):
            start = i * bucket_size
            end = start + bucket_size if i < n_buckets - 1 else len(df)
            bucket_vol = df["Volume"].iloc[start:end].sum()
            vol_pct = bucket_vol / total_vol * 100 if total_vol > 0 else 0
            start_date = str(df.index[start].date()) if hasattr(df.index[start], 'date') else str(df.index[start])
            end_date = str(df.index[min(end - 1, len(df) - 1)].date()) if hasattr(df.index[min(end - 1, len(df) - 1)], 'date') else str(df.index[min(end - 1, len(df) - 1)])
            buckets.append({
                "bucket": i + 1,
                "start": start_date,
                "end": end_date,
                "volume": int(bucket_vol),
                "volume_pct": round(vol_pct, 2),
                "activity": "HIGH" if vol_pct > 100 / n_buckets * 1.5 else ("LOW" if vol_pct < 100 / n_buckets * 0.5 else "NORMAL"),
            })

        max_bucket = max(buckets, key=lambda x: x["volume"])
        return {
            "buckets": buckets,
            "highest_activity_bucket": max_bucket,
            "volume_concentration": round(max_bucket["volume_pct"], 2),
        }


# ─────────────────────────────────────────────────────────────────────────────
# ADVANCED MOMENTUM
# ─────────────────────────────────────────────────────────────────────────────

class AdvancedMomentum:
    """RSI divergence, MACD histogram analysis, Relative Strength."""

    def calculate_rsi_divergence(self, df: pd.DataFrame, rsi_period: int = 14) -> dict:
        close = df["Close"]
        rsi = _rsi(close, rsi_period)

        # Find local price peaks and troughs
        close_arr = close.values
        rsi_arr = rsi.values

        price_highs = argrelextrema(close_arr, np.greater, order=5)[0]
        price_lows = argrelextrema(close_arr, np.less, order=5)[0]

        divergences = []

        # Bearish divergence: higher price highs, lower RSI highs
        if len(price_highs) >= 2:
            for j in range(1, len(price_highs)):
                i1, i2 = price_highs[j - 1], price_highs[j]
                if (close_arr[i2] > close_arr[i1] and
                        not np.isnan(rsi_arr[i2]) and not np.isnan(rsi_arr[i1]) and
                        rsi_arr[i2] < rsi_arr[i1]):
                    divergences.append({
                        "type": "BEARISH_DIVERGENCE",
                        "bar1": int(i1), "price1": round(float(close_arr[i1]), 2), "rsi1": round(float(rsi_arr[i1]), 2),
                        "bar2": int(i2), "price2": round(float(close_arr[i2]), 2), "rsi2": round(float(rsi_arr[i2]), 2),
                        "date": str(df.index[i2].date()) if hasattr(df.index[i2], 'date') else str(df.index[i2]),
                    })

        # Bullish divergence: lower price lows, higher RSI lows
        if len(price_lows) >= 2:
            for j in range(1, len(price_lows)):
                i1, i2 = price_lows[j - 1], price_lows[j]
                if (close_arr[i2] < close_arr[i1] and
                        not np.isnan(rsi_arr[i2]) and not np.isnan(rsi_arr[i1]) and
                        rsi_arr[i2] > rsi_arr[i1]):
                    divergences.append({
                        "type": "BULLISH_DIVERGENCE",
                        "bar1": int(i1), "price1": round(float(close_arr[i1]), 2), "rsi1": round(float(rsi_arr[i1]), 2),
                        "bar2": int(i2), "price2": round(float(close_arr[i2]), 2), "rsi2": round(float(rsi_arr[i2]), 2),
                        "date": str(df.index[i2].date()) if hasattr(df.index[i2], 'date') else str(df.index[i2]),
                    })

        # Hidden bullish: higher lows in price, lower lows in RSI (trend continuation)
        hidden_divs = []
        if len(price_lows) >= 2:
            for j in range(1, len(price_lows)):
                i1, i2 = price_lows[j - 1], price_lows[j]
                if (close_arr[i2] > close_arr[i1] and
                        not np.isnan(rsi_arr[i2]) and not np.isnan(rsi_arr[i1]) and
                        rsi_arr[i2] < rsi_arr[i1]):
                    hidden_divs.append({
                        "type": "HIDDEN_BULLISH_DIVERGENCE",
                        "bar2": int(i2),
                        "date": str(df.index[i2].date()) if hasattr(df.index[i2], 'date') else str(df.index[i2]),
                    })

        recent_divs = [d for d in divergences if d["bar2"] >= len(df) - 60]
        return {
            "divergences": recent_divs,
            "hidden_divergences": hidden_divs[-5:],
            "last_rsi": round(float(rsi.iloc[-1]), 2) if not np.isnan(rsi.iloc[-1]) else None,
            "rsi_zone": "OVERBOUGHT" if rsi.iloc[-1] > 70 else ("OVERSOLD" if rsi.iloc[-1] < 30 else "NEUTRAL"),
            "total_bullish_divs": len([d for d in recent_divs if d["type"] == "BULLISH_DIVERGENCE"]),
            "total_bearish_divs": len([d for d in recent_divs if d["type"] == "BEARISH_DIVERGENCE"]),
        }

    def calculate_macd_histogram_trend(self, df: pd.DataFrame) -> dict:
        close = df["Close"]
        ema12 = _ema(close, 12)
        ema26 = _ema(close, 26)
        macd_line = ema12 - ema26
        signal_line = _ema(macd_line, 9)
        histogram = macd_line - signal_line

        hist_values = histogram.dropna().values
        if len(hist_values) < 5:
            return {"error": "Insufficient data"}

        # Momentum: is histogram expanding or contracting?
        recent_5 = hist_values[-5:]
        if recent_5[-1] > recent_5[-2] > recent_5[-3]:
            momentum = "EXPANDING_POSITIVE" if recent_5[-1] > 0 else "EXPANDING_NEGATIVE"
        elif recent_5[-1] < recent_5[-2] < recent_5[-3]:
            momentum = "CONTRACTING_POSITIVE" if recent_5[-1] > 0 else "CONTRACTING_NEGATIVE"
        else:
            momentum = "MIXED"

        # Three drives pattern: three consecutive peaks in histogram
        hist_peaks = argrelextrema(hist_values, np.greater, order=3)[0]
        hist_troughs = argrelextrema(hist_values, np.less, order=3)[0]

        three_drives_bullish = False
        three_drives_bearish = False
        if len(hist_troughs) >= 3:
            last3 = hist_troughs[-3:]
            if hist_values[last3[0]] > hist_values[last3[1]] > hist_values[last3[2]]:
                three_drives_bullish = True
        if len(hist_peaks) >= 3:
            last3 = hist_peaks[-3:]
            if hist_values[last3[0]] < hist_values[last3[1]] < hist_values[last3[2]]:
                three_drives_bearish = True

        # Zero line cross
        zero_cross = "NONE"
        if len(hist_values) >= 2:
            if hist_values[-2] < 0 <= hist_values[-1]:
                zero_cross = "BULLISH_ZERO_CROSS"
            elif hist_values[-2] > 0 >= hist_values[-1]:
                zero_cross = "BEARISH_ZERO_CROSS"

        return {
            "current_histogram": round(float(hist_values[-1]), 4),
            "momentum": momentum,
            "zero_cross": zero_cross,
            "three_drives_bullish": three_drives_bullish,
            "three_drives_bearish": three_drives_bearish,
            "macd_line": round(float(macd_line.iloc[-1]), 4),
            "signal_line": round(float(signal_line.iloc[-1]), 4),
            "histogram_trend": "BULLISH" if hist_values[-1] > 0 else "BEARISH",
        }

    def calculate_relative_strength(self, symbol: str, benchmark: str = "^NSEI", period: int = 52) -> dict:
        """Relative strength vs benchmark (weekly periods)."""
        try:
            sym_ticker = yf.Ticker(f"{symbol}.NS")
            bench_ticker = yf.Ticker(benchmark)

            sym_data = sym_ticker.history(period="2y", interval="1wk")["Close"]
            bench_data = bench_ticker.history(period="2y", interval="1wk")["Close"]

            if sym_data.empty or bench_data.empty:
                return {"error": "No data available"}

            # Align
            common_idx = sym_data.index.intersection(bench_data.index)
            sym_data = sym_data.reindex(common_idx)
            bench_data = bench_data.reindex(common_idx)

            # RS ratio
            rs_ratio = sym_data / bench_data
            rs_ratio_normalized = (rs_ratio / rs_ratio.mean()) * 100

            # RS momentum (rate of change of RS line)
            rs_momentum = rs_ratio.pct_change(4) * 100  # 4-week ROC

            # JdK RS-Ratio and Momentum for RRG
            jdk_rs_ratio = rs_ratio_normalized
            jdk_rs_momentum = rs_momentum

            # Current values
            current_rs = float(rs_ratio_normalized.iloc[-1])
            current_mom = float(jdk_rs_momentum.iloc[-1]) if not np.isnan(jdk_rs_momentum.iloc[-1]) else 0

            # RRG quadrant
            if current_rs >= 100 and current_mom >= 0:
                rrg_quadrant = "LEADING"
            elif current_rs < 100 and current_mom >= 0:
                rrg_quadrant = "IMPROVING"
            elif current_rs >= 100 and current_mom < 0:
                rrg_quadrant = "WEAKENING"
            else:
                rrg_quadrant = "LAGGING"

            period_return_sym = (sym_data.iloc[-1] / sym_data.iloc[-period] - 1) * 100 if len(sym_data) > period else None
            period_return_bench = (bench_data.iloc[-1] / bench_data.iloc[-period] - 1) * 100 if len(bench_data) > period else None

            return {
                "symbol": symbol,
                "benchmark": benchmark,
                "rs_ratio_current": round(current_rs, 3),
                "rs_momentum_current": round(current_mom, 3),
                "rrg_quadrant": rrg_quadrant,
                "period_return_symbol_pct": round(period_return_sym, 2) if period_return_sym else None,
                "period_return_benchmark_pct": round(period_return_bench, 2) if period_return_bench else None,
                "outperforming": (period_return_sym or 0) > (period_return_bench or 0),
                "alpha": round((period_return_sym or 0) - (period_return_bench or 0), 2),
            }
        except Exception as e:
            return {"error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# DETECT ADVANCED CHART PATTERNS
# ─────────────────────────────────────────────────────────────────────────────

def detect_chart_patterns_advanced(df: pd.DataFrame) -> list:
    """Cup & Handle, Flag, Pennant, Wedge, Triangle detection."""
    close = df["Close"].values
    high = df["High"].values
    low = df["Low"].values
    n = len(close)
    patterns = []

    if n < 30:
        return patterns

    # CUP AND HANDLE
    # Cup: U-shaped decline and recovery over 30-60 bars
    for start in range(0, n - 30, 10):
        window = close[start:start + 30]
        cup_left = window[0]
        cup_bottom = window[10:20].min()
        cup_right = window[-1]
        cup_depth = (cup_left - cup_bottom) / cup_left if cup_left > 0 else 0
        if (cup_depth > 0.10 and abs(cup_right - cup_left) / cup_left < 0.05 and
                cup_bottom < cup_left * 0.95):
            # Handle: small pullback after the cup
            if start + 35 < n:
                handle_high = high[start + 28:start + 35].max()
                handle_low = low[start + 28:start + 35].min()
                handle_depth = (handle_high - handle_low) / handle_high if handle_high > 0 else 0
                if handle_depth < cup_depth * 0.5:
                    patterns.append({
                        "pattern": "CupAndHandle",
                        "type": "BULLISH",
                        "start_bar": start,
                        "end_bar": start + 35,
                        "confidence": 0.72,
                        "breakout_level": round(cup_right, 2),
                    })

    # FLAG PATTERN (consolidation after sharp move)
    for i in range(20, n - 10):
        # Prior pole: sharp move up in 10 bars
        pole_return = (close[i - 10] - close[i - 20]) / close[i - 20] if close[i - 20] > 0 else 0
        if pole_return > 0.08:  # 8% pole
            # Flag: consolidation (slight drift lower)
            flag_high = high[i - 10:i].max()
            flag_low = low[i - 10:i].min()
            flag_range = (flag_high - flag_low) / flag_low if flag_low > 0 else 0
            if flag_range < 0.05:  # tight consolidation
                patterns.append({
                    "pattern": "BullishFlag",
                    "type": "BULLISH",
                    "start_bar": i - 20,
                    "end_bar": i,
                    "pole_return_pct": round(pole_return * 100, 2),
                    "confidence": 0.70,
                })
        elif pole_return < -0.08:
            flag_high = high[i - 10:i].max()
            flag_low = low[i - 10:i].min()
            flag_range = (flag_high - flag_low) / flag_low if flag_low > 0 else 0
            if flag_range < 0.05:
                patterns.append({
                    "pattern": "BearishFlag",
                    "type": "BEARISH",
                    "start_bar": i - 20,
                    "end_bar": i,
                    "pole_return_pct": round(pole_return * 100, 2),
                    "confidence": 0.70,
                })

    # TRIANGLE PATTERNS (symmetric, ascending, descending)
    if n >= 40:
        window_high = high[-40:]
        window_low = low[-40:]
        x = np.arange(40)

        # Trend of highs and lows
        hi_slope, _, _, _, _ = stats.linregress(x, window_high)
        lo_slope, _, _, _, _ = stats.linregress(x, window_low)

        if abs(hi_slope) < 0.01 and lo_slope > 0.01:
            patterns.append({"pattern": "AscendingTriangle", "type": "BULLISH",
                              "confidence": 0.75, "breakout_level": round(window_high.max(), 2)})
        elif hi_slope < -0.01 and abs(lo_slope) < 0.01:
            patterns.append({"pattern": "DescendingTriangle", "type": "BEARISH",
                              "confidence": 0.75, "support_level": round(window_low.min(), 2)})
        elif hi_slope < -0.005 and lo_slope > 0.005:
            patterns.append({"pattern": "SymmetricTriangle", "type": "NEUTRAL",
                              "confidence": 0.65, "apex_price": round((window_high[-1] + window_low[-1]) / 2, 2)})

    # RISING/FALLING WEDGE
    if n >= 30:
        window_high = high[-30:]
        window_low = low[-30:]
        x = np.arange(30)
        hi_slope, _, _, _, _ = stats.linregress(x, window_high)
        lo_slope, _, _, _, _ = stats.linregress(x, window_low)
        if hi_slope > 0 and lo_slope > 0 and lo_slope > hi_slope:
            patterns.append({"pattern": "RisingWedge", "type": "BEARISH", "confidence": 0.68})
        elif hi_slope < 0 and lo_slope < 0 and hi_slope < lo_slope:
            patterns.append({"pattern": "FallingWedge", "type": "BULLISH", "confidence": 0.68})

    # Return unique last 10
    return patterns[-10:]


# ─────────────────────────────────────────────────────────────────────────────
# TECHNICAL SUMMARY (MAIN API INTERFACE)
# ─────────────────────────────────────────────────────────────────────────────

class TechnicalSummary:
    """Main API interface: full technical analysis aggregator."""

    def __init__(self):
        self.ichimoku = IchimokuCloud()
        self.supertrend = SupertrendIndicator()
        self.vwap = VWAPCalculator()
        self.vol_profile = VolumeProfile()
        self.fib = FibonacciAnalysis()
        self.candles = CandlePatterns()
        self.wyckoff = WyckoffAnalysis()
        self.elliott = ElliottWaveDetector()
        self.microstructure = MarketMicrostructure()
        self.momentum = AdvancedMomentum()

    def get_full_analysis(self, symbol: str) -> dict:
        """Download data and run all indicators."""
        try:
            ticker = yf.Ticker(f"{symbol}.NS")
            df = ticker.history(period="2y")
        except Exception as e:
            return {"error": f"Failed to fetch data for {symbol}: {str(e)}"}

        if df.empty or len(df) < 60:
            return {"error": f"Insufficient data for {symbol}"}

        df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
        close = df["Close"]
        current_price = round(float(close.iloc[-1]), 2)

        results = {"symbol": symbol, "current_price": current_price, "timestamp": datetime.now().isoformat()}

        # --- Ichimoku ---
        try:
            results["ichimoku"] = {
                "data": self.ichimoku.calculate(df),
                "signals": self.ichimoku.get_signals(df),
            }
        except Exception as e:
            results["ichimoku"] = {"error": str(e)}

        # --- Supertrend ---
        try:
            results["supertrend"] = self.supertrend.get_signals(df)
        except Exception as e:
            results["supertrend"] = {"error": str(e)}

        # --- VWAP ---
        try:
            results["vwap"] = self.vwap.calculate_intraday_vwap(df)
        except Exception as e:
            results["vwap"] = {"error": str(e)}

        # --- Volume Profile ---
        try:
            results["volume_profile"] = {
                "profile": self.vol_profile.calculate(df),
                "sr_levels": self.vol_profile.get_support_resistance(df),
            }
        except Exception as e:
            results["volume_profile"] = {"error": str(e)}

        # --- Fibonacci ---
        try:
            results["fibonacci"] = {
                "retracements": self.fib.calculate_retracements(df),
                "time_zones": self.fib.calculate_fib_time_zones(df),
            }
        except Exception as e:
            results["fibonacci"] = {"error": str(e)}

        # --- Candlestick Patterns ---
        try:
            results["candle_patterns"] = self.candles.detect_all(df)
        except Exception as e:
            results["candle_patterns"] = {"error": str(e)}

        # --- Wyckoff ---
        try:
            results["wyckoff"] = self.wyckoff.analyze(df)
        except Exception as e:
            results["wyckoff"] = {"error": str(e)}

        # --- Elliott Wave ---
        try:
            results["elliott_wave"] = self.elliott.detect_waves(df)
        except Exception as e:
            results["elliott_wave"] = {"error": str(e)}

        # --- Market Microstructure ---
        try:
            results["microstructure"] = {
                "amihud_illiquidity": self.microstructure.calculate_amihud_illiquidity(df),
                "kyle_lambda": self.microstructure.calculate_kyle_lambda(df),
                "roll_bid_ask_spread_pct": self.microstructure.calculate_bid_ask_proxy(df),
                "volume_clock": self.microstructure.calculate_volume_clock(df),
            }
        except Exception as e:
            results["microstructure"] = {"error": str(e)}

        # --- Advanced Momentum ---
        try:
            results["momentum"] = {
                "rsi_divergence": self.momentum.calculate_rsi_divergence(df),
                "macd_histogram": self.momentum.calculate_macd_histogram_trend(df),
                "relative_strength": self.momentum.calculate_relative_strength(symbol),
            }
        except Exception as e:
            results["momentum"] = {"error": str(e)}

        # --- Pivot Points (last candle) ---
        try:
            last_high = float(df["High"].iloc[-1])
            last_low = float(df["Low"].iloc[-1])
            last_close = float(df["Close"].iloc[-1])
            results["pivot_points"] = calculate_pivot_points(last_high, last_low, last_close)
        except Exception as e:
            results["pivot_points"] = {"error": str(e)}

        # --- Support / Resistance ---
        try:
            results["support_resistance"] = calculate_support_resistance(df)
        except Exception as e:
            results["support_resistance"] = {"error": str(e)}

        # --- Heikin Ashi ---
        try:
            ha = calculate_heikin_ashi(df)
            results["heikin_ashi"] = {
                "last_5": ha.tail(5).round(2).to_dict(orient="records"),
                "trend": "BULLISH" if ha["HA_Close"].iloc[-1] > ha["HA_Open"].iloc[-1] else "BEARISH",
            }
        except Exception as e:
            results["heikin_ashi"] = {"error": str(e)}

        # --- Regression Channel ---
        try:
            results["regression_channel"] = calculate_linear_regression_channel(df)
        except Exception as e:
            results["regression_channel"] = {"error": str(e)}

        # --- Chart Patterns ---
        try:
            results["chart_patterns"] = detect_chart_patterns_advanced(df)
        except Exception as e:
            results["chart_patterns"] = {"error": str(e)}

        # ── COMPOSITE TECHNICAL SCORE (0-100) ──
        bullish_signals = 0
        bearish_signals = 0
        total_signals = 0

        def _count(val, bull_cond, bear_cond):
            nonlocal bullish_signals, bearish_signals, total_signals
            total_signals += 1
            if bull_cond:
                bullish_signals += 1
            elif bear_cond:
                bearish_signals += 1

        # Ichimoku
        ich_sig = results.get("ichimoku", {}).get("signals", {})
        _count(ich_sig, ich_sig.get("overall_signal") == "BULLISH", ich_sig.get("overall_signal") == "BEARISH")

        # Supertrend
        st_sig = results.get("supertrend", {})
        _count(st_sig, st_sig.get("current_trend") == "UP", st_sig.get("current_trend") == "DOWN")

        # VWAP
        vwap_sig = results.get("vwap", {})
        pos = vwap_sig.get("price_position", "")
        _count(vwap_sig, "ABOVE" in pos, "BELOW" in pos or "OVERSOLD" in pos)

        # Candle patterns
        cp = results.get("candle_patterns", {})
        _count(cp, cp.get("bias") == "BULLISH", cp.get("bias") == "BEARISH")

        # Heikin Ashi
        ha_sig = results.get("heikin_ashi", {})
        _count(ha_sig, ha_sig.get("trend") == "BULLISH", ha_sig.get("trend") == "BEARISH")

        # MACD histogram
        macd_h = results.get("momentum", {}).get("macd_histogram", {})
        _count(macd_h, macd_h.get("histogram_trend") == "BULLISH", macd_h.get("histogram_trend") == "BEARISH")

        # RSI divergence
        rsi_div = results.get("momentum", {}).get("rsi_divergence", {})
        _count(rsi_div, rsi_div.get("total_bullish_divs", 0) > 0, rsi_div.get("total_bearish_divs", 0) > 0)

        # Wyckoff
        wy = results.get("wyckoff", {})
        _count(wy, "ACCUMULATION" in wy.get("current_phase", ""), "DISTRIBUTION" in wy.get("current_phase", ""))

        composite_score = int((bullish_signals / total_signals) * 100) if total_signals > 0 else 50

        results["composite_technical_score"] = {
            "score": composite_score,
            "bullish_signals": bullish_signals,
            "bearish_signals": bearish_signals,
            "neutral_signals": total_signals - bullish_signals - bearish_signals,
            "total_signals": total_signals,
            "interpretation": (
                "STRONG_BULLISH" if composite_score >= 75 else
                "BULLISH" if composite_score >= 60 else
                "NEUTRAL" if composite_score >= 40 else
                "BEARISH" if composite_score >= 25 else
                "STRONG_BEARISH"
            ),
        }

        return results
