'use client';

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import IndexBar from "@/components/IndexBar";
import Watchlist from "@/components/Watchlist";
import { api, fmt, changeClass, changeSign, type NewsArticle } from "@/lib/api";
import { usePrice, usePriceContext } from "@/contexts/PriceContext";

const Chart = dynamic(() => import("@/components/Chart"), { ssr: false, loading: () => <div className="skeleton" style={{ flex: 1, margin: 16 }} /> });
const MonteCarlo = dynamic(() => import("@/components/MonteCarlo"), { ssr: false });

const DEFAULT_SYMBOL = "HDFCBANK";

// ── Tiny sub-components ───────────────────────────────────────────

function Pill({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{
      padding: "3px 10px", background: "none", border: "none", cursor: "pointer",
      fontSize: 10, fontWeight: active ? 700 : 400, letterSpacing: "0.05em",
      color: active ? "#e5e5e5" : "#333",
      borderBottom: active ? "2px solid #3b82f6" : "2px solid transparent",
    }}>{label}</button>
  );
}

function MiniStat({ label, value, color = "#888" }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ textAlign: "center", padding: "0 6px" }}>
      <div className="num" style={{ fontSize: 12, fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: 8, color: "#2a2a2a", marginTop: 1 }}>{label}</div>
    </div>
  );
}

function StockHeader({ symbol }: { symbol: string }) {
  const live = usePrice(symbol);
  const [quote, setQuote] = useState<{ open: number; high: number; low: number; year_high: number; year_low: number; volume: number; market_cap: number } | null>(null);

  useEffect(() => {
    api.quote(symbol).then(d => setQuote(d as unknown as typeof quote)).catch(() => {});
  }, [symbol]);

  const price = live?.price ?? 0;
  const chg = live?.change_pct ?? 0;
  const change = live?.change ?? 0;
  const flash = live?.flash;

  return (
    <div style={{
      padding: "10px 16px", borderBottom: "1px solid #141414",
      display: "flex", alignItems: "center", gap: 0,
    }}>
      {/* Symbol + Price */}
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
          <span style={{ fontSize: 15, fontWeight: 800, color: "#fff", letterSpacing: "-0.02em", fontFamily: "monospace" }}>
            {symbol}
          </span>
          <span className={`num ${flash ? (flash === "up" ? "gain" : "loss") : changeClass(chg)} ${flash === "up" ? "price-flash-up" : flash === "down" ? "price-flash-down" : ""}`}
            style={{ fontSize: 20, fontWeight: 700 }}>
            {price > 0 ? `₹${fmt(price)}` : "—"}
          </span>
          <span className={`num ${changeClass(chg)}`} style={{ fontSize: 13, fontWeight: 600 }}>
            {changeSign(chg)}{fmt(chg)}% ({changeSign(change)}₹{Math.abs(change).toFixed(2)})
          </span>
        </div>
      </div>

      {/* OHLCV mini stats */}
      {quote && (
        <div style={{ display: "flex", gap: 0, borderLeft: "1px solid #141414", paddingLeft: 12 }}>
          <MiniStat label="OPEN"  value={`₹${fmt(quote.open)}`} />
          <MiniStat label="HIGH"  value={`₹${fmt(quote.high)}`}  color="#00d084" />
          <MiniStat label="LOW"   value={`₹${fmt(quote.low)}`}   color="#ff3b3b" />
          <MiniStat label="52W H" value={`₹${fmt(quote.year_high)}`} color="#00d084" />
          <MiniStat label="52W L" value={`₹${fmt(quote.year_low)}`}  color="#ff3b3b" />
          <MiniStat label="VOL"   value={quote.volume > 1e6 ? `${(quote.volume/1e6).toFixed(1)}M` : `${(quote.volume/1e3).toFixed(0)}K`} />
          <MiniStat label="MCAP"  value={quote.market_cap > 1e5 ? `₹${(quote.market_cap/1e7).toFixed(0)}K Cr` : "—"} />
        </div>
      )}
    </div>
  );
}

interface PatternData {
  trend: string; support: number; resistance: number; ma5: number; ma20: number;
  patterns: { name: string; signal: string; conf: number }[];
  mean_reversion?: { signal: string; zscore: number; rsi: number };
  breakout?: { type: string; vol_ratio: number };
}

