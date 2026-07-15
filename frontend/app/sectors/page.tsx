'use client';

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import IndexBar from "@/components/IndexBar";
import { api, fmt, changeClass, changeSign, type SectorData, type BreadthData } from "@/lib/api";

function heatColor(pct: number): string {
  if (pct >= 2) return "#166534";
  if (pct >= 1) return "#14532d";
  if (pct >= 0.3) return "#15803d";
  if (pct > 0) return "#1e3a2d";
  if (pct >= -0.3) return "#3a1e1e";
  if (pct >= -1) return "#7f1d1d";
  if (pct >= -2) return "#991b1b";
  return "#b91c1c";
}

function borderColor(pct: number): string {
  if (pct >= 1) return "#22c55e44";
  if (pct > 0) return "#22c55e22";
  if (pct >= -1) return "#ef444422";
  return "#ef444444";
}

export default function SectorsPage() {
  const router = useRouter();
  const [sectors, setSectors] = useState<SectorData[]>([]);
  const [breadth, setBreadth] = useState<BreadthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedSector, setSelectedSector] = useState<string | null>(null);
  const [view, setView] = useState<"heatmap" | "table">("heatmap");

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.sectors().then(r => setSectors(r.sectors || [])),
      api.breadth().then(setBreadth).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  const selectedData = sectors.find(s => s.sector === selectedSector);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden" }}>
      <IndexBar />
      <div style={{ flex: 1, overflow: "auto", background: "#080808" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", padding: "16px 20px" }}>
          {/* Header */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
            <button onClick={() => router.push("/")} style={{ background: "none", border: "none", color: "#555", cursor: "pointer", fontSize: 16 }}>←</button>
            <div>
              <h1 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "#e5e5e5" }}>Sector Heatmap</h1>
              <div style={{ fontSize: 11, color: "#555" }}>Nifty 100 + PSU sector performance</div>
            </div>
            <div style={{ marginLeft: "auto", display: "flex", gap: 4 }}>
              {(["heatmap", "table"] as const).map(v => (
                <button key={v} onClick={() => setView(v)} style={{
                  padding: "4px 12px", fontSize: 11, border: "none", borderRadius: 6, cursor: "pointer",
                  background: view === v ? "#3b82f6" : "#1a1a1a",
                  color: view === v ? "#fff" : "#555",
                  textTransform: "capitalize",
                }}>{v}</button>
              ))}
            </div>
          </div>

          {/* Market Breadth bar */}
          {breadth && breadth.adr != null && (
            <div style={{
              background: "#111", border: "1px solid #1e1e1e", borderRadius: 8,
              padding: "12px 16px", marginBottom: 16,
              display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 16,
            }}>
              {[
                { label: "A/D Ratio", value: breadth.adr.toFixed(2), color: breadth.breadth_color },
                { label: "Above 50DMA", value: breadth.pct_above_50dma + "%", color: (breadth.pct_above_50dma ?? 0) > 50 ? "#22c55e" : "#ef4444" },
                { label: "Above 200DMA", value: breadth.pct_above_200dma + "%", color: (breadth.pct_above_200dma ?? 0) > 50 ? "#22c55e" : "#ef4444" },
                { label: "Median RSI", value: breadth.median_rsi.toFixed(1), color: breadth.median_rsi > 60 ? "#f59e0b" : breadth.median_rsi < 40 ? "#22c55e" : "#888" },
                { label: "52W Highs", value: (breadth.near_52w_high ?? 0).toString(), color: "#22c55e" },
                { label: "52W Lows", value: (breadth.near_52w_low ?? 0).toString(), color: "#ef4444" },
              ].map(s => (
                <div key={s.label} style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 16, fontWeight: 700, color: s.color, fontFamily: "monospace" }}>{s.value}</div>
                  <div style={{ fontSize: 10, color: "#555", marginTop: 2 }}>{s.label}</div>
                </div>
              ))}
            </div>
          )}

          {loading ? (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
              {Array.from({ length: 12 }).map((_, i) => (
                <div key={i} className="skeleton" style={{ height: 100, borderRadius: 8 }} />
              ))}
            </div>
          ) : view === "heatmap" ? (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 8 }}>
              {sectors.map(s => (
                <div
                  key={s.sector}
                  onClick={() => setSelectedSector(selectedSector === s.sector ? null : s.sector)}
                  style={{
                    background: heatColor(s.avg_change_pct),
                    border: `1px solid ${borderColor(s.avg_change_pct)}`,
                    borderRadius: 8, padding: "14px 16px",
                    cursor: "pointer",
                    outline: selectedSector === s.sector ? `2px solid ${s.avg_change_pct > 0 ? "#22c55e" : "#ef4444"}` : "none",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: "#e5e5e5" }}>{s.sector}</span>
                    <span className={`num ${changeClass(s.avg_change_pct)}`} style={{ fontSize: 14, fontWeight: 700 }}>
                      {changeSign(s.avg_change_pct)}{fmt(Math.abs(s.avg_change_pct))}%
                    </span>
                  </div>
                  <div style={{ fontSize: 10, color: "#888" }}>
                    {s.advances}↑ {s.declines}↓ · {s.stock_count} stocks
                  </div>
                  {/* Mini bar showing advance/decline */}
                  <div style={{ height: 3, background: "#00000040", borderRadius: 2, overflow: "hidden", marginTop: 6 }}>
                    <div style={{
                      width: `${s.stock_count > 0 ? (s.advances / s.stock_count) * 100 : 50}%`,
                      height: "100%", background: "#22c55e88", borderRadius: 2,
                    }} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ background: "#111", border: "1px solid #1e1e1e", borderRadius: 8, overflow: "hidden" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #1e1e1e" }}>
                    {["Sector", "Avg Change", "Advances", "Declines", "Top Gainer", "Top Loser"].map(h => (
                      <th key={h} style={{ padding: "8px 14px", fontSize: 10, color: "#444", textAlign: h === "Sector" ? "left" : "right", textTransform: "uppercase", letterSpacing: "0.04em" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sectors.map(s => {
                    const top = s.stocks[0];
                    const bottom = s.stocks[s.stocks.length - 1];
                    return (
                      <tr key={s.sector} style={{ borderBottom: "1px solid #1a1a1a", cursor: "pointer" }}
                        onMouseEnter={e => (e.currentTarget.style.background = "#141414")}
                        onMouseLeave={e => (e.currentTarget.style.background = "transparent")}>
                        <td style={{ padding: "8px 14px", fontSize: 12, fontWeight: 600, color: "#e5e5e5" }}>{s.sector}</td>
                        <td style={{ padding: "8px 14px", textAlign: "right" }}>
                          <span className={`num ${changeClass(s.avg_change_pct)}`} style={{ fontSize: 13, fontWeight: 700 }}>
                            {changeSign(s.avg_change_pct)}{fmt(Math.abs(s.avg_change_pct))}%
                          </span>
                        </td>
                        <td className="num" style={{ padding: "8px 14px", textAlign: "right", color: "#22c55e", fontSize: 12 }}>{s.advances}</td>
                        <td className="num" style={{ padding: "8px 14px", textAlign: "right", color: "#ef4444", fontSize: 12 }}>{s.declines}</td>
                        <td style={{ padding: "8px 14px", textAlign: "right" }}>
                          {top && <span className="num" style={{ fontSize: 11 }}>
                            <span style={{ color: "#555", marginRight: 4 }}>{top.symbol}</span>
                            <span style={{ color: "#22c55e" }}>+{fmt(top.change_pct)}%</span>
                          </span>}
                        </td>
                        <td style={{ padding: "8px 14px", textAlign: "right" }}>
                          {bottom && <span className="num" style={{ fontSize: 11 }}>
                            <span style={{ color: "#555", marginRight: 4 }}>{bottom.symbol}</span>
                            <span style={{ color: "#ef4444" }}>{fmt(bottom.change_pct)}%</span>
                          </span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Selected sector drill-down */}
          {selectedData && (
            <div style={{ background: "#111", border: "1px solid #1e1e1e", borderRadius: 8, padding: 16, marginTop: 16 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#e5e5e5", marginBottom: 12 }}>
                {selectedData.sector} — {selectedData.stock_count} Stocks
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 6 }}>
                {selectedData.stocks.map(s => (
                  <div
                    key={s.symbol}
                    onClick={() => router.push(`/stock/${s.symbol}`)}
                    style={{
                      background: "#161616", borderRadius: 6, padding: "8px 10px",
                      cursor: "pointer", border: "1px solid #1e1e1e",
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = "#1e1e1e")}
                    onMouseLeave={e => (e.currentTarget.style.background = "#161616")}
                  >
                    <div style={{ fontSize: 11, fontWeight: 600, color: "#e5e5e5" }}>{s.symbol}</div>
                    <div style={{ display: "flex", justifyContent: "space-between", marginTop: 3 }}>
                      <span className="num" style={{ fontSize: 10, color: "#888" }}>₹{fmt(s.price)}</span>
                      <span className={`num ${changeClass(s.change_pct)}`} style={{ fontSize: 10 }}>
                        {changeSign(s.change_pct)}{fmt(Math.abs(s.change_pct))}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
