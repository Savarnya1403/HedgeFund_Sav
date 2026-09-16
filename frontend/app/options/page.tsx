"use client";
import { useState, useEffect } from "react";

const API = "http://localhost:8001";
const FNO_SYMBOLS = ["NIFTY","BANKNIFTY","FINNIFTY","RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","SBIN","BAJFINANCE","AXISBANK","TATASTEEL","HINDALCO","TATAMOTORS","WIPRO","HCLTECH","INDUSINDBK","ITC","ONGC","COALINDIA","NTPC","BPCL","DLF","ZOMATO","ADANIENT","ADANIPORTS","TITAN","MARUTI","LT","CIPLA","DRREDDY","SUNPHARMA","DIVISLAB","EICHERMOT","MM","HEROMOTOCO","TVSMOTOR","BAJAJFINSV","JSWSTEEL"];

function PCRGauge({ pcr }: { pcr: number }) {
  const pct = Math.min(100, Math.max(0, (pcr / 2) * 100));
  const color = pcr < 0.7 ? "#ef4444" : pcr > 1.3 ? "#22c55e" : "#f59e0b";
  const label = pcr < 0.7 ? "BEARISH (Greed)" : pcr > 1.3 ? "BULLISH (Fear)" : "NEUTRAL";
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 text-center">
      <div className="text-xs text-gray-400 mb-2">Put-Call Ratio</div>
      <div className="text-4xl font-bold mb-1" style={{ color }}>{pcr.toFixed(2)}</div>
      <div className="text-sm font-medium" style={{ color }}>{label}</div>
      <div className="w-full bg-gray-700 rounded-full h-2 mt-2">
        <div className="h-2 rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <div className="flex justify-between text-xs text-gray-500 mt-1"><span>0 Greed</span><span>2.0 Fear</span></div>
    </div>
  );
}

function MaxPainChart({ data }: { data: { strike: number; pain: number; current: number; max_pain: number }[] }) {
  if (!data?.length) return null;
  const pains = data.map(d => d.pain);
  const maxP = Math.max(...pains);
  const maxPainStrike = data.find(d => d.pain === maxP)?.strike;
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-semibold text-gray-200">Max Pain Analysis</div>
        <div className="text-sm text-yellow-400 font-bold">Max Pain: ₹{maxPainStrike?.toLocaleString()}</div>
      </div>
      <div className="flex items-end gap-0.5 h-40 overflow-x-auto">
        {data.map((d, i) => (
          <div key={i} className="flex flex-col items-center flex-1 min-w-8">
            <div className={`w-full rounded-t transition-all ${d.strike === maxPainStrike ? "bg-yellow-400" : d.strike === Math.round(d.current / 50) * 50 ? "bg-blue-500" : "bg-gray-600"}`}
              style={{ height: `${(d.pain / maxP) * 100}%` }} />
            {(i % 4 === 0) && <div className="text-xs text-gray-500 mt-1 rotate-45 origin-left text-nowrap">{(d.strike / 1000).toFixed(0)}k</div>}
          </div>
        ))}
      </div>
      <div className="flex gap-4 text-xs mt-2">
        <span className="flex items-center gap-1"><span className="w-3 h-3 bg-yellow-400 rounded-sm inline-block" />Max Pain</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 bg-blue-500 rounded-sm inline-block" />Current Price</span>
      </div>
    </div>
  );
}

function OIBar({ strike, callOI, putOI, isAtm }: { strike: number; callOI: number; putOI: number; isAtm: boolean }) {
  const maxOI = Math.max(callOI, putOI, 1);
  return (
    <div className={`grid grid-cols-7 items-center gap-1 py-1 text-xs ${isAtm ? "bg-blue-950/30" : ""}`}>
      <div className="col-span-3 flex justify-end">
        <div className="bg-red-500/70 h-5 rounded-l" style={{ width: `${(callOI / maxOI) * 100}%` }} />
      </div>
      <div className={`text-center font-medium ${isAtm ? "text-blue-400" : "text-gray-300"}`}>{strike.toLocaleString()}</div>
      <div className="col-span-3">
        <div className="bg-green-500/70 h-5 rounded-r" style={{ width: `${(putOI / maxOI) * 100}%` }} />
      </div>
    </div>
  );
}

