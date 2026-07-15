'use client';

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  createChart, LineSeries, type IChartApi, type Time,
} from "lightweight-charts";
import { useRef } from "react";
import IndexBar from "@/components/IndexBar";
import { api } from "@/lib/api";

interface PairData {
  sym1: string; sym2: string;
  hedge_ratio: number; alpha: number;
  current_zscore: number;
  half_life_days: number | null;
  correlation: number;
  signal: string;
  signal_color: string;
  action: string;
  zscore_series: number[];
  lookback: number;
  dates?: string[];
}

function ZScoreSparkline({ series, current }: { series: number[]; current: number }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || series.length < 2) return;

    const chart = createChart(ref.current, {
      width: ref.current.clientWidth,
      height: 80,
      layout: { background: { color: "transparent" }, textColor: "#555", fontSize: 9, fontFamily: "monospace" },
      grid: { vertLines: { color: "#141414" }, horzLines: { color: "#141414" } },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: "#1e1e1e", textColor: "#444", scaleMargins: { top: 0.1, bottom: 0.1 } },
      timeScale: { visible: false },
      handleScroll: false,
      handleScale: false,
    });

    const zSeries = chart.addSeries(LineSeries, { color: "#3b82f6", lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const upper = chart.addSeries(LineSeries, { color: "#ef444440", lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
    const lower = chart.addSeries(LineSeries, { color: "#22c55e40", lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });

    const now = Math.floor(Date.now() / 1000);
    const DAY = 86400;
    const mkpts = (vals: number[]) => vals.map((v, i) => ({ time: (now - (vals.length - i) * DAY) as Time, value: v }));

    zSeries.setData(mkpts(series));
    upper.setData(mkpts(series.map(() => 2)));
    lower.setData(mkpts(series.map(() => -2)));
    chart.timeScale().fitContent();
    let destroyed = false;
    const obs = new ResizeObserver(() => {
      if (!destroyed && ref.current) chart.applyOptions({ width: ref.current.clientWidth });
    });
    obs.observe(ref.current);
    return () => { destroyed = true; obs.disconnect(); chart.remove(); };
  }, [series]);

  const zColor = current > 2 ? "#ef4444" : current < -2 ? "#22c55e" : "#3b82f6";

  return (
    <div style={{ position: "relative" }}>
      <div ref={ref} />
      <div style={{
        position: "absolute", top: 4, right: 4,
        fontSize: 13, fontWeight: 700, color: zColor, fontFamily: "monospace",
      }}>
        z={current.toFixed(2)}
      </div>
    </div>
  );
}

function PairCard({ pair, onClick }: { pair: PairData; onClick: () => void }) {
  const bgSignal = pair.action === "buy_spread" ? "#22c55e08" :
    pair.action === "sell_spread" ? "#ef444408" : "transparent";

  return (
    <div onClick={onClick} style={{
      background: bgSignal || "#111", border: `1px solid ${Math.abs(pair.current_zscore) > 2 ? pair.signal_color + "44" : "#1e1e1e"}`,
      borderRadius: 8, padding: 14, cursor: "pointer", marginBottom: 10,
    }} onMouseEnter={e => (e.currentTarget.style.outline = "1px solid #333")}
      onMouseLeave={e => (e.currentTarget.style.outline = "none")}>

      <div style={{ display: "grid", gridTemplateColumns: "1fr auto", alignItems: "start", marginBottom: 10 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: "#e5e5e5" }}>{pair.sym1}</span>
            <span style={{ fontSize: 12, color: "#555" }}>vs</span>
            <span style={{ fontSize: 14, fontWeight: 700, color: "#e5e5e5" }}>{pair.sym2}</span>
          </div>
          <div style={{ fontSize: 10, color: "#555", marginTop: 2 }}>
            β={pair.hedge_ratio.toFixed(3)} · ρ={pair.correlation.toFixed(2)} · {pair.lookback}d lookback
            {pair.half_life_days && ` · ½-life ${pair.half_life_days.toFixed(0)}d`}
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{
            display: "inline-block", padding: "3px 10px", fontSize: 10, fontWeight: 700,
            background: pair.signal_color + "20", color: pair.signal_color,
            borderRadius: 4, fontFamily: "monospace",
          }}>{pair.signal}</div>
        </div>
      </div>

      <ZScoreSparkline series={pair.zscore_series} current={pair.current_zscore} />

      <div style={{ display: "flex", gap: 16, marginTop: 8, fontSize: 10, color: "#555" }}>
        <span>z-score: <strong style={{ color: Math.abs(pair.current_zscore) > 2 ? pair.signal_color : "#888", fontFamily: "monospace" }}>
          {pair.current_zscore > 0 ? "+" : ""}{pair.current_zscore.toFixed(3)}
        </strong></span>
        <span>|2σ| entry, |0.5σ| exit</span>
      </div>
    </div>
  );
}

