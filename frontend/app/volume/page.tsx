'use client';

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import IndexBar from "@/components/IndexBar";

type SortKey = "dev_20d" | "dev_3m" | "dev_1y" | "change_pct_asc" | "change_pct_desc";

interface VolumeRow {
  symbol: string;
  price: number;
  change_pct: number;
  today_vol: number;
  avg_20d: number;
  avg_3m: number;
  avg_6m: number;
  avg_1y: number;
  avg_all: number;
  dev_20d: number;
  dev_3m: number;
  dev_6m: number;
  dev_1y: number;
  dev_all: number;
}

interface ApiResponse {
  data: VolumeRow[];
  computed_at: string;
}

function fmtVol(v: number): string {
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + "M";
  if (v >= 1_000) return (v / 1_000).toFixed(0) + "K";
  return String(v);
}

function fmtDev(v: number): string {
  return (v >= 0 ? "+" : "") + v.toFixed(1) + "%";
}

function devColor(v: number): string {
  if (v > 50) return "#00d084";
  if (v > 20) return "#22a56a";
  if (v >= -10) return "#555";
  if (v >= -30) return "#c97a00";
  return "#ff3b3b";
}

function devBg(v: number): string {
  if (v > 50) return "rgba(0,208,132,0.08)";
  if (v > 20) return "rgba(34,165,106,0.06)";
  if (v >= -10) return "transparent";
  if (v >= -30) return "rgba(201,122,0,0.07)";
  return "rgba(255,59,59,0.08)";
}

function HeatBar({ value }: { value: number }) {
  const clamped = Math.max(-100, Math.min(100, value));
  const width = Math.abs(clamped) / 100;
  const color = devColor(value);
  return (
    <div style={{ position: "relative", width: 36, height: 3, background: "#1a1a1a", borderRadius: 2, overflow: "hidden" }}>
      <div style={{
        position: "absolute",
        top: 0,
        left: clamped >= 0 ? "50%" : `${50 - width * 50}%`,
        width: `${width * 50}%`,
        height: "100%",
        background: color,
        borderRadius: 2,
      }} />
      {clamped < 0 && (
        <div style={{
          position: "absolute",
          top: 0,
          left: `${50 - Math.abs(clamped) / 2}%`,
          width: `${Math.abs(clamped) / 2}%`,
          height: "100%",
          background: color,
          borderRadius: 2,
        }} />
      )}
    </div>
  );
}

function DevCell({ value }: { value: number }) {
  return (
    <td style={{
      padding: "5px 8px",
      textAlign: "right",
      background: devBg(value),
      verticalAlign: "middle",
    }}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2 }}>
        <span style={{
          fontFamily: "'Geist Mono', monospace",
          fontSize: 11,
          fontWeight: 600,
          color: devColor(value),
          letterSpacing: "-0.02em",
        }}>
          {fmtDev(value)}
        </span>
        <HeatBar value={value} />
      </div>
    </td>
  );
}

const thStyle: React.CSSProperties = {
  padding: "6px 8px",
  fontSize: 8,
  fontWeight: 700,
  letterSpacing: "0.1em",
  textTransform: "uppercase",
  color: "#333",
  background: "#0a0a0a",
  borderBottom: "1px solid #1a1a1a",
  whiteSpace: "nowrap",
  position: "sticky",
  top: 0,
  zIndex: 10,
};