function QuickSignalsBar({ symbol }: { symbol: string }) {
  const [patterns, setPatterns] = useState<PatternData | null>(null);

  useEffect(() => {
    setPatterns(null);
    api.patterns(symbol).then(d => setPatterns(d as unknown as PatternData)).catch(() => {});
  }, [symbol]);

  if (!patterns) return (
    <div style={{ height: 28, padding: "0 16px", display: "flex", alignItems: "center", gap: 6 }}>
      <div className="skeleton" style={{ width: 80, height: 16 }} />
      <div className="skeleton" style={{ width: 100, height: 16 }} />
    </div>
  );

  const mr = patterns.mean_reversion as { signal: string; zscore: number; rsi: number } | undefined;
  const br = patterns.breakout as { type: string; vol_ratio: number } | undefined;

  return (
    <div style={{
      padding: "4px 16px", borderBottom: "1px solid #141414",
      display: "flex", alignItems: "center", gap: 6, overflowX: "auto", flexShrink: 0,
    }}>
      {/* Trend */}
      <span style={{
        fontSize: 9, padding: "2px 6px", borderRadius: 2, fontWeight: 700, fontFamily: "monospace",
        background: patterns.trend === "uptrend" ? "rgba(0,208,132,0.1)" : patterns.trend === "downtrend" ? "rgba(255,59,59,0.1)" : "rgba(85,85,85,0.1)",
        color: patterns.trend === "uptrend" ? "#00d084" : patterns.trend === "downtrend" ? "#ff3b3b" : "#555",
      }}>{patterns.trend.toUpperCase()}</span>

      {patterns.patterns.map((p, i) => (
        <span key={i} style={{
          fontSize: 9, padding: "2px 6px", borderRadius: 2,
          background: p.signal === "bullish" ? "rgba(0,208,132,0.08)" : p.signal === "bearish" ? "rgba(255,59,59,0.08)" : "rgba(85,85,85,0.08)",
          color: p.signal === "bullish" ? "#00d084" : p.signal === "bearish" ? "#ff3b3b" : "#555",
          whiteSpace: "nowrap",
        }}>{p.name} <span style={{ opacity: 0.5 }}>{Math.round(p.conf * 100)}%</span></span>
      ))}

      {mr && mr.signal !== "neutral" && (
        <span style={{ fontSize: 9, padding: "2px 6px", borderRadius: 2, background: "rgba(245,158,11,0.1)", color: "#f59e0b" }}>
          {mr.signal.replace("_", " ").toUpperCase()} z={mr.zscore?.toFixed(2)} RSI={Math.round(mr.rsi)}
        </span>
      )}

      {br && br.type === "breakout" && (
        <span style={{ fontSize: 9, padding: "2px 6px", borderRadius: 2, background: "rgba(59,130,246,0.1)", color: "#3b82f6" }}>
          BREAKOUT {br.vol_ratio?.toFixed(1)}x VOL
        </span>
      )}

      <div style={{ marginLeft: "auto", display: "flex", gap: 8, flexShrink: 0 }}>
        <span className="num" style={{ fontSize: 9, color: "#2a2a2a" }}>S ₹{patterns.support?.toFixed(0)}</span>
        <span className="num" style={{ fontSize: 9, color: "#2a2a2a" }}>R ₹{patterns.resistance?.toFixed(0)}</span>
        <span className="num" style={{ fontSize: 9, color: "#2a2a2a" }}>MA5 ₹{patterns.ma5?.toFixed(0)}</span>
        <span className="num" style={{ fontSize: 9, color: "#2a2a2a" }}>MA20 ₹{patterns.ma20?.toFixed(0)}</span>
      </div>
    </div>
  );
}

function FearGreedWidget() {
  const [fg, setFg] = useState<{ score: number; label: string; color: string } | null>(null);

  useEffect(() => {
    api.fearGreed().then(d => setFg(d)).catch(() => {});
    const id = setInterval(() => api.fearGreed().then(d => setFg(d)).catch(() => {}), 300000);
    return () => clearInterval(id);
  }, []);

  if (!fg) return <div className="skeleton" style={{ height: 40, borderRadius: 3 }} />;

  const pct = (fg.score / 100) * 100;
  return (
    <div style={{ padding: "8px 10px", borderBottom: "1px solid #141414" }}>
      <div style={{ fontSize: 9, color: "#333", marginBottom: 5, letterSpacing: "0.08em" }}>FEAR & GREED</div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ flex: 1, height: 4, background: "#141414", borderRadius: 2 }}>
          <div style={{ width: `${pct}%`, height: "100%", background: fg.color, borderRadius: 2, transition: "width 0.5s" }} />
        </div>
        <span className="num" style={{ fontSize: 13, fontWeight: 700, color: fg.color, minWidth: 28 }}>{Math.round(fg.score)}</span>
      </div>
      <div style={{ fontSize: 9, color: fg.color, marginTop: 3, fontWeight: 600 }}>{fg.label}</div>
    </div>
  );
}

