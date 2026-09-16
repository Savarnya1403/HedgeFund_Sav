"""
TimesFM 2.5 Prediction Service — runs on port 8002 with Python 3.11
Google's TimesFM foundation model for zero-shot time-series forecasting.

Usage:
  cd ~/IndianHedgeFund/backend
  source .venv311/bin/activate
  python3 timesfm_service.py

Endpoints served:
  GET /health
  GET /predict/{symbol}?horizon=30
  GET /predict/batch?symbols=HDFCBANK,RELIANCE&horizon=30
  GET /portfolio-forecast?symbols=HDFCBANK,RELIANCE,TCS&horizon=30
"""

import os, time, logging, warnings
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── TimesFM Model ──────────────────────────────────────────────────

_tfm = None
_tfm_load_error: Optional[str] = None

def _load_timesfm():
    global _tfm, _tfm_load_error
    if _tfm is not None:
        return _tfm
    if _tfm_load_error:
        return None
    try:
        import timesfm
        logger.info("Loading TimesFM 2.5 200M (PyTorch, CPU) from HuggingFace — this may take ~60s on first run...")
        _tfm = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
            "google/timesfm-2.5-200m-pytorch",
        )
        # Must compile before calling forecast — set max_horizon >= any horizon we'll request
        # per_core_batch_size=1 avoids padding issues for single-series inference
        _tfm.compile(timesfm.ForecastConfig(
            max_horizon=128,
            per_core_batch_size=1,
            normalize_inputs=True,
        ))
        logger.info("TimesFM 2.5 loaded and compiled successfully")
        return _tfm
    except Exception as e:
        _tfm_load_error = str(e)
        logger.error(f"TimesFM load failed: {e}")
        return None

# ── Data Fetching ──────────────────────────────────────────────────

def _fetch_price_series(symbol: str, period: str = "2y") -> Optional[pd.Series]:
    """Fetch NSE closing prices via yfinance."""
    sym = symbol.upper().strip()
    if not sym.endswith(".NS") and not sym.startswith("^"):
        sym = f"{sym}.NS"
    try:
        ticker = yf.Ticker(sym)
        hist = ticker.history(period=period)
        if hist.empty:
            return None
        return hist["Close"].dropna()
    except Exception as e:
        logger.error(f"yfinance fetch failed for {sym}: {e}")
        return None

def _compute_features(series: pd.Series) -> Dict[str, Any]:
    """Compute statistical features of the price series."""
    pct = series.pct_change().dropna()
    returns_30d = series.iloc[-1] / series.iloc[-30] - 1 if len(series) >= 30 else 0
    returns_90d = series.iloc[-1] / series.iloc[-90] - 1 if len(series) >= 90 else 0
    returns_1y = series.iloc[-1] / series.iloc[-252] - 1 if len(series) >= 252 else 0
    ann_vol = pct.std() * (252 ** 0.5)
    sma20 = series.rolling(20).mean().iloc[-1]
    sma50 = series.rolling(50).mean().iloc[-1]
    sma200 = series.rolling(200).mean().iloc[-1] if len(series) >= 200 else None
    return {
        "current_price": float(series.iloc[-1]),
        "returns_30d": float(returns_30d),
        "returns_90d": float(returns_90d),
        "returns_1y": float(returns_1y),
        "ann_vol": float(ann_vol),
        "sma20": float(sma20),
        "sma50": float(sma50),
        "sma200": float(sma200) if sma200 else None,
        "above_sma20": bool(series.iloc[-1] > sma20),
        "above_sma50": bool(series.iloc[-1] > sma50),
        "above_sma200": bool(series.iloc[-1] > sma200) if sma200 else None,
        "52w_high": float(series.rolling(252).max().iloc[-1]) if len(series) >= 252 else float(series.max()),
        "52w_low": float(series.rolling(252).min().iloc[-1]) if len(series) >= 252 else float(series.min()),
    }

