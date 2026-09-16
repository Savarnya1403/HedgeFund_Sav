"use client";
import { useState } from "react";

const API = "http://localhost:8001";
const ALL_SYMBOLS = [
  "RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","HINDUNILVR","BAJFINANCE","BHARTIARTL",
  "SBIN","KOTAKBANK","ITC","LT","AXISBANK","TITAN","ASIANPAINT","MARUTI","WIPRO","HCLTECH",
  "SUNPHARMA","TATAMOTORS","BAJAJFINSV","DIVISLAB","CIPLA","DRREDDY","NESTLEIND","NTPC",
  "ONGC","POWERGRID","ADANIENT","TATASTEEL","JSWSTEEL","HINDALCO","EICHERMOT","BRITANNIA",
  "APOLLOHOSP","HEROMOTOCO","TATACONSUM","PIDILITIND","LTIM","COALINDIA",
];

const METHODS = [
  { value: "sharpe", label: "Max Sharpe", desc: "Maximizes risk-adjusted return" },
  { value: "min_vol", label: "Min Volatility", desc: "Minimizes portfolio variance" },
  { value: "risk_parity", label: "Risk Parity", desc: "Equal risk contribution per asset" },
  { value: "black_litterman", label: "Black-Litterman", desc: "Bayesian equilibrium + views" },
  { value: "cvar", label: "Min CVaR", desc: "Minimizes tail risk at 95% confidence" },
];

function WeightBar({ symbol, weight, color }: { symbol: string; weight: number; color: string }) {
  return (
    <div className="flex items-center gap-3 py-1">
      <div className="w-24 text-xs text-gray-300 shrink-0">{symbol}</div>
      <div className="flex-1 bg-gray-800 rounded-full h-4 relative">
        <div className="h-4 rounded-full transition-all" style={{ width: `${Math.min(weight * 100, 100)}%`, backgroundColor: color }} />
      </div>
      <div className="w-14 text-right text-xs font-medium text-white shrink-0">{(weight * 100).toFixed(1)}%</div>
    </div>
  );
}

function EfficientFrontierChart({ points }: { points: { vol: number; ret: number; sharpe: number }[] }) {
  if (!points?.length) return null;
  const vols = points.map(p => p.vol);
  const rets = points.map(p => p.ret);
  const minV = Math.min(...vols); const maxV = Math.max(...vols);
  const minR = Math.min(...rets); const maxR = Math.max(...rets);
  const W = 600; const H = 300; const PAD = 40;
  const px = (v: number) => PAD + (v - minV) / (maxV - minV + 0.001) * (W - 2 * PAD);
  const py = (r: number) => H - PAD - (r - minR) / (maxR - minR + 0.001) * (H - 2 * PAD);
  const maxSharpeIdx = points.reduce((best, p, i) => p.sharpe > points[best].sharpe ? i : best, 0);
  const pathData = points.map((p, i) => `${i === 0 ? "M" : "L"} ${px(p.vol)} ${py(p.ret)}`).join(" ");
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
      <div className="text-sm font-semibold text-gray-200 mb-3">Efficient Frontier</div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-64">
        <path d={pathData} fill="none" stroke="#3b82f6" strokeWidth="2" />
        {points.map((p, i) => (
          <circle key={i} cx={px(p.vol)} cy={py(p.ret)} r={i === maxSharpeIdx ? 6 : 3}
            fill={i === maxSharpeIdx ? "#22c55e" : `hsl(${p.sharpe * 40},70%,55%)`} opacity="0.8" />
        ))}
        <circle cx={px(points[maxSharpeIdx].vol)} cy={py(points[maxSharpeIdx].ret)} r={8} fill="none" stroke="#22c55e" strokeWidth="2" />
        <text x={px(points[maxSharpeIdx].vol) + 10} y={py(points[maxSharpeIdx].ret) - 5} fill="#22c55e" fontSize="10">Max Sharpe</text>
        <text x={PAD} y={H - 5} fill="#6b7280" fontSize="9">Volatility →</text>
        <text x={5} y={PAD} fill="#6b7280" fontSize="9" transform={`rotate(-90, 5, ${PAD})`}>Return</text>
      </svg>
    </div>
  );
}