export default function VolumePage() {
  const router = useRouter();
  const [data, setData] = useState<VolumeRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [computedAt, setComputedAt] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("dev_20d");
  const [sortDesc, setSortDesc] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const res = await fetch("http://localhost:8001/api/volume-scan");
      if (!res.ok) throw new Error("Network error");
      const json: ApiResponse = await res.json();
      setData(json.data || []);
      setComputedAt(json.computed_at || "");
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 180000);
    return () => clearInterval(interval);
  }, [load]);

  function handleSortClick(key: SortKey) {
    if (sortKey === key) {
      setSortDesc(d => !d);
    } else {
      setSortKey(key);
      setSortDesc(true);
    }
  }

  const sorted = [...data].sort((a, b) => {
    let av: number, bv: number;
    if (sortKey === "change_pct_asc" || sortKey === "change_pct_desc") {
      av = a.change_pct;
      bv = b.change_pct;
      return sortKey === "change_pct_desc" ? bv - av : av - bv;
    }
    av = Math.abs(a[sortKey]);
    bv = Math.abs(b[sortKey]);
    return sortDesc ? bv - av : av - bv;
  });

  const SortBtn = ({ label, sk }: { label: string; sk: SortKey }) => {
    const active = sortKey === sk;
    return (
      <button
        onClick={() => handleSortClick(sk)}
        style={{
          fontFamily: "'Geist Mono', monospace",
          fontSize: 9,
          fontWeight: 700,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          padding: "3px 10px",
          background: active ? "#1a1a1a" : "transparent",
          color: active ? "#e5e5e5" : "#444",
          border: active ? "1px solid #2e2e2e" : "1px solid #1a1a1a",
          borderRadius: 3,
          cursor: "pointer",
        }}
        onMouseEnter={e => { if (!active) e.currentTarget.style.color = "#888"; }}
        onMouseLeave={e => { if (!active) e.currentTarget.style.color = "#444"; }}
      >
        {label}{active ? (sortDesc ? " ↓" : " ↑") : ""}
      </button>
    );
  };

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      height: "100vh",
      overflow: "hidden",
      background: "#050505",
      fontFamily: "'Geist Mono', monospace",
    }}>
      <IndexBar />

      <div style={{ flex: 1, overflow: "auto" }}>
        <div style={{ padding: "10px 14px 0" }}>
          <div style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: "1px solid #141414",
            paddingBottom: 8,
            marginBottom: 8,
          }}>
            <div>
              <div style={{ fontSize: 9, color: "#333", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 4 }}>
                VOLUME DEVIATION SCAN
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                <SortBtn label="BY 20D DEV" sk="dev_20d" />
                <SortBtn label="BY 3M DEV" sk="dev_3m" />
                <SortBtn label="BY 1Y DEV" sk="dev_1y" />
                <SortBtn label="GAINERS" sk="change_pct_desc" />
                <SortBtn label="LOSERS" sk="change_pct_asc" />
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              {computedAt && (
                <span style={{ fontSize: 9, color: "#2a2a2a" }}>
                  {computedAt.slice(11, 16)} IST
                </span>
              )}
              {!loading && (
                <button
                  onClick={load}
                  style={{
                    fontFamily: "'Geist Mono', monospace",
                    fontSize: 9,
                    background: "#111",
                    border: "1px solid #1e1e1e",
                    color: "#555",
                    padding: "3px 10px",
                    borderRadius: 3,
                    cursor: "pointer",
                  }}
                >
                  ↻ REFRESH
                </button>
              )}
            </div>
          </div>
        </div>

        {loading && (
          <div style={{ padding: "14px 14px 0" }}>
            {Array.from({ length: 20 }).map((_, i) => (
              <div
                key={i}
                style={{
                  height: 28,
                  marginBottom: 2,
                  borderRadius: 2,
                  background: "#0d0d0d",
                  animation: "pulse 1.5s ease-in-out infinite",
                  opacity: 1 - i * 0.03,
                }}
              />
            ))}
            <style>{`@keyframes pulse { 0%,100%{opacity:.4} 50%{opacity:.7} }`}</style>
          </div>
        )}

        {error && !loading && (
          <div style={{ padding: 48, textAlign: "center" }}>
            <div style={{ color: "#ff3b3b", fontSize: 11, marginBottom: 12 }}>
              Error loading data.
            </div>
            <button
              onClick={load}
              style={{
                fontFamily: "'Geist Mono', monospace",
                fontSize: 10,
                background: "#1a1a1a",
                border: "1px solid #2e2e2e",
                color: "#e5e5e5",
                padding: "6px 18px",
                borderRadius: 3,
                cursor: "pointer",
              }}
            >
              RETRY?
            </button>
          </div>
        )}

        {!loading && !error && sorted.length > 0 && (
          <div style={{ padding: "0 14px 14px", overflow: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
              <colgroup>
                <col style={{ width: 90 }} />
                <col style={{ width: 80 }} />
                <col style={{ width: 60 }} />
                <col style={{ width: 80 }} />
                <col style={{ width: 80 }} />
                <col style={{ width: 80 }} />
                <col style={{ width: 80 }} />
                <col style={{ width: 80 }} />
                <col style={{ width: 80 }} />
              </colgroup>
              <thead>
                <tr>
                  <th style={{ ...thStyle, textAlign: "left" }}>SYMBOL</th>
                  <th style={{ ...thStyle, textAlign: "right" }}>PRICE</th>
                  <th style={{ ...thStyle, textAlign: "right" }}>CHG%</th>
                  <th style={{ ...thStyle, textAlign: "right" }}>TODAY VOL</th>
                  <th style={{ ...thStyle, textAlign: "right" }}>vs 20D</th>
                  <th style={{ ...thStyle, textAlign: "right" }}>vs 3M</th>
                  <th style={{ ...thStyle, textAlign: "right" }}>vs 6M</th>
                  <th style={{ ...thStyle, textAlign: "right" }}>vs 1Y</th>
                  <th style={{ ...thStyle, textAlign: "right" }}>vs ALL</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map(row => (
                  <tr
                    key={row.symbol}
                    onClick={() => router.push(`/stock/${row.symbol}`)}
                    style={{ cursor: "pointer", borderBottom: "1px solid #0f0f0f" }}
                    onMouseEnter={e => { e.currentTarget.style.background = "#0d0d0d"; }}
                    onMouseLeave={e => { e.currentTarget.style.background = "transparent"; }}
                  >
                    <td style={{ padding: "5px 8px", textAlign: "left" }}>
                      <span style={{
                        fontFamily: "'Geist Mono', monospace",
                        fontSize: 11,
                        fontWeight: 700,
                        color: "#e5e5e5",
                        letterSpacing: "-0.01em",
                      }}>
                        {row.symbol}
                      </span>
                    </td>
                    <td style={{ padding: "5px 8px", textAlign: "right" }}>
                      <span style={{
                        fontFamily: "'Geist Mono', monospace",
                        fontSize: 11,
                        color: "#aaa",
                      }}>
                        ₹{row.price.toLocaleString("en-IN", { maximumFractionDigits: 1 })}
                      </span>
                    </td>
                    <td style={{ padding: "5px 8px", textAlign: "right" }}>
                      <span style={{
                        fontFamily: "'Geist Mono', monospace",
                        fontSize: 11,
                        fontWeight: 600,
                        color: row.change_pct >= 0 ? "#00d084" : "#ff3b3b",
                      }}>
                        {row.change_pct >= 0 ? "+" : ""}{row.change_pct.toFixed(1)}%
                      </span>
                    </td>
                    <td style={{ padding: "5px 8px", textAlign: "right" }}>
                      <span style={{
                        fontFamily: "'Geist Mono', monospace",
                        fontSize: 11,
                        color: "#888",
                      }}>
                        {fmtVol(row.today_vol)}
                      </span>
                    </td>
                    <DevCell value={row.dev_20d} />
                    <DevCell value={row.dev_3m} />
                    <DevCell value={row.dev_6m} />
                    <DevCell value={row.dev_1y} />
                    <DevCell value={row.dev_all} />
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!loading && !error && sorted.length === 0 && (
          <div style={{ padding: 48, textAlign: "center", color: "#333", fontSize: 11, fontFamily: "'Geist Mono', monospace" }}>
            NO DATA
          </div>
        )}
      </div>
    </div>
  );
}