def _run_timesfm_forecast(series: pd.Series, horizon: int) -> Dict[str, Any]:
    """Run TimesFM forecast and return predictions with confidence intervals."""
    tfm = _load_timesfm()
    if tfm is None:
        return {"error": "TimesFM model not loaded"}

    # TimesFM 2.5 patch size is 32 — context must be a multiple of 32
    PATCH_SIZE = 32
    MAX_CTX = 512  # 512 = 32 * 16
    raw = series.values[-MAX_CTX:].astype(np.float32)
    # Pad or trim to nearest multiple of PATCH_SIZE
    n = len(raw)
    target = min(MAX_CTX, ((n + PATCH_SIZE - 1) // PATCH_SIZE) * PATCH_SIZE)
    if n < target:
        # Pad at the front by repeating first value
        context = np.concatenate([np.full(target - n, raw[0]), raw])
    else:
        context = raw[-target:]

    try:
        # TimesFM 2.5 API: forecast(horizon, inputs)
        # Returns (point_forecast [n_series, horizon], quantile_forecast [n_series, horizon, n_quantiles])
        # Runs with normalize_inputs=True so no manual scaling needed
        point_forecast, quantile_forecast = tfm.forecast(
            horizon=horizon,
            inputs=[context],
        )

        pf = np.array(point_forecast[0][:horizon])
        qf = np.array(quantile_forecast[0][:horizon])  # shape [horizon, 10]

        # Build forecast dates (business days only)
        last_date = pd.Timestamp(series.index[-1])
        forecast_dates = pd.bdate_range(start=last_date + timedelta(days=1), periods=horizon)

        # Quantiles: [0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]  (10 quantiles)
        n_q = qf.shape[1] if qf.ndim == 2 else 0
        q10 = qf[:, 1].tolist() if n_q > 1 else pf.tolist()   # 10th percentile
        q50 = qf[:, 5].tolist() if n_q > 5 else pf.tolist()   # 50th (median)
        q90 = qf[:, 9].tolist() if n_q > 9 else pf.tolist()   # 90th percentile

        # Compute predicted return and direction
        pred_return = (pf[-1] - series.iloc[-1]) / series.iloc[-1]
        direction = "bullish" if pred_return > 0.02 else "bearish" if pred_return < -0.02 else "neutral"

        return {
            "forecast": [
                {
                    "date": str(d.date()),
                    "predicted": round(float(p), 2),
                    "lower_80": round(float(q10[i]), 2),
                    "median": round(float(q50[i]), 2),
                    "upper_80": round(float(q90[i]), 2),
                }
                for i, (d, p) in enumerate(zip(forecast_dates, pf))
            ],
            "summary": {
                "horizon_days": horizon,
                "current_price": round(float(series.iloc[-1]), 2),
                "predicted_price_end": round(float(pf[-1]), 2),
                "predicted_return_pct": round(float(pred_return * 100), 2),
                "direction": direction,
                "confidence": "high" if abs(pred_return) > 0.05 else "medium" if abs(pred_return) > 0.02 else "low",
                "price_range_end": {
                    "low": round(float(q10[-1]), 2),
                    "median": round(float(q50[-1]), 2),
                    "high": round(float(q90[-1]), 2),
                },
            },
        }
    except Exception as e:
        logger.error(f"TimesFM forecast error: {e}")
        return {"error": str(e)}

# ── FastAPI App ────────────────────────────────────────────────────

app = FastAPI(title="TimesFM Prediction Service", version="2.5.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class _NpEncoder:
    @staticmethod
    def safe(obj):
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)):
            return None if (np.isnan(obj) or np.isinf(obj)) else float(obj)
        if isinstance(obj, np.bool_): return bool(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        return obj

def _safe_json(data):
    import json
    def _convert(o):
        if isinstance(o, dict): return {k: _convert(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)): return [_convert(v) for v in o]
        return _NpEncoder.safe(o)
    return json.loads(json.dumps(_convert(data), default=str))


@app.on_event("startup")
async def startup():
    import asyncio
    loop = asyncio.get_event_loop()
    logger.info("TimesFM service starting — pre-loading model...")
    await loop.run_in_executor(None, _load_timesfm)


@app.get("/health")
async def health():
    model_ok = _tfm is not None
    return {
        "status": "ok" if model_ok else "degraded",
        "model": "TimesFM 2.5 200M (PyTorch CPU)",
        "model_loaded": model_ok,
        "model_error": _tfm_load_error,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/predict/{symbol}")
async def predict(symbol: str, horizon: int = Query(default=30, ge=1, le=128)):
    """
    Zero-shot price forecast for a single NSE stock or index using TimesFM.

    - **symbol**: NSE symbol (e.g., HDFCBANK, RELIANCE, NIFTY50)
    - **horizon**: Forecast horizon in trading days (1-128, default 30)
    """
    import asyncio
    loop = asyncio.get_event_loop()

    def compute():
        series = _fetch_price_series(symbol)
        if series is None or len(series) < 60:
            return {"error": f"Insufficient price data for {symbol}", "symbol": symbol}

        features = _compute_features(series)
        forecast_result = _run_timesfm_forecast(series, horizon)

        if "error" in forecast_result:
            return {**forecast_result, "symbol": symbol, "features": features}

        return {
            "symbol": symbol.upper(),
            "model": "TimesFM 2.5 200M",
            "generated_at": datetime.now().isoformat(),
            "context_length": min(512, len(series)),
            "features": features,
            **forecast_result,
        }

    result = await loop.run_in_executor(None, compute)
    return JSONResponse(content=_safe_json(result))


@app.get("/predict/batch")
async def predict_batch(
    symbols: str = Query(..., description="Comma-separated NSE symbols"),
    horizon: int = Query(default=30, ge=1, le=128)
):
    """Forecast multiple stocks in one call."""
    import asyncio
    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()][:10]
    if not syms:
        raise HTTPException(400, "No symbols provided")

    loop = asyncio.get_event_loop()

    def compute_one(sym):
        series = _fetch_price_series(sym)
        if series is None or len(series) < 60:
            return {"symbol": sym, "error": "Insufficient data"}
        features = _compute_features(series)
        forecast = _run_timesfm_forecast(series, horizon)
        return {"symbol": sym, "features": features, **forecast}

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(compute_one, syms))

    return JSONResponse(content=_safe_json({
        "symbols": syms,
        "horizon": horizon,
        "model": "TimesFM 2.5 200M",
        "generated_at": datetime.now().isoformat(),
        "predictions": results,
    }))


@app.get("/portfolio-forecast")
async def portfolio_forecast(
    symbols: str = Query(..., description="Comma-separated NSE symbols"),
    horizon: int = Query(default=30, ge=1, le=128)
):
    """
    Forecast portfolio-level expected returns and risk using TimesFM predictions.
    Returns individual forecasts + portfolio-level summary with correlation-adjusted views.
    """
    import asyncio
    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()][:15]
    if not syms:
        raise HTTPException(400, "No symbols provided")

    loop = asyncio.get_event_loop()

    def compute():
        forecasts = {}
        series_map = {}
        for sym in syms:
            s = _fetch_price_series(sym, period="2y")
            if s is not None and len(s) >= 60:
                series_map[sym] = s
                fc = _run_timesfm_forecast(s, horizon)
                if "error" not in fc:
                    forecasts[sym] = fc

        if not forecasts:
            return {"error": "No valid data for any symbol"}

        # Build returns matrix for correlation
        ret_df = pd.DataFrame({
            sym: series_map[sym].pct_change().dropna()
            for sym in series_map if sym in forecasts
        }).dropna()

        corr_matrix = ret_df.corr().round(3).to_dict() if len(ret_df.columns) > 1 else {}

        # Portfolio-level expected return (equal-weight)
        n = len(forecasts)
        port_expected_return = np.mean([
            fc["summary"]["predicted_return_pct"] for fc in forecasts.values()
        ])
        port_volatility = float(ret_df.std().mean() * (252 ** 0.5) * 100)

        # Rank by predicted return
        ranked = sorted(
            [{"symbol": s, "predicted_return_pct": fc["summary"]["predicted_return_pct"],
              "direction": fc["summary"]["direction"]} for s, fc in forecasts.items()],
            key=lambda x: x["predicted_return_pct"], reverse=True
        )

        return {
            "symbols": syms,
            "valid_symbols": list(forecasts.keys()),
            "horizon": horizon,
            "model": "TimesFM 2.5 200M",
            "generated_at": datetime.now().isoformat(),
            "individual_forecasts": {
                sym: {
                    "summary": fc["summary"],
                    "forecast_7d": fc["forecast"][:7] if len(fc["forecast"]) >= 7 else fc["forecast"],
                    "forecast_30d_end": fc["forecast"][-1] if fc["forecast"] else None,
                }
                for sym, fc in forecasts.items()
            },
            "portfolio_summary": {
                "equal_weight_expected_return_pct": round(float(port_expected_return), 2),
                "avg_ann_volatility_pct": round(port_volatility, 2),
                "bullish_count": sum(1 for fc in forecasts.values() if fc["summary"]["direction"] == "bullish"),
                "bearish_count": sum(1 for fc in forecasts.values() if fc["summary"]["direction"] == "bearish"),
                "neutral_count": sum(1 for fc in forecasts.values() if fc["summary"]["direction"] == "neutral"),
                "top_picks": ranked[:3],
                "avoid": [r for r in ranked if r["predicted_return_pct"] < -2][:3],
            },
            "correlation_matrix": corr_matrix,
        }

    result = await loop.run_in_executor(None, compute)
    return JSONResponse(content=_safe_json(result))