function LiveNewsFeed() {
  const router = useRouter();
  const [articles, setArticles] = useState<{ title: string; url?: string; sentiment?: string; source?: string; age_hours?: number; tags?: string[] }[]>([]);

  useEffect(() => {
    api.marketNews().then(r => setArticles(r.articles.slice(0, 25))).catch(() => {});
    const id = setInterval(() => api.marketNews().then(r => setArticles(r.articles.slice(0, 25))).catch(() => {}), 180000);
    return () => clearInterval(id);
  }, []);

  const sentColor = (s?: string) => s === "positive" ? "#00d084" : s === "negative" ? "#ff3b3b" : "#333";

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{ padding: "6px 10px", borderBottom: "1px solid #141414", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: 9, color: "#333", letterSpacing: "0.08em", fontWeight: 700 }}>MARKET FEED</span>
        <button onClick={() => router.push("/news")} style={{ background: "none", border: "none", fontSize: 9, color: "#2a2a2a", cursor: "pointer" }}>ALL →</button>
      </div>
      <div style={{ flex: 1, overflowY: "auto" }}>
        {articles.length === 0 ? (
          <div style={{ padding: 10 }}>
            {Array.from({ length: 6 }).map((_, i) => <div key={i} className="skeleton" style={{ height: 44, marginBottom: 3 }} />)}
          </div>
        ) : (
          articles.map((a, i) => (
            <a key={i} href={a.url} target="_blank" rel="noopener noreferrer"
              style={{ display: "block", padding: "7px 10px", borderBottom: "1px solid #0d0d0d", textDecoration: "none" }}
              onMouseEnter={e => (e.currentTarget.style.background = "#0a0a0a")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 2 }}>
                <div style={{ width: 5, height: 5, borderRadius: "50%", background: sentColor(a.sentiment), flexShrink: 0 }} />
                <span style={{ fontSize: 9, color: "#2a2a2a" }}>{a.source}</span>
                <span style={{ fontSize: 9, color: "#1a1a1a", marginLeft: "auto" }}>
                  {a.age_hours != null ? (a.age_hours < 1 ? "<1h" : `${a.age_hours}h`) : ""}
                </span>
              </div>
              <div style={{ fontSize: 11, color: "#888", lineHeight: 1.3 }}>
                {a.title.slice(0, 90)}{a.title.length > 90 ? "…" : ""}
              </div>
              {a.tags && a.tags.length > 0 && a.tags[0] !== "general" && (
                <div style={{ fontSize: 8, color: "#222", marginTop: 2 }}>{a.tags.join(" · ")}</div>
              )}
            </a>
          ))
        )}
      </div>
    </div>
  );
}

// ── Main Terminal ─────────────────────────────────────────────────

type TabKey = "chart" | "technicals" | "montecarlo";
type ChartPeriod = "1D" | "1W" | "1M" | "3M" | "1Y" | "2Y";

const PERIOD_MAP: Record<ChartPeriod, [string, string]> = {
  "1D": ["1d", "5m"],
  "1W": ["5d", "15m"],
  "1M": ["1mo", "1d"],
  "3M": ["3mo", "1d"],
  "1Y": ["1y", "1d"],
  "2Y": ["2y", "1wk"],
};

