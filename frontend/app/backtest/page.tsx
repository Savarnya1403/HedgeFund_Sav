"use client";
import { useState } from "react";

const API = "http://localhost:8001";

const STRATEGIES = [
  { value: "momentum", label: "Dual Momentum", desc: "12-month absolute + relative momentum, monthly rebalancing" },
  { value: "mean_reversion", label: "Mean Reversion", desc: "Z-score + Bollinger Band + RSI oversold filter" },
  { value: "trend_following", label: "Trend Following", desc: "Donchian 20-day breakout with ATR trailing stop" },
  { value: "rsi_macd", label: "RSI + MACD", desc: "RSI oversold + MACD bullish crossover entry" },
  { value: "factor", label: "Multi-Factor", desc: "Composite: momentum + value + quality + low-vol" },
  { value: "pairs", label: "Pairs Trading", desc: "Cointegration-based statistical arbitrage" },
];

const UNIVERSES = [
  { value: "nifty50", label: "NIFTY 50" },
  { value: "nifty100", label: "NIFTY 100" },
  { value: "all", label: "Full Universe (127 stocks)" },
];

function MetricCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
      <div className="text-xs text-gray-400 mb-1">{label}</div>
      <div className={`text-2xl font-bold ${color ?? "text-white"}`}>{value}</div>
      {sub && <div className="text-xs text-gray-500 mt-1">{sub}</div>}
    </div>
  );
}

function EquityCurveChart({ data }: { data: { date: string; equity: number }[] }) {
  if (!data?.length) return null;
  const max = Math.max(...data.map(d => d.equity));
  const min = Math.min(...data.map(d => d.equity));
  const range = max - min || 1;
  const w = 900; const h = 200;
  const pts = data.map((d, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((d.equity - min) / range) * h;
    return `${x},${y}`;
  }).join(" ");
  const initial = data[0]?.equity ?? 1000000;
  const finalVal = data[data.length - 1]?.equity ?? initial;
  const color = finalVal >= initial ? "#22c55e" : "#ef4444";
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
      <div className="text-sm text-gray-400 mb-3">Equity Curve</div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-48">
        <polyline points={pts} fill="none" stroke={color} strokeWidth="2" />
        <line x1="0" y1={h - (initial - min) / range * h} x2={w} y2={h - (initial - min) / range * h}
          stroke="#4b5563" strokeDasharray="4" strokeWidth="1" />
      </svg>
      <div className="flex justify-between text-xs text-gray-500 mt-1">
        <span>{data[0]?.date}</span><span>{data[data.length - 1]?.date}</span>
      </div>
    </div>
  );
}

