'use client';

import { useState, useEffect, useCallback } from "react";
import IndexBar from "@/components/IndexBar";

// ── Types ─────────────────────────────────────────────────────────────────────

interface MacroItem {
  name: string;
  ticker: string;
  price: number;
  change: number;
  change_pct: number;
  currency: string;
  exchange: string;
}

interface GlobalMacroData {
  indices: MacroItem[];
  forex: MacroItem[];
  commodities: MacroItem[];
  bonds: MacroItem[];
  shipping: MacroItem[];
  crypto: MacroItem[];
  india_sectors: MacroItem[];
}

interface YieldCurveData {
  us_curve: { "3M": number; "5Y": number; "10Y": number; "30Y": number };
  spread_2_10: number;
  is_inverted: boolean;
  india_10y: number;
  india_us_spread: number;
  us_10y_trend: number[];
  interpretation: string;
}

interface MacroSignals {
  spx_momentum_3m: number;
  vix: number;
  india_vix: number;
  dxy_3m: number;
  gold_1m: number;
  crude_3m: number;
  nifty_3m: number;
}

interface MacroRegimeData {
  regime: string;
  color: string;
  score_pct: number;
  description: string;
  signals: MacroSignals;
  key_changes: string[];
}

interface MomentumAsset {
  name: string;
  ret_1m: number | null;
  ret_3m: number | null;
  ret_6m: number | null;
  ret_1y: number | null;
  above_200sma: boolean;
  trend_score: number;
  momentum_score: number;
  signal: string;
}

interface CrossAssetMomentumData {
  leaders: MomentumAsset[];
  laggards: MomentumAsset[];
  all: MomentumAsset[];
}

interface SensitivityItem {
  stock: string;
  inr_correlation: number;
  crude_correlation: number;
  inr_impact: string;
  crude_impact: string;
}

