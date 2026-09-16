'use client';

import { useState, useEffect, useRef } from "react";
import IndexBar from "@/components/IndexBar";
import { createChart, LineSeries, HistogramSeries, type IChartApi, type Time } from "lightweight-charts";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

const NIFTY50 = [
  "RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","HINDUNILVR","BAJFINANCE",
  "BHARTIARTL","SBIN","KOTAKBANK","ITC","LT","AXISBANK","TITAN","ASIANPAINT",
  "MARUTI","WIPRO","HCLTECH","NTPC","ONGC","TATASTEEL","SUNPHARMA","TECHM",
  "INDUSINDBK","TATAMOTORS","APOLLOHOSP","HEROMOTOCO","BAJAJFINSV","CIPLA","DRREDDY",
];

function signalColor(s: string) {
  if (s === "bullish") return "#22c55e";
  if (s === "bearish") return "#ef4444";
  return "#64748b";
}

function badge(label: string, color: string) {
  return (
    <span style={{
      background: color + "22", color, border: `1px solid ${color}44`,
      borderRadius: 4, padding: "2px 8px", fontSize: 11, fontWeight: 700,
      textTransform: "uppercase", letterSpacing: 1
    }}>{label}</span>
  );
}

interface OFData {
  buying_pressure_ratio: number;
  selling_pressure_ratio: number;
  cumulative_delta: number;
  delta_divergence: string;
  smart_money_flow: string;
  smart_money_score: number;
  obv_trend: string;
  vwap_20d: number;
  vwap_deviation_pct: number;
  volume_imbalance: number;
  signal: string;
  chart_data: Array<{
    date: string; buy_vol: number; sell_vol: number;
    cum_delta: number; obv: number; price: number; volume: number;
  }>;
}

interface DarkPoolData {
  symbol: string;
  event_count_20d: number;
  net_direction: string;
  avg_absorption_score: number;
  interpretation: string;
  absorption_events: Array<{ date: string; price: number; volume: number; vol_ratio: number; absorption_score: number; direction: string }>;
}

interface LiquidityData {
  amihud_illiquidity: number;
  roll_spread_bps: number;
  cs_spread_pct: number;
  avg_dollar_volume_cr: number;
  liquidity_score: number;
  liquidity_grade: string;
  interpretation: string;
}

interface SeasonalityData {
  day_of_week: Record<string, { mean_pct: number; win_rate: number; n: number }>;
  monthly: Record<string, { mean_pct: number; win_rate: number; n: number }>;
  best_day: string; worst_day: string;
  best_month: string; worst_month: string;
  expiry_week_return_pct: number;
  expiry_week_win_rate: number;
}

