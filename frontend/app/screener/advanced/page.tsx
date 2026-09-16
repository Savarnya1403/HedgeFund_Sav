"use client";
import { useState } from "react";

const API = "http://localhost:8001";

const SCREENS = [
  { value: "garp", label: "GARP", desc: "Growth at Reasonable Price — PEG < 1.5, ROE > 12%", icon: "📈" },
  { value: "deep_value", label: "Deep Value", desc: "Graham number, low PE/PB, high dividend yield", icon: "💎" },
  { value: "quality_compounder", label: "Quality Compounders", desc: "High ROE/margins, FCF+, low debt", icon: "🏆" },
  { value: "turnaround", label: "Turnarounds", desc: "Beaten down + improving earnings", icon: "🔄" },
  { value: "low_vol", label: "Low Volatility", desc: "Low beta, low drawdown, high Sharpe", icon: "🛡️" },
  { value: "dividend", label: "Dividend Yield", desc: "High sustainable yield with FCF coverage", icon: "💰" },
  { value: "earnings_momentum", label: "Earnings Momentum", desc: "Strong analyst upgrades + EPS revisions", icon: "🚀" },
  { value: "golden_cross", label: "Golden Cross", desc: "50 SMA recently crossed above 200 SMA", icon: "✨" },
  { value: "52w_breakout", label: "52W Breakout", desc: "Near or at new 52-week high", icon: "📊" },
  { value: "magic_formula", label: "Magic Formula", desc: "Greenblatt: high earnings yield + high ROIC", icon: "🔮" },
];

const UNIVERSES = [
  { value: "nifty50", label: "NIFTY 50" },
  { value: "nifty100", label: "NIFTY 100" },
  { value: "all", label: "Full Universe" },
];

function StockRow({ stock, columns }: { stock: any; columns: string[] }) {
  return (
    <tr className="border-t border-gray-800 hover:bg-gray-800/50">
      <td className="px-4 py-3 font-medium text-blue-400">{stock.symbol}</td>
      <td className="px-4 py-3 text-xs text-gray-400">{stock.sector}</td>
      <td className="px-4 py-3 text-white">₹{(stock.price ?? 0).toFixed(1)}</td>
      {columns.map(col => (
        <td key={col} className="px-4 py-3 text-right text-gray-300">
          {stock[col] != null ? (typeof stock[col] === "number" ? stock[col].toFixed(1) : stock[col]) : "—"}
          {col.includes("pct") || col.includes("yield") || col.includes("margin") || col.includes("growth") || col.includes("ret") ? "%" : ""}
        </td>
      ))}
      <td className="px-4 py-3 text-right">
        <span className={`px-2 py-1 rounded text-xs font-bold ${stock.score >= 70 ? "bg-green-900 text-green-300" : stock.score >= 40 ? "bg-yellow-900 text-yellow-300" : "bg-gray-800 text-gray-400"}`}>
          {stock.score ?? "—"}
        </span>
      </td>
    </tr>
  );
}

const SCREEN_COLUMNS: Record<string, string[]> = {
  garp: ["pe","peg","roe","revenue_growth","earnings_growth","net_margin","rsi"],
  deep_value: ["pe","pb","div_yield","roe","current_ratio","graham_premium_pct"],
  quality_compounder: ["roe","roa","operating_margin","gross_margin","revenue_growth","debt_equity"],
  turnaround: ["pe","forward_pe","pe_compression_pts","earnings_growth","dist_from_52wl","rsi"],
  low_vol: ["ann_vol","beta","sharpe","max_drawdown","div_yield","roe"],
  dividend: ["div_yield","payout_ratio","fcf_div_cover","net_margin","debt_equity"],
  earnings_momentum: ["pe","fwd_eps_growth","upside_pct","earnings_growth","revenue_growth"],
  golden_cross: ["sma50","sma200","days_since_cross","rsi","vol_ratio"],
  "52w_breakout": ["dist_52wh_pct","high_52w","vol_ratio","rsi","ret_1m"],
  magic_formula: ["pe","earnings_yield","roe","ev_ebitda"],
};