interface IndiaMacroSensitivityData {
  sensitivity: SensitivityItem[];
  inr_level: number;
  crude_level: number;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
const REFRESH_INTERVAL = 300; // seconds

// ── Helpers ───────────────────────────────────────────────────────────────────

function pct(v: number): string {
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

function clr(v: number): string {
  return v >= 0 ? "#00d084" : "#ff3b3b";
}

function fmtPrice(v: number, currency = ""): string {
  if (v === 0) return "—";
  const prefix = currency === "USD" ? "$" : currency === "INR" ? "₹" : "";
  if (v >= 1000) return prefix + v.toLocaleString("en-US", { maximumFractionDigits: 2 });
  return prefix + v.toFixed(v < 10 ? 4 : 2);
}

// ── Section Header ─────────────────────────────────────────────────────────────

function SectionHeader({ title, sub }: { title: string; sub?: string }) {
  return (
    <div style={{ padding: "6px 10px", borderBottom: "1px solid #141414", background: "#060606" }}>
      <span style={{ fontSize: 9, color: "#444", letterSpacing: "0.1em", fontWeight: 700 }}>{title}</span>
      {sub && <span style={{ fontSize: 8, color: "#2a2a2a", marginLeft: 8 }}>{sub}</span>}
    </div>
  );
}

// ── Macro Regime Box ──────────────────────────────────────────────────────────

function MacroRegimeBox({ data, loading }: { data: MacroRegimeData | null; loading: boolean }) {
  if (loading) return (
    <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 8 }}>
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="skeleton" style={{ height: i === 0 ? 36 : 18, borderRadius: 3 }} />
      ))}
    </div>
  );
  if (!data) return <div style={{ padding: 12, color: "#555", fontSize: 11 }}>Unavailable</div>;

  const signals: { label: string; value: number; key: keyof MacroSignals }[] = [
    { label: "VIX", value: data.signals.vix, key: "vix" },
    { label: "INDIA VIX", value: data.signals.india_vix, key: "india_vix" },
    { label: "SPX 3M", value: data.signals.spx_momentum_3m, key: "spx_momentum_3m" },
    { label: "DXY 3M", value: data.signals.dxy_3m, key: "dxy_3m" },
    { label: "CRUDE 3M", value: data.signals.crude_3m, key: "crude_3m" },
    { label: "NIFTY 3M", value: data.signals.nifty_3m, key: "nifty_3m" },
    { label: "GOLD 1M", value: data.signals.gold_1m, key: "gold_1m" },
  ];

  const score = data.score_pct; // -100 to +100
  const barPct = ((score + 100) / 200) * 100; // 0-100%

  return (
    <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 10 }}>
      {/* Regime name */}
      <div>
        <div style={{
          fontSize: 22, fontWeight: 800, fontFamily: "monospace",
          color: data.color, letterSpacing: "-0.02em", lineHeight: 1.1,
        }}>
          {data.regime}
        </div>
        <div style={{ fontSize: 9, color: "#444", marginTop: 3, lineHeight: 1.4 }}>
          {data.description}
        </div>
      </div>

      {/* Score bar */}
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
          <span style={{ fontSize: 9, color: "#333" }}>BEAR</span>
          <span className="num" style={{ fontSize: 10, color: data.color, fontWeight: 700 }}>
            {score > 0 ? "+" : ""}{score.toFixed(0)}
          </span>
          <span style={{ fontSize: 9, color: "#333" }}>BULL</span>
        </div>
        <div style={{ height: 4, background: "#1a1a1a", borderRadius: 2, overflow: "hidden" }}>
          <div style={{
            height: "100%", borderRadius: 2,
            width: `${barPct}%`,
            background: data.color,
            transition: "width 0.6s ease",
          }} />
        </div>
      </div>

      {/* Signal bullets */}
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {signals.map(sig => {
          const isVix = sig.key === "vix" || sig.key === "india_vix";
          // For VIX: high = bearish. For others: positive = bullish
          const bullish = isVix ? sig.value < 20 : sig.value > 0;
          const sigColor = bullish ? "#00d084" : "#ff3b3b";
          return (
            <div key={sig.key} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 9, color: "#444" }}>{sig.label}</span>
              <span className="num" style={{ fontSize: 10, fontWeight: 600, color: sigColor }}>
                {isVix ? sig.value.toFixed(1) : pct(sig.value)}
              </span>
            </div>
          );
        })}
      </div>

      {/* Key changes */}
      {data.key_changes && data.key_changes.length > 0 && (
        <div>
          <div style={{ fontSize: 9, color: "#333", marginBottom: 5, letterSpacing: "0.06em" }}>KEY CHANGES</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            {data.key_changes.slice(0, 3).map((change, i) => (
              <div key={i} style={{ fontSize: 9, color: "#666", paddingLeft: 8, borderLeft: "2px solid #2a2a2a", lineHeight: 1.4 }}>
                {change}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Yield Curve ───────────────────────────────────────────────────────────────

function YieldCurvePanel({ data, loading }: { data: YieldCurveData | null; loading: boolean }) {
  if (loading) return (
    <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 6 }}>
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="skeleton" style={{ height: 20, borderRadius: 3 }} />
      ))}
    </div>
  );
  if (!data) return <div style={{ padding: 12, color: "#555", fontSize: 11 }}>Unavailable</div>;

  const maturities: { label: string; key: keyof typeof data.us_curve }[] = [
    { label: "3M", key: "3M" },
    { label: "5Y", key: "5Y" },
    { label: "10Y", key: "10Y" },
    { label: "30Y", key: "30Y" },
  ];
  const maxYield = Math.max(...maturities.map(m => data.us_curve[m.key] || 0));

  return (
    <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 10 }}>
      {/* US Curve bars */}
      <div>
        <div style={{ fontSize: 9, color: "#333", marginBottom: 7, letterSpacing: "0.06em" }}>US YIELD CURVE</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          {maturities.map(({ label, key }) => {
            const val = data.us_curve[key] || 0;
            const barW = maxYield > 0 ? (val / maxYield) * 100 : 0;
            return (
              <div key={key} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontSize: 9, color: "#444", width: 24, flexShrink: 0 }}>{label}</span>
                <div style={{ flex: 1, height: 10, background: "#111", borderRadius: 2, overflow: "hidden" }}>
                  <div style={{
                    height: "100%", width: `${barW}%`,
                    background: data.is_inverted && key === "3M" ? "#ff3b3b" : "#3b82f6",
                    borderRadius: 2, transition: "width 0.5s ease",
                  }} />
                </div>
                <span className="num" style={{ fontSize: 10, color: "#888", width: 38, textAlign: "right", flexShrink: 0 }}>
                  {val.toFixed(2)}%
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Spread */}
      <div style={{
        padding: "7px 9px", borderRadius: 4,
        background: data.is_inverted ? "rgba(255,59,59,0.06)" : "rgba(0,208,132,0.06)",
        border: `1px solid ${data.is_inverted ? "rgba(255,59,59,0.15)" : "rgba(0,208,132,0.15)"}`,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 9, color: "#444" }}>SPREAD 2Y-10Y</span>
          <span style={{
            fontSize: 9, fontWeight: 700, padding: "1px 5px", borderRadius: 2,
            background: data.is_inverted ? "rgba(255,59,59,0.15)" : "rgba(0,208,132,0.15)",
            color: data.is_inverted ? "#ff3b3b" : "#00d084",
          }}>
            {data.is_inverted ? "INVERTED" : "NORMAL"}
          </span>
        </div>
        <div className="num" style={{ fontSize: 18, fontWeight: 800, color: data.is_inverted ? "#ff3b3b" : "#00d084", marginTop: 3 }}>
          {data.spread_2_10 >= 0 ? "+" : ""}{data.spread_2_10.toFixed(2)}bps
        </div>
      </div>

      {/* India */}
      <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span style={{ fontSize: 9, color: "#444" }}>INDIA 10Y</span>
          <span className="num" style={{ fontSize: 11, color: "#f59e0b" }}>
            {data.india_10y > 0 ? `${data.india_10y.toFixed(2)}%` : "—"}
          </span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span style={{ fontSize: 9, color: "#444" }}>IND-US SPREAD</span>
          <span className="num" style={{ fontSize: 11, color: "#888" }}>
            {data.india_us_spread > 0 ? `+${data.india_us_spread.toFixed(2)}bps` : `${data.india_us_spread.toFixed(2)}bps`}
          </span>
        </div>
      </div>

      {/* Interpretation */}
      {data.interpretation && (
        <div style={{ fontSize: 9, color: "#333", lineHeight: 1.5, borderTop: "1px solid #141414", paddingTop: 8 }}>
          {data.interpretation}
        </div>
      )}
    </div>
  );
}