export default function TerminalPage() {
  const router = useRouter();
  const { connected, lastUpdate } = usePriceContext();
  const [symbol, setSymbol] = useState(DEFAULT_SYMBOL);
  const [tab, setTab] = useState<TabKey>("chart");
  const [period, setPeriod] = useState<ChartPeriod>("1D");

  const TABS: { key: TabKey; label: string }[] = [
    { key: "chart",      label: "CHART"       },
    { key: "technicals", label: "TECHNICAL"   },
    { key: "montecarlo", label: "MONTE CARLO" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden", background: "#000" }}>
      <IndexBar />

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Left: Watchlist */}
        <Watchlist activeSymbol={symbol} />

        {/* Center: Main chart/analysis area */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 }}>
          {/* Stock header */}
          <StockHeader symbol={symbol} />

          {/* Signals bar */}
          <QuickSignalsBar symbol={symbol} />

          {/* Tab bar */}
          <div style={{ display: "flex", alignItems: "center", borderBottom: "1px solid #141414", padding: "0 10px", flexShrink: 0 }}>
            {TABS.map(t => <Pill key={t.key} label={t.label} active={tab === t.key} onClick={() => setTab(t.key)} />)}
            <div style={{ flex: 1 }} />
            {tab === "chart" && (
              <div style={{ display: "flex", gap: 2 }}>
                {(Object.keys(PERIOD_MAP) as ChartPeriod[]).map(p => (
                  <button key={p} onClick={() => setPeriod(p)} style={{
                    padding: "2px 7px", background: period === p ? "#141414" : "none",
                    border: "none", cursor: "pointer", fontSize: 9, fontWeight: period === p ? 700 : 400,
                    color: period === p ? "#e5e5e5" : "#333", borderRadius: 2,
                  }}>{p}</button>
                ))}
              </div>
            )}
            <button
              onClick={() => router.push(`/stock/${symbol}`)}
              style={{ padding: "2px 8px", background: "none", border: "none", cursor: "pointer", fontSize: 9, color: "#2a2a2a", marginLeft: 8 }}
            >FULL →</button>
          </div>

          {/* Content area */}
          <div style={{ flex: 1, overflow: "hidden", position: "relative" }}>
            {tab === "chart" && (
              <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
                <div style={{ flex: "0 0 57%", overflow: "hidden", minHeight: 0 }}>
                  <Chart key={`${symbol}-${period}`} symbol={symbol} period={PERIOD_MAP[period][0]} interval={PERIOD_MAP[period][1]} />
                </div>
                <div style={{ flex: 1, overflow: "hidden", minHeight: 0 }}>
                  <StockInfoPanel symbol={symbol} />
                </div>
              </div>
            )}
            {tab === "technicals" && (
              <TechnicalsTab symbol={symbol} />
            )}
            {tab === "montecarlo" && (
              <div style={{ overflow: "auto", height: "100%", padding: 16 }}>
                <MonteCarlo symbol={symbol} />
              </div>
            )}
          </div>
        </div>

        {/* Right: Fear&Greed + News */}
        <div style={{
          width: 270, background: "#050505", borderLeft: "1px solid #141414",
          display: "flex", flexDirection: "column", overflow: "hidden", flexShrink: 0,
        }}>
          <FearGreedWidget />
          <LiveNewsFeed />
        </div>
      </div>

      {/* Status bar */}
      <div style={{
        height: 22, background: "#030303", borderTop: "1px solid #0d0d0d",
        display: "flex", alignItems: "center", padding: "0 12px", gap: 16, flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <div style={{ width: 4, height: 4, borderRadius: "50%", background: connected ? "#00d084" : "#ff3b3b" }} />
          <span style={{ fontSize: 8, color: "#222" }}>{connected ? "SSE CONNECTED" : "RECONNECTING"}</span>
        </div>
        {lastUpdate > 0 && (
          <span style={{ fontSize: 8, color: "#1a1a1a" }}>
            LAST TICK {new Date(lastUpdate * 1000).toLocaleTimeString("en-IN", { hour12: false })}
          </span>
        )}
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 8, color: "#1a1a1a" }}>⌘K SEARCH</span>
        <span style={{ fontSize: 8, color: "#1a1a1a" }}>IndiaHedge Terminal v3</span>
      </div>
    </div>
  );
}

