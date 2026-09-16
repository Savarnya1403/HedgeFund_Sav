"use client";
import { useState, useEffect } from "react";

const API = "http://localhost:8001";

function GaugeChart({ value, min = 0, max = 100, label, thresholds }: {
  value: number; min?: number; max?: number; label: string;
  thresholds?: { val: number; color: string }[];
}) {
  const pct = (value - min) / (max - min);
  const angle = -135 + pct * 270;
  const r = 70; const cx = 100; const cy = 100;
  const rad = (deg: number) => deg * Math.PI / 180;
  const nx = cx + r * Math.cos(rad(angle - 90));
  const ny = cy + r * Math.sin(rad(angle - 90));
  const color = thresholds?.find(t => value <= t.val)?.color ?? "#22c55e";
  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 200 140" className="w-40">
        {[["#ef4444",-135,45],["#f59e0b",45,90],["#22c55e",90,135]].map(([c,s,e],i) => {
          const a1 = rad(Number(s)-90); const a2 = rad(Number(e)-90);
          const x1 = cx + r*Math.cos(a1); const y1 = cy + r*Math.sin(a1);
          const x2 = cx + r*Math.cos(a2); const y2 = cy + r*Math.sin(a2);
          return <path key={i} d={`M ${x1} ${y1} A ${r} ${r} 0 0 1 ${x2} ${y2}`} fill="none" stroke={String(c)} strokeWidth="12" strokeLinecap="round" />;
        })}
        <line x1={cx} y1={cy} x2={nx} y2={ny} stroke={color} strokeWidth="3" strokeLinecap="round" />
        <circle cx={cx} cy={cy} r="6" fill={color} />
        <text x={cx} y={cy+25} textAnchor="middle" fill="white" fontSize="20" fontWeight="bold">{value.toFixed(1)}</text>
      </svg>
      <div className="text-xs text-gray-400 text-center">{label}</div>
    </div>
  );
}

function VarCard({ method, var95, var99, cvar95 }: { method: string; var95: number; var99: number; cvar95: number }) {
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
      <div className="text-xs text-gray-400 uppercase tracking-wide mb-3">{method}</div>
      <div className="space-y-2">
        <div className="flex justify-between"><span className="text-gray-400 text-sm">VaR 95%</span><span className="text-red-400 font-bold">{(var95 * 100).toFixed(2)}%</span></div>
        <div className="flex justify-between"><span className="text-gray-400 text-sm">VaR 99%</span><span className="text-red-500 font-bold">{(var99 * 100).toFixed(2)}%</span></div>
        <div className="flex justify-between"><span className="text-gray-400 text-sm">CVaR 95%</span><span className="text-orange-400 font-bold">{(cvar95 * 100).toFixed(2)}%</span></div>
      </div>
    </div>
  );
}

