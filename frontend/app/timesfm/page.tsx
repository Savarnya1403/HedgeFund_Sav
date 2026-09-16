"use client";
import { useState, useEffect } from "react";

const API = "http://localhost:8001";

const PRESET_SYMBOLS = [
  "HDFCBANK","RELIANCE","TCS","INFY","ICICIBANK","HINDUNILVR","BAJFINANCE",
  "KOTAKBANK","LTIM","WIPRO","AXISBANK","ITC","SBIN","MARUTI","ASIANPAINT",
  "TITAN","NESTLEIND","ULTRACEMCO","SUNPHARMA","TATAMOTORS","BHARTIARTL",
  "TECHM","ADANIPORTS","POWERGRID","NTPC",
];

const SECTORS = [
  {label:"NIFTY 50", sym:"NSEI"},{label:"Bank Nifty", sym:"NSEBANK"},
  {label:"IT", sym:"CNXIT"},{label:"Pharma", sym:"CNXPHARMA"},
  {label:"FMCG", sym:"CNXFMCG"},{label:"Auto", sym:"CNXAUTO"},
  {label:"Metal", sym:"CNXMETAL"},{label:"Realty", sym:"CNXREALTY"},
];

function MiniChart({ forecast }: { forecast: {date:string;predicted:number;lower_80:number;upper_80:number}[] }) {
  if (!forecast || forecast.length === 0) return null;
  const prices = forecast.map(f => f.predicted);
  const lows = forecast.map(f => f.lower_80);
  const highs = forecast.map(f => f.upper_80);
  const allVals = [...prices, ...lows, ...highs];
  const minV = Math.min(...allVals);
  const maxV = Math.max(...allVals);
  const range = maxV - minV || 1;

  const W = 400, H = 100, pad = 10;
  const xScale = (i: number) => pad + (i / (forecast.length - 1)) * (W - 2*pad);
  const yScale = (v: number) => H - pad - ((v - minV) / range) * (H - 2*pad);

  const areaPath = [
    `M ${xScale(0)},${yScale(highs[0])}`,
    ...highs.map((h, i) => `L ${xScale(i)},${yScale(h)}`),
    ...lows.slice().reverse().map((l, i) => `L ${xScale(forecast.length - 1 - i)},${yScale(l)}`),
    "Z",
  ].join(" ");

  const linePath = prices.map((p, i) => `${i === 0 ? "M" : "L"} ${xScale(i)},${yScale(p)}`).join(" ");

  const trend = prices[prices.length-1] > prices[0];

  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="w-full">
      <path d={areaPath} fill={trend ? "rgba(0,208,132,0.08)" : "rgba(255,59,59,0.08)"} />
      <path d={linePath} fill="none" stroke={trend ? "#00d084" : "#ff3b3b"} strokeWidth={1.5} />
      {forecast.map((f, i) => (
        <circle key={i} cx={xScale(i)} cy={yScale(f.predicted)} r={2}
          fill={trend ? "#00d084" : "#ff3b3b"} opacity={0.6} />
      ))}
    </svg>
  );
}