export default function PairsPage() {
  const router = useRouter();
  const [pairs, setPairs] = useState<PairData[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterActive, setFilterActive] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.pairs().then(res => { setPairs(res.pairs || []); }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const displayPairs = filterActive
    ? pairs.filter(p => p.action !== "hold")
    : pairs;

  const signalCount = pairs.filter(p => p.action !== "hold").length;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden" }}>
      <IndexBar />
      <div style={{ flex: 1, overflow: "auto", background: "#080808" }}>
        <div style={{ maxWidth: 900, margin: "0 auto", padding: "16px 20px" }}>
          {/* Header */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
            <button onClick={() => router.push("/")} style={{ background: "none", border: "none", color: "#555", cursor: "pointer", fontSize: 16 }}>←</button>
            <div>
              <h1 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "#e5e5e5" }}>Pairs Trading</h1>
              <div style={{ fontSize: 11, color: "#555" }}>
                OLS spread Z-score · Entry at ±2σ · Exit at ±0.5σ · Ornstein-Uhlenbeck mean reversion
              </div>
            </div>
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
              <button
                onClick={() => setFilterActive(!filterActive)}
                style={{
                  padding: "5px 12px", fontSize: 11, border: "none", borderRadius: 6, cursor: "pointer",
                  background: filterActive ? "#22c55e20" : "#1a1a1a",
                  color: filterActive ? "#22c55e" : "#555",
                  outline: filterActive ? "1px solid #22c55e44" : "1px solid #1e1e1e",
                }}>
                Active Signals ({signalCount})
              </button>
            </div>
          </div>

          {/* Legend */}
          <div style={{
            background: "#111", border: "1px solid #1e1e1e", borderRadius: 8, padding: "10px 16px",
            marginBottom: 16, fontSize: 11, color: "#555", display: "flex", gap: 24, flexWrap: "wrap",
          }}>
            <span><strong style={{ color: "#22c55e" }}>BUY SPREAD</strong> = Long {"{sym1}"} / Short {"{sym2}"} (Z &lt; -2σ)</span>
            <span><strong style={{ color: "#ef4444" }}>SELL SPREAD</strong> = Short {"{sym1}"} / Long {"{sym2}"} (Z &gt; +2σ)</span>
            <span><strong style={{ color: "#f59e0b" }}>EXIT</strong> = Z converged to ±0.5σ</span>
            <span style={{ marginLeft: "auto" }}>Z-score chart — dashed lines = ±2σ thresholds</span>
          </div>

          {loading ? (
            <div>
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="skeleton" style={{ height: 140, marginBottom: 10, borderRadius: 8 }} />
              ))}
            </div>
          ) : displayPairs.length === 0 ? (
            <div style={{ padding: 48, textAlign: "center", color: "#555" }}>
              {filterActive ? "No active signals right now" : "No pairs data available"}
            </div>
          ) : (
            displayPairs.map(pair => (
              <PairCard
                key={`${pair.sym1}-${pair.sym2}`}
                pair={pair}
                onClick={() => {
                  // Open both stocks in new tabs conceptually — navigate to first
                  router.push(`/stock/${pair.sym1}`);
                }}
              />
            ))
          )}
        </div>
      </div>
    </div>
  );
}