export default function OptimizerPage() {
  const [selected, setSelected] = useState<string[]>(["RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","SBIN","ITC","LT","AXISBANK","TITAN"]);
  const [method, setMethod] = useState("sharpe");
  const [maxWeight, setMaxWeight] = useState(30);
  const [period, setPeriod] = useState("2y");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("weights");

  const toggleSymbol = (sym: string) => {
    setSelected(prev => prev.includes(sym) ? prev.filter(s => s !== sym) : [...prev, sym]);
  };

  const optimize = async () => {
    if (selected.length < 3) { setError("Select at least 3 stocks"); return; }
    setLoading(true); setError(""); setResult(null);
    try {
      const r = await fetch(`${API}/api/portfolio/optimize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbols: selected, method, max_weight: maxWeight / 100, period }),
      });
      if (!r.ok) throw new Error(await r.text());
      setResult(await r.json());
      setTab("weights");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const COLORS = ["#3b82f6","#22c55e","#f59e0b","#ef4444","#8b5cf6","#06b6d4","#f97316","#ec4899","#14b8a6","#a78bfa"];
  const weights = result?.weights ?? {};
  const weightEntries = Object.entries(weights).sort(([,a],[,b]) => (b as number) - (a as number));

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-1">Portfolio Optimizer</h1>
          <p className="text-gray-400">Modern Portfolio Theory • Black-Litterman • Risk Parity • CVaR Optimization</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          {/* Stock Selection */}
          <div className="lg:col-span-2 bg-gray-900 border border-gray-700 rounded-xl p-4">
            <div className="text-sm font-semibold text-gray-200 mb-3">Select Stocks ({selected.length} selected)</div>
            <div className="flex flex-wrap gap-2 max-h-56 overflow-y-auto">
              {ALL_SYMBOLS.map(sym => (
                <button key={sym} onClick={() => toggleSymbol(sym)}
                  className={`px-3 py-1 rounded text-xs font-medium transition-colors border ${
                    selected.includes(sym) ? "bg-blue-600 border-blue-500 text-white" : "bg-gray-800 border-gray-600 text-gray-300 hover:border-gray-400"
                  }`}>
                  {sym}
                </button>
              ))}
            </div>
          </div>

          {/* Settings */}
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-4 space-y-4">
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Optimization Method</label>
              <select value={method} onChange={e => setMethod(e.target.value)}
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-white">
                {METHODS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
              <p className="text-xs text-gray-500 mt-1">{METHODS.find(m => m.value === method)?.desc}</p>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Max Weight Per Stock: {maxWeight}%</label>
              <input type="range" min={5} max={50} step={5} value={maxWeight} onChange={e => setMaxWeight(Number(e.target.value))}
                className="w-full accent-blue-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Data Period</label>
              <select value={period} onChange={e => setPeriod(e.target.value)}
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-white">
                {["1y","2y","3y","5y"].map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <button onClick={optimize} disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white py-2.5 rounded-lg font-semibold text-sm transition-colors">
              {loading ? "Optimizing…" : "Optimize Portfolio"}
            </button>
            {error && <p className="text-red-400 text-xs">{error}</p>}
          </div>
        </div>

        {result && (
          <>
            {/* Portfolio Metrics */}
            <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-6">
              {[
                { l: "Expected Return", v: `${((result.expected_return ?? 0) * 100).toFixed(1)}%`, c: "text-green-400" },
                { l: "Expected Vol", v: `${((result.expected_vol ?? 0) * 100).toFixed(1)}%`, c: "text-yellow-400" },
                { l: "Sharpe Ratio", v: (result.sharpe ?? 0).toFixed(2), c: result.sharpe >= 1 ? "text-green-400" : "text-yellow-400" },
                { l: "HHI Concentration", v: (result.hhi ?? 0).toFixed(3), c: "text-gray-300" },
                { l: "Effective N", v: (result.effective_n ?? 0).toFixed(1), c: "text-blue-400" },
              ].map(m => (
                <div key={m.l} className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                  <div className="text-xs text-gray-400">{m.l}</div>
                  <div className={`text-2xl font-bold mt-1 ${m.c}`}>{m.v}</div>
                </div>
              ))}
            </div>

            {/* Tabs */}
            <div className="flex gap-2 mb-4 border-b border-gray-800">
              {["weights","frontier","risk","stress"].map(t => (
                <button key={t} onClick={() => setTab(t)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === t ? "border-blue-500 text-white" : "border-transparent text-gray-400 hover:text-white"}`}>
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>

            {tab === "weights" && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-gray-200 mb-4">Optimal Weights</h3>
                  {weightEntries.map(([sym, w], i) => (
                    <WeightBar key={sym} symbol={sym} weight={w as number} color={COLORS[i % COLORS.length]} />
                  ))}
                </div>
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-gray-200 mb-4">Risk Contributions</h3>
                  {Object.entries(result.risk_contributions ?? {}).sort(([,a],[,b]) => (b as number) - (a as number)).map(([sym, rc], i) => (
                    <WeightBar key={sym} symbol={sym} weight={rc as number} color={COLORS[i % COLORS.length]} />
                  ))}
                </div>
              </div>
            )}

            {tab === "frontier" && <EfficientFrontierChart points={result.efficient_frontier ?? []} />}

            {tab === "risk" && (
              <div className="grid grid-cols-2 gap-4">
                {[["VaR 95% (1D)", result.var_95, "text-red-400"], ["CVaR 95% (1D)", result.cvar_95, "text-red-400"],
                  ["Diversification Ratio", result.diversification_ratio, "text-blue-400"]].map(([l, v, c]) => (
                  <div key={String(l)} className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                    <div className="text-xs text-gray-400">{l}</div>
                    <div className={`text-2xl font-bold mt-1 ${c}`}>
                      {v != null ? `${typeof v === "number" && l.toString().includes("Ratio") ? v.toFixed(2) : ((v as number) * 100).toFixed(2) + "%"}` : "N/A"}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {tab === "stress" && (
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                <h3 className="text-sm font-semibold text-gray-200 mb-4">Stress Test Results</h3>
                <div className="space-y-2">
                  {Object.entries(result.stress_tests ?? {}).map(([scenario, val]) => (
                    <div key={scenario} className="flex items-center gap-4 p-3 bg-gray-800 rounded">
                      <div className="flex-1 text-sm text-gray-300">{scenario.replace(/_/g, " ")}</div>
                      <div className={`text-sm font-bold ${(val as number) >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {(val as number) >= 0 ? "+" : ""}{((val as number) * 100).toFixed(1)}%
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
