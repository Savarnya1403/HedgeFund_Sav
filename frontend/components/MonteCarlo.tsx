'use client';

import { useEffect, useRef, useState } from "react";
import {
  createChart, LineSeries, type IChartApi, type Time,
} from "lightweight-charts";
import { api, fmt } from "@/lib/api";

interface MCResult {
  current_price: number;
  days: number;
  simulations: number;
  daily_volatility_pct: number;
  annual_volatility_pct: number;
  daily_drift_pct: number;
  bands: { p5: number[]; p25: number[]; p50: number[]; p75: number[]; p95: number[] };
  var_95_pct: number;
  var_99_pct: number;
  cvar_95_pct: number;
  expected_price: number;
  expected_return_pct: number;
  prob_profit_pct: number;
  prob_up5_pct: number;
  prob_down5_pct: number;
  prob_down10_pct: number;
  price_range_95: { low: number; high: number };
  symbol: string;
}

function StatBox({ label, value, color = "#e5e5e5", sub }: { label: string; value: string; color?: string; sub?: string }) {
  return (
    <div style={{ background: "#111", border: "1px solid #1e1e1e", borderRadius: 6, padding: "10px 14px" }}>
      <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.05em", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color, fontFamily: "monospace" }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: "#555", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function ProbBar({ label, pct, color }: { label: string; pct: number; color: string }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
        <span style={{ fontSize: 11, color: "#888" }}>{label}</span>
        <span style={{ fontSize: 11, fontWeight: 700, color, fontFamily: "monospace" }}>{pct}%</span>
      </div>
      <div style={{ height: 4, background: "#1e1e1e", borderRadius: 2, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 2, transition: "width 0.5s" }} />
      </div>
    </div>
  );
}