@app.get("/sector-forecast")
async def sector_forecast(horizon: int = Query(default=30, ge=1, le=128)):
    """Forecast key sector ETFs / indices using TimesFM."""
    sector_symbols = {
        "NIFTY50": "^NSEI",
        "BANKEX": "^NSEBANK",
        "IT": "^CNXIT",
        "Pharma": "^CNXPHARMA",
        "FMCG": "^CNXFMCG",
        "Auto": "^CNXAUTO",
        "Metal": "^CNXMETAL",
        "Realty": "^CNXREALTY",
    }
    import asyncio, concurrent.futures
    loop = asyncio.get_event_loop()

    def compute_sector(name_sym):
        name, sym = name_sym
        try:
            series = _fetch_price_series(sym, period="2y")
            if series is None or len(series) < 60:
                return name, {"error": "Insufficient data"}
            fc = _run_timesfm_forecast(series, horizon)
            return name, fc.get("summary", {"error": "forecast failed"})
        except Exception as e:
            return name, {"error": str(e)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        results = dict(ex.map(compute_sector, sector_symbols.items()))

    ranked = sorted(
        [(k, v.get("predicted_return_pct", 0)) for k, v in results.items() if "error" not in v],
        key=lambda x: x[1], reverse=True
    )

    return JSONResponse(content=_safe_json({
        "horizon_days": horizon,
        "model": "TimesFM 2.5 200M",
        "generated_at": datetime.now().isoformat(),
        "sectors": results,
        "sector_ranking": [{"sector": k, "predicted_return_pct": round(v, 2)} for k, v in ranked],
        "top_sector": ranked[0][0] if ranked else None,
        "worst_sector": ranked[-1][0] if ranked else None,
    }))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
