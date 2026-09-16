'use client';

import { useState, useEffect, useCallback } from "react";
import { api, type SectorSpotlight, type NewsArticle } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────
interface IndexData { name: string; value: number; change: number; change_pct: number }
interface BreadthData {
  advances: number; declines: number; total: number; adr: number;
  pct_above_50dma: number; pct_above_200dma: number;
  median_rsi: number; pct_overbought: number; pct_oversold: number;
  near_52w_high: number; near_52w_low: number;
  breadth_signal: string; breadth_color: string;
}
interface FiiRow { category: string; buyValue: number; sellValue: number; netValue: number }
interface MacroItem { label: string; symbol: string; price: number; change_pct: number }
interface CalEvent { description: string; date: string; days_to_event: number; type: string; importance: string }

// ── Helpers ────────────────────────────────────────────────────────────
function cc(v: number | null | undefined) {
  if (v == null) return "#6b7280";
  return v >= 0 ? "#10b981" : "#ef4444";
}
function sgn(v: number | null | undefined) {
  if (v == null) return "";
  return v >= 0 ? "+" : "";
}
function fmtN(v: number | null | undefined, d = 2) {
  if (v == null || isNaN(v)) return "—";
  return v.toFixed(d);
}
function fmtK(v: number) {
  if (Math.abs(v) >= 1e5) return `₹${(v / 1e5).toFixed(1)}L`;
  if (Math.abs(v) >= 1e3) return `₹${(v / 1e3).toFixed(1)}K`;
  return `₹${v.toFixed(0)}`;
}

// ── Sub-components ─────────────────────────────────────────────────────

function Card({ title, children, accent }: { title: string; children: React.ReactNode; accent?: string }) {
  return (
    <div style={{
      background: "#0a0a0a", border: `1px solid ${accent || "#1e1e1e"}`,
      borderRadius: 8, overflow: "hidden", display: "flex", flexDirection: "column",
    }}>
      <div style={{
        padding: "6px 12px", borderBottom: `1px solid ${accent || "#1e1e1e"}`,
        background: accent ? `${accent}11` : "#0f0f0f",
        fontSize: 9, color: accent || "#444", letterSpacing: "0.08em", fontWeight: 700,
      }}>{title}</div>
      <div style={{ padding: 12, flex: 1 }}>{children}</div>
    </div>
  );
}

function IndexStrip({ indices }: { indices: IndexData[] }) {
  return (
    <div style={{ display: "flex", gap: 2, overflowX: "auto", paddingBottom: 2 }}>
      {indices.map(idx => (
        <div key={idx.name} style={{
          minWidth: 130, background: "#0a0a0a", border: "1px solid #1a1a1a",
          borderRadius: 6, padding: "6px 10px", flexShrink: 0,
        }}>
          <div style={{ fontSize: 9, color: "#444", letterSpacing: "0.06em" }}>{idx.name}</div>
          <div style={{ fontSize: 15, fontWeight: 700, color: "#e5e5e5", fontFamily: "monospace" }}>
            {idx.value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: 10, color: cc(idx.change_pct), fontWeight: 600 }}>
            {sgn(idx.change_pct)}{fmtN(idx.change_pct)}% &nbsp;
            <span style={{ fontWeight: 400, color: "#333" }}>
              {sgn(idx.change)}{fmtN(idx.change, 1)}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

function FearGauge({ score, label, color }: { score: number; label: string; color: string }) {
  const pct = Math.min(100, Math.max(0, score));
  const segments = [
    { label: "Extreme Fear", color: "#ef4444", w: 20 },
    { label: "Fear", color: "#f97316", w: 20 },
    { label: "Neutral", color: "#f59e0b", w: 20 },
    { label: "Greed", color: "#84cc16", w: 20 },
    { label: "Extreme Greed", color: "#10b981", w: 20 },
  ];
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: 32, fontWeight: 800, color, fontFamily: "monospace" }}>{Math.round(score)}</div>
      <div style={{ fontSize: 11, color, fontWeight: 700, marginBottom: 8 }}>{label}</div>
      <div style={{ display: "flex", height: 8, borderRadius: 4, overflow: "hidden", gap: 1 }}>
        {segments.map((s, i) => (
          <div key={i} style={{ flex: s.w, background: s.color, opacity: 0.7 }} />
        ))}
      </div>
      <div style={{ position: "relative", height: 16 }}>
        <div style={{
          position: "absolute", left: `${pct}%`, transform: "translateX(-50%)",
          width: 2, height: 14, background: "#fff", top: 0,
        }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 8, color: "#333", marginTop: 2 }}>
        <span>0 Extreme Fear</span><span>100 Extreme Greed</span>
      </div>
    </div>
  );
}

