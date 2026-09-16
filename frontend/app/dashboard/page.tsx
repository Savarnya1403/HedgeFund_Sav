'use client';

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import IndexBar from "@/components/IndexBar";
import { api, changeClass } from "@/lib/api";

// ── helpers ──────────────────────────────────────────────────────────

function Panel({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div style={{ background: "#111", border: "1px solid #1e1e1e", borderRadius: 8, overflow: "hidden" }}>
      <div style={{ padding: "8px 14px", borderBottom: "1px solid #1e1e1e", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: 10, color: "#555", letterSpacing: "0.06em", fontWeight: 600 }}>{title}</span>
        {action}
      </div>
      <div style={{ padding: 14 }}>{children}</div>
    </div>
  );
}

function StatChip({ label, value, color = "#e5e5e5", sub }: { label: string; value: string | number; color?: string; sub?: string }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: 18, fontWeight: 700, color, fontFamily: "monospace" }}>{value}</div>
      <div style={{ fontSize: 9, color: "#555", marginTop: 1 }}>{label}</div>
      {sub && <div style={{ fontSize: 9, color: "#444" }}>{sub}</div>}
    </div>
  );
}

// ── sub-components ────────────────────────────────────────────────────

interface TurnoverItem {
  name: string;
  yesterday: { volume: number; value: number; openInterest: number };
  today: Record<string, number> | unknown[];
}

function MarketTurnover() {
  const [items, setItems] = useState<TurnoverItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.nseMarketTurnover()
      .then(d => {
        const raw = d as { data?: TurnoverItem[] };
        setItems(raw.data || []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="skeleton" style={{ height: 80, borderRadius: 6 }} />;
  if (items.length === 0) return <div style={{ color: "#555", fontSize: 11 }}>Unavailable</div>;

  const fmt2 = (v: number) => {
    const cr = v / 1e7;
    if (cr >= 1e5) return `₹${(cr / 1e5).toFixed(2)}L Cr`;
    if (cr >= 1000) return `₹${(cr / 1000).toFixed(1)}K Cr`;
    return `₹${cr.toFixed(0)} Cr`;
  };

  const equities = items.find(i => i.name === "Equities");
  const idxFut = items.find(i => i.name === "Index Futures");
  const idxOpt = items.find(i => i.name === "Index Options");
  const stkFut = items.find(i => i.name === "Stock Futures");
  const stkOpt = items.find(i => i.name === "Stock Options");
  const foTotal = [idxFut, idxOpt, stkFut, stkOpt].reduce((acc, x) => acc + (x?.yesterday?.value || 0), 0);

  const stats = [
    { label: "Equities (Cash)", value: equities ? fmt2(equities.yesterday.value) : "—", color: "#3b82f6" },
    { label: "F&O Total", value: foTotal > 0 ? fmt2(foTotal) : "—", color: "#8b5cf6" },
    { label: "Index Options", value: idxOpt ? fmt2(idxOpt.yesterday.value) : "—", color: "#f59e0b" },
    { label: "Stock Options", value: stkOpt ? fmt2(stkOpt.yesterday.value) : "—", color: "#ec4899" },
  ];

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginBottom: 8 }}>
        {stats.map(s => <StatChip key={s.label} label={s.label} value={s.value} color={s.color} />)}
      </div>
      <div style={{ fontSize: 9, color: "#333", textAlign: "center" }}>Previous day · NSE Market Turnover</div>
    </div>
  );
}

interface PreOpenItem {
  metadata: {
    symbol: string;
    lastPrice: number;
    change: number;
    pChange: number;
    iep: number;
    finalQuantity: number;
    totalTurnover: number;
    yearHigh: number;
    yearLow: number;
  };
}