function ForecastCard({ symbol, data }: { symbol: string; data: any }) {
  const s = data?.summary ?? {};
  const trend = s.direction === "bullish" ? "up" : s.direction === "bearish" ? "down" : "flat";
  const colors = { up: "#00d084", down: "#ff3b3b", flat: "#888" };
  const c = colors[trend] ?? "#888";
  const icons = { up: "▲", down: "▼", flat: "—" };

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
        <div>
          <span className="font-bold text-white text-sm font-mono">{symbol}</span>
          <span className="ml-2 text-xs text-gray-500">TimesFM 2.5 · {data?.context_length ?? 0}pt ctx</span>
        </div>
        <span className="text-xs px-2 py-0.5 rounded font-bold" style={{ color: c, background: `${c}22` }}>
          {icons[trend]} {s.direction?.toUpperCase() ?? "—"}
        </span>
      </div>

      <div className="px-4 py-3">
        <div className="grid grid-cols-3 gap-3 mb-3">
          <div>
            <div className="text-xs text-gray-500 mb-0.5">Current</div>
            <div className="font-mono font-bold text-white">₹{s.current_price?.toFixed(2) ?? "—"}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-0.5">Predicted ({data?.summary?.horizon_days}d)</div>
            <div className="font-mono font-bold" style={{ color: c }}>₹{s.predicted_price_end?.toFixed(2) ?? "—"}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-0.5">Expected Return</div>
            <div className="font-mono font-bold" style={{ color: c }}>
              {s.predicted_return_pct != null ? `${s.predicted_return_pct > 0 ? "+" : ""}${s.predicted_return_pct.toFixed(2)}%` : "—"}
            </div>
          </div>
        </div>

        {data?.features && (
          <div className="grid grid-cols-3 gap-2 mb-3 text-xs">
            <div className="bg-gray-800 rounded p-1.5">
              <div className="text-gray-500">30d Ret</div>
              <div style={{ color: data.features.returns_30d > 0 ? "#00d084" : "#ff3b3b" }}>
                {data.features.returns_30d > 0 ? "+" : ""}{(data.features.returns_30d * 100).toFixed(1)}%
              </div>
            </div>
            <div className="bg-gray-800 rounded p-1.5">
              <div className="text-gray-500">Ann Vol</div>
              <div className="text-white">{(data.features.ann_vol * 100).toFixed(1)}%</div>
            </div>
            <div className="bg-gray-800 rounded p-1.5">
              <div className="text-gray-500">vs SMA50</div>
              <div style={{ color: data.features.above_sma50 ? "#00d084" : "#ff3b3b" }}>
                {data.features.above_sma50 ? "Above" : "Below"}
              </div>
            </div>
          </div>
        )}

        <MiniChart forecast={data?.forecast ?? []} />

        {s.price_range_end && (
          <div className="flex justify-between text-xs mt-2 text-gray-500">
            <span>Low: <span className="text-red-400 font-mono">₹{s.price_range_end.low?.toFixed(0)}</span></span>
            <span>Median: <span className="text-gray-300 font-mono">₹{s.price_range_end.median?.toFixed(0)}</span></span>
            <span>High: <span className="text-green-400 font-mono">₹{s.price_range_end.high?.toFixed(0)}</span></span>
          </div>
        )}
      </div>
    </div>
  );
}