function EarningsCol({ symbol }: { symbol: string }) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const livePrice = usePrice(symbol);

  useEffect(() => {
    setData(null);
    api.earnings(symbol).then(r => setData(r as Record<string, unknown>)).catch(() => {});
  }, [symbol]);

  const price = livePrice?.price ?? 0;

  const fmtCr = (v: unknown) => {
    const n = Number(v);
    if (!n || isNaN(n)) return "—";
    if (Math.abs(n) >= 1e9) return `₹${(n / 1e7).toFixed(0)}K Cr`;
    if (Math.abs(n) >= 1e7) return `₹${(n / 1e7).toFixed(1)} Cr`;
    return `₹${(n / 1e5).toFixed(0)} L`;
  };

  const qEps = data?.quarterly_eps as { date: string; actual: number; estimate: number }[] | undefined;
  const qFin = data?.quarterly_financials as { date: string; total_revenue: number; net_income: number; operating_income: number }[] | undefined;

  const metricColor = (v: unknown) => {
    const n = Number(v);
    return n > 0 ? "#00d084" : n < 0 ? "#ff3b3b" : "#888";
  };

  const metrics = data ? [
    { label: "ROCE",     value: data.roce != null ? `${Number(data.roce).toFixed(1)}%` : "—",    color: data.roce != null ? (Number(data.roce) > 15 ? "#00d084" : Number(data.roce) > 8 ? "#f59e0b" : "#ff3b3b") : "#444" },
    { label: "ROE",      value: data.roe  != null ? `${Number(data.roe).toFixed(1)}%`  : "—",    color: data.roe  != null ? metricColor(data.roe)  : "#444" },
    { label: "OPM",      value: data.operating_margin != null ? `${Number(data.operating_margin).toFixed(1)}%` : "—", color: "#888" },
    { label: "NPM",      value: data.net_margin != null ? `${Number(data.net_margin).toFixed(1)}%` : "—", color: "#888" },
    { label: "Rev Gr",   value: data.revenue_growth  != null ? `${changeSign(Number(data.revenue_growth))}${Number(data.revenue_growth).toFixed(1)}%`  : "—", color: metricColor(data.revenue_growth)  },
    { label: "EPS Gr",   value: data.earnings_growth != null ? `${changeSign(Number(data.earnings_growth))}${Number(data.earnings_growth).toFixed(1)}%` : "—", color: metricColor(data.earnings_growth) },
    { label: "P/E",      value: data.pe_ratio  != null ? `${Number(data.pe_ratio).toFixed(1)}x`  : "—", color: "#888" },
    { label: "Fwd P/E",  value: data.forward_pe != null ? `${Number(data.forward_pe).toFixed(1)}x` : "—", color: "#888" },
    { label: "D/E",      value: data.debt_to_equity != null ? `${Number(data.debt_to_equity).toFixed(2)}x` : "—", color: Number(data.debt_to_equity) > 1 ? "#ff3b3b" : "#888" },
    { label: "EV/EBITDA",value: (() => { const e = Number(data.ebitda); const mc = price > 0 && data.total_revenue ? price : 0; return e > 0 ? "—" : "—"; })(), color: "#888" },
  ] : [];

  return (
    <div style={{ flex: 0.9, borderRight: "1px solid #141414", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{ padding: "3px 10px", borderBottom: "1px solid #141414", flexShrink: 0 }}>
        <span style={{ fontSize: 8, color: "#333", letterSpacing: "0.1em", fontWeight: 700 }}>
          EARNINGS & FINANCIALS
        </span>
      </div>
      <div style={{ flex: 1, overflowY: "auto", padding: "6px 8px" }}>
        {!data ? (
          <div className="skeleton" style={{ height: 80 }} />
        ) : (
          <>
            {/* Company + sector */}
            <div style={{ fontSize: 9, color: "#555", marginBottom: 5, lineHeight: 1.4 }}>
              {data.sector as string} · {data.industry as string}
            </div>
            {/* Key metrics grid */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 2, marginBottom: 6 }}>
              {metrics.filter(m => m.value !== "—").map((m, i) => (
                <div key={i} style={{ padding: "2px 5px", background: "#0a0a0a", borderRadius: 2 }}>
                  <div style={{ fontSize: 7, color: "#2a2a2a" }}>{m.label}</div>
                  <div className="num" style={{ fontSize: 10, fontWeight: 700, color: m.color }}>{m.value}</div>
                </div>
              ))}
            </div>
            {/* Quarterly EPS trend */}
            {qEps && qEps.length > 0 && (
              <div style={{ marginBottom: 5 }}>
                <div style={{ fontSize: 7, color: "#333", marginBottom: 2, letterSpacing: "0.06em" }}>QUARTERLY EPS</div>
                {qEps.slice(0, 4).map((q, i) => (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "2px 0", borderBottom: "1px solid #0d0d0d", fontSize: 9 }}>
                    <span style={{ color: "#444" }}>{q.date}</span>
                    <span className="num" style={{ color: q.actual != null ? (q.actual >= 0 ? "#00d084" : "#ff3b3b") : "#333" }}>
                      ₹{q.actual?.toFixed(2) ?? "—"}
                      {q.estimate != null && <span style={{ color: "#2a2a2a", marginLeft: 3 }}>e:{q.estimate?.toFixed(2)}</span>}
                    </span>
                  </div>
                ))}
              </div>
            )}
            {/* Latest quarter revenue */}
            {qFin && qFin.length > 0 && (
              <div style={{ fontSize: 9, color: "#444", marginTop: 4 }}>
                <span>Rev: </span>
                <span className="num" style={{ color: "#888" }}>{fmtCr(qFin[0]?.total_revenue)}</span>
                <span style={{ marginLeft: 8 }}>PAT: </span>
                <span className="num" style={{ color: qFin[0]?.net_income > 0 ? "#00d084" : "#ff3b3b" }}>
                  {fmtCr(qFin[0]?.net_income)}
                </span>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function StockInfoPanel({ symbol }: { symbol: string }) {
  const [stockNews, setStockNews] = useState<NewsArticle[] | null>(null);
  const [tradeInfo, setTradeInfo] = useState<Record<string, unknown> | null>(null);
  const [techInd, setTechInd] = useState<Record<string, unknown> | null>(null);
  const livePrice = usePrice(symbol);

  useEffect(() => {
    setStockNews(null); setTradeInfo(null); setTechInd(null);
    api.news(symbol).then(r => setStockNews(r.articles)).catch(() => {});
    api.nseTradeInfo(symbol).then(r => setTradeInfo(r as Record<string, unknown>)).catch(() => {});
    api.technicals(symbol).then(r => setTechInd(r.indicators as unknown as Record<string, unknown>)).catch(() => {});
  }, [symbol]);

  const price = livePrice?.price ?? 0;

  const tiData = (tradeInfo?.data || tradeInfo) as Record<string, unknown> | null;
  const orderBook = tiData?.marketDeptOrderBook as { bid?: { price: string; quantity: string }[]; ask?: { price: string; quantity: string }[] } | undefined;
  const tradeStats = tiData?.tradeInfo as { vwap?: string | number; deliveryToTradedQuantity?: string | number; totalTradedVolume?: string | number } | undefined;

  const rsi = techInd?.rsi as number | undefined;
  const sma20 = techInd?.sma_20 as number | undefined;
  const sma50 = techInd?.sma_50 as number | undefined;
  const sma200 = techInd?.sma_200 as number | undefined;
  const trend = techInd?.trend as string | undefined;
  const volRatio = techInd?.volume_ratio as number | undefined;

  const smaDevs = price > 0 ? [
    { label: "vs SMA20",  val: sma20  ? ((price - sma20)  / sma20)  * 100 : null, ref: sma20  },
    { label: "vs SMA50",  val: sma50  ? ((price - sma50)  / sma50)  * 100 : null, ref: sma50  },
    { label: "vs SMA200", val: sma200 ? ((price - sma200) / sma200) * 100 : null, ref: sma200 },
  ] : [];

  const sentColor = (s?: string) => s === "positive" ? "#00d084" : s === "negative" ? "#ff3b3b" : "#333";

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden", background: "#040404", borderTop: "1px solid #141414" }}>

      {/* Col 1 — Stock News */}
      <div style={{ flex: 1.2, borderRight: "1px solid #141414", display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <div style={{ padding: "3px 10px", borderBottom: "1px solid #141414", flexShrink: 0 }}>
          <span style={{ fontSize: 8, color: "#333", letterSpacing: "0.1em", fontWeight: 700 }}>STOCK NEWS</span>
        </div>
        <div style={{ flex: 1, overflowY: "auto" }}>
          {!stockNews ? (
            <div style={{ padding: "6px 8px" }}>
              {[0, 1, 2].map(i => <div key={i} className="skeleton" style={{ height: 42, marginBottom: 3 }} />)}
            </div>
          ) : stockNews.length === 0 ? (
            <div style={{ padding: 10, fontSize: 9, color: "#2a2a2a" }}>No news found</div>
          ) : stockNews.slice(0, 6).map((a, i) => (
            <a key={i} href={a.url} target="_blank" rel="noopener noreferrer"
              style={{ display: "block", padding: "5px 8px", borderBottom: "1px solid #0d0d0d", textDecoration: "none" }}
              onMouseEnter={e => (e.currentTarget.style.background = "#0a0a0a")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 1 }}>
                <div style={{ width: 4, height: 4, borderRadius: "50%", flexShrink: 0, background: sentColor(a.sentiment) }} />
                <span style={{ fontSize: 8, color: "#222" }}>{a.source}</span>
                <span style={{ fontSize: 8, color: "#1a1a1a", marginLeft: "auto" }}>
                  {a.age_hours < 1 ? "<1h" : a.age_hours < 24 ? `${Math.round(a.age_hours)}h` : `${a.age_days}d`}
                </span>
              </div>
              <div style={{ fontSize: 10, color: "#666", lineHeight: 1.3 }}>
                {a.title.slice(0, 78)}{a.title.length > 78 ? "…" : ""}
              </div>
            </a>
          ))}
        </div>
      </div>

      {/* Col 2 — Earnings + ROCE */}
      <EarningsCol symbol={symbol} />

      {/* Col 3 — Order Book */}
      <div style={{ flex: 0.8, borderRight: "1px solid #141414", display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <div style={{ padding: "3px 10px", borderBottom: "1px solid #141414", flexShrink: 0 }}>
          <span style={{ fontSize: 8, color: "#333", letterSpacing: "0.1em", fontWeight: 700 }}>ORDER BOOK</span>
        </div>
        <div style={{ flex: 1, overflowY: "auto", padding: "6px 8px" }}>
          {tradeStats && (
            <div style={{ display: "flex", gap: 8, marginBottom: 6, flexWrap: "wrap" }}>
              {tradeStats.vwap != null && (
                <span style={{ fontSize: 9 }}>
                  <span style={{ color: "#333" }}>VWAP </span>
                  <span className="num" style={{ color: "#888" }}>₹{Number(tradeStats.vwap).toFixed(2)}</span>
                </span>
              )}
              {tradeStats.deliveryToTradedQuantity != null && (
                <span style={{ fontSize: 9 }}>
                  <span style={{ color: "#333" }}>DEL </span>
                  <span className="num" style={{ color: "#888" }}>{Number(tradeStats.deliveryToTradedQuantity).toFixed(1)}%</span>
                </span>
              )}
            </div>
          )}
          {orderBook ? (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 2 }}>
              <div>
                <div style={{ fontSize: 7, color: "#00d084", marginBottom: 2, letterSpacing: "0.06em" }}>BID</div>
                {(orderBook.bid || []).slice(0, 5).map((b, i) => (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: 8, padding: "2px 0", borderBottom: "1px solid #0d0d0d" }}>
                    <span className="num" style={{ color: "#00d08490" }}>₹{Number(b.price).toFixed(1)}</span>
                    <span className="num" style={{ color: "#444" }}>{Number(b.quantity).toLocaleString("en-IN")}</span>
                  </div>
                ))}
              </div>
              <div>
                <div style={{ fontSize: 7, color: "#ff3b3b", marginBottom: 2, letterSpacing: "0.06em" }}>ASK</div>
                {(orderBook.ask || []).slice(0, 5).map((a, i) => (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: 8, padding: "2px 0", borderBottom: "1px solid #0d0d0d" }}>
                    <span className="num" style={{ color: "#ff3b3b90" }}>₹{Number(a.price).toFixed(1)}</span>
                    <span className="num" style={{ color: "#444" }}>{Number(a.quantity).toLocaleString("en-IN")}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div style={{ fontSize: 8, color: "#1a1a1a" }}>Fetching depth…</div>
          )}
        </div>
      </div>

      {/* Col 4 — Trend & Mean Deviation */}
      <div style={{ flex: 0.8, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <div style={{ padding: "3px 10px", borderBottom: "1px solid #141414", flexShrink: 0 }}>
          <span style={{ fontSize: 8, color: "#333", letterSpacing: "0.1em", fontWeight: 700 }}>TREND & DEVIATION</span>
        </div>
        <div style={{ flex: 1, overflowY: "auto", padding: "8px 8px" }}>
          {!techInd ? (
            <div className="skeleton" style={{ height: 80 }} />
          ) : (
            <>
              {rsi != null && (
                <div style={{ marginBottom: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                    <span style={{ fontSize: 9, color: "#444" }}>RSI (14)</span>
                    <span className="num" style={{
                      fontSize: 9, fontWeight: 700,
                      color: rsi > 70 ? "#ff3b3b" : rsi < 30 ? "#00d084" : "#888",
                    }}>
                      {rsi.toFixed(1)}{rsi > 70 ? " OB" : rsi < 30 ? " OS" : ""}
                    </span>
                  </div>
                  <div style={{ height: 3, background: "#141414", borderRadius: 2, overflow: "hidden" }}>
                    <div style={{
                      width: `${Math.min(rsi, 100)}%`, height: "100%", borderRadius: 2,
                      background: rsi > 70 ? "#ff3b3b" : rsi < 30 ? "#00d084" : "#3b82f6",
                    }} />
                  </div>
                </div>
              )}
              {smaDevs.filter(d => d.val != null).map((d, i) => (
                <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "3px 0", borderBottom: "1px solid #0d0d0d" }}>
                  <span style={{ fontSize: 9, color: "#444" }}>{d.label}</span>
                  <span className={`num ${changeClass(d.val!)}`} style={{ fontSize: 9, fontWeight: 600 }}>
                    {changeSign(d.val!)}{d.val!.toFixed(2)}%
                  </span>
                </div>
              ))}
              {trend && (
                <div style={{
                  marginTop: 6, padding: "3px 7px", borderRadius: 2, fontSize: 8, fontWeight: 700,
                  textTransform: "uppercase",
                  background: trend === "uptrend" ? "rgba(0,208,132,0.08)" : trend === "downtrend" ? "rgba(255,59,59,0.08)" : "rgba(85,85,85,0.06)",
                  color: trend === "uptrend" ? "#00d084" : trend === "downtrend" ? "#ff3b3b" : "#555",
                }}>{trend}</div>
              )}
              {volRatio != null && (
                <div style={{ marginTop: 6, display: "flex", justifyContent: "space-between" }}>
                  <span style={{ fontSize: 9, color: "#444" }}>Vol Ratio</span>
                  <span className="num" style={{ fontSize: 9, color: volRatio > 1.5 ? "#00d084" : volRatio < 0.5 ? "#ff3b3b" : "#888" }}>
                    {volRatio.toFixed(2)}x
                  </span>
                </div>
              )}
            </>
          )}
        </div>
      </div>

    </div>
  );
}

function TechnicalsTab({ symbol }: { symbol: string }) {
  const [data, setData] = useState<{ symbol: string; indicators: Record<string, unknown> } | null>(null);

  useEffect(() => {
    setData(null);
    api.technicals(symbol).then(d => setData(d as unknown as typeof data)).catch(() => {});
  }, [symbol]);

  if (!data) return (
    <div style={{ padding: 16 }}>
      {Array.from({ length: 6 }).map((_, i) => <div key={i} className="skeleton" style={{ height: 32, marginBottom: 8 }} />)}
    </div>
  );

  const ind = data.indicators as Record<string, unknown>;
  const rows = [
    { label: "RSI (14)", value: ind.rsi != null ? `${(ind.rsi as number).toFixed(1)}` : "—",
      color: (ind.rsi as number) > 70 ? "#ff3b3b" : (ind.rsi as number) < 30 ? "#00d084" : "#888" },
    { label: "MACD", value: ind.macd != null ? `${(ind.macd as number).toFixed(2)}` : "—", color: (ind.macd as number) >= 0 ? "#00d084" : "#ff3b3b" },
    { label: "Signal Line", value: ind.macd_signal != null ? `${(ind.macd_signal as number).toFixed(2)}` : "—", color: "#888" },
    { label: "MACD Hist", value: ind.macd_hist != null ? `${(ind.macd_hist as number).toFixed(2)}` : "—", color: (ind.macd_hist as number) >= 0 ? "#00d084" : "#ff3b3b" },
    { label: "BB Upper", value: ind.bb_upper != null ? `₹${(ind.bb_upper as number).toFixed(2)}` : "—", color: "#ff3b3b" },
    { label: "BB Middle", value: ind.bb_middle != null ? `₹${(ind.bb_middle as number).toFixed(2)}` : "—", color: "#888" },
    { label: "BB Lower", value: ind.bb_lower != null ? `₹${(ind.bb_lower as number).toFixed(2)}` : "—", color: "#00d084" },
    { label: "SMA 20", value: ind.sma_20 != null ? `₹${(ind.sma_20 as number).toFixed(2)}` : "—", color: "#888" },
    { label: "SMA 50", value: ind.sma_50 != null ? `₹${(ind.sma_50 as number).toFixed(2)}` : "—", color: "#888" },
    { label: "SMA 200", value: ind.sma_200 != null ? `₹${(ind.sma_200 as number).toFixed(2)}` : "—", color: "#888" },
    { label: "ATR (14)", value: ind.atr != null ? `₹${(ind.atr as number).toFixed(2)}` : "—", color: "#888" },
    { label: "Volume SMA", value: ind.vol_sma != null ? `${((ind.vol_sma as number)/1e6).toFixed(1)}M` : "—", color: "#888" },
  ].filter(r => r.value !== "—");

  const signal = ind.signal as string | undefined;
  const signalColor = signal?.includes("BUY") || signal?.includes("Bullish") ? "#00d084"
    : signal?.includes("SELL") || signal?.includes("Bearish") ? "#ff3b3b" : "#888";

  return (
    <div style={{ overflow: "auto", height: "100%", padding: 16 }}>
      {signal && (
        <div style={{
          padding: "8px 14px", borderRadius: 4, marginBottom: 16,
          background: `${signalColor}10`, border: `1px solid ${signalColor}22`,
          fontSize: 12, fontWeight: 700, color: signalColor,
        }}>{signal}</div>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
        {rows.map(r => (
          <div key={r.label} style={{ padding: "6px 10px", background: "#0a0a0a", borderRadius: 3 }}>
            <div style={{ fontSize: 9, color: "#333" }}>{r.label}</div>
            <div className="num" style={{ fontSize: 13, fontWeight: 600, color: r.color }}>{r.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
