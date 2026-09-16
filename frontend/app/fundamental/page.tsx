"use client";
import { useState } from "react";

const API = "http://localhost:8001";

function ScoreRing({ score, label, color }: { score: number; label: string; color: string }) {
  const r = 36; const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  return (
    <div className="flex flex-col items-center gap-2">
      <svg width="96" height="96" viewBox="0 0 96 96">
        <circle cx="48" cy="48" r={r} fill="none" stroke="#1f2937" strokeWidth="8" />
        <circle cx="48" cy="48" r={r} fill="none" stroke={color} strokeWidth="8"
          strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
          transform="rotate(-90 48 48)" />
        <text x="48" y="48" textAnchor="middle" dominantBaseline="middle" fill="white" fontSize="18" fontWeight="bold">{score}</text>
      </svg>
      <div className="text-xs text-gray-400 text-center max-w-20">{label}</div>
    </div>
  );
}

function CriterionRow({ label, passed, value, note }: { label: string; passed: boolean; value?: string; note?: string }) {
  return (
    <div className="flex items-start gap-3 py-2 border-b border-gray-800 last:border-0">
      <span className={`mt-0.5 text-lg ${passed ? "text-green-400" : "text-red-400"}`}>{passed ? "✓" : "✗"}</span>
      <div className="flex-1">
        <div className="text-sm text-gray-200">{label}</div>
        {note && <div className="text-xs text-gray-500">{note}</div>}
      </div>
      {value && <div className="text-sm font-medium text-gray-300">{value}</div>}
    </div>
  );
}