export default function TimesFMPage() {
  const [symbol, setSymbol] = useState("HDFCBANK");
  const [symbols, setSymbols] = useState<string[]>(["HDFCBANK","RELIANCE","TCS","ICICIBANK"]);
  const [horizon, setHorizon] = useState(30);
  const [tab, setTab] = useState<"single"|"batch"|"sector">("single");
  const [singleResult, setSingleResult] = useState<any>(null);
  const [batchResult, setBatchResult] = useState<any>(null);
  const [sectorResult, setSectorResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [tfStatus, setTfStatus] = useState<{status:string}>({status:"checking"});

  useEffect(() => {
    fetch(`${API}/api/timesfm/status`)
      .then(r => r.json()).then(setTfStatus).catch(() => setTfStatus({status:"offline"}));
  }, []);

  const runSingle = async () => {
    setLoading(true); setSingleResult(null);
    try {
      const r = await fetch(`${API}/api/timesfm/predict/${symbol}?horizon=${horizon}`);
      if (r.ok) setSingleResult(await r.json());
    } catch {}
    setLoading(false);
  };

  const runBatch = async () => {
    setLoading(true); setBatchResult(null);
    try {
      const r = await fetch(`${API}/api/timesfm/batch?symbols=${symbols.join(",")}&horizon=${horizon}`);
      if (r.ok) setBatchResult(await r.json());
    } catch {}
    setLoading(false);
  };

  const runSector = async () => {
    setLoading(true); setSectorResult(null);
    try {
      const r = await fetch(`${API}/api/timesfm/sector?horizon=${horizon}`);
      if (r.ok) setSectorResult(await r.json());
    } catch {}
    setLoading(false);
  };

  const toggleSym = (s: string) =>
    setSymbols(prev => prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]);

  const statusOk = tfStatus.status === "online";

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-3xl font-bold text-white">TimesFM Predictions</h1>
            <span className={`px-2 py-0.5 text-xs rounded font-bold ${statusOk ? "bg-green-900 text-green-300" : "bg-red-900 text-red-300"}`}>
              {statusOk ? "● ONLINE" : "● OFFLINE"}
            </span>
          </div>
          <p className="text-gray-400 text-sm">
            Google&apos;s TimesFM 2.5 — 200M parameter foundation model for zero-shot time-series forecasting
          </p>
          {!statusOk && (
            <div className="mt-2 px-4 py-2 bg-yellow-950 border border-yellow-800 rounded-lg text-xs text-yellow-300">
              TimesFM service offline. Start it: <code className="font-mono bg-black/40 px-1">cd ~/IndianHedgeFund/backend && source .venv311/bin/activate && python3 timesfm_service.py</code>
            </div>
          )}
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 border-b border-gray-800">
          {([["single","Single Stock"],["batch","Multi-Stock"],["sector","Sector Forecast"]] as const).map(([key, label]) => (
            <button key={key} onClick={() => setTab(key)}
              className={`px-4 py-2 text-sm font-semibold border-b-2 transition-colors ${tab === key ? "border-blue-500 text-white" : "border-transparent text-gray-500 hover:text-gray-300"}`}>
              {label}
            </button>
          ))}
        </div>

        {/* Single Stock Tab */}
        {tab === "single" && (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-3 items-end">
              <div>
                <label className="block text-xs text-gray-500 mb-1">NSE Symbol</label>
                <input value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())}
                  className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm w-40 font-mono uppercase"
                  placeholder="HDFCBANK" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Horizon (days)</label>
                <select value={horizon} onChange={e => setHorizon(Number(e.target.value))}
                  className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm">
                  {[7,14,21,30,60,90].map(h => <option key={h} value={h}>{h}d</option>)}
                </select>
              </div>
              <button onClick={runSingle} disabled={loading || !statusOk}
                className="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white px-6 py-2 rounded-lg font-semibold text-sm">
                {loading ? "Forecasting…" : "Run Forecast"}
              </button>
            </div>

            {/* Quick picks */}
            <div className="flex flex-wrap gap-1">
              {PRESET_SYMBOLS.map(s => (
                <button key={s} onClick={() => setSymbol(s)}
                  className={`px-2 py-0.5 text-xs rounded font-mono ${symbol === s ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"}`}>
                  {s}
                </button>
              ))}
            </div>

            {singleResult && !singleResult.error && (
              <ForecastCard symbol={singleResult.symbol} data={singleResult} />
            )}
            {singleResult?.error && (
              <div className="text-red-400 bg-red-950 border border-red-800 rounded-lg p-4 text-sm">
                Error: {singleResult.error}
              </div>
            )}

            {/* Forecast table */}
            {singleResult?.forecast && singleResult.forecast.length > 0 && (
              <div className="bg-gray-900 border border-gray-700 rounded-xl overflow-hidden">
                <div className="px-4 py-3 bg-gray-800 text-sm font-semibold text-gray-200">
                  Daily Forecast — {singleResult.symbol}
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-xs text-gray-400 bg-gray-800/40">
                      <tr>
                        <th className="px-4 py-2 text-left">Date</th>
                        <th className="px-4 py-2 text-right">Bear (10%)</th>
                        <th className="px-4 py-2 text-right">Base (50%)</th>
                        <th className="px-4 py-2 text-right">Point Est</th>
                        <th className="px-4 py-2 text-right">Bull (90%)</th>
                        <th className="px-4 py-2 text-right">Band Width</th>
                      </tr>
                    </thead>
                    <tbody>
                      {singleResult.forecast.map((f: any, i: number) => {
                        const base = singleResult.features?.current_price ?? singleResult.summary?.current_price ?? f.median;
                        const ret = base ? ((f.predicted - base) / base * 100) : 0;
                        const width = f.upper_80 - f.lower_80;
                        return (
                          <tr key={i} className="border-t border-gray-800 hover:bg-gray-800/40">
                            <td className="px-4 py-2 text-gray-400 font-mono text-xs">{f.date}</td>
                            <td className="px-4 py-2 text-right text-red-400 font-mono">₹{f.lower_80?.toFixed(1)}</td>
                            <td className="px-4 py-2 text-right text-gray-300 font-mono">₹{f.median?.toFixed(1)}</td>
                            <td className="px-4 py-2 text-right font-mono font-bold" style={{ color: ret >= 0 ? "#00d084" : "#ff3b3b" }}>
                              ₹{f.predicted?.toFixed(1)}
                            </td>
                            <td className="px-4 py-2 text-right text-green-400 font-mono">₹{f.upper_80?.toFixed(1)}</td>
                            <td className="px-4 py-2 text-right text-gray-500 font-mono text-xs">₹{width?.toFixed(1)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Multi-Stock Tab */}
        {tab === "batch" && (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2 items-end mb-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Horizon</label>
                <select value={horizon} onChange={e => setHorizon(Number(e.target.value))}
                  className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm">
                  {[7,14,21,30,60].map(h => <option key={h} value={h}>{h}d</option>)}
                </select>
              </div>
              <button onClick={runBatch} disabled={loading || !statusOk || symbols.length === 0}
                className="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white px-6 py-2 rounded-lg font-semibold text-sm">
                {loading ? "Forecasting…" : `Forecast ${symbols.length} Stocks`}
              </button>
            </div>

            <div className="flex flex-wrap gap-1 mb-4">
              {PRESET_SYMBOLS.map(s => (
                <button key={s} onClick={() => toggleSym(s)}
                  className={`px-2 py-0.5 text-xs rounded font-mono transition-colors ${symbols.includes(s) ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"}`}>
                  {s}
                </button>
              ))}
            </div>

            {batchResult?.predictions && (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {batchResult.predictions
                  .filter((p: any) => !p.error)
                  .sort((a: any, b: any) => (b.summary?.predicted_return_pct ?? 0) - (a.summary?.predicted_return_pct ?? 0))
                  .map((p: any) => (
                    <ForecastCard key={p.symbol} symbol={p.symbol} data={p} />
                  ))}
              </div>
            )}
          </div>
        )}

        {/* Sector Forecast Tab */}
        {tab === "sector" && (
          <div className="space-y-4">
            <div className="flex gap-3 items-end">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Horizon</label>
                <select value={horizon} onChange={e => setHorizon(Number(e.target.value))}
                  className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm">
                  {[7,14,21,30,60].map(h => <option key={h} value={h}>{h}d</option>)}
                </select>
              </div>
              <button onClick={runSector} disabled={loading || !statusOk}
                className="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white px-6 py-2 rounded-lg font-semibold text-sm">
                {loading ? "Forecasting…" : "Run Sector Forecast"}
              </button>
            </div>

            {sectorResult && (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                  <div className="bg-green-950 border border-green-800 rounded-xl p-3">
                    <div className="text-xs text-green-400 mb-1">Top Sector</div>
                    <div className="font-bold text-white">{sectorResult.top_sector ?? "—"}</div>
                  </div>
                  <div className="bg-red-950 border border-red-800 rounded-xl p-3">
                    <div className="text-xs text-red-400 mb-1">Worst Sector</div>
                    <div className="font-bold text-white">{sectorResult.worst_sector ?? "—"}</div>
                  </div>
                  <div className="bg-gray-900 border border-gray-700 rounded-xl p-3">
                    <div className="text-xs text-gray-400 mb-1">Horizon</div>
                    <div className="font-bold text-white">{sectorResult.horizon_days}d</div>
                  </div>
                  <div className="bg-gray-900 border border-gray-700 rounded-xl p-3">
                    <div className="text-xs text-gray-400 mb-1">Sectors Analysed</div>
                    <div className="font-bold text-white">{Object.keys(sectorResult.sectors ?? {}).length}</div>
                  </div>
                </div>

                <div className="bg-gray-900 border border-gray-700 rounded-xl overflow-hidden">
                  <div className="px-4 py-3 bg-gray-800 text-sm font-semibold text-gray-200">Sector Rankings</div>
                  <div className="overflow-x-auto">
                  <table className="w-full text-sm" style={{ minWidth: 520 }}>
                    <thead className="text-xs text-gray-400 bg-gray-800/40">
                      <tr>
                        <th className="px-4 py-2 text-left">Rank</th>
                        <th className="px-4 py-2 text-left">Sector</th>
                        <th className="px-4 py-2 text-right">Expected Return</th>
                        <th className="px-4 py-2 text-right">Direction</th>
                        <th className="px-4 py-2 text-right">Current Price</th>
                        <th className="px-4 py-2 text-right">Predicted Price</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(sectorResult.sector_ranking ?? []).map((r: any, i: number) => {
                        const s = sectorResult.sectors?.[r.sector];
                        const ret = r.predicted_return_pct ?? 0;
                        const color = ret > 2 ? "#00d084" : ret < -2 ? "#ff3b3b" : "#888";
                        return (
                          <tr key={r.sector} className="border-t border-gray-800 hover:bg-gray-800/40">
                            <td className="px-4 py-2 text-gray-500 text-xs">{i+1}</td>
                            <td className="px-4 py-2 text-white font-semibold">{r.sector}</td>
                            <td className="px-4 py-2 text-right font-mono font-bold" style={{ color }}>
                              {ret > 0 ? "+" : ""}{ret.toFixed(2)}%
                            </td>
                            <td className="px-4 py-2 text-right">
                              <span className="px-2 py-0.5 rounded text-xs" style={{ color, background: `${color}22` }}>
                                {s?.direction?.toUpperCase() ?? "—"}
                              </span>
                            </td>
                            <td className="px-4 py-2 text-right font-mono text-gray-300 text-xs">
                              {s?.current_price ? `₹${s.current_price.toFixed(1)}` : "—"}
                            </td>
                            <td className="px-4 py-2 text-right font-mono text-xs" style={{ color }}>
                              {s?.predicted_price_end ? `₹${s.predicted_price_end.toFixed(1)}` : "—"}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  </div>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