function PreOpenAuction() {
  const [data, setData] = useState<PreOpenItem[]>([]);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    api.nsePreOpen()
      .then(d => {
        const raw = d as { data?: PreOpenItem[] };
        const arr = raw?.data || [];
        const sorted = [...arr]
          .filter(x => x?.metadata?.symbol)
          .sort((a, b) => Math.abs(b.metadata.pChange) - Math.abs(a.metadata.pChange))
          .slice(0, 14);
        setData(sorted);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div>{Array.from({length: 5}).map((_,i) => <div key={i} className="skeleton" style={{ height: 28, marginBottom: 4, borderRadius: 4 }} />)}</div>;
  if (data.length === 0) return <div style={{ color: "#555", fontSize: 11 }}>Pre-open data unavailable</div>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2, maxHeight: 300, overflow: "auto" }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 70px 60px 50px", fontSize: 9, color: "#444", padding: "0 8px 4px" }}>
        <span>SYMBOL</span><span style={{textAlign:"right"}}>IEP</span><span style={{textAlign:"right"}}>CHG%</span><span style={{textAlign:"right"}}>QTY</span>
      </div>
      {data.map((item, i) => {
        const m = item.metadata;
        return (
          <div key={i} onClick={() => router.push(`/stock/${m.symbol}`)}
            style={{ display: "grid", gridTemplateColumns: "1fr 70px 60px 50px", padding: "3px 8px", borderRadius: 3, cursor: "pointer", background: "#0d0d0d", alignItems: "center" }}
            onMouseEnter={e => (e.currentTarget.style.background = "#141414")}
            onMouseLeave={e => (e.currentTarget.style.background = "#0d0d0d")}
          >
            <span style={{ fontSize: 11, fontWeight: 600, color: "#d4d4d4" }}>{m.symbol}</span>
            <span className="num" style={{ fontSize: 11, color: "#888", textAlign: "right" }}>₹{m.iep.toFixed(2)}</span>
            <span className={`num ${changeClass(m.pChange)}`} style={{ fontSize: 11, textAlign: "right" }}>
              {m.pChange > 0 ? "+" : ""}{m.pChange.toFixed(1)}%
            </span>
            <span className="num" style={{ fontSize: 9, color: "#444", textAlign: "right" }}>
              {m.finalQuantity > 0 ? (m.finalQuantity / 1000).toFixed(0) + "k" : "—"}
            </span>
          </div>
        );
      })}
    </div>
  );
}

interface Circular {
  circDate: string;
  circDisplayDate: string;
  circCategory: string;
  circDepartment: string;
  circDisplayNo: string;
  circFilelink: string;
  sub: string;
}