export default function FundamentalPage() {
  const [symbol, setSymbol] = useState("RELIANCE");
  const [input, setInput] = useState("RELIANCE");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState("overview");

  const load = async (sym: string) => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/fundamental/deep/${sym}`);
      if (r.ok) setData(await r.json());
    } catch { }
    setLoading(false);
  };

  const d = data ?? {};
  const piotroski = d.piotroski ?? {};
  const altman = d.altman ?? {};
  const beneish = d.beneish ?? {};
  const dupont = d.dupont ?? {};
  const dcf = d.dcf ?? {};
  const roic = d.roic ?? {};
  const wc = d.working_capital ?? {};

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-1">Deep Fundamental Analysis</h1>
          <p className="text-gray-400">Piotroski F-Score • Altman Z-Score • Beneish M-Score • DCF • DuPont • ROIC • Working Capital</p>
        </div>

        <div className="flex gap-3 mb-6">
          <input value={input} onChange={e => setInput(e.target.value.toUpperCase())} onKeyDown={e => e.key === "Enter" && (setSymbol(input), load(input))}
            placeholder="Enter NSE symbol…" className="bg-gray-800 border border-gray-600 rounded-lg px-4 py-2.5 text-white text-sm w-64" />
          <button onClick={() => { setSymbol(input); load(input); }}
            className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2.5 rounded-lg text-sm font-medium">Analyze</button>
        </div>

        {!data && !loading && (
          <div className="text-center py-20 text-gray-500">Enter a stock symbol above to run deep fundamental analysis</div>
        )}
        {loading && <div className="text-center py-20 text-gray-400">Running fundamental analysis for {symbol}…</div>}

        {!loading && data && (
          <>
            {/* Score summary */}
            <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 mb-6">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-xl font-bold text-white">{symbol}</h2>
                  <p className="text-gray-400 text-sm">{d.sector} • {d.industry}</p>
                </div>
                <div className={`px-4 py-2 rounded-lg text-lg font-bold ${
                  d.overall_score >= 70 ? "bg-green-900 text-green-300" : d.overall_score >= 40 ? "bg-yellow-900 text-yellow-300" : "bg-red-900 text-red-300"
                }`}>
                  Quality Score: {d.overall_score ?? "N/A"}/100
                </div>
              </div>
              <div className="flex flex-wrap justify-around gap-6">
                <ScoreRing score={piotroski.score ?? 0} label="Piotroski F-Score /9" color={piotroski.score >= 7 ? "#22c55e" : piotroski.score >= 4 ? "#f59e0b" : "#ef4444"} />
                <ScoreRing score={Math.round(Math.min(100, Math.max(0, (altman.z_score ?? 0) / 3 * 100)))} label="Altman Z-Score" color={altman.zone === "SAFE" ? "#22c55e" : altman.zone === "GREY" ? "#f59e0b" : "#ef4444"} />
                <ScoreRing score={Math.round(Math.min(100, Math.max(0, (beneish.m_score ?? -4) + 8) / 10 * 100))} label="Beneish (Low=Safe)" color={beneish.risk === "LOW" ? "#22c55e" : beneish.risk === "MEDIUM" ? "#f59e0b" : "#ef4444"} />
                <ScoreRing score={Math.round(Math.min(100, (roic.roic_pct ?? 0) * 4))} label="ROIC vs WACC" color={(roic.roic_pct ?? 0) > (roic.wacc_pct ?? 12) ? "#22c55e" : "#ef4444"} />
              </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-2 mb-4 border-b border-gray-800 overflow-x-auto">
              {["overview","piotroski","altman","beneish","dcf","dupont","roic","working_capital"].map(t => (
                <button key={t} onClick={() => setTab(t)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap ${tab === t ? "border-blue-500 text-white" : "border-transparent text-gray-400 hover:text-white"}`}>
                  {t.replace("_"," ").split(" ").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ")}
                </button>
              ))}
            </div>

            {tab === "overview" && (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {[
                  ["P/E Ratio", d.pe_ratio?.toFixed(1), ""],
                  ["P/B Ratio", d.pb_ratio?.toFixed(2), ""],
                  ["ROE", `${d.roe?.toFixed(1)}%`, d.roe > 18 ? "text-green-400" : "text-yellow-400"],
                  ["ROIC", `${roic.roic_pct?.toFixed(1)}%`, (roic.roic_pct ?? 0) > (roic.wacc_pct ?? 12) ? "text-green-400" : "text-red-400"],
                  ["Net Margin", `${d.net_margin?.toFixed(1)}%`, ""],
                  ["Debt/Equity", d.debt_equity?.toFixed(2), d.debt_equity < 0.5 ? "text-green-400" : d.debt_equity < 1.5 ? "text-yellow-400" : "text-red-400"],
                  ["Revenue Growth", `${d.revenue_growth?.toFixed(1)}%`, d.revenue_growth > 15 ? "text-green-400" : ""],
                  ["EV/EBITDA", d.ev_ebitda?.toFixed(1), ""],
                  ["FCF Yield", d.fcf_yield ? `${d.fcf_yield.toFixed(2)}%` : "N/A", ""],
                  ["Div Yield", `${d.div_yield?.toFixed(2)}%`, ""],
                  ["Current Ratio", d.current_ratio?.toFixed(2), d.current_ratio > 2 ? "text-green-400" : d.current_ratio > 1 ? "text-yellow-400" : "text-red-400"],
                  ["Graham Number", d.graham_number ? `₹${d.graham_number.toFixed(0)}` : "N/A", ""],
                ].map(([l, v, c]) => (
                  <div key={String(l)} className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                    <div className="text-xs text-gray-400">{l}</div>
                    <div className={`text-xl font-bold mt-1 ${c || "text-white"}`}>{v ?? "N/A"}</div>
                  </div>
                ))}
              </div>
            )}

            {tab === "piotroski" && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-semibold text-gray-200">Piotroski F-Score: {piotroski.score}/9</h3>
                    <span className={`px-3 py-1 rounded text-sm font-bold ${piotroski.rating === "STRONG" ? "bg-green-900 text-green-300" : piotroski.rating === "NEUTRAL" ? "bg-yellow-900 text-yellow-300" : "bg-red-900 text-red-300"}`}>
                      {piotroski.rating}
                    </span>
                  </div>
                  <div className="text-xs text-gray-500 mb-4">Profitability</div>
                  {(piotroski.criteria?.profitability ?? []).map((c: any) => (
                    <CriterionRow key={c.name} label={c.name} passed={c.passed} value={c.value} note={c.note} />
                  ))}
                  <div className="text-xs text-gray-500 mb-2 mt-4">Leverage / Liquidity</div>
                  {(piotroski.criteria?.leverage ?? []).map((c: any) => (
                    <CriterionRow key={c.name} label={c.name} passed={c.passed} value={c.value} note={c.note} />
                  ))}
                  <div className="text-xs text-gray-500 mb-2 mt-4">Operating Efficiency</div>
                  {(piotroski.criteria?.efficiency ?? []).map((c: any) => (
                    <CriterionRow key={c.name} label={c.name} passed={c.passed} value={c.value} note={c.note} />
                  ))}
                </div>
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-gray-200 mb-4">Score Interpretation</h3>
                  <div className="space-y-3">
                    {[[8,9,"STRONG BUY","bg-green-900 text-green-300"],[6,7,"BUY","bg-green-800 text-green-400"],[4,5,"HOLD","bg-yellow-900 text-yellow-300"],[0,3,"WEAK / SELL","bg-red-900 text-red-300"]].map(([lo,hi,label,cls]) => (
                      <div key={String(label)} className={`flex items-center justify-between p-3 rounded ${piotroski.score >= lo && piotroski.score <= hi ? cls : "bg-gray-800 text-gray-400"}`}>
                        <span className="text-sm font-medium">{lo}-{hi}: {label}</span>
                        {piotroski.score >= lo && piotroski.score <= hi && <span className="text-xs">← Current</span>}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {tab === "altman" && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-semibold text-gray-200">Altman Z-Score: {altman.z_score?.toFixed(2)}</h3>
                    <span className={`px-3 py-1 rounded font-bold text-sm ${altman.zone === "SAFE" ? "bg-green-900 text-green-300" : altman.zone === "GREY" ? "bg-yellow-900 text-yellow-300" : "bg-red-900 text-red-300"}`}>
                      {altman.zone} ZONE
                    </span>
                  </div>
                  {["T1 (Working Capital/TA)","T2 (Retained Earnings/TA)","T3 (EBIT/TA)","T4 (Market Cap/Liabilities)","T5 (Revenue/TA)"].map((label, i) => {
                    const keys = ["t1","t2","t3","t4","t5"];
                    const weights = [1.2,1.4,3.3,0.6,1.0];
                    const val = altman[keys[i]];
                    return (
                      <div key={label} className="py-2 border-b border-gray-800">
                        <div className="flex justify-between text-sm mb-1">
                          <span className="text-gray-400">{label}</span>
                          <span className="text-gray-200">{val?.toFixed(3) ?? "N/A"}</span>
                        </div>
                        <div className="text-xs text-gray-500">Weight: {weights[i]}x → Contribution: {val ? (val * weights[i]).toFixed(3) : "N/A"}</div>
                      </div>
                    );
                  })}
                </div>
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-gray-200 mb-4">Bankruptcy Risk Zones</h3>
                  {[["≥ 2.99","SAFE ZONE","Low financial distress","bg-green-900 text-green-300"],["> 1.81 < 2.99","GREY ZONE","Moderate risk","bg-yellow-900 text-yellow-300"],["≤ 1.81","DISTRESS ZONE","High bankruptcy risk","bg-red-900 text-red-300"]].map(([r,z,d,c]) => (
                    <div key={z} className={`p-3 rounded mb-2 ${altman.zone === z.split(" ")[0] ? c : "bg-gray-800 text-gray-400"}`}>
                      <div className="font-semibold text-sm">{r}: {z}</div>
                      <div className="text-xs mt-0.5">{d}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {tab === "beneish" && (
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="text-sm font-semibold text-gray-200">Beneish M-Score: {beneish.m_score?.toFixed(3)}</h3>
                  <span className={`px-3 py-1 rounded font-bold text-sm ${beneish.risk === "LOW" ? "bg-green-900 text-green-300" : beneish.risk === "MEDIUM" ? "bg-yellow-900 text-yellow-300" : "bg-red-900 text-red-300"}`}>
                    {beneish.risk} MANIPULATION RISK
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  {[["DSRI","Days Sales Receivable Index"],["GMI","Gross Margin Index"],["AQI","Asset Quality Index"],["SGI","Sales Growth Index"],["DEPI","Depreciation Index"],["SGAI","SGA Expenses Index"],["LVGI","Leverage Index"],["TATA","Total Accruals/TA"]].map(([key, label]) => (
                    <div key={key} className="bg-gray-800 rounded p-3">
                      <div className="flex justify-between items-baseline mb-1">
                        <span className="text-sm font-medium text-blue-400">{key}</span>
                        <span className="text-sm text-white">{beneish[key.toLowerCase()]?.toFixed(3) ?? "N/A"}</span>
                      </div>
                      <div className="text-xs text-gray-400">{label}</div>
                    </div>
                  ))}
                </div>
                <div className="mt-4 p-3 bg-gray-800 rounded">
                  <div className="text-xs text-gray-400">Threshold: M-Score &gt; -1.78 indicates possible earnings manipulation</div>
                  <div className={`text-sm font-semibold mt-1 ${beneish.risk === "LOW" ? "text-green-400" : "text-red-400"}`}>
                    {beneish.m_score < -1.78 ? `Score of ${beneish.m_score?.toFixed(2)} is below threshold — low manipulation risk` : `Score of ${beneish.m_score?.toFixed(2)} exceeds threshold — investigate further`}
                  </div>
                </div>
              </div>
            )}

            {tab === "dcf" && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-gray-200 mb-4">DCF Intrinsic Value</h3>
                  {[["Intrinsic Value (Base)", `₹${dcf.intrinsic_value?.toFixed(0)}`,"text-blue-400"],["Current Market Price", `₹${d.current_price?.toFixed(0)}`,"text-white"],["Margin of Safety", `${dcf.margin_of_safety_pct?.toFixed(1)}%`,dcf.margin_of_safety_pct > 20 ? "text-green-400" : dcf.margin_of_safety_pct > 0 ? "text-yellow-400" : "text-red-400"],["WACC Used", `${dcf.wacc_pct?.toFixed(1)}%`,"text-gray-300"],["Terminal Growth Rate", `${(dcf.terminal_growth * 100)?.toFixed(1)}%`,"text-gray-300"],["10Y FCF Growth Rate", `${dcf.growth_rate?.toFixed(1)}%`,"text-gray-300"]].map(([l,v,c]) => (
                    <div key={String(l)} className="flex justify-between py-2 border-b border-gray-800 last:border-0">
                      <span className="text-gray-400 text-sm">{l}</span>
                      <span className={`font-bold text-sm ${c}`}>{v ?? "N/A"}</span>
                    </div>
                  ))}
                </div>
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-gray-200 mb-4">Sensitivity Table (Intrinsic Value)</h3>
                  {dcf.sensitivity && (
                    <div className="overflow-x-auto">
                      <table className="text-xs w-full">
                        <thead>
                          <tr className="text-gray-400">
                            <th className="p-2">WACC \ Growth</th>
                            {Object.keys(dcf.sensitivity[Object.keys(dcf.sensitivity)[0]] ?? {}).map(g => (
                              <th key={g} className="p-2">{g}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(dcf.sensitivity).map(([wacc, growths]) => (
                            <tr key={wacc} className="border-t border-gray-800">
                              <td className="p-2 text-gray-400 font-medium">{wacc}</td>
                              {Object.entries(growths as Record<string, number>).map(([g, v]) => (
                                <td key={g} className={`p-2 text-center font-medium ${v > (d.current_price ?? 0) ? "text-green-400" : "text-red-400"}`}>₹{Math.round(v)}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            )}

            {tab === "dupont" && (
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                <h3 className="text-sm font-semibold text-gray-200 mb-6">5-Factor DuPont Decomposition</h3>
                <div className="flex items-center gap-3 flex-wrap justify-center text-center mb-8">
                  {[["Tax Burden", dupont.tax_burden?.toFixed(3)],["×",""],["Interest Burden", dupont.interest_burden?.toFixed(3)],["×",""],["EBIT Margin", `${(dupont.ebit_margin * 100)?.toFixed(1)}%`],["×",""],["Asset Turnover", dupont.asset_turnover?.toFixed(3)],["×",""],["Leverage", dupont.financial_leverage?.toFixed(3)],["=",""],["ROE", `${dupont.roe_pct?.toFixed(1)}%`]].map(([l,v],i) => (
                    l === "×" || l === "=" ? <div key={i} className="text-2xl text-gray-500">{l}</div> :
                    <div key={i} className="bg-gray-800 rounded-lg p-3 min-w-28">
                      <div className="text-xs text-gray-400 mb-1">{l}</div>
                      <div className={`text-xl font-bold ${l === "ROE" ? "text-green-400" : "text-white"}`}>{v}</div>
                    </div>
                  ))}
                </div>
                <div className="text-xs text-gray-500 text-center">ROE = Tax Burden × Interest Burden × EBIT Margin × Asset Turnover × Equity Multiplier</div>
              </div>
            )}

            {tab === "roic" && (
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                {[["ROIC", `${roic.roic_pct?.toFixed(1)}%`, (roic.roic_pct ?? 0) > (roic.wacc_pct ?? 12) ? "text-green-400" : "text-red-400"],["WACC (Estimated)", `${roic.wacc_pct?.toFixed(1)}%`,"text-yellow-400"],["ROIC - WACC Spread", `${((roic.roic_pct ?? 0) - (roic.wacc_pct ?? 0)).toFixed(1)}%`,(roic.roic_pct ?? 0) > (roic.wacc_pct ?? 12) ? "text-green-400" : "text-red-400"],["NOPAT (₹ Cr)", roic.nopat_cr ? `₹${roic.nopat_cr?.toFixed(0)} Cr` : "N/A","text-white"],["Invested Capital (₹ Cr)", roic.invested_capital_cr ? `₹${roic.invested_capital_cr?.toFixed(0)} Cr` : "N/A","text-white"],["EVA (₹ Cr)", roic.eva_cr ? `₹${roic.eva_cr?.toFixed(0)} Cr` : "N/A",(roic.eva_cr ?? 0) > 0 ? "text-green-400" : "text-red-400"]].map(([l,v,c]) => (
                  <div key={String(l)} className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                    <div className="text-xs text-gray-400">{l}</div>
                    <div className={`text-2xl font-bold mt-1 ${c}`}>{v}</div>
                  </div>
                ))}
              </div>
            )}

            {tab === "working_capital" && (
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                {[["Cash Conversion Cycle", wc.cash_conversion_cycle ? `${wc.cash_conversion_cycle.toFixed(0)} days` : "N/A", wc.cash_conversion_cycle < 0 ? "text-green-400" : "text-white"],["Days Inventory Outstanding", wc.dio ? `${wc.dio.toFixed(0)} days` : "N/A","text-white"],["Days Sales Outstanding", wc.dso ? `${wc.dso.toFixed(0)} days` : "N/A","text-white"],["Days Payable Outstanding", wc.dpo ? `${wc.dpo.toFixed(0)} days` : "N/A","text-white"],["Net Working Capital (₹ Cr)", wc.nwc_cr ? `₹${wc.nwc_cr.toFixed(0)} Cr` : "N/A", (wc.nwc_cr ?? 0) > 0 ? "text-green-400" : "text-red-400"],["WC Change YoY (₹ Cr)", wc.nwc_change_cr ? `₹${wc.nwc_change_cr.toFixed(0)} Cr` : "N/A","text-gray-200"]].map(([l,v,c]) => (
                  <div key={String(l)} className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                    <div className="text-xs text-gray-400">{l}</div>
                    <div className={`text-2xl font-bold mt-1 ${c}`}>{v}</div>
                    {String(l) === "Cash Conversion Cycle" && <div className="text-xs text-gray-500 mt-1">{wc.cash_conversion_cycle < 0 ? "Negative CCC = competitive advantage (like DMart)" : "Positive CCC — working capital tied up"}</div>}
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