function SectorSpotlightPanel({ sectors }: { sectors: SectorSpotlight[] }) {
  const LABEL_ICON: Record<string, string> = {
    HOT: "🔥", BUILDING: "📈", NEUTRAL: "➖", COOLING: "❄️", FALLING: "📉",
  };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {sectors.map((s, i) => (
        <div key={s.sector} style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "7px 10px", background: "#0f0f0f",
          border: `1px solid ${s.color}22`, borderRadius: 6,
          borderLeft: `3px solid ${s.color}`,
        }}>
          <div style={{ width: 20, textAlign: "center", fontSize: 9, color: "#444", fontWeight: 700 }}>#{i + 1}</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: "#e5e5e5" }}>{s.sector}</span>
              <span style={{
                fontSize: 8, padding: "1px 5px", borderRadius: 3,
                background: `${s.color}22`, color: s.color, fontWeight: 700, letterSpacing: "0.06em",
              }}>{LABEL_ICON[s.label]} {s.label}</span>
            </div>
            <div style={{ display: "flex", gap: 12, marginTop: 3, fontSize: 10, color: "#666" }}>
              <span>1D <span style={{ color: cc(s.mom_1d), fontWeight: 600 }}>{sgn(s.mom_1d)}{fmtN(s.mom_1d)}%</span></span>
              <span>5D <span style={{ color: cc(s.mom_5d), fontWeight: 600 }}>{sgn(s.mom_5d)}{fmtN(s.mom_5d)}%</span></span>
              <span>Breadth <span style={{ color: s.breadth_pct >= 60 ? "#10b981" : s.breadth_pct <= 40 ? "#ef4444" : "#f59e0b", fontWeight: 600 }}>{fmtN(s.breadth_pct, 0)}%</span></span>
              <span>Vol <span style={{ color: s.vol_surge >= 1.3 ? "#10b981" : "#888", fontWeight: 600 }}>{fmtN(s.vol_surge, 1)}x</span></span>
            </div>
          </div>
          <div style={{ textAlign: "right", flexShrink: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 800, color: s.color, fontFamily: "monospace" }}>
              {sgn(s.shine_score)}{fmtN(s.shine_score, 1)}
            </div>
            <div style={{ fontSize: 8, color: "#333" }}>SCORE</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function BreadthPanel({ b }: { b: BreadthData }) {
  const rows = [
    { label: "Advances / Declines", value: `${b.advances} / ${b.declines}`, color: b.adr >= 1.2 ? "#10b981" : b.adr <= 0.8 ? "#ef4444" : "#f59e0b" },
    { label: "A/D Ratio", value: fmtN(b.adr), color: cc(b.adr - 1) },
    { label: "Above 50 DMA", value: `${fmtN(b.pct_above_50dma)}%`, color: b.pct_above_50dma >= 60 ? "#10b981" : "#f59e0b" },
    { label: "Above 200 DMA", value: `${fmtN(b.pct_above_200dma)}%`, color: b.pct_above_200dma >= 60 ? "#10b981" : "#ef4444" },
    { label: "Median RSI", value: fmtN(b.median_rsi), color: b.median_rsi > 60 ? "#f59e0b" : b.median_rsi < 40 ? "#10b981" : "#e5e5e5" },
    { label: "Overbought / Oversold", value: `${fmtN(b.pct_overbought)}% / ${fmtN(b.pct_oversold)}%`, color: "#888" },
    { label: "Near 52W High", value: b.near_52w_high.toString(), color: "#10b981" },
    { label: "Near 52W Low", value: b.near_52w_low.toString(), color: "#ef4444" },
  ];
  return (
    <div>
      <div style={{
        textAlign: "center", fontSize: 11, fontWeight: 700,
        padding: "4px 10px", borderRadius: 4, marginBottom: 10,
        background: `${b.breadth_color}22`, color: b.breadth_color, border: `1px solid ${b.breadth_color}44`,
      }}>{b.breadth_signal} — {b.advances + b.declines} stocks tracked</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
        {rows.map(r => (
          <div key={r.label} style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
            <span style={{ color: "#555" }}>{r.label}</span>
            <span style={{ color: r.color, fontWeight: 600, fontFamily: "monospace" }}>{r.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function FiiPanel({ rows }: { rows: FiiRow[] }) {
  const fii = rows.find(r => r.category.includes("FII") || r.category.includes("FPI"));
  const dii = rows.find(r => r.category.includes("DII"));
  const items = [fii, dii].filter(Boolean) as FiiRow[];
  const netFII = fii?.netValue ?? 0;
  const netDII = dii?.netValue ?? 0;
  const combined = netFII + netDII;

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
        {items.map(row => (
          <div key={row.category} style={{
            flex: 1, padding: "8px 10px", background: "#0f0f0f",
            border: `1px solid ${row.netValue >= 0 ? "#10b98133" : "#ef444433"}`,
            borderRadius: 6, textAlign: "center",
          }}>
            <div style={{ fontSize: 9, color: "#444", marginBottom: 3 }}>{row.category}</div>
            <div style={{ fontSize: 15, fontWeight: 800, color: cc(row.netValue), fontFamily: "monospace" }}>
              {row.netValue >= 0 ? "+" : ""}{(row.netValue / 100).toFixed(0)} Cr
            </div>
            <div style={{ fontSize: 8, color: "#333", marginTop: 2 }}>
              B: {(row.buyValue / 100).toFixed(0)} · S: {(row.sellValue / 100).toFixed(0)}
            </div>
          </div>
        ))}
      </div>
      <div style={{ textAlign: "center", fontSize: 10, color: "#666" }}>
        Combined Net:&nbsp;
        <span style={{ color: cc(combined), fontWeight: 700, fontFamily: "monospace" }}>
          {combined >= 0 ? "+" : ""}{(combined / 100).toFixed(0)} Cr
        </span>
        &nbsp;—&nbsp;
        <span style={{ color: combined >= 0 ? "#10b981" : "#ef4444", fontWeight: 600 }}>
          {combined >= 0 ? "Institutional BUYING" : "Institutional SELLING"}
        </span>
      </div>
    </div>
  );
}

function MacroPanel({ items }: { items: MacroItem[] }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
      {items.map(m => (
        <div key={m.label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 11 }}>
          <span style={{ color: "#555" }}>{m.label}</span>
          <div style={{ textAlign: "right" }}>
            <span style={{ color: "#e5e5e5", fontFamily: "monospace", fontWeight: 600 }}>{fmtN(m.price, 2)}</span>
            <span style={{ color: cc(m.change_pct), fontSize: 9, marginLeft: 6 }}>
              {sgn(m.change_pct)}{fmtN(m.change_pct)}%
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

function NewsPanel({ articles }: { articles: NewsArticle[] }) {
  const SENTIMENT_COLORS: Record<string, string> = {
    positive: "#10b981", negative: "#ef4444", neutral: "#6b7280",
  };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {articles.slice(0, 10).map((a, i) => (
        <div key={i} style={{
          padding: "8px 10px", background: "#0f0f0f",
          border: "1px solid #1a1a1a", borderRadius: 6,
          borderLeft: `3px solid ${SENTIMENT_COLORS[a.sentiment || "neutral"]}`,
        }}>
          <div style={{ fontSize: 11, color: "#ccc", lineHeight: 1.4, marginBottom: 4 }}>{a.title}</div>
          <div style={{ display: "flex", gap: 8, fontSize: 9, color: "#444", alignItems: "center" }}>
            <span style={{ color: SENTIMENT_COLORS[a.sentiment || "neutral"] }}>● {(a.sentiment || "neutral").toUpperCase()}</span>
            {a.tags?.length ? (
              <span style={{ color: "#3b82f6" }}>{a.tags.slice(0, 3).join(", ")}</span>
            ) : null}
            <span style={{ marginLeft: "auto" }}>{a.source}</span>
          </div>
        </div>
      ))}
      {articles.length === 0 && (
        <div style={{ textAlign: "center", color: "#333", fontSize: 11, padding: "20px 0" }}>No news available</div>
      )}
    </div>
  );
}

function EventsPanel({ events }: { events: CalEvent[] }) {
  const IMPORTANCE_COLORS: Record<string, string> = {
    CRITICAL: "#ef4444", HIGH: "#f97316", MEDIUM: "#f59e0b", LOW: "#6b7280",
  };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
      {events.slice(0, 8).map((e, i) => (
        <div key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 11 }}>
          <div style={{
            minWidth: 32, fontSize: 9, fontWeight: 700, textAlign: "center",
            padding: "2px 4px", borderRadius: 3,
            background: `${IMPORTANCE_COLORS[e.importance] || "#333"}22`,
            color: IMPORTANCE_COLORS[e.importance] || "#555",
          }}>
            {e.days_to_event === 0 ? "TODAY" : `${e.days_to_event}d`}
          </div>
          <div style={{ color: "#aaa", lineHeight: 1.4 }}>{e.description}</div>
        </div>
      ))}
      {events.length === 0 && (
        <div style={{ textAlign: "center", color: "#333", fontSize: 11, padding: "10px 0" }}>No upcoming events</div>
      )}
    </div>
  );
}

function Spinner() {
  return <div style={{ color: "#333", fontSize: 11, textAlign: "center", padding: "20px 0" }}>Loading…</div>;
}

// ── Main Dashboard ─────────────────────────────────────────────────────
export default function HomeDashboard() {
  const [indices, setIndices] = useState<IndexData[]>([]);
  const [breadth, setBreadth] = useState<BreadthData | null>(null);
  const [fii, setFii] = useState<FiiRow[]>([]);
  const [fearGreed, setFearGreed] = useState<{ score: number; label: string; color: string } | null>(null);
  const [sectors, setSectors] = useState<SectorSpotlight[]>([]);
  const [macro, setMacro] = useState<MacroItem[]>([]);
  const [news, setNews] = useState<NewsArticle[]>([]);
  const [events, setEvents] = useState<CalEvent[]>([]);
  const [lastUpdated, setLastUpdated] = useState<string>("");
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const [overviewRes, breadthRes, fiiRes, fgRes, spotlightRes, macroRes, newsRes, calRes] = await Promise.allSettled([
        api.marketOverview(),
        api.breadth(),
        api.fiiDii(),
        api.fearGreed(),
        api.sectorSpotlight(),
        api.macro(),
        api.marketNews(),
        fetch("http://localhost:8001/api/calendar/events?days=30").then(r => r.json()),
      ]);

      if (overviewRes.status === "fulfilled") {
        const d = overviewRes.value as { indices: IndexData[] };
        setIndices(d.indices || []);
      }
      if (breadthRes.status === "fulfilled") setBreadth(breadthRes.value as BreadthData);
      if (fiiRes.status === "fulfilled") {
        const d = fiiRes.value as { data: FiiRow[] };
        setFii(d.data || []);
      }
      if (fgRes.status === "fulfilled") setFearGreed(fgRes.value);
      if (spotlightRes.status === "fulfilled") {
        const d = spotlightRes.value as { sectors: SectorSpotlight[] };
        setSectors(d.sectors || []);
      }
      if (macroRes.status === "fulfilled") {
        const d = macroRes.value as { data: MacroItem[] };
        setMacro(d.data || []);
      }
      if (newsRes.status === "fulfilled") {
        const nd = newsRes.value as { articles?: NewsArticle[] } | NewsArticle[];
        setNews(Array.isArray(nd) ? nd : (nd as { articles?: NewsArticle[] }).articles || []);
      }
      if (calRes.status === "fulfilled") {
        const d = calRes.value as { events: CalEvent[] };
        setEvents(d.events || []);
      }
      setLastUpdated(new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }));
    } catch {/* ignore */}
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 60_000); // refresh every 60s
    return () => clearInterval(id);
  }, [refresh]);

  const hotSectors = sectors.filter(s => s.label === "HOT" || s.label === "BUILDING");
  const topSector = sectors[0];

  // Derive overall market signal
  const marketSignal = (() => {
    if (!breadth || !fearGreed) return null;
    const positives = [
      breadth.adr > 1.2,
      breadth.pct_above_50dma > 60,
      fearGreed.score > 55,
      (fii.find(r => r.category.includes("FII"))?.netValue ?? 0) > 0,
    ].filter(Boolean).length;
    if (positives >= 3) return { label: "BULLISH", color: "#10b981" };
    if (positives <= 1) return { label: "BEARISH", color: "#ef4444" };
    return { label: "NEUTRAL", color: "#f59e0b" };
  })();

  return (
    <div style={{ minHeight: "100vh", background: "#050505", color: "#e5e5e5", fontFamily: "monospace" }}>
      {/* ── Top Navigation Bar ── */}
      <div style={{
        padding: "8px 16px", borderBottom: "1px solid #111",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        background: "#080808", position: "sticky", top: 0, zIndex: 10,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 12, fontWeight: 800, color: "#e5e5e5", letterSpacing: "0.1em" }}>
            INDIAHEDGE
          </span>
          <span style={{ fontSize: 9, color: "#444", padding: "2px 8px", border: "1px solid #222", borderRadius: 3 }}>
            HOME DASHBOARD
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {marketSignal && (
            <div style={{
              fontSize: 9, fontWeight: 800, padding: "3px 10px", borderRadius: 3,
              background: `${marketSignal.color}22`, color: marketSignal.color,
              border: `1px solid ${marketSignal.color}44`, letterSpacing: "0.08em",
            }}>MARKET {marketSignal.label}</div>
          )}
          {lastUpdated && (
            <span style={{ fontSize: 9, color: "#333" }}>Updated {lastUpdated}</span>
          )}
          <button onClick={refresh} style={{
            background: "none", border: "1px solid #222", borderRadius: 4,
            color: "#555", fontSize: 9, padding: "3px 8px", cursor: "pointer",
          }}>↻ REFRESH</button>
        </div>
      </div>

      <div style={{ padding: 12, maxWidth: 1600, margin: "0 auto" }}>
        {/* ── Index Strip ── */}
        <div style={{ marginBottom: 12 }}>
          <IndexStrip indices={indices} />
        </div>

        {/* ── Key Insight Banner ── */}
        {!loading && topSector && (
          <div style={{
            marginBottom: 12, padding: "8px 14px",
            background: `${topSector.color}11`, border: `1px solid ${topSector.color}33`,
            borderRadius: 6, display: "flex", alignItems: "center", gap: 12,
          }}>
            <span style={{ fontSize: 9, color: topSector.color, fontWeight: 700, letterSpacing: "0.06em" }}>
              TODAY'S SPOTLIGHT
            </span>
            <span style={{ fontSize: 11, color: "#ccc" }}>
              <strong style={{ color: topSector.color }}>{topSector.sector}</strong> is the strongest sector today
              with {sgn(topSector.mom_1d)}{fmtN(topSector.mom_1d)}% today, {sgn(topSector.mom_5d)}{fmtN(topSector.mom_5d)}% this week,
              {topSector.breadth_pct}% breadth and {fmtN(topSector.vol_surge, 1)}x volume.
              {hotSectors.length > 1 && ` Also watch: ${hotSectors.slice(1, 3).map(s => s.sector).join(", ")}.`}
            </span>
          </div>
        )}

        {/* ── Main Grid: 3 columns ── */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 320px 260px", gap: 12, marginBottom: 12 }}>

          {/* Column 1: Sector Spotlight */}
          <Card title="SECTOR SPOTLIGHT — MULTI-FACTOR RANKING" accent="#3b82f6">
            {loading ? <Spinner /> : sectors.length > 0 ? (
              <div style={{ overflow: "auto", maxHeight: "calc(100vh - 280px)" }}>
                <SectorSpotlightPanel sectors={sectors} />
              </div>
            ) : (
              <div style={{ color: "#444", fontSize: 11, textAlign: "center", padding: "30px 0" }}>
                Computing sector scores… (first load may take ~30s)
              </div>
            )}
          </Card>

          {/* Column 2: Market Pulse */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {/* Fear & Greed */}
            <Card title="FEAR & GREED INDEX" accent={fearGreed?.color}>
              {loading ? <Spinner /> : fearGreed ? (
                <FearGauge score={fearGreed.score} label={fearGreed.label} color={fearGreed.color} />
              ) : <Spinner />}
            </Card>

            {/* Market Breadth */}
            <Card title="MARKET BREADTH — NIFTY 50" accent="#8b5cf6">
              {loading ? <Spinner /> : breadth ? (
                <BreadthPanel b={breadth} />
              ) : <Spinner />}
            </Card>

            {/* Macro */}
            <Card title="MACRO PULSE" accent="#06b6d4">
              {loading ? <Spinner /> : macro.length > 0 ? (
                <MacroPanel items={macro} />
              ) : <Spinner />}
            </Card>
          </div>

          {/* Column 3: FII/DII + Events */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {/* FII/DII */}
            <Card title="FII / DII FLOW (TODAY)" accent="#10b981">
              {loading ? <Spinner /> : fii.length > 0 ? (
                <FiiPanel rows={fii} />
              ) : <Spinner />}
            </Card>

            {/* Market Signal Summary */}
            {!loading && breadth && fearGreed && (
              <Card title="MARKET OUTLOOK" accent={marketSignal?.color}>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {[
                    { label: "Breadth Signal", value: breadth.breadth_signal, color: breadth.breadth_color },
                    { label: "Fear & Greed", value: fearGreed.label, color: fearGreed.color },
                    { label: "FII Flow", value: (fii.find(r => r.category.includes("FII"))?.netValue ?? 0) >= 0 ? "BUYING" : "SELLING", color: (fii.find(r => r.category.includes("FII"))?.netValue ?? 0) >= 0 ? "#10b981" : "#ef4444" },
                    { label: "DII Flow", value: (fii.find(r => r.category.includes("DII"))?.netValue ?? 0) >= 0 ? "BUYING" : "SELLING", color: (fii.find(r => r.category.includes("DII"))?.netValue ?? 0) >= 0 ? "#10b981" : "#ef4444" },
                    { label: "Top Sector", value: sectors[0]?.sector || "—", color: sectors[0]?.color || "#888" },
                    { label: "Weakest Sector", value: sectors[sectors.length - 1]?.sector || "—", color: sectors[sectors.length - 1]?.color || "#888" },
                  ].map(row => (
                    <div key={row.label} style={{ display: "flex", justifyContent: "space-between", fontSize: 10 }}>
                      <span style={{ color: "#444" }}>{row.label}</span>
                      <span style={{ color: row.color, fontWeight: 700 }}>{row.value}</span>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {/* Upcoming Events */}
            <Card title="UPCOMING EVENTS" accent="#f59e0b">
              {loading ? <Spinner /> : <EventsPanel events={events} />}
            </Card>
          </div>
        </div>

        {/* ── Bottom: Market News ── */}
        <Card title="MARKET NEWS — SENTIMENT TAGGED" accent="#6366f1">
          {loading ? <Spinner /> : <NewsPanel articles={news} />}
        </Card>
      </div>
    </div>
  );
}