export default function OptionsPage() {
  const [symbol, setSymbol] = useState("NIFTY");
  const [expiry, setExpiry] = useState("");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState("chain");

  const load = async (sym: string, exp: string = "") => {
    setLoading(true);
    try {
      const url = exp ? `${API}/api/options/dashboard/${sym}?expiry=${exp}` : `${API}/api/options/dashboard/${sym}`;
      const r = await fetch(url);
      if (r.ok) {
        const d = await r.json();
        setData(d);
        if (!expiry && d.expiries?.length > 0) setExpiry(d.expiries[0]);
      }
    } catch { }
    setLoading(false);
  };

  useEffect(() => { load(symbol); }, []);

  const d = data ?? {};
  const chain = d.chain ?? {};
  const nearChain = chain[expiry] ?? chain[Object.keys(chain)[0]] ?? {};
  const strikes = Object.keys(nearChain).map(Number).sort((a, b) => a - b);
  const underlying = d.underlying_price ?? 0;
  const atmStrike = strikes.reduce((best, s) => Math.abs(s - underlying) < Math.abs(best - underlying) ? s : best, strikes[0] ?? 0);
  const strikeWindow = strikes.filter(s => s >= atmStrike * 0.95 && s <= atmStrike * 1.05);

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-white mb-1">Options Analytics</h1>
          <p className="text-gray-400">Real NSE Options Chain • IV Surface • Max Pain • Greeks • OI Analysis • PCR</p>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap gap-3 mb-6">
          <select value={symbol} onChange={e => { setSymbol(e.target.value); setExpiry(""); load(e.target.value); }}
            className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white">
            {FNO_SYMBOLS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          {d.expiries?.length > 0 && (
            <select value={expiry} onChange={e => setExpiry(e.target.value)}
              className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white">
              {d.expiries.map((e: string) => <option key={e} value={e}>{e}</option>)}
            </select>
          )}
          <button onClick={() => load(symbol, expiry)} className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-medium">Refresh</button>
          {loading && <span className="text-gray-400 text-sm self-center">Loading…</span>}
        </div>

        {/* Summary Row */}
        {data && (
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-6">
            <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
              <div className="text-xs text-gray-400">Underlying Price</div>
              <div className="text-2xl font-bold text-white">₹{underlying.toLocaleString(undefined, { maximumFractionDigits: 2 })}</div>
            </div>
            {d.pcr != null && (
              <PCRGauge pcr={d.pcr} />
            )}
            <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
              <div className="text-xs text-gray-400">Max Pain Strike</div>
              <div className="text-2xl font-bold text-yellow-400">₹{(d.max_pain?.max_pain_strike ?? 0).toLocaleString()}</div>
              <div className="text-xs text-gray-500 mt-1">Distance: {d.max_pain?.distance_pct?.toFixed(1) ?? "N/A"}%</div>
            </div>
            <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
              <div className="text-xs text-gray-400">ATM IV</div>
              <div className="text-2xl font-bold text-purple-400">{(d.atm_iv ?? 0).toFixed(1)}%</div>
            </div>
            <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
              <div className="text-xs text-gray-400">Expected Move</div>
              <div className="text-2xl font-bold text-blue-400">±{(d.expected_move_pct ?? 0).toFixed(1)}%</div>
              <div className="text-xs text-gray-500 mt-1">1σ by expiry</div>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-2 mb-4 border-b border-gray-800 overflow-x-auto">
          {["chain","oi_analysis","greeks","iv_surface","max_pain","skew"].map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap ${tab === t ? "border-blue-500 text-white" : "border-transparent text-gray-400 hover:text-white"}`}>
              {t.replace("_"," ").toUpperCase()}
            </button>
          ))}
        </div>

        {tab === "chain" && (
          <div className="bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
            <div style={{ minWidth: 640 }}>
            <div className="grid grid-cols-11 text-xs text-gray-400 bg-gray-800 px-3 py-2 font-medium">
              <div className="col-span-2">OI (CE)</div><div>Chg OI</div><div>Vol</div><div>IV</div>
              <div className="text-center font-bold text-gray-200">STRIKE</div>
              <div className="text-right">IV</div><div className="text-right">Vol</div><div className="text-right">Chg OI</div><div className="col-span-2 text-right">OI (PE)</div>
            </div>
            <div className="overflow-y-auto max-h-[500px]">
              {strikeWindow.map(strike => {
                const row = nearChain[strike] ?? {};
                const ce = row.CE ?? {}; const pe = row.PE ?? {};
                const isAtm = strike === atmStrike;
                return (
                  <div key={strike} className={`grid grid-cols-11 text-xs px-3 py-2 border-t border-gray-800 ${isAtm ? "bg-blue-950/40" : "hover:bg-gray-800/50"}`}>
                    <div className={`col-span-2 ${isAtm ? "font-bold text-blue-300" : "text-red-400"}`}>{(ce.oi ?? 0).toLocaleString()}</div>
                    <div className={ce.change_oi > 0 ? "text-green-400" : "text-red-400"}>{(ce.change_oi ?? 0) > 0 ? "+" : ""}{(ce.change_oi ?? 0).toLocaleString()}</div>
                    <div className="text-gray-300">{(ce.volume ?? 0).toLocaleString()}</div>
                    <div className="text-purple-400">{(ce.iv ?? 0).toFixed(1)}%</div>
                    <div className={`text-center font-bold ${isAtm ? "text-blue-400" : "text-white"}`}>{strike.toLocaleString()}</div>
                    <div className="text-right text-purple-400">{(pe.iv ?? 0).toFixed(1)}%</div>
                    <div className="text-right text-gray-300">{(pe.volume ?? 0).toLocaleString()}</div>
                    <div className={`text-right ${pe.change_oi > 0 ? "text-green-400" : "text-red-400"}`}>{(pe.change_oi ?? 0) > 0 ? "+" : ""}{(pe.change_oi ?? 0).toLocaleString()}</div>
                    <div className={`col-span-2 text-right ${isAtm ? "font-bold text-blue-300" : "text-green-400"}`}>{(pe.oi ?? 0).toLocaleString()}</div>
                  </div>
                );
              })}
            </div>
            </div>
            </div>
          </div>
        )}

        {tab === "oi_analysis" && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                <h3 className="text-sm font-semibold text-gray-200 mb-3">Top Call OI (Resistance)</h3>
                {(d.oi_analysis?.top_call_oi ?? []).map((item: any) => (
                  <div key={item.strike} className="flex items-center justify-between py-1.5 border-b border-gray-800">
                    <span className="text-red-400 font-medium">₹{item.strike.toLocaleString()}</span>
                    <div className="flex-1 mx-3 bg-gray-700 rounded-full h-2">
                      <div className="bg-red-500 h-2 rounded-full" style={{ width: `${Math.min((item.oi / (d.oi_analysis?.top_call_oi?.[0]?.oi ?? 1)) * 100, 100)}%` }} />
                    </div>
                    <span className="text-gray-300 text-xs">{(item.oi / 1000).toFixed(0)}K</span>
                  </div>
                ))}
              </div>
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                <h3 className="text-sm font-semibold text-gray-200 mb-3">Top Put OI (Support)</h3>
                {(d.oi_analysis?.top_put_oi ?? []).map((item: any) => (
                  <div key={item.strike} className="flex items-center justify-between py-1.5 border-b border-gray-800">
                    <span className="text-green-400 font-medium">₹{item.strike.toLocaleString()}</span>
                    <div className="flex-1 mx-3 bg-gray-700 rounded-full h-2">
                      <div className="bg-green-500 h-2 rounded-full" style={{ width: `${Math.min((item.oi / (d.oi_analysis?.top_put_oi?.[0]?.oi ?? 1)) * 100, 100)}%` }} />
                    </div>
                    <span className="text-gray-300 text-xs">{(item.oi / 1000).toFixed(0)}K</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-gray-200 mb-3">OI Visual (Calls vs Puts)</h3>
              <div className="grid grid-cols-7 text-xs text-gray-400 mb-2"><div className="col-span-3 text-right pr-2">Calls (Resistance)</div><div className="text-center">Strike</div><div className="col-span-3 pl-2">Puts (Support)</div></div>
              {strikeWindow.slice(0, 20).map(strike => {
                const row = nearChain[strike] ?? {};
                const callOI = row.CE?.oi ?? 0;
                const putOI = row.PE?.oi ?? 0;
                return <OIBar key={strike} strike={strike} callOI={callOI} putOI={putOI} isAtm={strike === atmStrike} />;
              })}
            </div>
          </div>
        )}

        {tab === "greeks" && (
          <div className="bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
            <div style={{ minWidth: 560 }}>
            <div className="grid grid-cols-9 text-xs text-gray-400 bg-gray-800 px-3 py-2">
              <div>Strike</div><div>Type</div><div>Delta</div><div>Gamma</div><div>Theta</div><div>Vega</div><div>Rho</div><div>IV</div><div>LTP</div>
            </div>
            <div className="overflow-y-auto max-h-[500px]">
              {strikeWindow.flatMap(strike => {
                const row = nearChain[strike] ?? {};
                return ["CE","PE"].map(type => {
                  const opt = row[type] ?? {};
                  const g = opt.greeks ?? {};
                  if (!g.delta) return null;
                  return (
                    <div key={`${strike}-${type}`} className="grid grid-cols-9 text-xs px-3 py-2 border-t border-gray-800 hover:bg-gray-800/50">
                      <div className={strike === atmStrike ? "text-blue-400 font-bold" : "text-white"}>{strike.toLocaleString()}</div>
                      <div className={type === "CE" ? "text-red-400" : "text-green-400"}>{type}</div>
                      <div className="text-gray-300">{g.delta?.toFixed(3)}</div>
                      <div className="text-gray-300">{g.gamma?.toFixed(5)}</div>
                      <div className="text-orange-400">{g.theta?.toFixed(3)}</div>
                      <div className="text-purple-400">{g.vega?.toFixed(3)}</div>
                      <div className="text-gray-300">{g.rho?.toFixed(3)}</div>
                      <div className="text-purple-300">{(opt.iv ?? 0).toFixed(1)}%</div>
                      <div className="text-white">₹{(opt.ltp ?? 0).toFixed(2)}</div>
                    </div>
                  );
                }).filter(Boolean);
              })}
            </div>
            </div>
            </div>
          </div>
        )}

        {tab === "iv_surface" && (
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-gray-200 mb-4">IV Surface — Strikes × Expiries</h3>
            {d.iv_surface && (
              <div className="overflow-x-auto">
                <table className="text-xs w-full">
                  <thead>
                    <tr className="text-gray-400">
                      <th className="p-2 text-left">Strike</th>
                      {(d.expiries ?? []).map((e: string) => <th key={e} className="p-2 text-center">{e}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(d.iv_surface).map(([strike, expData]) => (
                      <tr key={strike} className={`border-t border-gray-800 ${Number(strike) === atmStrike ? "bg-blue-950/30" : ""}`}>
                        <td className={`p-2 font-medium ${Number(strike) === atmStrike ? "text-blue-400" : "text-gray-300"}`}>{Number(strike).toLocaleString()}</td>
                        {(d.expiries ?? []).map((e: string) => {
                          const iv = (expData as any)[e];
                          const color = iv > 30 ? "text-red-400" : iv > 20 ? "text-yellow-400" : "text-green-400";
                          return <td key={e} className={`p-2 text-center ${color}`}>{iv ? `${iv.toFixed(1)}%` : "-"}</td>;
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="mt-4 grid grid-cols-3 gap-4">
              <div className="bg-gray-800 rounded p-3">
                <div className="text-xs text-gray-400">IV Percentile</div>
                <div className="text-xl font-bold text-purple-400 mt-1">{d.iv_rank?.iv_percentile?.toFixed(0) ?? "N/A"}%</div>
              </div>
              <div className="bg-gray-800 rounded p-3">
                <div className="text-xs text-gray-400">IV Rank (52W)</div>
                <div className="text-xl font-bold text-purple-400 mt-1">{d.iv_rank?.iv_rank?.toFixed(0) ?? "N/A"}%</div>
              </div>
              <div className="bg-gray-800 rounded p-3">
                <div className="text-xs text-gray-400">25Δ Skew</div>
                <div className="text-xl font-bold text-orange-400 mt-1">{d.skew?.skew_25d?.toFixed(1) ?? "N/A"}%</div>
              </div>
            </div>
          </div>
        )}

        {tab === "max_pain" && d.max_pain && (
          <div className="space-y-4">
            <MaxPainChart data={d.max_pain.pain_by_strike ?? []} />
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                <div className="text-xs text-gray-400">Max Pain Strike</div>
                <div className="text-2xl font-bold text-yellow-400">₹{(d.max_pain.max_pain_strike ?? 0).toLocaleString()}</div>
              </div>
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                <div className="text-xs text-gray-400">Distance from Current</div>
                <div className="text-2xl font-bold text-white">{d.max_pain.distance_pct?.toFixed(2) ?? "N/A"}%</div>
              </div>
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                <div className="text-xs text-gray-400">Signal</div>
                <div className={`text-2xl font-bold ${d.max_pain.distance_pct > 2 ? "text-red-400" : d.max_pain.distance_pct < -2 ? "text-green-400" : "text-gray-300"}`}>
                  {d.max_pain.distance_pct > 2 ? "BEARISH PULL" : d.max_pain.distance_pct < -2 ? "BULLISH PULL" : "NEAR MAX PAIN"}
                </div>
              </div>
            </div>
          </div>
        )}

        {tab === "skew" && (
          <div className="grid grid-cols-2 gap-4">
            {[["25Δ Skew", `${d.skew?.skew_25d?.toFixed(1) ?? "N/A"}%`, "text-orange-400", "Put IV - Call IV at 25 delta"],["Risk Reversal", `${d.skew?.risk_reversal?.toFixed(2) ?? "N/A"}%`,"text-yellow-400","Sentiment: positive = put demand higher"],["Butterfly", `${d.skew?.butterfly?.toFixed(2) ?? "N/A"}%`,"text-blue-400","ATM vol vs OTM wings"],["IV Term Structure", d.skew?.term_structure_slope > 0 ? "CONTANGO" : "BACKWARDATION","text-purple-400","Near vs far month IV slope"]].map(([l,v,c,note]) => (
              <div key={String(l)} className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                <div className="text-xs text-gray-400">{l}</div>
                <div className={`text-2xl font-bold mt-1 ${c}`}>{v}</div>
                <div className="text-xs text-gray-500 mt-1">{note}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
