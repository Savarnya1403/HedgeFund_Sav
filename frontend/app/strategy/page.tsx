'use client';

import { useState, useEffect, useRef } from "react";
import IndexBar from "@/components/IndexBar";
import { createChart, LineSeries, type IChartApi, type Time } from "lightweight-charts";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

const NIFTY50 = ["RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","BAJFINANCE","SBIN","TATASTEEL","SUNPHARMA","ITC","AXISBANK","KOTAKBANK","LT","MARUTI","HCLTECH"];

const STRATEGIES = [
  { id: "long_straddle", label: "Long Straddle", category: "Volatility" },
  { id: "short_straddle", label: "Short Straddle", category: "Volatility" },
  { id: "long_strangle", label: "Long Strangle", category: "Volatility" },
  { id: "short_strangle", label: "Short Strangle", category: "Volatility" },
  { id: "bull_call_spread", label: "Bull Call Spread", category: "Directional" },
  { id: "bear_put_spread", label: "Bear Put Spread", category: "Directional" },
  { id: "iron_condor", label: "Iron Condor", category: "Income" },
  { id: "iron_butterfly", label: "Iron Butterfly", category: "Income" },
  { id: "butterfly", label: "Butterfly", category: "Income" },
  { id: "protective_put", label: "Protective Put", category: "Hedge" },
  { id: "covered_call", label: "Covered Call", category: "Income" },
  { id: "ratio_spread", label: "Ratio Spread", category: "Advanced" },
];

const CATEGORIES = ["All", "Volatility", "Directional", "Income", "Hedge", "Advanced"];

interface StrategyData {
  strategy: string;
  description: string;
  symbol: string;
  spot: number;
  iv_pct: number;
  days_to_expiry: number;
  legs: Array<{ type: string; strike: number; qty: number; action: string; premium: number }>;
  price_range: number[];
  pnl_expiry: number[];
  pnl_today: number[];
  breakevens: number[];
  max_profit: number;
  max_loss: number;
  net_premium_paid: number;
  risk_reward: number;
  greeks: { delta: number; gamma: number; theta: number; vega: number; rho: number };
}

function PnLChart({ data }: { data: StrategyData }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !data?.price_range?.length) return;
    ref.current.innerHTML = "";

    const chart = createChart(ref.current, {
      width: ref.current.clientWidth, height: 280,
      layout: { background: { color: "#0a0a0a" }, textColor: "#888", fontSize: 10, fontFamily: "monospace" },
      grid: { vertLines: { color: "#111" }, horzLines: { color: "#111" } },
      rightPriceScale: { scaleMargins: { top: 0.1, bottom: 0.1 } },
      timeScale: { visible: false },
    });

    const expirySeries = chart.addSeries(LineSeries, {
      color: "#3b82f6", lineWidth: 2, priceLineVisible: false, lastValueVisible: false, title: "At Expiry"
    });
    const todaySeries = chart.addSeries(LineSeries, {
      color: "#f59e0b", lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false, title: "Today"
    });
    const zeroLine = chart.addSeries(LineSeries, {
      color: "#334155", lineWidth: 1, lineStyle: 3, priceLineVisible: false, lastValueVisible: false
    });

    const toTime = (i: number) => (1000000 + i) as Time;
    expirySeries.setData(data.price_range.map((p, i) => ({ time: toTime(i), value: data.pnl_expiry[i] })));
    todaySeries.setData(data.price_range.map((p, i) => ({ time: toTime(i), value: data.pnl_today[i] })));
    zeroLine.setData(data.price_range.map((_, i) => ({ time: toTime(i), value: 0 })));
    chart.timeScale().fitContent();

    const obs = new ResizeObserver(() => {
      if (ref.current) chart.applyOptions({ width: ref.current.clientWidth });
    });
    obs.observe(ref.current);
    return () => { obs.disconnect(); chart.remove(); };
  }, [data]);

  return <div ref={ref} style={{ width: "100%" }} />;
}

