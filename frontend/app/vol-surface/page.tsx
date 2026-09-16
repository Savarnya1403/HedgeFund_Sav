'use client';

import { useState, useEffect } from "react";
import IndexBar from "@/components/IndexBar";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

const NIFTY50 = [
  "RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","HINDUNILVR","BAJFINANCE",
  "BHARTIARTL","SBIN","KOTAKBANK","ITC","LT","AXISBANK","TITAN","ASIANPAINT",
  "MARUTI","WIPRO","HCLTECH","NTPC","ONGC","TATASTEEL","SUNPHARMA","TECHM",
];

interface VolSurface {
  symbol: string;
  spot: number;
  atm_iv_pct: number;
  hv30_pct: number;
  iv_hv_ratio: number;
  vol_rank_pct: number;
  vol_regime: string;
  surface: Record<string, Record<string, number>>;
  term_structure: Record<string, number>;
  moneyness_labels: string[];
  expiry_labels: string[];
  skew: { rr_25d_pct: number; butterfly_25d_pct: number; note: string };
}

function volColor(v: number): string {
  if (v < 15) return "#1e3a5f";
  if (v < 20) return "#1d4ed8";
  if (v < 25) return "#2563eb";
  if (v < 30) return "#7c3aed";
  if (v < 35) return "#db2777";
  if (v < 45) return "#ef4444";
  return "#991b1b";
}

function regimeColor(r: string) {
  if (r === "Low") return "#22c55e";
  if (r === "Normal") return "#3b82f6";
  if (r === "Elevated") return "#f59e0b";
  return "#ef4444";
}