export default function MonteCarlo({ symbol }: { symbol: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [data, setData] = useState<MCResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  useEffect(() => {
    setLoading(true);
    api.montecarlo(symbol, days)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [symbol, days]);

  useEffect(() => {
    if (!data || !containerRef.current) return;

    // Build time axis: today + N future days as unix timestamps
    const todayMs = Date.now();
    const DAY_SEC = 86400;
    const todayTs = Math.floor(todayMs / 1000);

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 280,
      layout: { background: { color: "#0e0e0e" }, textColor: "#555", fontSize: 11, fontFamily: "monospace" },
      grid: { vertLines: { color: "#141414" }, horzLines: { color: "#141414" } },
      crosshair: { mode: 1, vertLine: { color: "#333", labelBackgroundColor: "#222" }, horzLine: { color: "#333", labelBackgroundColor: "#222" } },
      rightPriceScale: { borderColor: "#222", textColor: "#555" },
      timeScale: { borderColor: "#222", timeVisible: false },
    });

    const makeTimePoints = (vals: number[]): { time: Time; value: number }[] =>
      vals.map((v, i) => ({ time: (todayTs + i * DAY_SEC) as Time, value: v }));

    const bands = [
      { key: "p95", color: "#22c55e18", width: 1 as const },
      { key: "p75", color: "#22c55e40", width: 1 as const },
      { key: "p50", color: "#22c55e", width: 2 as const },
      { key: "p25", color: "#ef444440", width: 1 as const },
      { key: "p5", color: "#ef444418", width: 1 as const },
    ];

    for (const b of bands) {
      const series = chart.addSeries(LineSeries, {
        color: b.color, lineWidth: b.width,
        priceLineVisible: false, lastValueVisible: b.key === "p50",
        crosshairMarkerVisible: b.key === "p50",
      });
      series.setData(makeTimePoints(data.bands[b.key as keyof typeof data.bands]));
    }

    chart.timeScale().fitContent();
    let destroyed = false;
    const obs = new ResizeObserver(() => {
      if (!destroyed && containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    });
    obs.observe(containerRef.current);
    return () => { destroyed = true; obs.disconnect(); chart.remove(); };
  }, [data]);

  if (loading) {
    return (
      <div style={{ padding: 16 }}>
        <div className="skeleton" style={{ height: 280, borderRadius: 8, marginBottom: 12 }} />
        <p style={{ color: "#555", fontSize: 11, textAlign: "center" }}>Running {days}-day Monte Carlo simulation…</p>
      </div>
    );
  }

  if (!data) {
    return <div style={{ padding: 32, textAlign: "center", color: "#555" }}>Simulation unavailable</div>;
  }

  const varColor = data.var_95_pct < -10 ? "#ef4444" : data.var_95_pct < -5 ? "#f59e0b" : "#22c55e";

  return (
    <div>
      {/* Controls */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <span style={{ fontSize: 11, color: "#555" }}>Horizon</span>
        {[10, 30, 60].map(d => (
          <button key={d} onClick={() => setDays(d)} style={{
            padding: "3px 12px", fontSize: 11, border: "none", borderRadius: 4, cursor: "pointer",
            background: days === d ? "#3b82f6" : "#1a1a1a",
            color: days === d ? "#fff" : "#555",
          }}>{d}d</button>
        ))}
        <span style={{ marginLeft: "auto", fontSize: 10, color: "#333" }}>
          {data.simulations.toLocaleString()} paths · {data.annual_volatility_pct}% annual vol
        </span>
      </div>

      {/* Chart */}
      <div style={{ background: "#0e0e0e", borderRadius: 8, padding: 4, marginBottom: 16, position: "relative" }}>
        <div ref={containerRef} />
        <div style={{ position: "absolute", top: 8, left: 12, fontSize: 10, color: "#444" }}>
          <span style={{ color: "#22c55e", marginRight: 12 }}>— P95/P75/P50 (median)</span>
          <span style={{ color: "#ef4444" }}>— P25/P5</span>
        </div>
      </div>

      {/* Key stats grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginBottom: 16 }}>
        <StatBox label="Expected Price" value={`₹${fmt(data.expected_price)}`}
          sub={`${data.expected_return_pct > 0 ? "+" : ""}${data.expected_return_pct}% expected`} />
        <StatBox label="VaR 95% (daily)" value={`${data.var_95_pct}%`} color={varColor}
          sub={`CVaR: ${data.cvar_95_pct}%`} />
        <StatBox label="VaR 99%" value={`${data.var_99_pct}%`} color="#ef4444"
          sub="1% tail risk" />
        <StatBox label="95% Price Range" value={`₹${fmt(data.price_range_95.low)} – ₹${fmt(data.price_range_95.high)}`}
          sub={`in ${data.days} trading days`} />
      </div>

      {/* Probability bars */}
      <div style={{ background: "#111", border: "1px solid #1e1e1e", borderRadius: 8, padding: 16 }}>
        <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.05em", marginBottom: 12 }}>
          OUTCOME PROBABILITIES ({data.days}D)
        </div>
        <ProbBar label="Probability of profit" pct={data.prob_profit_pct} color="#22c55e" />
        <ProbBar label="Probability +5% gain" pct={data.prob_up5_pct} color="#16a34a" />
        <ProbBar label="Probability -5% loss" pct={data.prob_down5_pct} color="#f59e0b" />
        <ProbBar label="Probability -10% loss" pct={data.prob_down10_pct} color="#ef4444" />
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid #1e1e1e", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, fontSize: 11 }}>
          <div style={{ color: "#555" }}>Daily Vol: <span style={{ color: "#e5e5e5", fontFamily: "monospace" }}>{data.daily_volatility_pct}%</span></div>
          <div style={{ color: "#555" }}>Daily Drift: <span style={{ color: "#e5e5e5", fontFamily: "monospace" }}>{data.daily_drift_pct > 0 ? "+" : ""}{data.daily_drift_pct}%</span></div>
        </div>
      </div>
    </div>
  );
}