export default function RiskPage() {
  const [symbol, setSymbol] = useState("RELIANCE");
  const [input, setInput] = useState("RELIANCE");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState("overview");

  const load = async (sym: string) => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/risk/stock/${sym}`);
      if (r.ok) setData(await r.json());
    } catch { }
    setLoading(false);
  };

  useEffect(() => { load("RELIANCE"); }, []);

  const d = data ?? {};

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-1">Risk Dashboard</h1>
          <p className="text-gray-400">VaR • CVaR • GARCH Volatility • Tail Risk • Stress Testing • Factor Decomposition</p>
        </div>

        {/* Symbol search */}
        <div className="flex gap-3 mb-6">
          <input value={input} onChange={e => setInput(e.target.value.toUpperCase())} onKeyDown={e => e.key === "Enter" && (setSymbol(input), load(input))}
            placeholder="Enter symbol…" className="bg-gray-800 border border-gray-600 rounded-lg px-4 py-2.5 text-white text-sm w-64" />
          <button onClick={() => { setSymbol(input); load(input); }}
            className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2.5 rounded-lg text-sm font-medium">Analyze</button>
        </div>

        {loading && <div className="text-gray-400 text-center py-20">Calculating risk metrics…</div>}

        {!loading && data && (
          <>
            {/* Gauges Row */}
            <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 mb-6">
              <h2 className="text-sm font-semibold text-gray-200 mb-6">{symbol} — Risk Profile</h2>
              <div className="flex flex-wrap justify-around gap-4">
                <GaugeChart value={d.ann_vol_pct ?? 0} min={0} max={80} label="Annualized Volatility %"
                  thresholds={[{val:20,color:"#22c55e"},{val:40,color:"#f59e0b"},{val:80,color:"#ef4444"}]} />
                <GaugeChart value={Math.abs(d.var_historical_95_pct ?? 0)} min={0} max={15} label="VaR 95% (1D %)"
                  thresholds={[{val:3,color:"#22c55e"},{val:6,color:"#f59e0b"},{val:15,color:"#ef4444"}]} />
                <GaugeChart value={d.beta_vs_nifty ?? 1} min={0} max={3} label="Beta vs NIFTY50"
                  thresholds={[{val:0.8,color:"#22c55e"},{val:1.3,color:"#f59e0b"},{val:3,color:"#ef4444"}]} />
                <GaugeChart value={Math.abs(d.max_drawdown_pct ?? 0)} min={0} max={80} label="Max Drawdown %"
                  thresholds={[{val:20,color:"#22c55e"},{val:40,color:"#f59e0b"},{val:80,color:"#ef4444"}]} />
                <GaugeChart value={d.tail_ratio ?? 1} min={0} max={3} label="Tail Ratio (Win/Loss)"
                  thresholds={[{val:0.8,color:"#ef4444"},{val:1.2,color:"#f59e0b"},{val:3,color:"#22c55e"}]} />
              </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-2 mb-4 border-b border-gray-800">
              {["overview","var","garch","stress","tail"].map(t => (
                <button key={t} onClick={() => setTab(t)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === t ? "border-blue-500 text-white" : "border-transparent text-gray-400 hover:text-white"}`}>
                  {t.toUpperCase()}
                </button>
              ))}
            </div>

            {tab === "overview" && (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {[
                  ["Sharpe Ratio (1Y)", d.sharpe_1y?.toFixed(2) ?? "N/A", d.sharpe_1y >= 1 ? "text-green-400" : "text-red-400"],
                  ["Sortino Ratio", d.sortino?.toFixed(2) ?? "N/A", "text-blue-400"],
                  ["Ann. Volatility", `${(d.ann_vol_pct ?? 0).toFixed(1)}%`, "text-yellow-400"],
                  ["Beta vs Nifty", (d.beta_vs_nifty ?? 0).toFixed(2), "text-gray-200"],
                  ["Max Drawdown", `${(d.max_drawdown_pct ?? 0).toFixed(1)}%`, "text-red-400"],
                  ["Calmar Ratio", d.calmar?.toFixed(2) ?? "N/A", "text-blue-400"],
                  ["Skewness", d.skewness?.toFixed(3) ?? "N/A", "text-gray-200"],
                  ["Excess Kurtosis", d.excess_kurtosis?.toFixed(3) ?? "N/A", "text-orange-400"],
                ].map(([l, v, c]) => (
                  <div key={String(l)} className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                    <div className="text-xs text-gray-400">{l}</div>
                    <div className={`text-2xl font-bold mt-1 ${c}`}>{v}</div>
                  </div>
                ))}
              </div>
            )}

            {tab === "var" && (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <VarCard method="Parametric (Normal)" var95={d.var_parametric_95 ?? 0} var99={d.var_parametric_99 ?? 0} cvar95={d.cvar_parametric_95 ?? 0} />
                <VarCard method="Historical Simulation" var95={d.var_historical_95 ?? 0} var99={d.var_historical_99 ?? 0} cvar95={d.cvar_historical_95 ?? 0} />
                <VarCard method="Monte Carlo (GARCH)" var95={d.var_mc_95 ?? 0} var99={d.var_mc_99 ?? 0} cvar95={d.cvar_mc_95 ?? 0} />
              </div>
            )}

            {tab === "garch" && (
              <div className="grid grid-cols-2 gap-4">
                {[
                  ["GARCH Alpha (arch effect)", d.garch_alpha?.toFixed(4)],
                  ["GARCH Beta (vol persistence)", d.garch_beta?.toFixed(4)],
                  ["Persistence (α+β)", d.garch_persistence?.toFixed(4)],
                  ["Unconditional Vol (ann)", `${((d.garch_uncond_vol ?? 0) * Math.sqrt(252) * 100).toFixed(1)}%`],
                  ["1-Day Vol Forecast", `${((d.garch_forecast_1d ?? 0) * 100).toFixed(2)}%`],
                  ["5-Day Vol Forecast", `${((d.garch_forecast_5d ?? 0) * 100).toFixed(2)}%`],
                  ["21-Day Vol Forecast", `${((d.garch_forecast_21d ?? 0) * 100).toFixed(2)}%`],
                  ["Current Realized Vol (21D)", `${(d.realized_vol_21d_pct ?? 0).toFixed(1)}%`],
                ].map(([l, v]) => (
                  <div key={String(l)} className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                    <div className="text-xs text-gray-400">{l}</div>
                    <div className="text-xl font-bold mt-1 text-white">{v ?? "N/A"}</div>
                  </div>
                ))}
              </div>
            )}

            {tab === "stress" && (
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                <h3 className="text-sm font-semibold text-gray-200 mb-4">Historical Stress Scenarios</h3>
                <div className="space-y-2">
                  {Object.entries(d.stress_scenarios ?? {}).map(([scenario, ret]) => (
                    <div key={scenario} className="flex items-center gap-4 p-3 bg-gray-800 rounded-lg">
                      <div className="flex-1">
                        <div className="text-sm text-gray-200">{scenario.replace(/_/g, " ")}</div>
                      </div>
                      <div className="w-48 bg-gray-700 rounded-full h-3">
                        <div className={`h-3 rounded-full ${(ret as number) >= 0 ? "bg-green-500" : "bg-red-500"}`}
                          style={{ width: `${Math.min(Math.abs(ret as number) * 2, 100)}%`, marginLeft: (ret as number) >= 0 ? "50%" : `${50 - Math.min(Math.abs(ret as number) * 2, 50)}%` }} />
                      </div>
                      <div className={`w-16 text-right font-bold text-sm ${(ret as number) >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {(ret as number) >= 0 ? "+" : ""}{((ret as number) * 100).toFixed(1)}%
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {tab === "tail" && (
              <div className="grid grid-cols-2 gap-4">
                {[
                  ["Skewness", d.skewness?.toFixed(3), d.skewness < 0 ? "text-red-400" : "text-green-400", "Negative = left tail risk"],
                  ["Excess Kurtosis", d.excess_kurtosis?.toFixed(3), "text-orange-400", "> 0 = fat tails vs normal"],
                  ["Tail Ratio", d.tail_ratio?.toFixed(3), d.tail_ratio > 1 ? "text-green-400" : "text-red-400", "95th pct gain / 5th pct loss"],
                  ["99th Pct Worst Day", `${((d.pct_99_loss ?? 0) * 100).toFixed(2)}%`, "text-red-400", "1-in-100 day worst loss"],
                  ["JB Normality p-value", d.jarque_bera_pvalue?.toFixed(4), d.jarque_bera_pvalue > 0.05 ? "text-green-400" : "text-red-400", "< 0.05 = non-normal returns"],
                  ["EVT 99.9% VaR", d.evt_var_999 ? `${(d.evt_var_999 * 100).toFixed(2)}%` : "N/A", "text-red-500", "Extreme Value Theory tail VaR"],
                ].map(([l, v, c, note]) => (
                  <div key={String(l)} className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                    <div className="text-xs text-gray-400">{l}</div>
                    <div className={`text-2xl font-bold mt-1 ${c}`}>{v ?? "N/A"}</div>
                    <div className="text-xs text-gray-500 mt-1">{note}</div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