function MonthlyReturnsTable({ data }: { data: Record<string, Record<string, number>> }) {
  if (!data) return null;
  const years = Object.keys(data).sort().reverse();
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className="text-gray-400">
            <th className="p-2 text-left">Year</th>
            {months.map(m => <th key={m} className="p-2 text-center">{m}</th>)}
            <th className="p-2 text-center">Annual</th>
          </tr>
        </thead>
        <tbody>
          {years.map(yr => {
            const yearData = data[yr] || {};
            const annual = Object.values(yearData).reduce((a, b) => a + b, 0);
            return (
              <tr key={yr} className="border-t border-gray-800">
                <td className="p-2 text-gray-300 font-medium">{yr}</td>
                {months.map((m, i) => {
                  const val = yearData[m] ?? yearData[String(i + 1).padStart(2, "0")];
                  const bg = val == null ? "" : val > 0 ? "bg-green-900/40 text-green-400" : val < 0 ? "bg-red-900/40 text-red-400" : "text-gray-500";
                  return <td key={m} className={`p-2 text-center ${bg}`}>{val != null ? `${val > 0 ? "+" : ""}${val.toFixed(1)}%` : "-"}</td>;
                })}
                <td className={`p-2 text-center font-bold ${annual >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {annual >= 0 ? "+" : ""}{annual.toFixed(1)}%
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function BacktestPage() {
  const [strategy, setStrategy] = useState("momentum");
  const [universe, setUniverse] = useState("nifty50");
  const [startDate, setStartDate] = useState("2020-01-01");
  const [endDate, setEndDate] = useState("2024-12-31");
  const [capital, setCapital] = useState(1000000);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("overview");

  const run = async () => {
    setLoading(true); setError(""); setResult(null);
    try {
      const r = await fetch(`${API}/api/backtest/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy, universe, start_date: startDate, end_date: endDate, initial_capital: capital }),
      });
      if (!r.ok) throw new Error(await r.text());
      setResult(await r.json());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const metrics = result?.metrics ?? {};
  const trades = result?.trades ?? [];

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-1">Strategy Backtester</h1>
          <p className="text-gray-400">Event-driven backtesting engine • Transaction costs included • Walk-forward validated</p>
        </div>

        {/* Config Panel */}
        <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4 text-gray-200">Configuration</h2>
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
            <div>
              <label className="block text-xs text-gray-400 mb-2">Strategy</label>
              <select value={strategy} onChange={e => setStrategy(e.target.value)}
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-white">
                {STRATEGIES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
              <p className="text-xs text-gray-500 mt-1">{STRATEGIES.find(s => s.value === strategy)?.desc}</p>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-2">Universe</label>
              <select value={universe} onChange={e => setUniverse(e.target.value)}
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-white">
                {UNIVERSES.map(u => <option key={u.value} value={u.value}>{u.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-2">Initial Capital (₹)</label>
              <input type="number" value={capital} onChange={e => setCapital(Number(e.target.value))}
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-white" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-2">Start Date</label>
              <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-white" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-2">End Date</label>
              <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)}
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-white" />
            </div>
          </div>
          <button onClick={run} disabled={loading}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white px-8 py-2.5 rounded-lg font-semibold text-sm transition-colors">
            {loading ? "Running Backtest…" : "Run Backtest"}
          </button>
          {error && <p className="text-red-400 text-sm mt-3">{error}</p>}
        </div>

        {result && (
          <>
            {/* Key Metrics */}
            <div className="grid grid-cols-2 lg:grid-cols-4 xl:grid-cols-6 gap-3 mb-6">
              <MetricCard label="Total Return" value={`${(metrics.total_return_pct ?? 0) >= 0 ? "+" : ""}${(metrics.total_return_pct ?? 0).toFixed(1)}%`}
                color={metrics.total_return_pct >= 0 ? "text-green-400" : "text-red-400"} />
              <MetricCard label="CAGR" value={`${(metrics.cagr_pct ?? 0).toFixed(1)}%`}
                color={metrics.cagr_pct >= 0 ? "text-green-400" : "text-red-400"} sub="Annualized" />
              <MetricCard label="Sharpe Ratio" value={(metrics.sharpe_ratio ?? 0).toFixed(2)}
                color={metrics.sharpe_ratio >= 1 ? "text-green-400" : metrics.sharpe_ratio >= 0.5 ? "text-yellow-400" : "text-red-400"}
                sub="vs 6.5% risk-free" />
              <MetricCard label="Max Drawdown" value={`${(metrics.max_drawdown_pct ?? 0).toFixed(1)}%`} color="text-red-400" />
              <MetricCard label="Win Rate" value={`${(metrics.win_rate_pct ?? 0).toFixed(1)}%`}
                color={metrics.win_rate_pct >= 50 ? "text-green-400" : "text-red-400"} sub={`${metrics.total_trades ?? 0} trades`} />
              <MetricCard label="Profit Factor" value={(metrics.profit_factor ?? 0).toFixed(2)}
                color={metrics.profit_factor >= 1.5 ? "text-green-400" : "text-yellow-400"} />
            </div>

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
              <MetricCard label="Sortino Ratio" value={(metrics.sortino_ratio ?? 0).toFixed(2)} />
              <MetricCard label="Calmar Ratio" value={(metrics.calmar_ratio ?? 0).toFixed(2)} />
              <MetricCard label="Ann. Volatility" value={`${(metrics.annualized_vol_pct ?? 0).toFixed(1)}%`} />
              <MetricCard label="Avg Hold Period" value={`${(metrics.avg_holding_days ?? 0).toFixed(0)}d`} />
            </div>

            {/* Tabs */}
            <div className="flex gap-2 mb-4 border-b border-gray-800">
              {["overview","monthly","trades","drawdowns"].map(t => (
                <button key={t} onClick={() => setTab(t)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === t ? "border-blue-500 text-white" : "border-transparent text-gray-400 hover:text-white"}`}>
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>

            {tab === "overview" && (
              <div className="space-y-4">
                {result.equity_curve?.length > 0 && <EquityCurveChart data={result.equity_curve} />}
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                    <h3 className="text-sm font-semibold text-gray-300 mb-3">Return Statistics</h3>
                    {[
                      ["Total Return", `${(metrics.total_return_pct ?? 0).toFixed(2)}%`],
                      ["CAGR", `${(metrics.cagr_pct ?? 0).toFixed(2)}%`],
                      ["Best Month", `${(metrics.best_month_pct ?? 0).toFixed(2)}%`],
                      ["Worst Month", `${(metrics.worst_month_pct ?? 0).toFixed(2)}%`],
                    ].map(([k, v]) => (
                      <div key={k} className="flex justify-between py-1.5 border-b border-gray-800 last:border-0">
                        <span className="text-gray-400 text-sm">{k}</span>
                        <span className="text-white text-sm font-medium">{v}</span>
                      </div>
                    ))}
                  </div>
                  <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                    <h3 className="text-sm font-semibold text-gray-300 mb-3">Trade Statistics</h3>
                    {[
                      ["Total Trades", metrics.total_trades ?? 0],
                      ["Win Rate", `${(metrics.win_rate_pct ?? 0).toFixed(1)}%`],
                      ["Avg Win", `${(metrics.avg_win_pct ?? 0).toFixed(2)}%`],
                      ["Avg Loss", `${(metrics.avg_loss_pct ?? 0).toFixed(2)}%`],
                    ].map(([k, v]) => (
                      <div key={String(k)} className="flex justify-between py-1.5 border-b border-gray-800 last:border-0">
                        <span className="text-gray-400 text-sm">{k}</span>
                        <span className="text-white text-sm font-medium">{String(v)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {tab === "monthly" && (
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">Monthly Returns (%)</h3>
                <MonthlyReturnsTable data={result.monthly_returns ?? {}} />
              </div>
            )}

            {tab === "trades" && (
              <div className="bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead className="bg-gray-800 text-gray-400">
                      <tr>{["Symbol","Action","Entry Date","Exit Date","Entry ₹","Exit ₹","Return %","P&L ₹"].map(h =>
                        <th key={h} className="px-3 py-2 text-left">{h}</th>)}</tr>
                    </thead>
                    <tbody>
                      {trades.slice(0, 100).map((t: any, i: number) => (
                        <tr key={i} className="border-t border-gray-800 hover:bg-gray-800/50">
                          <td className="px-3 py-2 font-medium text-blue-400">{t.symbol}</td>
                          <td className={`px-3 py-2 font-medium ${t.action === "BUY" ? "text-green-400" : "text-red-400"}`}>{t.action}</td>
                          <td className="px-3 py-2 text-gray-300">{t.entry_date}</td>
                          <td className="px-3 py-2 text-gray-300">{t.exit_date ?? "-"}</td>
                          <td className="px-3 py-2 text-gray-300">₹{(t.entry_price ?? 0).toFixed(2)}</td>
                          <td className="px-3 py-2 text-gray-300">{t.exit_price ? `₹${t.exit_price.toFixed(2)}` : "-"}</td>
                          <td className={`px-3 py-2 font-medium ${(t.return_pct ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                            {t.return_pct != null ? `${t.return_pct >= 0 ? "+" : ""}${t.return_pct.toFixed(2)}%` : "-"}
                          </td>
                          <td className={`px-3 py-2 font-medium ${(t.pnl ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                            {t.pnl != null ? `${t.pnl >= 0 ? "+" : ""}₹${Math.round(t.pnl).toLocaleString()}` : "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {trades.length > 100 && <div className="text-center text-gray-500 text-xs py-3">Showing first 100 of {trades.length} trades</div>}
              </div>
            )}

            {tab === "drawdowns" && (
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">Top Drawdown Periods</h3>
                <div className="space-y-3">
                  {(result.drawdowns ?? []).map((d: any, i: number) => (
                    <div key={i} className="bg-gray-800 rounded-lg p-3 flex items-center gap-6">
                      <div className="text-red-400 text-2xl font-bold w-24">{d.depth_pct?.toFixed(1)}%</div>
                      <div>
                        <div className="text-sm text-gray-200">{d.start} → {d.trough} → {d.end ?? "Ongoing"}</div>
                        <div className="text-xs text-gray-400 mt-0.5">
                          Duration: {d.duration_days}d • Recovery: {d.recovery_days ?? "N/A"}d
                        </div>
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
