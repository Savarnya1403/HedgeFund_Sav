'use client';

import { useState, useEffect, useCallback } from "react";
import IndexBar from "@/components/IndexBar";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

// ── Types ────────────────────────────────────────────────────────────────────

interface FiiDiiDay {
  date: string;
  fii_buy: number;
  fii_sell: number;
  fii_net: number;
  dii_buy: number;
  dii_sell: number;
  dii_net: number;
}

interface PeriodStats {
  fii_net: number;
  dii_net: number;
}

interface FiiDiiStats {
  "5d": PeriodStats;
  "10d": PeriodStats;
  "20d": PeriodStats;
  fii_sentiment: string;
  latest_date: string;
}

interface FiiDiiResponse {
  daily: FiiDiiDay[];
  stats: FiiDiiStats;
}

interface BulkDeal {
  date: string;
  symbol: string;
  company: string;
  client: string;
  transaction: string;
  quantity: number;
  price: number;
  exchange: string;
}

interface BulkDealsResponse {
  deals: BulkDeal[];
  total: number;
}

interface BlockDeal {
  date: string;
  time: string;
  symbol: string;
  company: string;
  client: string;
  transaction: string;
  quantity: number;
  price: number;
  value_cr: number;
}

interface BlockDealsResponse {
  deals: BlockDeal[];
  total: number;
}

interface SectorFlow {
  sector: string;
  ret_3m: number;
  ret_1m: number | null;
  momentum: string;
  signal: string;
  signal_color: string;
}

interface SectorFlowResponse {
  sectors: SectorFlow[];
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtCr(val: number): string {
  const abs = Math.abs(val);
  const formatted = abs >= 10000
    ? (abs / 1000).toFixed(1) + "K"
    : abs.toLocaleString("en-IN", { maximumFractionDigits: 0 });
  return `₹${formatted} Cr`;
}

function fmtSign(val: number): string {
  return val >= 0 ? "+" : "−";
}

function fmtDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
  } catch {
    return iso;
  }
}

function sentimentColor(s: string): string {
  const u = s?.toUpperCase();
  if (u === "BULLISH") return "#00d084";
  if (u === "BEARISH") return "#ff3b3b";
  return "#f59e0b";
}

function sectorBg(ret3m: number): string {
  if (ret3m >= 15) return "#0a2e1a";
  if (ret3m >= 8) return "#0d2216";
  if (ret3m >= 3) return "#112b1a";
  if (ret3m >= 0) return "#151f16";
  if (ret3m >= -3) return "#1f1515";
  if (ret3m >= -8) return "#2b1212";
  if (ret3m >= -15) return "#2e0f0f";
  return "#380a0a";
}

function sectorBorder(ret3m: number): string {
  if (ret3m >= 3) return "#00d08433";
  if (ret3m >= 0) return "#00d08418";
  if (ret3m >= -3) return "#ff3b3b18";
  return "#ff3b3b33";
}

function retColor(ret: number): string {
  if (ret >= 5) return "#00d084";
  if (ret >= 0) return "#4ade80";
  if (ret >= -5) return "#f87171";
  return "#ff3b3b";
}

// ── Bar Chart ─────────────────────────────────────────────────────────────────