export default function StrategyPage() {
  const [symbol, setSymbol] = useState("RELIANCE");
  const [input, setInput] = useState("RELIANCE");
  const [strategy, setStrategy] = useState("iron_condor");
  const [days, setDays] = useState(30);
  const [data, setData] = useState<StrategyData | null>(null);
  const [loading, setLoading] = useState(false);
  const [catFilter, setCatFilter] = useState("All");

  async function load(sym: string, strat: string, d: number) {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/strategy/${strat}/${sym}?days=${d}`);
      const json = await res.json();
      setData(json);
    } catch (e) { console.error(e); }
    setLoading(false);
  }

  useEffect(() => { load(symbol, strategy, days); }, [symbol, strategy, days]);

  const filteredStrategies = STRATEGIES.filter(s => catFilter === "All" || s.category === catFilter);

  const gColor = (v: number) => v > 0 ? "#22c55e" : v < 0 ? "#ef4444" : "#64748b";

  return (
    <div style={{ background: "#050505", minHeight: "100vh", color: "#e2e8f0", fontFamily: "monospace" }}>
      <IndexBar />
      <div style={{ padding: "16px 24px" }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 11, color: "#64748b", textTransform: "uppercase", letterSpacing: 2 }}>Options Trading</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: "#f1f5f9" }}>Strategy Builder</div>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
            <input
              value={input}
              onChange={e => setInput(e.target.value.toUpperCase())}
              onKeyDown={e => { if (e.key === "Enter") { setSymbol(input); } }}
              style={{ background: "#0f0f0f", border: "1px solid #222", borderRadius: 6, padding: "6px 12px", color: "#f1f5f9", fontSize: 13, width: 120, fontFamily: "monospace" }}
              placeholder="Symbol"
            />
            <select
              value={days}
              onChange={e => setDays(Number(e.target.value))}
              style={{ background: "#0f0f0f", border: "1px solid #222", borderRadius: 6, padding: "6px 12px", color: "#f1f5f9", fontSize: 13, fontFamily: "monospace" }}
            >
              {[7, 14, 21, 30, 45, 60, 90].map(d => (
                <option key={d} value={d}>{d}d</option>
              ))}
            </select>
            <button onClick={() => load(input, strategy, days)}
              style={{ background: "#7c3aed", border: "none", borderRadius: 6, padding: "6px 16px", color: "#fff", fontSize: 13, cursor: "pointer" }}>
              {loading ? "..." : "Analyze"}
            </button>
          </div>
        </div>

        {/* Symbol strip */}
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 }}>
          {NIFTY50.slice(0, 12).map(s => (
            <button key={s} onClick={() => { setSymbol(s); setInput(s); load(s, strategy, days); }}
              style={{
                background: symbol === s ? "#7c3aed" : "#0f0f0f",
                border: `1px solid ${symbol === s ? "#8b5cf6" : "#222"}`,
                borderRadius: 4, padding: "3px 10px", color: symbol === s ? "#fff" : "#888",
                fontSize: 11, cursor: "pointer", fontFamily: "monospace"
              }}>{s}</button>
          ))}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: 16 }}>
          {/* Strategy selector */}
          <div style={{ background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: 8, padding: 12 }}>
            <div style={{ fontSize: 11, color: "#64748b", marginBottom: 10, textTransform: "uppercase", letterSpacing: 1 }}>Strategy</div>
            {/* Category filter */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 10 }}>
              {CATEGORIES.map(c => (
                <button key={c} onClick={() => setCatFilter(c)}
                  style={{
                    background: catFilter === c ? "#1d4ed8" : "#111",
                    border: "1px solid #222", borderRadius: 4, padding: "2px 8px",
                    color: catFilter === c ? "#fff" : "#64748b", fontSize: 10, cursor: "pointer"
                  }}>{c}</button>
              ))}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {filteredStrategies.map(s => (
                <button key={s.id} onClick={() => { setStrategy(s.id); load(symbol, s.id, days); }}
                  style={{
                    background: strategy === s.id ? "#1d4ed822" : "transparent",
                    border: `1px solid ${strategy === s.id ? "#3b82f6" : "#111"}`,
                    borderRadius: 6, padding: "8px 10px", textAlign: "left",
                    color: strategy === s.id ? "#93c5fd" : "#94a3b8", cursor: "pointer",
                    display: "flex", flexDirection: "column", gap: 2
                  }}>
                  <span style={{ fontSize: 12, fontWeight: strategy === s.id ? 700 : 400 }}>{s.label}</span>
                  <span style={{ fontSize: 9, color: "#475569" }}>{s.category}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Main content */}
          {data && (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {/* Description */}
              <div style={{ background: "#0f1a2e", border: "1px solid #1d3461", borderRadius: 8, padding: 12, fontSize: 13, color: "#93c5fd" }}>
                <span style={{ fontWeight: 700 }}>{STRATEGIES.find(s => s.id === data.strategy)?.label || data.strategy}</span>
                {" — "}{data.description}
              </div>

              {/* Key numbers */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10 }}>
                {[
                  { label: "Max Profit", value: data.max_profit === 999 ? "Unlimited" : `₹${data.max_profit.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`, color: "#22c55e" },
                  { label: "Max Loss", value: data.max_loss === -999 ? "Unlimited" : `₹${Math.abs(data.max_loss).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`, color: "#ef4444" },
                  { label: "Net Premium", value: `₹${Math.abs(data.net_premium_paid).toFixed(2)}`, color: data.net_premium_paid > 0 ? "#ef4444" : "#22c55e" },
                  { label: "R/R Ratio", value: data.risk_reward === 999 ? "∞" : data.risk_reward.toFixed(2), color: data.risk_reward > 1.5 ? "#22c55e" : "#f59e0b" },
                ].map((m, i) => (
                  <div key={i} style={{ background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: 8, padding: "12px 14px" }}>
                    <div style={{ fontSize: 10, color: "#64748b", marginBottom: 4, textTransform: "uppercase", letterSpacing: 1 }}>{m.label}</div>
                    <div style={{ fontSize: 18, fontWeight: 700, color: m.color }}>{m.value}</div>
                  </div>
                ))}
              </div>

              {/* Breakevens */}
              {data.breakevens.length > 0 && (
                <div style={{ background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: 8, padding: 12, display: "flex", alignItems: "center", gap: 12 }}>
                  <span style={{ fontSize: 11, color: "#64748b", textTransform: "uppercase", letterSpacing: 1 }}>Breakevens:</span>
                  {data.breakevens.map((be, i) => (
                    <span key={i} style={{ background: "#1a1a1a", borderRadius: 4, padding: "3px 10px", fontSize: 13, fontWeight: 700, color: "#f59e0b" }}>
                      ₹{be.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                    </span>
                  ))}
                  <span style={{ fontSize: 11, color: "#475569", marginLeft: "auto" }}>
                    Spot: ₹{data.spot.toLocaleString("en-IN", { maximumFractionDigits: 2 })} | IV: {data.iv_pct.toFixed(1)}% | DTE: {data.days_to_expiry}d
                  </span>
                </div>
              )}

              {/* P&L Chart */}
              <div style={{ background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: 8, padding: 16 }}>
                <div style={{ fontSize: 12, color: "#64748b", marginBottom: 8, display: "flex", gap: 16 }}>
                  <span style={{ textTransform: "uppercase", letterSpacing: 1 }}>P&L Diagram</span>
                  <span style={{ color: "#3b82f6" }}>— At Expiry</span>
                  <span style={{ color: "#f59e0b" }}>- - Today</span>
                </div>
                <PnLChart data={data} />
                <div style={{ fontSize: 10, color: "#475569", marginTop: 6, textAlign: "center" }}>
                  X-axis: Price range ±30% from spot · Y-axis: P&L (₹ per lot)
                </div>
              </div>

              {/* Greeks + Legs */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                {/* Net Greeks */}
                <div style={{ background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: 8, padding: 16 }}>
                  <div style={{ fontSize: 12, color: "#64748b", marginBottom: 12, textTransform: "uppercase", letterSpacing: 1 }}>Net Greeks</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    {[
                      { name: "Δ Delta", value: data.greeks.delta, note: "Directional exposure" },
                      { name: "Γ Gamma", value: data.greeks.gamma, note: "Delta acceleration" },
                      { name: "Θ Theta", value: data.greeks.theta, note: "Daily time decay" },
                      { name: "V Vega", value: data.greeks.vega, note: "IV sensitivity" },
                      { name: "ρ Rho", value: data.greeks.rho, note: "Rate sensitivity" },
                    ].map(g => (
                      <div key={g.name} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <span style={{ width: 70, fontSize: 12, fontWeight: 700 }}>{g.name}</span>
                        <span style={{ width: 70, fontSize: 14, fontWeight: 700, color: gColor(g.value) }}>{g.value.toFixed(4)}</span>
                        <span style={{ fontSize: 10, color: "#475569" }}>{g.note}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Legs */}
                <div style={{ background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: 8, padding: 16 }}>
                  <div style={{ fontSize: 12, color: "#64748b", marginBottom: 12, textTransform: "uppercase", letterSpacing: 1 }}>Legs</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {data.legs.map((leg, i) => (
                      <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 10px", background: "#050505", borderRadius: 6, border: "1px solid #111" }}>
                        <span style={{
                          background: leg.action === "buy" ? "#22c55e22" : "#ef444422",
                          color: leg.action === "buy" ? "#22c55e" : "#ef4444",
                          border: `1px solid ${leg.action === "buy" ? "#22c55e44" : "#ef444444"}`,
                          borderRadius: 4, padding: "2px 8px", fontSize: 11, fontWeight: 700, textTransform: "uppercase"
                        }}>{leg.action}</span>
                        <span style={{ fontWeight: 700, fontSize: 13 }}>{leg.qty}x</span>
                        <span style={{ color: leg.type === "call" ? "#3b82f6" : "#f59e0b", fontWeight: 700, fontSize: 13 }}>
                          {leg.type.toUpperCase()}
                        </span>
                        <span style={{ fontSize: 13 }}>₹{leg.strike.toLocaleString("en-IN")}</span>
                        <span style={{ marginLeft: "auto", fontSize: 12, color: "#94a3b8" }}>₹{leg.premium.toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {loading && !data && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 300, color: "#64748b" }}>
              Computing strategy P&L...
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