export default function OrderFlowPage() {
  const [symbol, setSymbol] = useState("RELIANCE");
  const [input, setInput] = useState("RELIANCE");
  const [of, setOf] = useState<OFData | null>(null);
  const [dp, setDp] = useState<DarkPoolData | null>(null);
  const [liq, setLiq] = useState<LiquidityData | null>(null);
  const [sea, setSea] = useState<SeasonalityData | null>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<"flow" | "dark" | "liq" | "season">("flow");

  const deltaRef = useRef<HTMLDivElement>(null);
  const volRef = useRef<HTMLDivElement>(null);

  async function load(sym: string) {
    setLoading(true);
    try {
      const [ofRes, dpRes, liqRes, seaRes] = await Promise.all([
        fetch(`${API}/api/orderflow/${sym}`).then(r => r.json()),
        fetch(`${API}/api/dark-pool/${sym}`).then(r => r.json()),
        fetch(`${API}/api/liquidity/${sym}`).then(r => r.json()),
        fetch(`${API}/api/seasonality/${sym}`).then(r => r.json()),
      ]);
      setOf(ofRes);
      setDp(dpRes);
      setLiq(liqRes);
      setSea(seaRes);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  }

  useEffect(() => { load(symbol); }, [symbol]);

  useEffect(() => {
    if (!of?.chart_data?.length || !deltaRef.current) return;
    deltaRef.current.innerHTML = "";

    const chart = createChart(deltaRef.current, {
      width: deltaRef.current.clientWidth, height: 200,
      layout: { background: { color: "#0a0a0a" }, textColor: "#888", fontSize: 10, fontFamily: "monospace" },
      grid: { vertLines: { color: "#111" }, horzLines: { color: "#111" } },
      rightPriceScale: { scaleMargins: { top: 0.1, bottom: 0.1 } },
      timeScale: { borderColor: "#222" },
    });

    const series = chart.addSeries(LineSeries, { color: "#3b82f6", lineWidth: 2, priceLineVisible: false, lastValueVisible: true, title: "Cum Delta" });
    const data = of.chart_data.map((d, i) => ({
      time: (Math.floor(Date.now() / 1000) - (of.chart_data.length - i) * 86400) as Time,
      value: d.cum_delta,
    }));
    series.setData(data);
    chart.timeScale().fitContent();

    const obs = new ResizeObserver(() => {
      if (deltaRef.current) chart.applyOptions({ width: deltaRef.current.clientWidth });
    });
    obs.observe(deltaRef.current);
    return () => { obs.disconnect(); chart.remove(); };
  }, [of]);

  useEffect(() => {
    if (!of?.chart_data?.length || !volRef.current) return;
    volRef.current.innerHTML = "";

    const chart = createChart(volRef.current, {
      width: volRef.current.clientWidth, height: 160,
      layout: { background: { color: "#0a0a0a" }, textColor: "#888", fontSize: 10, fontFamily: "monospace" },
      grid: { vertLines: { color: "#111" }, horzLines: { color: "#111" } },
      rightPriceScale: { scaleMargins: { top: 0.05, bottom: 0.05 } },
      timeScale: { borderColor: "#222" },
    });

    const buySeries = chart.addSeries(HistogramSeries, { color: "#22c55e88", priceLineVisible: false, lastValueVisible: false, title: "Buy Vol" });
    const sellSeries = chart.addSeries(HistogramSeries, { color: "#ef444488", priceLineVisible: false, lastValueVisible: false, title: "Sell Vol" });

    const now = Math.floor(Date.now() / 1000);
    const len = of.chart_data.length;
    buySeries.setData(of.chart_data.map((d, i) => ({ time: (now - (len - i) * 86400) as Time, value: d.buy_vol })));
    sellSeries.setData(of.chart_data.map((d, i) => ({ time: (now - (len - i) * 86400) as Time, value: -d.sell_vol })));
    chart.timeScale().fitContent();

    const obs = new ResizeObserver(() => {
      if (volRef.current) chart.applyOptions({ width: volRef.current.clientWidth });
    });
    obs.observe(volRef.current);
    return () => { obs.disconnect(); chart.remove(); };
  }, [of]);

  const tabs = [
    { id: "flow", label: "Order Flow" },
    { id: "dark", label: "Dark Pool" },
    { id: "liq", label: "Liquidity" },
    { id: "season", label: "Seasonality" },
  ] as const;

  return (
    <div style={{ background: "#050505", minHeight: "100vh", color: "#e2e8f0", fontFamily: "monospace" }}>
      <IndexBar />
      <div style={{ padding: "16px 24px" }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 11, color: "#64748b", textTransform: "uppercase", letterSpacing: 2 }}>Order Flow Intelligence</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: "#f1f5f9" }}>Market Microstructure</div>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
            <input
              value={input}
              onChange={e => setInput(e.target.value.toUpperCase())}
              onKeyDown={e => { if (e.key === "Enter") { setSymbol(input); } }}
              style={{ background: "#0f0f0f", border: "1px solid #222", borderRadius: 6, padding: "6px 12px", color: "#f1f5f9", fontSize: 13, width: 120, fontFamily: "monospace" }}
              placeholder="Symbol"
            />
            <button
              onClick={() => setSymbol(input)}
              style={{ background: "#1d4ed8", border: "none", borderRadius: 6, padding: "6px 16px", color: "#fff", fontSize: 13, cursor: "pointer" }}
            >
              {loading ? "..." : "Load"}
            </button>
          </div>
        </div>

        {/* Quick symbol strip */}
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 16 }}>
          {NIFTY50.slice(0, 15).map(s => (
            <button key={s} onClick={() => { setSymbol(s); setInput(s); }}
              style={{
                background: symbol === s ? "#1d4ed8" : "#0f0f0f",
                border: `1px solid ${symbol === s ? "#3b82f6" : "#222"}`,
                borderRadius: 4, padding: "3px 10px", color: symbol === s ? "#fff" : "#888",
                fontSize: 11, cursor: "pointer", fontFamily: "monospace"
              }}>{s}</button>
          ))}
        </div>

        {/* Tabs */}
        <div style={{ display: "flex", gap: 4, marginBottom: 16, borderBottom: "1px solid #1a1a1a", paddingBottom: 8 }}>
          {tabs.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              style={{
                background: tab === t.id ? "#1d4ed8" : "transparent",
                border: `1px solid ${tab === t.id ? "#3b82f6" : "#222"}`,
                borderRadius: 6, padding: "5px 16px", color: tab === t.id ? "#fff" : "#64748b",
                fontSize: 12, cursor: "pointer", fontFamily: "monospace"
              }}>{t.label}</button>
          ))}
        </div>

        {/* ORDER FLOW TAB */}
        {tab === "flow" && of && (
          <div>
            {/* Key metrics row */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginBottom: 16 }}>
              {[
                { label: "Signal", value: badge(of.signal, signalColor(of.signal)) },
                { label: "Buying Pressure", value: `${(of.buying_pressure_ratio * 100).toFixed(1)}%` },
                { label: "VWAP Dev", value: `${of.vwap_deviation_pct > 0 ? "+" : ""}${of.vwap_deviation_pct.toFixed(2)}%`, color: of.vwap_deviation_pct > 0 ? "#22c55e" : "#ef4444" },
                { label: "Smart Money", value: badge(of.smart_money_flow, signalColor(of.smart_money_flow)) },
              ].map((m, i) => (
                <div key={i} style={{ background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: 8, padding: "12px 16px" }}>
                  <div style={{ fontSize: 10, color: "#64748b", marginBottom: 4, textTransform: "uppercase", letterSpacing: 1 }}>{m.label}</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: (m as any).color || "#f1f5f9" }}>{m.value}</div>
                </div>
              ))}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginBottom: 16 }}>
              {[
                { label: "Cumulative Delta", value: of.cumulative_delta.toLocaleString(), color: of.cumulative_delta > 0 ? "#22c55e" : "#ef4444" },
                { label: "Delta Divergence", value: of.delta_divergence === "none" ? "—" : of.delta_divergence, color: of.delta_divergence === "bullish" ? "#22c55e" : of.delta_divergence === "bearish" ? "#ef4444" : "#64748b" },
                { label: "OBV Trend", value: of.obv_trend, color: of.obv_trend === "rising" ? "#22c55e" : "#ef4444" },
                { label: "Vol Imbalance", value: `${(of.volume_imbalance * 100).toFixed(1)}%`, color: of.volume_imbalance > 0 ? "#22c55e" : "#ef4444" },
              ].map((m, i) => (
                <div key={i} style={{ background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: 8, padding: "12px 16px" }}>
                  <div style={{ fontSize: 10, color: "#64748b", marginBottom: 4, textTransform: "uppercase", letterSpacing: 1 }}>{m.label}</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: m.color }}>{m.value}</div>
                </div>
              ))}
            </div>

            {/* Cumulative Delta Chart */}
            <div style={{ background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: 8, padding: 16, marginBottom: 12 }}>
              <div style={{ fontSize: 12, color: "#64748b", marginBottom: 8, textTransform: "uppercase", letterSpacing: 1 }}>Cumulative Volume Delta (60 days)</div>
              <div ref={deltaRef} style={{ width: "100%" }} />
            </div>

            {/* Buy/Sell Volume Bars */}
            <div style={{ background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: 8, padding: 16 }}>
              <div style={{ fontSize: 12, color: "#64748b", marginBottom: 8, textTransform: "uppercase", letterSpacing: 1 }}>Buy vs Sell Volume</div>
              <div ref={volRef} style={{ width: "100%" }} />
            </div>
          </div>
        )}

        {/* DARK POOL TAB */}
        {tab === "dark" && dp && (
          <div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginBottom: 16 }}>
              {[
                { label: "Net Direction", value: badge(dp.net_direction, dp.net_direction === "accumulation" ? "#22c55e" : dp.net_direction === "distribution" ? "#ef4444" : "#64748b") },
                { label: "Events (20d)", value: dp.event_count_20d },
                { label: "Avg Absorption", value: dp.avg_absorption_score.toFixed(2) },
                { label: "Symbol", value: dp.symbol },
              ].map((m, i) => (
                <div key={i} style={{ background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: 8, padding: "12px 16px" }}>
                  <div style={{ fontSize: 10, color: "#64748b", marginBottom: 4, textTransform: "uppercase", letterSpacing: 1 }}>{m.label}</div>
                  <div style={{ fontSize: 18, fontWeight: 700 }}>{m.value}</div>
                </div>
              ))}
            </div>
            <div style={{ background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: 8, padding: 12, marginBottom: 16, fontSize: 13, color: "#94a3b8" }}>
              {dp.interpretation}
            </div>
            <div style={{ background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: 8, padding: 16 }}>
              <div style={{ fontSize: 12, color: "#64748b", marginBottom: 12, textTransform: "uppercase", letterSpacing: 1 }}>Absorption Events</div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #1a1a1a", color: "#64748b" }}>
                    {["Date", "Price", "Volume", "Vol Ratio", "Absorption Score", "Direction"].map(h => (
                      <th key={h} style={{ padding: "4px 8px", textAlign: "left", fontWeight: 400 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {dp.absorption_events.map((ev, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid #111" }}>
                      <td style={{ padding: "6px 8px", color: "#94a3b8" }}>{ev.date}</td>
                      <td style={{ padding: "6px 8px" }}>₹{ev.price.toLocaleString()}</td>
                      <td style={{ padding: "6px 8px", color: "#94a3b8" }}>{(ev.volume / 1e6).toFixed(2)}M</td>
                      <td style={{ padding: "6px 8px" }}>{ev.vol_ratio.toFixed(2)}x</td>
                      <td style={{ padding: "6px 8px", color: "#f59e0b" }}>{ev.absorption_score.toFixed(2)}</td>
                      <td style={{ padding: "6px 8px" }}>{badge(ev.direction, ev.direction === "buy" ? "#22c55e" : "#ef4444")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* LIQUIDITY TAB */}
        {tab === "liq" && liq && (
          <div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12, marginBottom: 16 }}>
              {[
                { label: "Liquidity Score", value: `${liq.liquidity_score}/100`, color: liq.liquidity_score > 70 ? "#22c55e" : liq.liquidity_score > 50 ? "#f59e0b" : "#ef4444" },
                { label: "Grade", value: liq.liquidity_grade, color: liq.liquidity_grade === "A" ? "#22c55e" : liq.liquidity_grade === "B" ? "#3b82f6" : liq.liquidity_grade === "C" ? "#f59e0b" : "#ef4444" },
                { label: "Avg Dollar Vol", value: `₹${liq.avg_dollar_volume_cr.toFixed(1)} Cr/day` },
              ].map((m, i) => (
                <div key={i} style={{ background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: 8, padding: "16px 20px" }}>
                  <div style={{ fontSize: 10, color: "#64748b", marginBottom: 4, textTransform: "uppercase", letterSpacing: 1 }}>{m.label}</div>
                  <div style={{ fontSize: 24, fontWeight: 700, color: (m as any).color || "#f1f5f9" }}>{m.value}</div>
                </div>
              ))}
            </div>
            <div style={{ background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: 8, padding: 20 }}>
              <div style={{ fontSize: 12, color: "#64748b", marginBottom: 16, textTransform: "uppercase", letterSpacing: 1 }}>Microstructure Metrics</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                {[
                  { label: "Amihud Illiquidity", value: liq.amihud_illiquidity.toFixed(6), note: "Lower = more liquid" },
                  { label: "Roll Spread (bps)", value: `${liq.roll_spread_bps} bps`, note: "Effective bid-ask proxy" },
                  { label: "Corwin-Schultz Spread", value: `${liq.cs_spread_pct.toFixed(4)}%`, note: "High-low spread estimator" },
                ].map((m, i) => (
                  <div key={i} style={{ padding: 12, background: "#050505", borderRadius: 6, border: "1px solid #111" }}>
                    <div style={{ fontSize: 11, color: "#64748b" }}>{m.label}</div>
                    <div style={{ fontSize: 20, fontWeight: 700, margin: "4px 0" }}>{m.value}</div>
                    <div style={{ fontSize: 10, color: "#475569" }}>{m.note}</div>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 16, padding: 12, background: "#0f1a2e", borderRadius: 6, fontSize: 13, color: "#93c5fd" }}>
                {liq.interpretation}
              </div>
            </div>
          </div>
        )}

        {/* SEASONALITY TAB */}
        {tab === "season" && sea && (
          <div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              {/* Day of Week */}
              <div style={{ background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: 8, padding: 16 }}>
                <div style={{ fontSize: 12, color: "#64748b", marginBottom: 12, textTransform: "uppercase", letterSpacing: 1 }}>Day-of-Week Returns</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {Object.entries(sea.day_of_week).map(([day, stats]) => (
                    <div key={day} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <div style={{ width: 36, fontSize: 12, fontWeight: 700, color: day === sea.best_day ? "#22c55e" : day === sea.worst_day ? "#ef4444" : "#e2e8f0" }}>{day}</div>
                      <div style={{ flex: 1, height: 20, background: "#111", borderRadius: 4, overflow: "hidden" }}>
                        <div style={{
                          height: "100%", width: `${Math.min(100, Math.abs(stats.mean_pct) * 200)}%`,
                          background: stats.mean_pct > 0 ? "#22c55e44" : "#ef444444",
                          borderRight: `2px solid ${stats.mean_pct > 0 ? "#22c55e" : "#ef4444"}`,
                        }} />
                      </div>
                      <div style={{ width: 60, textAlign: "right", fontSize: 12, color: stats.mean_pct > 0 ? "#22c55e" : "#ef4444" }}>
                        {stats.mean_pct > 0 ? "+" : ""}{stats.mean_pct.toFixed(3)}%
                      </div>
                      <div style={{ width: 44, textAlign: "right", fontSize: 11, color: "#64748b" }}>{stats.win_rate.toFixed(0)}% W</div>
                    </div>
                  ))}
                </div>
                <div style={{ marginTop: 12, fontSize: 11, color: "#475569" }}>
                  Best: <span style={{ color: "#22c55e" }}>{sea.best_day}</span> · Worst: <span style={{ color: "#ef4444" }}>{sea.worst_day}</span>
                </div>
              </div>

              {/* Monthly */}
              <div style={{ background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: 8, padding: 16 }}>
                <div style={{ fontSize: 12, color: "#64748b", marginBottom: 12, textTransform: "uppercase", letterSpacing: 1 }}>Monthly Seasonality</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {Object.entries(sea.monthly).map(([month, stats]) => (
                    <div key={month} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <div style={{ width: 32, fontSize: 11, fontWeight: 700, color: month === sea.best_month ? "#22c55e" : month === sea.worst_month ? "#ef4444" : "#e2e8f0" }}>{month}</div>
                      <div style={{ flex: 1, height: 16, background: "#111", borderRadius: 3, overflow: "hidden" }}>
                        <div style={{
                          height: "100%", width: `${Math.min(100, Math.abs(stats.mean_pct) * 100)}%`,
                          background: stats.mean_pct > 0 ? "#22c55e44" : "#ef444444",
                          borderRight: `2px solid ${stats.mean_pct > 0 ? "#22c55e" : "#ef4444"}`,
                        }} />
                      </div>
                      <div style={{ width: 56, textAlign: "right", fontSize: 11, color: stats.mean_pct > 0 ? "#22c55e" : "#ef4444" }}>
                        {stats.mean_pct > 0 ? "+" : ""}{stats.mean_pct.toFixed(2)}%
                      </div>
                      <div style={{ width: 40, textAlign: "right", fontSize: 10, color: "#64748b" }}>{stats.win_rate.toFixed(0)}%</div>
                    </div>
                  ))}
                </div>
                <div style={{ marginTop: 12, padding: 10, background: "#0f1a1a", borderRadius: 6, fontSize: 12 }}>
                  <div style={{ color: "#94a3b8" }}>Expiry Week avg: <span style={{ color: sea.expiry_week_return_pct > 0 ? "#22c55e" : "#ef4444", fontWeight: 700 }}>
                    {sea.expiry_week_return_pct > 0 ? "+" : ""}{sea.expiry_week_return_pct.toFixed(3)}%
                  </span> · Win rate: {sea.expiry_week_win_rate.toFixed(0)}%</div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