function Circulars() {
  const [data, setData] = useState<Circular[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("All");
  const [categories, setCategories] = useState<string[]>([]);

  useEffect(() => {
    api.nseCirculars()
      .then(d => {
        const raw = d as { data?: Circular[] };
        const arr = raw?.data || [];
        const cats = Array.from(new Set(arr.map(c => c.circCategory))).slice(0, 5);
        setCategories(["All", ...cats]);
        setData(arr.slice(0, 40));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div>{Array.from({length: 4}).map((_,i) => <div key={i} className="skeleton" style={{ height: 48, marginBottom: 6, borderRadius: 5 }} />)}</div>;
  if (data.length === 0) return <div style={{ color: "#555", fontSize: 11 }}>No circulars available</div>;

  const filtered = filter === "All" ? data : data.filter(c => c.circCategory === filter);

  const catColor: Record<string, string> = {
    "Trading": "#3b82f6",
    "Listing": "#22c55e",
    "Risk Management": "#ef4444",
    "Technology": "#f59e0b",
    "General": "#8b5cf6",
  };

  return (
    <div>
      <div style={{ display: "flex", gap: 4, marginBottom: 8, flexWrap: "wrap" }}>
        {categories.map(c => (
          <button key={c} onClick={() => setFilter(c)} style={{
            fontSize: 9, padding: "2px 7px", border: "none", borderRadius: 3, cursor: "pointer",
            background: filter === c ? (catColor[c] || "#3b82f6") + "30" : "#1e1e1e",
            color: filter === c ? (catColor[c] || "#3b82f6") : "#555",
            fontWeight: filter === c ? 700 : 400,
          }}>{c}</button>
        ))}
      </div>
      <div style={{ maxHeight: 280, overflow: "auto" }}>
        {filtered.slice(0, 15).map((circ, i) => (
          <a key={i} href={circ.circFilelink} target="_blank" rel="noopener noreferrer"
            style={{ display: "block", padding: "6px 0", borderBottom: "1px solid #1a1a1a", textDecoration: "none" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 2 }}>
              <span style={{
                fontSize: 9, padding: "1px 5px", borderRadius: 2, flexShrink: 0,
                background: (catColor[circ.circCategory] || "#555") + "20",
                color: catColor[circ.circCategory] || "#555",
              }}>{circ.circCategory}</span>
              <span style={{ fontSize: 9, color: "#444" }}>{circ.circDepartment}</span>
              <span style={{ fontSize: 9, color: "#333", marginLeft: "auto" }}>{circ.circDisplayDate}</span>
            </div>
            <div style={{ fontSize: 11, color: "#ccc", lineHeight: 1.35 }}>
              {circ.sub?.slice(0, 100)}{(circ.sub?.length || 0) > 100 ? "…" : ""}
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}

interface DailyReport {
  name: string;
  type: string;
  category: string;
  section: string;
  link: string;
}

function BlockDeals() {
  const [reports, setReports] = useState<DailyReport[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.nseDailyReports()
      .then(d => {
        const arr = Array.isArray(d) ? d as DailyReport[] : [];
        setReports(arr.slice(0, 12));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div>{Array.from({length: 5}).map((_,i) => <div key={i} className="skeleton" style={{ height: 28, marginBottom: 4, borderRadius: 4 }} />)}</div>;
  if (reports.length === 0) return <div style={{ color: "#555", fontSize: 11 }}>Daily reports unavailable</div>;

  const catColor: Record<string, string> = {
    "capital-market": "#3b82f6",
    "derivatives": "#8b5cf6",
    "currency": "#f59e0b",
    "commodity": "#22c55e",
  };

  return (
    <div style={{ maxHeight: 280, overflow: "auto" }}>
      {reports.map((r, i) => (
        <a key={i} href={r.link} target="_blank" rel="noopener noreferrer"
          style={{ display: "flex", alignItems: "center", gap: 8, padding: "5px 0", borderBottom: "1px solid #1a1a1a", textDecoration: "none" }}>
          <span style={{
            fontSize: 9, padding: "1px 5px", borderRadius: 3, flexShrink: 0,
            background: (catColor[r.category] || "#555") + "20",
            color: catColor[r.category] || "#555",
            fontWeight: 600,
          }}>{r.section?.toUpperCase() || r.category?.toUpperCase()}</span>
          <span style={{ fontSize: 10, color: "#aaa", lineHeight: 1.3, flex: 1 }}>{r.name.replace(/\s*\(.*?\)\s*/g, " ").trim()}</span>
          <span style={{ fontSize: 9, color: "#444", flexShrink: 0 }}>↗</span>
        </a>
      ))}
    </div>
  );
}

function CorporateCalendar({ symbol }: { symbol: string }) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    api.nseCorporateInfo(symbol)
      .then(d => setData(d as Record<string, unknown>))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [symbol]);

  if (loading) return <div className="skeleton" style={{ height: 80, borderRadius: 6 }} />;
  if (!data) return <div style={{ color: "#555", fontSize: 11 }}>No corporate data</div>;

  const meetings = (data.corporateInfo as Record<string, unknown>)?.boardMeetings as unknown[] ?? [];
  const dividends = (data.corporateInfo as Record<string, unknown>)?.dividends as unknown[] ?? [];
  const results = (data.corporateInfo as Record<string, unknown>)?.companyResults as unknown[] ?? [];

  return (
    <div>
      {meetings.slice(0, 3).map((m, i) => {
        const d = m as Record<string, unknown>;
        return (
          <div key={i} style={{ padding: "5px 0", borderBottom: "1px solid #1a1a1a" }}>
            <span style={{ fontSize: 10, color: "#3b82f6", marginRight: 8 }}>BOARD</span>
            <span style={{ fontSize: 11, color: "#d4d4d4" }}>{String(d.purpose || d.bm_purpose || "Meeting")}</span>
            <span style={{ fontSize: 10, color: "#555", marginLeft: 8 }}>{String(d.date || d.bm_date || "")}</span>
          </div>
        );
      })}
      {dividends.slice(0, 2).map((d, i) => {
        const div = d as Record<string, unknown>;
        return (
          <div key={i} style={{ padding: "5px 0", borderBottom: "1px solid #1a1a1a" }}>
            <span style={{ fontSize: 10, color: "#22c55e", marginRight: 8 }}>DIV</span>
            <span style={{ fontSize: 11, color: "#d4d4d4" }}>{String(div.purpose || div.div_dividend || "Dividend")}</span>
            <span style={{ fontSize: 10, color: "#555", marginLeft: 8 }}>{String(div.exDate || div.ex_date || "")}</span>
          </div>
        );
      })}
      {results.slice(0, 2).map((r, i) => {
        const res = r as Record<string, unknown>;
        return (
          <div key={i} style={{ padding: "5px 0", borderBottom: "1px solid #1a1a1a" }}>
            <span style={{ fontSize: 10, color: "#f59e0b", marginRight: 8 }}>RESULT</span>
            <span style={{ fontSize: 11, color: "#d4d4d4" }}>{String(res.period || res.description || "Quarterly Result")}</span>
            <span style={{ fontSize: 10, color: "#555", marginLeft: 8 }}>{String(res.date || res.fromDate || "")}</span>
          </div>
        );
      })}
      {meetings.length === 0 && dividends.length === 0 && results.length === 0 && (
        <div style={{ color: "#555", fontSize: 11 }}>No upcoming events</div>
      )}
    </div>
  );
}

function TradeInfo({ symbol }: { symbol: string }) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    api.nseTradeInfo(symbol)
      .then(d => setData(d as Record<string, unknown>))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [symbol]);

  if (loading) return <div className="skeleton" style={{ height: 100, borderRadius: 6 }} />;
  if (!data) return <div style={{ color: "#555", fontSize: 11 }}>Trade data unavailable</div>;

  const mkt = (data.markets as Record<string, unknown>)?.tradeInfo as Record<string, unknown> ?? {};
  const sec = (data.securityWiseDP as Record<string, unknown>) ?? {};
  const deliveryPct = parseFloat(String(sec.deliveryToTradedQuantity || mkt.deliveryToTradedQuantity || sec.deliveryQuantity || 0));
  const totalVol = parseFloat(String(mkt.totalTradedVolume || 0));
  const totalVal = parseFloat(String(mkt.totalTradedValue || 0));
  const vwap = parseFloat(String(mkt.vwap || mkt.VWAP || 0));
  const upper = parseFloat(String(mkt.upper_Circuit_Limit || mkt.upperCircuitPrice || 0));
  const lower = parseFloat(String(mkt.lower_Circuit_Limit || mkt.lowerCircuitPrice || 0));

  const metaRows = [
    { label: "Delivery %", value: deliveryPct > 0 ? `${deliveryPct.toFixed(1)}%` : "—", color: deliveryPct > 60 ? "#22c55e" : deliveryPct > 40 ? "#f59e0b" : "#555" },
    { label: "VWAP", value: vwap > 0 ? `₹${vwap.toFixed(2)}` : "—", color: "#888" },
    { label: "Total Volume", value: totalVol > 0 ? `${(totalVol / 1e6).toFixed(2)}M` : "—", color: "#888" },
    { label: "Total Value", value: totalVal > 0 ? `₹${(totalVal / 100).toFixed(0)} Cr` : "—", color: "#888" },
    { label: "Upper Circuit", value: upper > 0 ? `₹${upper.toFixed(2)}` : "—", color: "#22c55e" },
    { label: "Lower Circuit", value: lower > 0 ? `₹${lower.toFixed(2)}` : "—", color: "#ef4444" },
  ];

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
      {metaRows.map(r => (
        <div key={r.label} style={{ padding: "6px 8px", background: "#0e0e0e", borderRadius: 5 }}>
          <div style={{ fontSize: 9, color: "#444", marginBottom: 2 }}>{r.label}</div>
          <div className="num" style={{ fontSize: 13, fontWeight: 600, color: r.color }}>{r.value}</div>
        </div>
      ))}
    </div>
  );
}

// ── Main Dashboard ────────────────────────────────────────────────────

const QUICK_STOCKS = ["HDFCBANK", "TCS", "RELIANCE", "NTPC", "SBIN", "INFY", "ONGC", "HAL"];

export default function DashboardPage() {
  const router = useRouter();
  const [selectedStock, setSelectedStock] = useState("HDFCBANK");
  const [breadth, setBreadth] = useState<Record<string, unknown> | null>(null);
  const [loadingBreadth, setLoadingBreadth] = useState(true);

  useEffect(() => {
    api.breadth()
      .then(d => setBreadth(d as unknown as Record<string, unknown>))
      .catch(() => {})
      .finally(() => setLoadingBreadth(false));
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden" }}>
      <IndexBar />
      <div style={{ flex: 1, overflow: "auto", background: "#080808" }}>
        <div style={{ maxWidth: 1400, margin: "0 auto", padding: "14px 20px" }}>

          {/* Header */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
            <button onClick={() => router.push("/")} style={{ background: "none", border: "none", color: "#555", cursor: "pointer", fontSize: 16 }}>←</button>
            <div>
              <h1 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: "#e5e5e5" }}>Market Intelligence Dashboard</h1>
              <div style={{ fontSize: 10, color: "#555" }}>Live NSE data · Block deals · Corporate actions · Regulatory feed</div>
            </div>
            <div style={{ marginLeft: "auto", fontSize: 11, color: "#444" }}>
              {new Date().toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false })} IST
            </div>
          </div>

          {/* Market Breadth banner */}
          {!loadingBreadth && breadth && (
            <div style={{
              background: "#111", border: "1px solid #1e1e1e", borderRadius: 8,
              padding: "12px 20px", marginBottom: 14,
              display: "flex", alignItems: "center", gap: 32, overflowX: "auto",
            }}>
              <div style={{ display: "flex", gap: 4, alignItems: "center", flexShrink: 0 }}>
                <span style={{ fontSize: 9, color: "#555", letterSpacing: "0.06em" }}>BREADTH</span>
                <span style={{ fontSize: 11, fontWeight: 700, color: String(breadth.breadth_color || "#555") }}>
                  {String(breadth.breadth_signal || "—")}
                </span>
              </div>
              {[
                { label: "Advances", value: String(breadth.advances || 0), color: "#22c55e" },
                { label: "Declines", value: String(breadth.declines || 0), color: "#ef4444" },
                { label: "A/D Ratio", value: String(breadth.adr || "—"), color: "#e5e5e5" },
                { label: "Above 50DMA", value: `${breadth.pct_above_50dma || 0}%`, color: "#3b82f6" },
                { label: "Above 200DMA", value: `${breadth.pct_above_200dma || 0}%`, color: "#8b5cf6" },
                { label: "Median RSI", value: String(breadth.median_rsi || "—"), color: "#f59e0b" },
                { label: "52W Highs", value: String(breadth.near_52w_high || 0), color: "#22c55e" },
                { label: "52W Lows", value: String(breadth.near_52w_low || 0), color: "#ef4444" },
              ].map(s => (
                <div key={s.label} style={{ flexShrink: 0 }}>
                  <div className="num" style={{ fontSize: 16, fontWeight: 700, color: s.color }}>{s.value}</div>
                  <div style={{ fontSize: 9, color: "#555" }}>{s.label}</div>
                </div>
              ))}
            </div>
          )}

          {/* Main grid */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 380px", gap: 12, minWidth: 900 }}>

            {/* Column 1 */}
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <Panel title="NSE MARKET TURNOVER">
                <MarketTurnover />
              </Panel>

              <Panel title="PRE-OPEN AUCTION (9:00 AM)">
                <PreOpenAuction />
              </Panel>

              <Panel title="NSE DAILY REPORTS (DOWNLOAD)">
                <BlockDeals />
              </Panel>
            </div>

            {/* Column 2 */}
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <Panel title="NSE REGULATORY CIRCULARS"
                action={<span style={{ fontSize: 9, color: "#444" }}>Live from NSE</span>}
              >
                <Circulars />
              </Panel>

              <Panel title="SCREENER SIGNALS">
                <QuickScreenerSummary />
              </Panel>
            </div>

            {/* Column 3: stock deep-dive */}
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {/* Stock selector */}
              <Panel title="STOCK DEEP DIVE">
                <div style={{ marginBottom: 12 }}>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 8 }}>
                    {QUICK_STOCKS.map(s => (
                      <button key={s} onClick={() => setSelectedStock(s)} style={{
                        padding: "3px 8px", fontSize: 10, border: "none", borderRadius: 4, cursor: "pointer",
                        background: selectedStock === s ? "#3b82f6" : "#1e1e1e",
                        color: selectedStock === s ? "#fff" : "#666",
                        fontWeight: selectedStock === s ? 600 : 400,
                      }}>{s}</button>
                    ))}
                  </div>
                  <button onClick={() => router.push(`/stock/${selectedStock}`)} style={{
                    width: "100%", padding: "6px", fontSize: 11, border: "1px solid #2e2e2e",
                    borderRadius: 5, cursor: "pointer", background: "#1a1a1a", color: "#3b82f6",
                  }}>Open {selectedStock} Full View →</button>
                </div>

                <div style={{ fontSize: 10, color: "#555", marginBottom: 8, letterSpacing: "0.05em" }}>TRADE INFO</div>
                <TradeInfo symbol={selectedStock} />
              </Panel>

              <Panel title={`${selectedStock} CORPORATE CALENDAR`}>
                <CorporateCalendar symbol={selectedStock} />
              </Panel>

              <Panel title="PAIRS TRADING SIGNALS">
                <PairSignalsMini />
              </Panel>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function QuickScreenerSummary() {
  const [momentum, setMomentum] = useState<unknown[] | null>(null);
  const [meanrev, setMeanrev] = useState<unknown[] | null>(null);
  const [breakout, setBreakout] = useState<unknown[] | null>(null);
  const router = useRouter();

  useEffect(() => {
    api.screenerMomentum().then(r => setMomentum(r.results.slice(0, 5))).catch(() => {});
    api.screenerMeanRev().then(r => setMeanrev(r.results.filter((x: Record<string, unknown>) => x.signal === "strong_buy" || x.signal === "strong_sell").slice(0, 4))).catch(() => {});
    api.screenerBreakout().then(r => setBreakout(r.results.slice(0, 4))).catch(() => {});
  }, []);

  const Section = ({ title, items, color, labelFn, valueFn }: {
    title: string; items: unknown[] | null; color: string;
    labelFn: (d: Record<string, unknown>) => string;
    valueFn: (d: Record<string, unknown>) => string;
  }) => (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 9, color, letterSpacing: "0.06em", marginBottom: 5, fontWeight: 600 }}>{title}</div>
      {!items ? (
        <div className="skeleton" style={{ height: 80, borderRadius: 5 }} />
      ) : items.length === 0 ? (
        <div style={{ fontSize: 10, color: "#444" }}>No signals</div>
      ) : (
        items.map((item, i) => {
          const d = item as Record<string, unknown>;
          return (
            <div key={i} onClick={() => router.push(`/stock/${d.symbol}`)}
              style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", borderBottom: "1px solid #1a1a1a", cursor: "pointer" }}>
              <span style={{ fontSize: 11, color: "#d4d4d4" }}>{String(d.symbol)}</span>
              <span style={{ fontSize: 10, color: "#666" }}>{labelFn(d)}</span>
              <span style={{ fontSize: 11, fontWeight: 600, color, fontFamily: "monospace" }}>{valueFn(d)}</span>
            </div>
          );
        })
      )}
    </div>
  );

  return (
    <div>
      <Section title="▲ TOP MOMENTUM (RS RANK)" items={momentum} color="#22c55e"
        labelFn={d => `RS ${(d.rs_score as number).toFixed(1)}`}
        valueFn={d => `${(d.ret_65d as number) > 0 ? "+" : ""}${(d.ret_65d as number).toFixed(1)}% 65d`} />
      <Section title="⚡ MEAN REVERSION SIGNALS" items={meanrev} color="#f59e0b"
        labelFn={d => `z=${(d.zscore as number).toFixed(2)}`}
        valueFn={d => String(d.signal).replace("_", " ").toUpperCase()} />
      <Section title="🔥 BREAKOUTS" items={breakout} color="#3b82f6"
        labelFn={d => `${(d.vol_ratio as number).toFixed(1)}x vol`}
        valueFn={d => `${(d.distance_52wh_pct as number).toFixed(1)}% from 52H`} />
    </div>
  );
}

function PairSignalsMini() {
  const [pairs, setPairs] = useState<unknown[]>([]);
  const router = useRouter();

  useEffect(() => {
    api.pairs().then(r => {
      const active = r.pairs.filter(p => p.action !== "hold").slice(0, 5);
      setPairs(active);
    }).catch(() => {});
  }, []);

  if (pairs.length === 0) return (
    <div style={{ color: "#555", fontSize: 11 }}>Loading pairs…</div>
  );

  return (
    <div>
      {pairs.map((pair, i) => {
        const p = pair as { sym1: string; sym2: string; current_zscore: number; signal: string; signal_color: string; action: string };
        return (
          <div key={i} style={{ padding: "6px 0", borderBottom: "1px solid #1a1a1a" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: "#e5e5e5" }}>{p.sym1} / {p.sym2}</span>
              <span style={{ fontSize: 10, fontWeight: 700, color: p.signal_color, fontFamily: "monospace" }}>
                z={p.current_zscore > 0 ? "+" : ""}{p.current_zscore.toFixed(2)}
              </span>
            </div>
            <div style={{ fontSize: 10, color: p.signal_color }}>{p.signal}</div>
          </div>
        );
      })}
      <button onClick={() => router.push("/pairs")} style={{
        marginTop: 8, width: "100%", padding: "5px", fontSize: 10, border: "1px solid #2e2e2e",
        borderRadius: 5, cursor: "pointer", background: "none", color: "#3b82f6",
      }}>View All Pairs →</button>
    </div>
  );
}