// ── Global Indices Table ──────────────────────────────────────────────────────

function IndicesTable({ items, loading }: { items: MacroItem[]; loading: boolean }) {
  if (loading) return (
    <div style={{ padding: "8px 10px", display: "flex", flexDirection: "column", gap: 4 }}>
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="skeleton" style={{ height: 22, borderRadius: 3 }} />
      ))}
    </div>
  );

  type Group = { label: string; items: MacroItem[] };
  const groups: Group[] = [
    { label: "INDIA", items: items.filter(i => i.exchange === "NSE" || i.name.includes("Nifty") || i.name.includes("SENSEX") || i.name.includes("India")) },
    { label: "US", items: items.filter(i => ["NYSE", "NASDAQ", "CBOE", "CME"].includes(i.exchange) || i.name.includes("S&P") || i.name.includes("Dow") || i.name.includes("Nasdaq") || i.name.includes("Russell")) },
    { label: "EUROPE", items: items.filter(i => i.name.includes("DAX") || i.name.includes("FTSE") || i.name.includes("CAC") || i.name.includes("Euro") || i.name.includes("IBEX")) },
    { label: "ASIA-PAC", items: items.filter(i => i.name.includes("Nikkei") || i.name.includes("HSI") || i.name.includes("Shanghai") || i.name.includes("ASX") || i.name.includes("Kospi") || i.name.includes("Taiwan")) },
  ];

  // Remaining ungrouped
  const groupedNames = new Set(groups.flatMap(g => g.items.map(x => x.name)));
  const others = items.filter(i => !groupedNames.has(i.name));
  if (others.length > 0) groups.push({ label: "OTHER", items: others });

  return (
    <div style={{ overflowY: "auto", maxHeight: 260 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 80px 60px 60px", padding: "4px 10px", borderBottom: "1px solid #141414" }}>
        {["NAME", "PRICE", "CHG", "CHG%"].map(h => (
          <span key={h} style={{ fontSize: 8, color: "#333", letterSpacing: "0.08em" }}>{h}</span>
        ))}
      </div>
      {groups.map(group => (
        group.items.length > 0 && (
          <div key={group.label}>
            <div style={{ padding: "3px 10px", background: "#050505" }}>
              <span style={{ fontSize: 8, color: "#2a2a2a", letterSpacing: "0.1em" }}>{group.label}</span>
            </div>
            {group.items.map((item, i) => (
              <div key={i} style={{
                display: "grid", gridTemplateColumns: "1fr 80px 60px 60px",
                padding: "4px 10px", borderBottom: "1px solid #0d0d0d",
                alignItems: "center",
              }}
                onMouseEnter={e => (e.currentTarget.style.background = "#0a0a0a")}
                onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
              >
                <span style={{ fontSize: 11, color: "#c8c8c8", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {item.name}
                </span>
                <span className="num" style={{ fontSize: 11, color: "#888" }}>
                  {fmtPrice(item.price, item.currency)}
                </span>
                <span className="num" style={{ fontSize: 11, color: clr(item.change) }}>
                  {item.change >= 0 ? "+" : ""}{item.change.toFixed(2)}
                </span>
                <span className="num" style={{ fontSize: 11, color: clr(item.change_pct), fontWeight: 600 }}>
                  {pct(item.change_pct)}
                </span>
              </div>
            ))}
          </div>
        )
      ))}
    </div>
  );
}

// ── Forex Table ───────────────────────────────────────────────────────────────

function ForexTable({ items, loading }: { items: MacroItem[]; loading: boolean }) {
  if (loading) return (
    <div style={{ padding: "6px 10px", display: "flex", flexDirection: "column", gap: 3 }}>
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="skeleton" style={{ height: 20, borderRadius: 3 }} />
      ))}
    </div>
  );

  return (
    <div style={{ overflowY: "auto", maxHeight: 160 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 80px 60px 60px", padding: "4px 10px", borderBottom: "1px solid #141414" }}>
        {["PAIR", "RATE", "CHG", "CHG%"].map(h => (
          <span key={h} style={{ fontSize: 8, color: "#333", letterSpacing: "0.08em" }}>{h}</span>
        ))}
      </div>
      {items.map((item, i) => (
        <div key={i} style={{
          display: "grid", gridTemplateColumns: "1fr 80px 60px 60px",
          padding: "4px 10px", borderBottom: "1px solid #0d0d0d", alignItems: "center",
        }}
          onMouseEnter={e => (e.currentTarget.style.background = "#0a0a0a")}
          onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
        >
          <span style={{ fontSize: 11, color: "#c8c8c8" }}>{item.name}</span>
          <span className="num" style={{ fontSize: 11, color: "#888" }}>
            {item.price > 0 ? item.price.toFixed(4) : "—"}
          </span>
          <span className="num" style={{ fontSize: 11, color: clr(item.change) }}>
            {item.change >= 0 ? "+" : ""}{item.change.toFixed(4)}
          </span>
          <span className="num" style={{ fontSize: 11, color: clr(item.change_pct), fontWeight: 600 }}>
            {pct(item.change_pct)}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Commodities Cards ─────────────────────────────────────────────────────────

function CommoditiesPanel({ items, loading }: { items: MacroItem[]; loading: boolean }) {
  if (loading) return (
    <div style={{ padding: 10, display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6 }}>
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="skeleton" style={{ height: 56, borderRadius: 4 }} />
      ))}
    </div>
  );

  return (
    <div style={{ padding: 10, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(100px, 1fr))", gap: 5 }}>
      {items.slice(0, 12).map((item, i) => (
        <div key={i} style={{
          padding: "7px 9px", background: "#080808", borderRadius: 4,
          border: "1px solid #141414",
        }}>
          <div style={{ fontSize: 9, color: "#444", marginBottom: 3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {item.name}
          </div>
          <div className="num" style={{ fontSize: 12, fontWeight: 700, color: "#c8c8c8" }}>
            {fmtPrice(item.price, item.currency)}
          </div>
          <div className="num" style={{ fontSize: 10, color: clr(item.change_pct), marginTop: 2 }}>
            {pct(item.change_pct)}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Momentum Leaders / Laggards ───────────────────────────────────────────────

function MomentumPanel({ data, loading }: { data: CrossAssetMomentumData | null; loading: boolean }) {
  if (loading) return (
    <div style={{ padding: 10, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
      {Array.from({ length: 2 }).map((_, i) => (
        <div key={i} className="skeleton" style={{ height: 120, borderRadius: 4 }} />
      ))}
    </div>
  );
  if (!data) return <div style={{ padding: 10, color: "#555", fontSize: 11 }}>Unavailable</div>;

  const MomentumList = ({ title, items, accent }: { title: string; items: MomentumAsset[]; accent: string }) => (
    <div>
      <div style={{ fontSize: 9, color: accent, letterSpacing: "0.08em", fontWeight: 700, marginBottom: 6, padding: "0 4px" }}>
        {title}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
        {items.slice(0, 5).map((asset, i) => (
          <div key={i} style={{
            padding: "5px 7px", background: "#080808", borderRadius: 3,
            border: `1px solid ${accent}18`,
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
              <span style={{ fontSize: 11, color: "#c8c8c8", fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "55%" }}>
                {asset.name}
              </span>
              <span style={{
                fontSize: 8, padding: "1px 5px", borderRadius: 2, flexShrink: 0,
                background: `${accent}18`, color: accent,
              }}>
                {asset.signal?.toUpperCase() || "—"}
              </span>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <span style={{ fontSize: 9, color: "#444" }}>1M</span>
              <span className="num" style={{ fontSize: 9, color: asset.ret_1m != null ? clr(asset.ret_1m) : "#555" }}>{asset.ret_1m != null ? pct(asset.ret_1m) : "—"}</span>
              <span style={{ fontSize: 9, color: "#333" }}>3M</span>
              <span className="num" style={{ fontSize: 9, color: asset.ret_3m != null ? clr(asset.ret_3m) : "#555" }}>{asset.ret_3m != null ? pct(asset.ret_3m) : "—"}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div style={{ padding: 10, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
      <MomentumList title="▲ LEADERS" items={data.leaders} accent="#00d084" />
      <MomentumList title="▼ LAGGARDS" items={data.laggards} accent="#ff3b3b" />
    </div>
  );
}

// ── India Macro Sensitivity Table ─────────────────────────────────────────────

function IndiaSensitivityTable({ data, loading }: { data: IndiaMacroSensitivityData | null; loading: boolean }) {
  if (loading) return (
    <div style={{ padding: "8px 12px", display: "flex", flexDirection: "column", gap: 5 }}>
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="skeleton" style={{ height: 24, borderRadius: 3 }} />
      ))}
    </div>
  );
  if (!data) return <div style={{ padding: 12, color: "#555", fontSize: 11 }}>Unavailable</div>;

  const impactColor = (impact: string): string => {
    const lower = (impact || "").toLowerCase();
    if (lower.includes("positive") || lower.includes("bullish")) return "#00d084";
    if (lower.includes("negative") || lower.includes("bearish")) return "#ff3b3b";
    return "#888";
  };

  return (
    <div>
      {/* Levels banner */}
      <div style={{
        display: "flex", gap: 24, padding: "7px 12px",
        background: "#050505", borderBottom: "1px solid #141414",
      }}>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <span style={{ fontSize: 9, color: "#444" }}>USD/INR</span>
          <span className="num" style={{ fontSize: 13, fontWeight: 700, color: "#f59e0b" }}>
            {data.inr_level > 0 ? `₹${data.inr_level.toFixed(2)}` : "—"}
          </span>
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <span style={{ fontSize: 9, color: "#444" }}>CRUDE WTI</span>
          <span className="num" style={{ fontSize: 13, fontWeight: 700, color: "#f59e0b" }}>
            {data.crude_level > 0 ? `$${data.crude_level.toFixed(1)}` : "—"}
          </span>
        </div>
      </div>

      {/* Table */}
      <div style={{ overflowY: "auto", maxHeight: 220 }}>
        <div style={{
          display: "grid", gridTemplateColumns: "140px 1fr 70px 1fr 70px",
          padding: "5px 12px", borderBottom: "1px solid #141414",
        }}>
          {["STOCK", "INR IMPACT", "INR CORR", "CRUDE IMPACT", "CRUDE CORR"].map(h => (
            <span key={h} style={{ fontSize: 8, color: "#333", letterSpacing: "0.07em" }}>{h}</span>
          ))}
        </div>
        {data.sensitivity.map((row, i) => (
          <div key={i} style={{
            display: "grid", gridTemplateColumns: "140px 1fr 70px 1fr 70px",
            padding: "5px 12px", borderBottom: "1px solid #0d0d0d", alignItems: "center",
          }}
            onMouseEnter={e => (e.currentTarget.style.background = "#090909")}
            onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
          >
            <span style={{ fontSize: 11, color: "#e5e5e5", fontWeight: 600 }}>{row.stock}</span>
            <span style={{ fontSize: 10, color: impactColor(row.inr_impact), lineHeight: 1.3 }}>
              {row.inr_impact || "—"}
            </span>
            <span className="num" style={{ fontSize: 10, color: row.inr_correlation != null && Math.abs(row.inr_correlation) > 0.5 ? "#f59e0b" : "#555" }}>
              {row.inr_correlation != null ? row.inr_correlation.toFixed(2) : "—"}
            </span>
            <span style={{ fontSize: 10, color: impactColor(row.crude_impact), lineHeight: 1.3 }}>
              {row.crude_impact || "—"}
            </span>
            <span className="num" style={{ fontSize: 10, color: row.crude_correlation != null && Math.abs(row.crude_correlation) > 0.5 ? "#f59e0b" : "#555" }}>
              {row.crude_correlation != null ? row.crude_correlation.toFixed(2) : "—"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function MacroPage() {
  const [globalMacro, setGlobalMacro] = useState<GlobalMacroData | null>(null);
  const [yieldCurve, setYieldCurve] = useState<YieldCurveData | null>(null);
  const [macroRegime, setMacroRegime] = useState<MacroRegimeData | null>(null);
  const [momentum, setMomentum] = useState<CrossAssetMomentumData | null>(null);
  const [sensitivity, setSensitivity] = useState<IndiaMacroSensitivityData | null>(null);

  const [loadingMacro, setLoadingMacro] = useState(true);
  const [loadingYield, setLoadingYield] = useState(true);
  const [loadingRegime, setLoadingRegime] = useState(true);
  const [loadingMomentum, setLoadingMomentum] = useState(true);
  const [loadingSensitivity, setLoadingSensitivity] = useState(true);

  const [countdown, setCountdown] = useState(REFRESH_INTERVAL);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const fetchAll = useCallback(async () => {
    setLoadingMacro(true);
    setLoadingYield(true);
    setLoadingRegime(true);
    setLoadingMomentum(true);
    setLoadingSensitivity(true);

    const safeJson = async (url: string) => {
      try {
        const r = await fetch(url);
        if (!r.ok) return null;
        return r.json();
      } catch {
        return null;
      }
    };

    const [gm, yc, mr, mom, sens] = await Promise.all([
      safeJson(`${API}/api/global-macro`),
      safeJson(`${API}/api/yield-curve`),
      safeJson(`${API}/api/macro-regime`),
      safeJson(`${API}/api/cross-asset-momentum`),
      safeJson(`${API}/api/india-macro-sensitivity`),
    ]);

    if (gm) setGlobalMacro(gm);
    if (yc) setYieldCurve(yc);
    if (mr) setMacroRegime(mr);
    if (mom) setMomentum(mom);
    if (sens) setSensitivity(sens);

    setLoadingMacro(false);
    setLoadingYield(false);
    setLoadingRegime(false);
    setLoadingMomentum(false);
    setLoadingSensitivity(false);
    setLastRefresh(new Date());
    setCountdown(REFRESH_INTERVAL);
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // Countdown + auto-refresh
  useEffect(() => {
    const tick = setInterval(() => {
      setCountdown(c => {
        if (c <= 1) {
          fetchAll();
          return REFRESH_INTERVAL;
        }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(tick);
  }, [fetchAll]);

  const indices = globalMacro?.indices ?? [];
  const forex = globalMacro?.forex ?? [];
  const commodities = globalMacro?.commodities ?? [];
  const momentumData = momentum ?? null;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden", background: "#000", fontFamily: "monospace" }}>
      <IndexBar />

      {/* Page header */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "6px 14px", borderBottom: "1px solid #141414", background: "#000", flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: "#e5e5e5", letterSpacing: "0.05em" }}>
            GLOBAL MACRO DASHBOARD
          </span>
          <span style={{ fontSize: 9, color: "#333" }}>
            {lastRefresh ? `Updated ${lastRefresh.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })} IST` : "Loading…"}
          </span>
          <button
            onClick={fetchAll}
            style={{
              fontSize: 9, color: "#2a2a2a", background: "none", border: "1px solid #1e1e1e",
              padding: "1px 7px", borderRadius: 3, cursor: "pointer",
            }}
            onMouseEnter={e => (e.currentTarget.style.color = "#666")}
            onMouseLeave={e => (e.currentTarget.style.color = "#2a2a2a")}
          >
            REFRESH
          </button>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {/* Countdown */}
          <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <div style={{
              width: 28, height: 28, borderRadius: "50%",
              background: `conic-gradient(#3b82f6 ${(countdown / REFRESH_INTERVAL) * 360}deg, #1a1a1a 0deg)`,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <div style={{ width: 22, height: 22, borderRadius: "50%", background: "#000", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <span className="num" style={{ fontSize: 7, color: "#555" }}>{countdown}s</span>
              </div>
            </div>
          </div>
          {/* LIVE badge */}
          <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <div className="live-dot" />
            <span style={{ fontSize: 9, fontWeight: 700, color: "#00d084", letterSpacing: "0.12em" }}>LIVE</span>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div style={{ flex: 1, overflow: "auto", background: "#000" }}>
        <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", height: "100%" }}>

          {/* LEFT COLUMN */}
          <div style={{ borderRight: "1px solid #141414", display: "flex", flexDirection: "column", overflowY: "auto" }}>
            {/* Macro Regime */}
            <div style={{ borderBottom: "1px solid #141414", flexShrink: 0 }}>
              <SectionHeader title="MACRO REGIME" sub="Risk assessment" />
              <MacroRegimeBox data={macroRegime} loading={loadingRegime} />
            </div>

            {/* Yield Curve */}
            <div style={{ flex: 1, overflow: "auto" }}>
              <SectionHeader title="YIELD CURVE" sub="US & India rates" />
              <YieldCurvePanel data={yieldCurve} loading={loadingYield} />
            </div>
          </div>

          {/* RIGHT COLUMN */}
          <div style={{ display: "flex", flexDirection: "column", overflowY: "auto" }}>

            {/* TOP ROW: Indices + Forex */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", borderBottom: "1px solid #141414", flexShrink: 0 }}>
              {/* Global Indices */}
              <div style={{ borderRight: "1px solid #141414" }}>
                <SectionHeader title="GLOBAL INDICES" sub={`${indices.length} markets`} />
                <IndicesTable items={indices} loading={loadingMacro} />
              </div>

              {/* Forex */}
              <div>
                <SectionHeader title="FOREX RATES" sub="Major pairs" />
                <ForexTable items={forex} loading={loadingMacro} />

                {/* Bonds inline below forex */}
                <SectionHeader title="BONDS" sub="Government yields" />
                <div style={{ overflowY: "auto", maxHeight: 140 }}>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 80px 60px", padding: "4px 10px", borderBottom: "1px solid #141414" }}>
                    {["INSTRUMENT", "YIELD", "CHG%"].map(h => (
                      <span key={h} style={{ fontSize: 8, color: "#333", letterSpacing: "0.08em" }}>{h}</span>
                    ))}
                  </div>
                  {loadingMacro
                    ? Array.from({ length: 4 }).map((_, i) => (
                        <div key={i} className="skeleton" style={{ height: 20, margin: "4px 10px", borderRadius: 3 }} />
                      ))
                    : (globalMacro?.bonds ?? []).map((item, i) => (
                        <div key={i} style={{
                          display: "grid", gridTemplateColumns: "1fr 80px 60px",
                          padding: "4px 10px", borderBottom: "1px solid #0d0d0d", alignItems: "center",
                        }}
                          onMouseEnter={e => (e.currentTarget.style.background = "#0a0a0a")}
                          onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                        >
                          <span style={{ fontSize: 10, color: "#c8c8c8" }}>{item.name}</span>
                          <span className="num" style={{ fontSize: 10, color: "#888" }}>
                            {item.price > 0 ? `${item.price.toFixed(2)}%` : "—"}
                          </span>
                          <span className="num" style={{ fontSize: 10, color: clr(item.change_pct), fontWeight: 600 }}>
                            {pct(item.change_pct)}
                          </span>
                        </div>
                      ))}
                </div>
              </div>
            </div>

            {/* MIDDLE ROW: Commodities + Momentum */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", borderBottom: "1px solid #141414", flexShrink: 0 }}>
              {/* Commodities */}
              <div style={{ borderRight: "1px solid #141414" }}>
                <SectionHeader title="COMMODITIES" sub="Energy · Metals · Agri" />
                <CommoditiesPanel items={commodities} loading={loadingMacro} />
              </div>

              {/* Momentum Leaders / Laggards */}
              <div>
                <SectionHeader title="CROSS-ASSET MOMENTUM" sub="Leaders & laggards" />
                <MomentumPanel data={momentumData} loading={loadingMomentum} />
              </div>
            </div>

            {/* BOTTOM ROW: India Macro Sensitivity (full width) */}
            <div style={{ flex: 1, overflow: "auto" }}>
              <SectionHeader title="INDIA MACRO SENSITIVITY" sub="INR & Crude impact by stock" />
              <IndiaSensitivityTable data={sensitivity} loading={loadingSensitivity} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
