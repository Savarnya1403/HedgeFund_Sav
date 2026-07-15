'use client';

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import IndexBar from "@/components/IndexBar";
import Watchlist from "@/components/Watchlist";
import Chart from "@/components/Chart";
import AnalysisPanel from "@/components/AnalysisPanel";
import OptionChain from "@/components/OptionChain";
import NewsSection from "@/components/NewsSection";
import TrendPanel from "@/components/TrendPanel";
import MonteCarlo from "@/components/MonteCarlo";
import OptionsAnalytics from "@/components/OptionsAnalytics";
import { api, fmt, fmtCrore, changeClass, changeSign, type StockQuote, type Fundamentals, type TechnicalIndicators } from "@/lib/api";

type Tab = "overview" | "technicals" | "fundamentals" | "options" | "optanalytics" | "montecarlo" | "trends" | "news" | "analysis";

function KV({ label, value, cls }: { label: string; value: string | number | undefined | null; cls?: string }) {
  return (
    <div style={{ padding: "8px 0", borderBottom: "1px solid #1a1a1a" }}>
      <div style={{ fontSize: 10, color: "#555", marginBottom: 2 }}>{label}</div>
      <div className={`num ${cls || ""}`} style={{ fontSize: 12, fontWeight: 500, color: cls ? undefined : "#e5e5e5" }}>
        {value == null ? "—" : value}
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.06em", marginBottom: 12, paddingBottom: 6, borderBottom: "1px solid #1e1e1e" }}>
        {title}
      </div>
      {children}
    </div>
  );
}

function TechGauge({ label, value, min, max, colorFn }: {
  label: string; value: number | undefined; min: number; max: number;
  colorFn: (v: number) => string;
}) {
  if (value == null) return <KV label={label} value={undefined} />;
  const pct = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
  const color = colorFn(value);
  return (
    <div style={{ padding: "8px 0", borderBottom: "1px solid #1a1a1a" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ fontSize: 10, color: "#555" }}>{label}</span>
        <span className="num" style={{ fontSize: 12, fontWeight: 600, color }}>{fmt(value, 1)}</span>
      </div>
      <div style={{ height: 3, background: "#1e1e1e", borderRadius: 2, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 2 }} />
      </div>
    </div>
  );
}