export default function VolSurfacePage() {
  const [symbol, setSymbol] = useState("NIFTY");
  const [input, setInput] = useState("NIFTY");
  const [data, setData] = useState<VolSurface | null>(null);
  const [loading, setLoading] = useState(false);
  const [hoveredCell, setHoveredCell] = useState<{ expiry: string; moneyness: string; val: number } | null>(null);
  const [tab, setTab] = useState<"surface" | "term" | "skew">("surface");

  async function load(sym: string) {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/vol-surface/${sym}`);
      const json = await res.json();
      setData(json);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  }

  useEffect(() => { load(symbol); }, [symbol]);

  return (
    <div style={{ background: "#050505", minHeight: "100vh", color: "#e2e8f0", fontFamily: "monospace" }}>
      <IndexBar />
      <div style={{ padding: "16px 24px" }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 11, color: "#64748b", textTransform: "uppercase", letterSpacing: 2 }}>Options Analytics</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: "#f1f5f9" }}>Volatility Surface</div>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
            <input
              value={input}
              onChange={e => setInput(e.target.value.toUpperCase())}
              onKeyDown={e => { if (e.key === "Enter") setSymbol(input); }}
              style={{ background: "#0f0f0f", border: "1px solid #222", borderRadius: 6, padding: "6px 12px", color: "#f1f5f9", fontSize: 13, width: 120, fontFamily: "monospace" }}
              placeholder="Symbol"
            />
            <button onClick={() => setSymbol(input)}
              style={{ background: "#7c3aed", border: "none", borderRadius: 6, padding: "6px 16px", color: "#fff", fontSize: 13, cursor: "pointer" }}>
              {loading ? "..." : "Load"}
            </button>
          </div>
        </div>

        {/* Symbol strip */}
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 16 }}>
          {["NIFTY", "BANKNIFTY", ...NIFTY50.slice(0, 12)].map(s => (
            <button key={s} onClick={() => { setSymbol(s); setInput(s); }}
              style={{
                background: symbol === s ? "#7c3aed" : "#0f0f0f",
                border: `1px solid ${symbol === s ? "#8b5cf6" : "#222"}`,
                borderRadius: 4, padding: "3px 10px",
                color: symbol === s ? "#fff" : "#888", fontSize: 11, cursor: "pointer", fontFamily: "monospace"
              }}>{s}</button>
          ))}
        </div>

        {data && (
          <>
            {/* Key metrics */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 12, marginBottom: 16 }}>
              {[
                { label: "Spot", value: `₹${data.spot.toLocaleString("en-IN", { maximumFractionDigits: 2 })}` },
                { label: "ATM IV", value: `${data.atm_iv_pct.toFixed(1)}%`, color: regimeColor(data.vol_regime) },
                { label: "HV30", value: `${data.hv30_pct.toFixed(1)}%` },
                { label: "IV/HV Ratio", value: data.iv_hv_ratio.toFixed(2), color: data.iv_hv_ratio > 1.3 ? "#ef4444" : data.iv_hv_ratio < 0.9 ? "#22c55e" : "#f59e0b" },
                { label: "Vol Rank", value: `${data.vol_rank_pct.toFixed(0)}th %ile`, color: regimeColor(data.vol_regime) },
              ].map((m, i) => (
                <div key={i} style={{ background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: 8, padding: "12px 16px" }}>
                  <div style={{ fontSize: 10, color: "#64748b", marginBottom: 4, textTransform: "uppercase", letterSpacing: 1 }}>{m.label}</div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: (m as any).color || "#f1f5f9" }}>{m.value}</div>
                </div>
              ))}
            </div>

            {/* Vol regime badge */}
            <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 16 }}>
              <span style={{
                background: regimeColor(data.vol_regime) + "22", color: regimeColor(data.vol_regime),
                border: `1px solid ${regimeColor(data.vol_regime)}44`, borderRadius: 20,
                padding: "4px 16px", fontSize: 13, fontWeight: 700
              }}>Vol Regime: {data.vol_regime}</span>
              <span style={{ color: "#64748b", fontSize: 12 }}>
                25Δ RR: <span style={{ color: "#f59e0b" }}>{data.skew.rr_25d_pct > 0 ? "+" : ""}{data.skew.rr_25d_pct.toFixed(1)}%</span>
                &nbsp;·&nbsp;
                25Δ Butterfly: <span style={{ color: "#8b5cf6" }}>{data.skew.butterfly_25d_pct.toFixed(2)}%</span>
              </span>
            </div>

            {/* Tabs */}
            <div style={{ display: "flex", gap: 4, marginBottom: 16, borderBottom: "1px solid #1a1a1a", paddingBottom: 8 }}>
              {[
                { id: "surface", label: "Vol Surface Heatmap" },
                { id: "term", label: "Term Structure" },
                { id: "skew", label: "Vol Skew" },
              ].map(t => (
                <button key={t.id} onClick={() => setTab(t.id as any)}
                  style={{
                    background: tab === t.id ? "#7c3aed" : "transparent",
                    border: `1px solid ${tab === t.id ? "#8b5cf6" : "#222"}`,
                    borderRadius: 6, padding: "5px 16px",
                    color: tab === t.id ? "#fff" : "#64748b", fontSize: 12, cursor: "pointer", fontFamily: "monospace"
                  }}>{t.label}</button>
              ))}
            </div>

            {/* SURFACE HEATMAP */}
            {tab === "surface" && (
              <div style={{ background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: 8, padding: 16 }}>
                <div style={{ fontSize: 12, color: "#64748b", marginBottom: 12 }}>
                  Implied Volatility (%) — hover for details
                </div>
                <div style={{ overflowX: "auto" }}>
                  <table style={{ borderCollapse: "collapse", fontSize: 12, minWidth: 700 }}>
                    <thead>
                      <tr>
                        <th style={{ padding: "6px 12px", textAlign: "left", color: "#64748b", fontWeight: 400, borderBottom: "1px solid #1a1a1a" }}>
                          Expiry ↓ / Moneyness →
                        </th>
                        {data.moneyness_labels.map(m => (
                          <th key={m} style={{
                            padding: "6px 8px", textAlign: "center", color: m === "100%" ? "#f1f5f9" : "#64748b",
                            fontWeight: m === "100%" ? 700 : 400, borderBottom: "1px solid #1a1a1a", minWidth: 52
                          }}>{m}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {data.expiry_labels.map(expiry => (
                        <tr key={expiry}>
                          <td style={{ padding: "6px 12px", color: "#94a3b8", whiteSpace: "nowrap", borderBottom: "1px solid #111" }}>{expiry}</td>
                          {data.moneyness_labels.map(m => {
                            const v = data.surface[expiry]?.[m] ?? 0;
                            const isHovered = hoveredCell?.expiry === expiry && hoveredCell?.moneyness === m;
                            return (
                              <td key={m}
                                onMouseEnter={() => setHoveredCell({ expiry, moneyness: m, val: v })}
                                onMouseLeave={() => setHoveredCell(null)}
                                style={{
                                  padding: "6px 4px", textAlign: "center", background: volColor(v),
                                  border: isHovered ? "1px solid #fff" : "1px solid transparent",
                                  cursor: "default", fontWeight: m === "100%" ? 700 : 400,
                                  color: "#fff", borderBottom: "1px solid #111",
                                }}>
                                {v.toFixed(1)}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {hoveredCell && (
                  <div style={{ marginTop: 12, padding: 10, background: "#0f0f2e", borderRadius: 6, fontSize: 12, color: "#93c5fd" }}>
                    {hoveredCell.expiry} | {hoveredCell.moneyness} moneyness — IV: <strong>{hoveredCell.val.toFixed(2)}%</strong>
                    {" "} | vs ATM ({data.atm_iv_pct.toFixed(1)}%): <strong style={{ color: hoveredCell.val > data.atm_iv_pct ? "#f59e0b" : "#22c55e" }}>
                      {(hoveredCell.val - data.atm_iv_pct).toFixed(2)} vol pts
                    </strong>
                  </div>
                )}

                {/* Legend */}
                <div style={{ display: "flex", gap: 8, marginTop: 16, alignItems: "center" }}>
                  <span style={{ fontSize: 11, color: "#64748b" }}>IV%:</span>
                  {[
                    { label: "<15%", color: "#1e3a5f" },
                    { label: "15-20%", color: "#1d4ed8" },
                    { label: "20-25%", color: "#2563eb" },
                    { label: "25-30%", color: "#7c3aed" },
                    { label: "30-35%", color: "#db2777" },
                    { label: "35-45%", color: "#ef4444" },
                    { label: ">45%", color: "#991b1b" },
                  ].map(l => (
                    <span key={l.label} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                      <span style={{ width: 12, height: 12, borderRadius: 2, background: l.color, display: "inline-block" }} />
                      <span style={{ fontSize: 10, color: "#64748b" }}>{l.label}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* TERM STRUCTURE */}
            {tab === "term" && (
              <div style={{ background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: 8, padding: 20 }}>
                <div style={{ fontSize: 12, color: "#64748b", marginBottom: 16, textTransform: "uppercase", letterSpacing: 1 }}>ATM Vol Term Structure</div>
                <div style={{ display: "flex", gap: 12, alignItems: "flex-end", height: 200, padding: "0 0 16px" }}>
                  {Object.entries(data.term_structure).map(([expiry, vol]) => {
                    const h = (vol / 50) * 160;
                    return (
                      <div key={expiry} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                        <div style={{ fontSize: 12, fontWeight: 700, color: "#8b5cf6" }}>{vol.toFixed(1)}%</div>
                        <div style={{ width: "100%", height: h, background: "linear-gradient(to top, #7c3aed, #8b5cf6)", borderRadius: "4px 4px 0 0", minHeight: 20 }} />
                        <div style={{ fontSize: 10, color: "#64748b", textAlign: "center" }}>{expiry}</div>
                      </div>
                    );
                  })}
                </div>
                <div style={{ padding: 12, background: "#0f0f1e", borderRadius: 6, fontSize: 12, color: "#94a3b8" }}>
                  {Object.values(data.term_structure)[0] > Object.values(data.term_structure).slice(-1)[0]
                    ? "⬇ Backwardation — near-term vol elevated (event risk / earnings / uncertainty)"
                    : "⬆ Contango — vol term structure normal (longer-dated options costlier)"}
                </div>
              </div>
            )}

            {/* SKEW */}
            {tab === "skew" && (
              <div style={{ background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: 8, padding: 20 }}>
                <div style={{ fontSize: 12, color: "#64748b", marginBottom: 16, textTransform: "uppercase", letterSpacing: 1 }}>Volatility Skew (Near-Term)</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
                  <div style={{ padding: 16, background: "#0f1a2e", borderRadius: 8 }}>
                    <div style={{ fontSize: 11, color: "#64748b", marginBottom: 4 }}>25Δ Risk Reversal</div>
                    <div style={{ fontSize: 32, fontWeight: 700, color: "#f59e0b" }}>
                      {data.skew.rr_25d_pct > 0 ? "+" : ""}{data.skew.rr_25d_pct.toFixed(2)}%
                    </div>
                    <div style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}>
                      {data.skew.rr_25d_pct > 0 ? "Put premium — OTM puts costlier than OTM calls (typical for equities)" : "Call premium — OTM calls costlier (unusual, bullish skew)"}
                    </div>
                  </div>
                  <div style={{ padding: 16, background: "#1a0f2e", borderRadius: 8 }}>
                    <div style={{ fontSize: 11, color: "#64748b", marginBottom: 4 }}>25Δ Butterfly</div>
                    <div style={{ fontSize: 32, fontWeight: 700, color: "#8b5cf6" }}>
                      {data.skew.butterfly_25d_pct.toFixed(2)}%
                    </div>
                    <div style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}>Smile curvature — wings premium over ATM</div>
                  </div>
                </div>

                {/* Smile visualization across moneyness */}
                <div style={{ fontSize: 12, color: "#64748b", marginBottom: 8 }}>Near-term IV Smile</div>
                <div style={{ display: "flex", gap: 0, alignItems: "flex-end", height: 100, padding: "0 8px" }}>
                  {data.moneyness_labels.map((m, i) => {
                    const v = data.surface["Near (1M)"]?.[m] ?? 0;
                    const atm = data.surface["Near (1M)"]?.["100%"] ?? data.atm_iv_pct;
                    const h = Math.max(10, (v / (atm * 1.5)) * 80);
                    return (
                      <div key={m} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center" }}>
                        <div style={{ fontSize: 9, color: "#64748b", marginBottom: 2 }}>{v.toFixed(0)}</div>
                        <div style={{
                          width: "80%", height: h,
                          background: m === "100%" ? "#8b5cf6" : m < "100%" ? "#ef4444aa" : "#3b82f6aa",
                          borderRadius: "2px 2px 0 0"
                        }} />
                        <div style={{ fontSize: 8, color: "#374151", marginTop: 2 }}>{m}</div>
                      </div>
                    );
                  })}
                </div>
                <div style={{ marginTop: 12, padding: 12, background: "#111", borderRadius: 6, fontSize: 12, color: "#94a3b8" }}>
                  {data.skew.note}
                </div>
              </div>
            )}
          </>
        )}

        {loading && (
          <div style={{ textAlign: "center", padding: 60, color: "#64748b", fontSize: 14 }}>
            Computing volatility surface...
          </div>
        )}
      </div>
    </div>
  );
}