export default function AdvancedScreenerPage() {
  const [screen, setScreen] = useState("garp");
  const [universe, setUniverse] = useState("nifty100");
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [ran, setRan] = useState(false);

  const run = async () => {
    setLoading(true); setRan(true);
    try {
      const r = await fetch(`${API}/api/screener/advanced/${screen}?universe=${universe}&limit=30`);
      if (r.ok) {
        const d = await r.json();
        setResults(d.results ?? d ?? []);
      }
    } catch { }
    setLoading(false);
  };

  const cols = SCREEN_COLUMNS[screen] ?? ["score"];
  const colLabels: Record<string, string> = {
    pe:"P/E", pb:"P/B", peg:"PEG", roe:"ROE%", roa:"ROA%", earnings_yield:"Earn Yield",
    revenue_growth:"Rev Gro%", earnings_growth:"EPS Gro%", net_margin:"Net Margin",
    operating_margin:"Op Margin", gross_margin:"Gross Margin", debt_equity:"D/E",
    div_yield:"Div Yield", payout_ratio:"Payout%", fcf_div_cover:"FCF Cover",
    current_ratio:"Curr Ratio", graham_premium_pct:"Vs Graham%",
    ann_vol:"Ann Vol%", beta:"Beta", sharpe:"Sharpe", max_drawdown:"Max DD%",
    forward_pe:"Fwd P/E", pe_compression_pts:"PE Compress", dist_from_52wl:"From 52wL%",
    dist_52wh_pct:"From 52wH%", high_52w:"52W High", ev_ebitda:"EV/EBITDA",
    rsi:"RSI", vol_ratio:"Vol Ratio", ret_1m:"1M Ret%", upside_pct:"Upside%",
    fwd_eps_growth:"Fwd EPS%", sma50:"50 SMA", sma200:"200 SMA", days_since_cross:"Days Since",
  };

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-1">Advanced Stock Screener</h1>
          <p className="text-gray-400">GARP • Deep Value • Quality Compounders • Turnarounds • Low Vol • Dividend • Magic Formula</p>
        </div>

        {/* Screen Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-6">
          {SCREENS.map(s => (
            <button key={s.value} onClick={() => setScreen(s.value)}
              className={`p-3 rounded-lg border text-left transition-all ${screen === s.value ? "border-blue-500 bg-blue-950/40" : "border-gray-700 bg-gray-900 hover:border-gray-500"}`}>
              <div className="text-lg mb-1">{s.icon}</div>
              <div className="text-sm font-semibold text-white">{s.label}</div>
              <div className="text-xs text-gray-400 mt-0.5 leading-tight">{s.desc}</div>
            </button>
          ))}
        </div>

        {/* Controls */}
        <div className="flex flex-wrap gap-3 mb-6">
          <select value={universe} onChange={e => setUniverse(e.target.value)}
            className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white">
            {UNIVERSES.map(u => <option key={u.value} value={u.value}>{u.label}</option>)}
          </select>
          <button onClick={run} disabled={loading}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white px-8 py-2 rounded-lg font-semibold text-sm transition-colors">
            {loading ? "Screening…" : `Run ${SCREENS.find(s => s.value === screen)?.label} Screen`}
          </button>
        </div>

        {ran && !loading && results.length === 0 && (
          <div className="text-center py-20 text-gray-500">No stocks matched the screen criteria.</div>
        )}

        {results.length > 0 && (
          <div className="bg-gray-900 border border-gray-700 rounded-xl overflow-hidden">
            <div className="px-4 py-3 bg-gray-800 flex items-center justify-between">
              <div className="text-sm font-semibold text-gray-200">
                {SCREENS.find(s => s.value === screen)?.icon} {SCREENS.find(s => s.value === screen)?.label} — {results.length} stocks found
              </div>
              <div className="text-xs text-gray-400">{SCREENS.find(s => s.value === screen)?.desc}</div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs text-gray-400 bg-gray-800/50">
                  <tr>
                    <th className="px-4 py-2 text-left">Symbol</th>
                    <th className="px-4 py-2 text-left">Sector</th>
                    <th className="px-4 py-2 text-left">Price</th>
                    {cols.map(c => <th key={c} className="px-4 py-2 text-right">{colLabels[c] ?? c}</th>)}
                    <th className="px-4 py-2 text-right">Score</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((s: any, i: number) => <StockRow key={i} stock={s} columns={cols} />)}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