export default function StockPage({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = use(params);
  const router = useRouter();
  const sym = symbol.toUpperCase();

  const [quote, setQuote] = useState<StockQuote | null>(null);
  const [fund, setFund] = useState<Fundamentals | null>(null);
  const [tech, setTech] = useState<TechnicalIndicators | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setQuote(null); setFund(null); setTech(null);
    Promise.all([
      api.quote(sym).catch(() => null),
      api.fundamentals(sym).catch(() => null),
      api.technicals(sym).catch(() => null),
    ]).then(([q, f, t]) => {
      setQuote(q);
      setFund(f?.fundamentals || null);
      setTech(t?.indicators || null);
      setLoading(false);
    });
  }, [sym]);

  useEffect(() => {
    const id = setInterval(() => {
      api.quote(sym).then(setQuote).catch(() => {});
    }, 60000);
    return () => clearInterval(id);
  }, [sym]);

  const tabs: { key: Tab; label: string }[] = [
    { key: "overview", label: "Overview" },
    { key: "technicals", label: "Technicals" },
    { key: "fundamentals", label: "Fundamentals" },
    { key: "trends", label: "Trend Score" },
    { key: "montecarlo", label: "Monte Carlo" },
    { key: "news", label: "News" },
    { key: "options", label: "Option Chain" },
    { key: "optanalytics", label: "Options Analytics" },
    { key: "analysis", label: "AI Analysis" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden" }}>
      <IndexBar />
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <Watchlist activeSymbol={sym} />

        {/* Main content */}
        <div style={{ flex: 1, overflow: "auto", background: "#080808" }}>
          {/* Stock header */}
          <div style={{
            background: "#0d0d0d",
            borderBottom: "1px solid #1e1e1e",
            padding: "14px 20px",
            display: "flex",
            alignItems: "center",
            gap: 16,
          }}>
            <button
              onClick={() => router.push("/")}
              style={{
                background: "none", border: "none", color: "#555",
                cursor: "pointer", fontSize: 16, padding: 0, lineHeight: 1,
              }}
            >←</button>

            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
                <span style={{ fontSize: 18, fontWeight: 700, color: "#fff" }}>{sym}</span>
                {fund?.name && (
                  <span style={{ fontSize: 12, color: "#888" }}>{fund.name}</span>
                )}
                {fund?.sector && (
                  <span style={{ fontSize: 11, color: "#555", background: "#1e1e1e", padding: "1px 8px", borderRadius: 3 }}>
                    {fund.sector}
                  </span>
                )}
              </div>
              {quote && (
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 4, flexWrap: "wrap" }}>
                  <span className="num" style={{ fontSize: 24, fontWeight: 700, color: "#fff" }}>
                    ₹{fmt(quote.price)}
                  </span>
                  <span className={`num ${changeClass(quote.change_pct)}`} style={{ fontSize: 14, fontWeight: 600 }}>
                    {changeSign(quote.change_pct)}{fmt(quote.change)} ({changeSign(quote.change_pct)}{fmt(quote.change_pct)}%)
                  </span>
                  <span style={{ fontSize: 11, color: "#555" }}>NSE</span>
                </div>
              )}
            </div>

            {quote && (
              <div style={{ display: "flex", gap: 20 }}>
                {[
                  { l: "Open", v: fmt(quote.open) },
                  { l: "High", v: fmt(quote.high), c: "gain" },
                  { l: "Low", v: fmt(quote.low), c: "loss" },
                  { l: "Prev Close", v: fmt(quote.prev_close) },
                  { l: "Mkt Cap", v: fmtCrore(quote.market_cap) },
                  { l: "52W High", v: fmt(quote.year_high) },
                  { l: "52W Low", v: fmt(quote.year_low) },
                ].map(item => (
                  <div key={item.l} style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 10, color: "#555" }}>{item.l}</div>
                    <div className={`num ${item.c || ""}`} style={{ fontSize: 12, fontWeight: 500, color: item.c ? undefined : "#e5e5e5" }}>
                      ₹{item.v}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {loading && !quote && (
              <div className="skeleton" style={{ width: 200, height: 40, borderRadius: 6 }} />
            )}
          </div>

          {/* Chart */}
          <div style={{ padding: "16px 20px 0" }}>
            <Chart symbol={sym} height={360} />
          </div>

          {/* Tabs */}
          <div style={{
            display: "flex", borderBottom: "1px solid #1e1e1e",
            padding: "0 20px", marginTop: 16, background: "#0d0d0d",
          }}>
            {tabs.map(t => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                style={{
                  padding: "10px 16px", fontSize: 12,
                  border: "none", borderBottom: tab === t.key ? "2px solid #3b82f6" : "2px solid transparent",
                  background: "transparent",
                  color: tab === t.key ? "#e5e5e5" : "#555",
                  cursor: "pointer",
                  fontWeight: tab === t.key ? 600 : 400,
                }}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div style={{ padding: "20px 20px" }}>

            {/* ── OVERVIEW ── */}
            {tab === "overview" && quote && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 20 }}>
                <Section title="PRICE DATA">
                  <KV label="Current Price" value={`₹${fmt(quote.price)}`} />
                  <KV label="Open" value={`₹${fmt(quote.open)}`} />
                  <KV label="High" value={`₹${fmt(quote.high)}`} cls="gain" />
                  <KV label="Low" value={`₹${fmt(quote.low)}`} cls="loss" />
                  <KV label="Previous Close" value={`₹${fmt(quote.prev_close)}`} />
                  <KV label="Change" value={`${changeSign(quote.change)}₹${fmt(quote.change)} (${changeSign(quote.change_pct)}${fmt(quote.change_pct)}%)`} cls={changeClass(quote.change_pct)} />
                </Section>
                <Section title="TRADING DATA">
                  <KV label="Volume" value={(quote.volume / 1e6).toFixed(2) + "M"} />
                  {quote.vwap ? <KV label="VWAP" value={`₹${fmt(quote.vwap)}`} /> : null}
                  {quote.delivery_pct ? <KV label="Delivery %" value={`${fmt(quote.delivery_pct)}%`} /> : null}
                  {quote.lower_circuit ? <KV label="Lower Circuit" value={`₹${fmt(quote.lower_circuit)}`} cls="loss" /> : null}
                  {quote.upper_circuit ? <KV label="Upper Circuit" value={`₹${fmt(quote.upper_circuit)}`} cls="gain" /> : null}
                  <KV label="Market Cap" value={fmtCrore(quote.market_cap)} />
                </Section>
                <Section title="52-WEEK RANGE">
                  <KV label="52W High" value={`₹${fmt(quote.year_high)}`} cls="gain" />
                  <KV label="52W Low" value={`₹${fmt(quote.year_low)}`} cls="loss" />
                  <KV label="From 52W High" value={`${fmt((quote.price / quote.year_high - 1) * 100)}%`} cls={changeClass(quote.price - quote.year_high)} />
                  <KV label="From 52W Low" value={`+${fmt((quote.price / quote.year_low - 1) * 100)}%`} cls="gain" />
                  {fund?.pe_ratio ? <KV label="P/E Ratio" value={`${fmt(fund.pe_ratio)}x`} /> : null}
                  {fund?.eps ? <KV label="EPS (TTM)" value={`₹${fmt(fund.eps)}`} /> : null}
                </Section>
              </div>
            )}

            {/* ── TECHNICALS ── */}
            {tab === "technicals" && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 20 }}>
                <Section title="MOMENTUM">
                  <TechGauge
                    label="RSI (14)"
                    value={tech?.rsi_14}
                    min={0} max={100}
                    colorFn={v => v > 70 ? "#ef4444" : v < 30 ? "#22c55e" : "#3b82f6"}
                  />
                  <KV label="RSI Signal" value={tech?.rsi_signal} />
                  <KV label="MACD" value={tech ? fmt(tech.macd, 4) : undefined} cls={tech && tech.macd > 0 ? "gain" : "loss"} />
                  <KV label="MACD Signal" value={tech ? fmt(tech.macd_signal, 4) : undefined} />
                  <KV label="MACD Histogram" value={tech ? fmt(tech.macd_histogram, 4) : undefined} cls={tech && tech.macd_histogram > 0 ? "gain" : "loss"} />
                  <KV label="MACD Crossover" value={tech?.macd_crossover} cls={tech?.macd_crossover === "Bullish" ? "gain" : "loss"} />
                </Section>
                <Section title="MOVING AVERAGES">
                  <KV label="SMA 20" value={tech ? `₹${fmt(tech.sma_20)}` : undefined}
                    cls={quote && tech && quote.price > tech.sma_20 ? "gain" : "loss"} />
                  <KV label="SMA 50" value={tech?.sma_50 ? `₹${fmt(tech.sma_50)}` : undefined}
                    cls={quote && tech?.sma_50 && quote.price > tech.sma_50 ? "gain" : "loss"} />
                  <KV label="SMA 200" value={tech?.sma_200 ? `₹${fmt(tech.sma_200)}` : undefined}
                    cls={quote && tech?.sma_200 && quote.price > tech.sma_200 ? "gain" : "loss"} />
                  <KV label="EMA 20" value={tech ? `₹${fmt(tech.ema_20)}` : undefined}
                    cls={quote && tech && quote.price > tech.ema_20 ? "gain" : "loss"} />
                  <KV label="EMA 50" value={tech?.ema_50 ? `₹${fmt(tech.ema_50)}` : undefined}
                    cls={quote && tech?.ema_50 && quote.price > tech.ema_50 ? "gain" : "loss"} />
                  <KV label="Trend" value={tech?.trend}
                    cls={tech?.trend === "Uptrend" ? "gain" : tech?.trend === "Downtrend" ? "loss" : "neutral"} />
                </Section>
                <Section title="LEVELS & VOLATILITY">
                  <KV label="Resistance" value={tech ? `₹${fmt(tech.resistance_1)}` : undefined} cls="loss" />
                  <KV label="Support" value={tech ? `₹${fmt(tech.support_1)}` : undefined} cls="gain" />
                  <KV label="BB Upper" value={tech ? `₹${fmt(tech.bb_upper)}` : undefined} />
                  <KV label="BB Mid" value={tech ? `₹${fmt(tech.bb_mid)}` : undefined} />
                  <KV label="BB Lower" value={tech ? `₹${fmt(tech.bb_lower)}` : undefined} />
                  <KV label="ATR (14)" value={tech ? `₹${fmt(tech.atr)}` : undefined} />
                  <KV label="Volume Ratio" value={tech ? `${fmt(tech.volume_ratio)}x` : undefined}
                    cls={tech && tech.volume_ratio > 1.5 ? "gain" : "neutral"} />
                  <div style={{ marginTop: 12 }}>
                    <div style={{ fontSize: 10, color: "#555", marginBottom: 6 }}>SIGNALS</div>
                    {tech?.signals?.map((s, i) => (
                      <div key={i} style={{
                        fontSize: 11, color: s.includes("Bullish") || s.includes("Above") || s.includes("High Vol") ? "#22c55e"
                          : s.includes("Bearish") || s.includes("Overbought") ? "#ef4444" : "#777",
                        padding: "2px 0",
                      }}>• {s}</div>
                    ))}
                  </div>
                </Section>
              </div>
            )}

            {/* ── FUNDAMENTALS ── */}
            {tab === "fundamentals" && fund && (
              <div>
                {fund.description && (
                  <div style={{
                    background: "#111", border: "1px solid #1e1e1e",
                    borderRadius: 8, padding: 16, marginBottom: 20,
                    fontSize: 12, color: "#777", lineHeight: 1.7,
                  }}>
                    {fund.description}
                  </div>
                )}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 20 }}>
                  <Section title="VALUATION">
                    <KV label="P/E Ratio (TTM)" value={fund.pe_ratio ? `${fmt(fund.pe_ratio)}x` : undefined} />
                    <KV label="Forward P/E" value={fund.forward_pe ? `${fmt(fund.forward_pe)}x` : undefined} />
                    <KV label="P/B Ratio" value={fund.pb_ratio ? `${fmt(fund.pb_ratio)}x` : undefined} />
                    <KV label="EPS (TTM)" value={fund.eps ? `₹${fmt(fund.eps)}` : undefined} />
                    <KV label="Forward EPS" value={fund.forward_eps ? `₹${fmt(fund.forward_eps)}` : undefined} />
                    <KV label="Book Value" value={fund.book_value ? `₹${fmt(fund.book_value)}` : undefined} />
                    <KV label="Dividend Yield" value={fund.dividend_yield ? `${fmt(fund.dividend_yield)}%` : undefined} cls="gain" />
                  </Section>
                  <Section title="PROFITABILITY">
                    <KV label="ROE" value={fund.roe ? `${fmt(fund.roe)}%` : undefined} cls={fund.roe && fund.roe > 15 ? "gain" : "neutral"} />
                    <KV label="ROA" value={fund.roa ? `${fmt(fund.roa)}%` : undefined} />
                    <KV label="Gross Margin" value={fund.gross_margin ? `${fmt(fund.gross_margin)}%` : undefined} />
                    <KV label="Operating Margin" value={fund.operating_margin ? `${fmt(fund.operating_margin)}%` : undefined} />
                    <KV label="Net Margin" value={fund.net_margin ? `${fmt(fund.net_margin)}%` : undefined} cls={fund.net_margin && fund.net_margin > 10 ? "gain" : "neutral"} />
                    <KV label="Revenue Growth" value={fund.revenue_growth ? `${changeSign(fund.revenue_growth)}${fmt(fund.revenue_growth)}%` : undefined} cls={changeClass(fund.revenue_growth)} />
                    <KV label="Earnings Growth" value={fund.earnings_growth ? `${changeSign(fund.earnings_growth)}${fmt(fund.earnings_growth)}%` : undefined} cls={changeClass(fund.earnings_growth)} />
                  </Section>
                  <Section title="BALANCE SHEET">
                    <KV label="Market Cap" value={fmtCrore(fund.market_cap)} />
                    <KV label="Debt / Equity" value={fund.debt_equity ? `${fmt(fund.debt_equity)}x` : undefined}
                      cls={fund.debt_equity && fund.debt_equity < 0.5 ? "gain" : fund.debt_equity && fund.debt_equity > 2 ? "loss" : "neutral"} />
                    <KV label="Current Ratio" value={fund.current_ratio ? `${fmt(fund.current_ratio)}x` : undefined}
                      cls={fund.current_ratio && fund.current_ratio > 1.5 ? "gain" : fund.current_ratio && fund.current_ratio < 1 ? "loss" : "neutral"} />
                    <KV label="Sector" value={fund.sector} />
                    <KV label="Industry" value={fund.industry} />
                    <KV label="Employees" value={fund.employees ? fund.employees.toLocaleString("en-IN") : undefined} />
                  </Section>
                </div>
              </div>
            )}

            {/* ── FUNDAMENTALS loading state ── */}
            {tab === "fundamentals" && !fund && !loading && (
              <div style={{ color: "#555", textAlign: "center", padding: 40, fontSize: 13 }}>
                Fundamental data not available for {sym}
              </div>
            )}

            {/* ── TREND SCORE ── */}
            {tab === "trends" && (
              <TrendPanel symbol={sym} />
            )}

            {/* ── NEWS ── */}
            {tab === "news" && (
              <div style={{ margin: "0 -20px" }}>
                <NewsSection symbol={sym} maxItems={30} />
              </div>
            )}

            {/* ── OPTIONS ── */}
            {tab === "options" && (
              <div style={{ margin: "0 -20px" }}>
                <OptionChain symbol={sym} />
              </div>
            )}

            {/* ── OPTIONS ANALYTICS ── */}
            {tab === "optanalytics" && (
              <OptionsAnalytics symbol={sym} />
            )}

            {/* ── MONTE CARLO ── */}
            {tab === "montecarlo" && (
              <MonteCarlo symbol={sym} />
            )}

            {/* ── ANALYSIS ── */}
            {tab === "analysis" && (
              <div style={{ maxWidth: 800 }}>
                <AnalysisPanel symbol={sym} />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