function FlowBarChart({ daily }: { daily: FiiDiiDay[] }) {
  const last20 = [...daily].slice(-20);
  if (last20.length === 0) return null;

  const allVals = last20.flatMap(d => [d.fii_net, d.dii_net]);
  const maxAbs = Math.max(1, ...allVals.map(Math.abs));

  const chartH = 160;
  const barW = 10;
  const gap = 3;
  const groupW = barW * 2 + gap + 4;
  const totalW = last20.length * groupW;
  const midY = chartH / 2;

  return (
    <div style={{ overflowX: "auto" }}>
      <svg width={Math.max(totalW, 100)} height={chartH + 32} style={{ display: "block" }}>
        {/* Zero line */}
        <line x1={0} y1={midY} x2={Math.max(totalW, 100)} y2={midY}
          stroke="#2a2a2a" strokeWidth={1} />

        {last20.map((d, i) => {
          const x = i * groupW;
          const fiiH = Math.abs((d.fii_net / maxAbs) * (midY - 4));
          const diiH = Math.abs((d.dii_net / maxAbs) * (midY - 4));
          const fiiY = d.fii_net >= 0 ? midY - fiiH : midY;
          const diiY = d.dii_net >= 0 ? midY - diiH : midY;
          const fiiColor = d.fii_net >= 0 ? "#00d084" : "#ff3b3b";
          const diiColor = d.dii_net >= 0 ? "#3b82f6" : "#f59e0b";

          return (
            <g key={`${d.date}-${i}`}>
              <rect x={x} y={fiiY} width={barW} height={Math.max(1, fiiH)}
                fill={fiiColor} opacity={0.85} rx={1} />
              <rect x={x + barW + gap} y={diiY} width={barW} height={Math.max(1, diiH)}
                fill={diiColor} opacity={0.85} rx={1} />
              {i % 4 === 0 && (
                <text x={x + barW} y={chartH + 14}
                  fontSize={8} fill="#444" textAnchor="middle"
                  fontFamily="monospace">
                  {fmtDate(d.date)}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Legend */}
      <div style={{ display: "flex", gap: 16, marginTop: 4 }}>
        {[
          { color: "#00d084", label: "FII +" },
          { color: "#ff3b3b", label: "FII −" },
          { color: "#3b82f6", label: "DII +" },
          { color: "#f59e0b", label: "DII −" },
        ].map(l => (
          <div key={l.label} style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <div style={{ width: 8, height: 8, background: l.color, borderRadius: 1 }} />
            <span style={{ fontSize: 9, color: "#555", fontFamily: "monospace" }}>{l.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Section Header ─────────────────────────────────────────────────────────────

function SectionHeader({ title }: { title: string }) {
  return (
    <div style={{
      fontSize: 9, color: "#444", textTransform: "uppercase",
      letterSpacing: "0.08em", fontFamily: "monospace",
      paddingBottom: 6, marginBottom: 10,
      borderBottom: "1px solid #141414",
    }}>
      {title}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function InstitutionalPage() {
  const [fiiDiiData, setFiiDiiData] = useState<FiiDiiResponse | null>(null);
  const [bulkDeals, setBulkDeals] = useState<BulkDeal[]>([]);
  const [blockDeals, setBlockDeals] = useState<BlockDeal[]>([]);
  const [sectorFlows, setSectorFlows] = useState<SectorFlow[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    setError(null);
    try {
      const [fiiRes, bulkRes, blockRes, sectorRes] = await Promise.allSettled([
        fetch(`${API_BASE}/api/fii-dii/daily`).then(r => r.json()) as Promise<FiiDiiResponse>,
        fetch(`${API_BASE}/api/bulk-deals`).then(r => r.json()) as Promise<BulkDealsResponse>,
        fetch(`${API_BASE}/api/block-deals`).then(r => r.json()) as Promise<BlockDealsResponse>,
        fetch(`${API_BASE}/api/fii-sector-flow`).then(r => r.json()) as Promise<SectorFlowResponse>,
      ]);

      if (fiiRes.status === "fulfilled") setFiiDiiData(fiiRes.value);
      if (bulkRes.status === "fulfilled") setBulkDeals(bulkRes.value.deals || []);
      if (blockRes.status === "fulfilled") setBlockDeals(blockRes.value.deals || []);
      if (sectorRes.status === "fulfilled") setSectorFlows(sectorRes.value.sectors || []);

      setLastRefresh(new Date());
    } catch (e) {
      setError("Failed to load institutional data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 60_000);
    return () => clearInterval(id);
  }, [fetchAll]);

  const stats = fiiDiiData?.stats;
  const daily = fiiDiiData?.daily || [];

  const sortedBulk = [...bulkDeals].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 20);
  const sortedBlock = [...blockDeals].sort((a, b) => {
    const dc = b.date.localeCompare(a.date);
    if (dc !== 0) return dc;
    return (b.time || "").localeCompare(a.time || "");
  }).slice(0, 20);

  return (
    <div style={{
      display: "flex", flexDirection: "column", height: "100vh",
      overflow: "hidden", background: "#000", fontFamily: "monospace",
    }}>
      <IndexBar />

      <div style={{ flex: 1, overflow: "auto", background: "#000" }}>
        <div style={{ maxWidth: 1440, margin: "0 auto", padding: "12px 16px" }}>

          {/* Page Header */}
          <div style={{
            display: "flex", alignItems: "center", gap: 12,
            marginBottom: 14, borderBottom: "1px solid #141414", paddingBottom: 10,
          }}>
            <div>
              <span style={{
                fontSize: 14, fontWeight: 700, color: "#e5e5e5",
                letterSpacing: "0.06em", fontFamily: "monospace",
              }}>
                INSTITUTIONAL INTELLIGENCE
              </span>
              {stats?.latest_date && (
                <span style={{ fontSize: 10, color: "#555", marginLeft: 12 }}>
                  Latest: {fmtDate(stats.latest_date)}
                </span>
              )}
            </div>
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{
                display: "flex", alignItems: "center", gap: 5,
                background: "#0d1f0d", border: "1px solid #00d08433",
                borderRadius: 4, padding: "3px 8px",
              }}>
                <div style={{
                  width: 6, height: 6, borderRadius: "50%",
                  background: "#00d084", animation: "pulse 2s infinite",
                }} />
                <span style={{ fontSize: 9, color: "#00d084", letterSpacing: "0.05em" }}>
                  AUTO-REFRESH 60s
                </span>
              </div>
              <span style={{ fontSize: 9, color: "#333" }}>
                {lastRefresh.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
              </span>
            </div>
          </div>

          {error && (
            <div style={{
              background: "#1a0a0a", border: "1px solid #ff3b3b44",
              borderRadius: 6, padding: "8px 14px", marginBottom: 12,
              fontSize: 11, color: "#ff3b3b",
            }}>
              {error}
            </div>
          )}

          {/* Main grid: left column | right column */}
          <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 12 }}>

            {/* ── LEFT COLUMN ── */}
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

              {/* FII/DII FLOW Summary */}
              <div style={{
                background: "#0a0a0a", border: "1px solid #141414",
                borderRadius: 8, padding: "12px 14px",
              }}>
                <SectionHeader title="FII / DII FLOW" />

                {loading ? (
                  <div style={{ color: "#333", fontSize: 11 }}>Loading…</div>
                ) : stats && stats["5d"] ? (
                  <>
                    {/* Period stat cards */}
                    {(["5d", "10d", "20d"] as const).map(period => {
                      const ps = stats[period];
                      return (
                        <div key={period} style={{
                          background: "#0f0f0f", border: "1px solid #1a1a1a",
                          borderRadius: 6, padding: "10px 12px", marginBottom: 8,
                        }}>
                          <div style={{ fontSize: 9, color: "#444", textTransform: "uppercase", marginBottom: 6 }}>
                            {period.toUpperCase()} CUMULATIVE
                          </div>
                          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                            <div>
                              <div style={{ fontSize: 9, color: "#555", marginBottom: 2 }}>FII NET</div>
                              <div style={{
                                fontSize: 15, fontWeight: 700,
                                color: ps.fii_net >= 0 ? "#00d084" : "#ff3b3b",
                              }}>
                                {fmtSign(ps.fii_net)}{fmtCr(ps.fii_net)}
                              </div>
                            </div>
                            <div>
                              <div style={{ fontSize: 9, color: "#555", marginBottom: 2 }}>DII NET</div>
                              <div style={{
                                fontSize: 15, fontWeight: 700,
                                color: ps.dii_net >= 0 ? "#3b82f6" : "#f59e0b",
                              }}>
                                {fmtSign(ps.dii_net)}{fmtCr(ps.dii_net)}
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}

                    {/* Sentiment badge */}
                    <div style={{
                      marginTop: 4, textAlign: "center",
                      background: "#0c0c0c", border: `1px solid ${sentimentColor(stats.fii_sentiment)}33`,
                      borderRadius: 6, padding: "10px 0",
                    }}>
                      <div style={{ fontSize: 9, color: "#444", marginBottom: 4 }}>FII SENTIMENT</div>
                      <div style={{
                        fontSize: 22, fontWeight: 800, letterSpacing: "0.1em",
                        color: sentimentColor(stats.fii_sentiment),
                      }}>
                        {stats.fii_sentiment?.toUpperCase() || "—"}
                      </div>
                    </div>
                  </>
                ) : (
                  <div style={{ color: "#555", fontSize: 11 }}>No data</div>
                )}
              </div>

              {/* FII/DII Bar Chart */}
              <div style={{
                background: "#0a0a0a", border: "1px solid #141414",
                borderRadius: 8, padding: "12px 14px", flex: 1,
              }}>
                <SectionHeader title="DAILY NET FLOW — LAST 20 DAYS" />
                {loading ? (
                  <div style={{ color: "#333", fontSize: 11 }}>Loading…</div>
                ) : daily.length > 0 ? (
                  <FlowBarChart daily={daily} />
                ) : (
                  <div style={{ color: "#555", fontSize: 11 }}>No chart data</div>
                )}
              </div>
            </div>

            {/* ── RIGHT COLUMN ── */}
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

              {/* FII Sector Flow Heatmap */}
              <div style={{
                background: "#0a0a0a", border: "1px solid #141414",
                borderRadius: 8, padding: "12px 14px",
              }}>
                <SectionHeader title="FII SECTOR FLOW HEATMAP" />
                {loading ? (
                  <div style={{
                    display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6,
                  }}>
                    {Array.from({ length: 8 }).map((_, i) => (
                      <div key={i} style={{
                        height: 72, background: "#111", borderRadius: 6, opacity: 0.5,
                      }} />
                    ))}
                  </div>
                ) : sectorFlows.length > 0 ? (
                  <div style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
                    gap: 6,
                  }}>
                    {sectorFlows.map(s => (
                      <div key={s.sector} style={{
                        background: sectorBg(s.ret_3m),
                        border: `1px solid ${sectorBorder(s.ret_3m)}`,
                        borderRadius: 6, padding: "10px 12px",
                      }}>
                        <div style={{
                          fontSize: 10, fontWeight: 600, color: "#ccc",
                          marginBottom: 4, textTransform: "uppercase",
                          letterSpacing: "0.03em",
                        }}>
                          {s.sector}
                        </div>
                        <div style={{
                          fontSize: 18, fontWeight: 700,
                          color: retColor(s.ret_3m),
                          lineHeight: 1,
                        }}>
                          {s.ret_3m != null ? `${s.ret_3m >= 0 ? "+" : ""}${s.ret_3m.toFixed(1)}%` : "—"}
                        </div>
                        <div style={{ fontSize: 9, color: "#555", marginTop: 2 }}>3M return</div>
                        <div style={{
                          marginTop: 6, display: "flex", justifyContent: "space-between",
                          alignItems: "center",
                        }}>
                          <span style={{
                            fontSize: 9, color: "#666",
                          }}>
                            1M: <span style={{ color: s.ret_1m != null ? retColor(s.ret_1m) : "#555" }}>
                              {s.ret_1m != null ? `${s.ret_1m >= 0 ? "+" : ""}${s.ret_1m.toFixed(1)}%` : "—"}
                            </span>
                          </span>
                          <span style={{
                            fontSize: 8, color: s.signal_color || "#888",
                            background: "#0a0a0a", borderRadius: 3, padding: "1px 5px",
                            border: `1px solid ${s.signal_color || "#444"}33`,
                          }}>
                            {s.momentum}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ color: "#555", fontSize: 11 }}>No sector flow data</div>
                )}
              </div>

              {/* Bulk Deals */}
              <div style={{
                background: "#0a0a0a", border: "1px solid #141414",
                borderRadius: 8, padding: "12px 14px",
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                  <SectionHeader title={`BULK DEALS (${bulkDeals.length})`} />
                </div>
                {loading ? (
                  <div style={{ color: "#333", fontSize: 11 }}>Loading…</div>
                ) : sortedBulk.length > 0 ? (
                  <div style={{ overflowX: "auto" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
                      <thead>
                        <tr style={{ borderBottom: "1px solid #1a1a1a" }}>
                          {["Date", "Symbol", "Client", "Type", "Qty (L)", "Price"].map(h => (
                            <th key={h} style={{
                              padding: "4px 8px", fontSize: 9, color: "#444",
                              textAlign: h === "Date" || h === "Symbol" || h === "Client" || h === "Type" ? "left" : "right",
                              textTransform: "uppercase", letterSpacing: "0.05em",
                              fontFamily: "monospace", fontWeight: 400,
                            }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {sortedBulk.map((d, i) => {
                          const isBuy = d.transaction?.toUpperCase().includes("BUY");
                          return (
                            <tr key={i}
                              style={{ borderBottom: "1px solid #0f0f0f", cursor: "default" }}
                              onMouseEnter={e => (e.currentTarget.style.background = "#111")}
                              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                            >
                              <td style={{ padding: "5px 8px", color: "#555" }}>{fmtDate(d.date)}</td>
                              <td style={{ padding: "5px 8px", color: "#e5e5e5", fontWeight: 600 }}>{d.symbol}</td>
                              <td style={{
                                padding: "5px 8px", color: "#888",
                                maxWidth: 160, overflow: "hidden",
                                textOverflow: "ellipsis", whiteSpace: "nowrap",
                              }}>
                                {d.client}
                              </td>
                              <td style={{ padding: "5px 8px", color: isBuy ? "#00d084" : "#ff3b3b", fontWeight: 600 }}>
                                {isBuy ? "BUY" : "SELL"}
                              </td>
                              <td style={{ padding: "5px 8px", textAlign: "right", color: "#aaa" }}>
                                {(d.quantity / 100000).toFixed(2)}
                              </td>
                              <td style={{ padding: "5px 8px", textAlign: "right", color: "#ccc" }}>
                                ₹{d.price?.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div style={{ color: "#555", fontSize: 11 }}>No bulk deal data</div>
                )}
              </div>

              {/* Block Deals */}
              <div style={{
                background: "#0a0a0a", border: "1px solid #141414",
                borderRadius: 8, padding: "12px 14px",
              }}>
                <SectionHeader title={`BLOCK DEALS (${blockDeals.length})`} />
                {loading ? (
                  <div style={{ color: "#333", fontSize: 11 }}>Loading…</div>
                ) : sortedBlock.length > 0 ? (
                  <div style={{ overflowX: "auto" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
                      <thead>
                        <tr style={{ borderBottom: "1px solid #1a1a1a" }}>
                          {["Date", "Time", "Symbol", "Client", "Type", "Value (Cr)"].map(h => (
                            <th key={h} style={{
                              padding: "4px 8px", fontSize: 9, color: "#444",
                              textAlign: h === "Date" || h === "Time" || h === "Symbol" || h === "Client" || h === "Type" ? "left" : "right",
                              textTransform: "uppercase", letterSpacing: "0.05em",
                              fontFamily: "monospace", fontWeight: 400,
                            }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {sortedBlock.map((d, i) => {
                          const isBuy = d.transaction?.toUpperCase().includes("BUY");
                          return (
                            <tr key={i}
                              style={{ borderBottom: "1px solid #0f0f0f" }}
                              onMouseEnter={e => (e.currentTarget.style.background = "#111")}
                              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                            >
                              <td style={{ padding: "5px 8px", color: "#555" }}>{fmtDate(d.date)}</td>
                              <td style={{ padding: "5px 8px", color: "#444" }}>{d.time || "—"}</td>
                              <td style={{ padding: "5px 8px", color: "#e5e5e5", fontWeight: 600 }}>{d.symbol}</td>
                              <td style={{
                                padding: "5px 8px", color: "#888",
                                maxWidth: 150, overflow: "hidden",
                                textOverflow: "ellipsis", whiteSpace: "nowrap",
                              }}>
                                {d.client}
                              </td>
                              <td style={{ padding: "5px 8px", color: isBuy ? "#00d084" : "#ff3b3b", fontWeight: 600 }}>
                                {isBuy ? "BUY" : "SELL"}
                              </td>
                              <td style={{
                                padding: "5px 8px", textAlign: "right",
                                color: d.value_cr >= 100 ? "#f59e0b" : "#aaa",
                                fontWeight: d.value_cr >= 100 ? 600 : 400,
                              }}>
                                ₹{d.value_cr?.toLocaleString("en-IN", { maximumFractionDigits: 1 })} Cr
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div style={{ color: "#555", fontSize: 11 }}>No block deal data</div>
                )}
              </div>

            </div>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  );
}
