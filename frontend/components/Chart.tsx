'use client';

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type CandlestickData,
  type Time,
} from "lightweight-charts";
import { api, type HistoryPoint } from "@/lib/api";

const PERIODS = [
  { label: "1D", period: "5d", interval: "5m" },
  { label: "1W", period: "1mo", interval: "1d" },
  { label: "1M", period: "3mo", interval: "1d" },
  { label: "3M", period: "6mo", interval: "1d" },
  { label: "6M", period: "1y", interval: "1d" },
  { label: "1Y", period: "2y", interval: "1wk" },
  { label: "5Y", period: "5y", interval: "1wk" },
];

interface ChartProps {
  symbol: string;
  height?: number;
  period?: string;
  interval?: string;
}

export default function Chart({ symbol, height = 400, period: periodProp, interval: intervalProp }: ChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const [activePeriod, setActivePeriod] = useState(2);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: {
        background: { color: "#161616" },
        textColor: "#737373",
        fontSize: 11,
        fontFamily: "'Geist Mono', monospace",
      },
      grid: {
        vertLines: { color: "#1e1e1e" },
        horzLines: { color: "#1e1e1e" },
      },
      crosshair: {
        mode: 1,
        vertLine: { color: "#333", labelBackgroundColor: "#222" },
        horzLine: { color: "#333", labelBackgroundColor: "#222" },
      },
      rightPriceScale: {
        borderColor: "#222",
        textColor: "#555",
      },
      timeScale: {
        borderColor: "#222",
        timeVisible: true,
        secondsVisible: false,
      },
    });
    chartRef.current = chart;

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: "#3b82f620",
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });

    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    const ma20Series = chart.addSeries(LineSeries, {
      color: "#f59e0b",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    const ma50Series = chart.addSeries(LineSeries, {
      color: "#3b82f6",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    async function loadData() {
      setLoading(true);
      const { period, interval } = periodProp && intervalProp
        ? { period: periodProp, interval: intervalProp }
        : PERIODS[activePeriod];
      try {
        const res = await api.history(symbol, period, interval);
        // Deduplicate by unix timestamp (handles intraday 5m and daily/weekly equally)
        const seen = new Map<number, HistoryPoint>();
        for (const d of res.data) {
          seen.set(d.time, d);
        }
        const sorted = Array.from(seen.values()).sort((a, b) => a.time - b.time);
        const candles: CandlestickData<Time>[] = sorted.map((d: HistoryPoint) => ({
          time: d.time as Time,
          open: d.open,
          high: d.high,
          low: d.low,
          close: d.close,
        }));
        const vols = sorted.map((d: HistoryPoint) => ({
          time: d.time as Time,
          value: d.volume,
          color: d.close >= d.open ? "#22c55e20" : "#ef444420",
        }));

        // MA20
        const ma20: { time: Time; value: number }[] = [];
        const ma50: { time: Time; value: number }[] = [];
        for (let i = 0; i < sorted.length; i++) {
          if (i >= 19) {
            const slice = sorted.slice(i - 19, i + 1);
            const avg = slice.reduce((s: number, d: HistoryPoint) => s + d.close, 0) / 20;
            ma20.push({ time: sorted[i].time as Time, value: avg });
          }
          if (i >= 49) {
            const slice = sorted.slice(i - 49, i + 1);
            const avg = slice.reduce((s: number, d: HistoryPoint) => s + d.close, 0) / 50;
            ma50.push({ time: sorted[i].time as Time, value: avg });
          }
        }

        candleSeries.setData(candles);
        volumeSeries.setData(vols);
        ma20Series.setData(ma20);
        ma50Series.setData(ma50);
        chart.timeScale().fitContent();
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    }

    loadData();

    let destroyed = false;
    const obs = new ResizeObserver(() => {
      if (!destroyed && containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    obs.observe(containerRef.current);

    return () => {
      destroyed = true;
      obs.disconnect();
      chart.remove();
    };
  }, [symbol, activePeriod, height]);

  return (
    <div style={{ background: "#161616", borderRadius: 8, overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 4, padding: "8px 12px", borderBottom: "1px solid #222" }}>
        <span style={{ color: "#555", fontSize: 11, marginRight: 8 }}>Period</span>
        {PERIODS.map((p, i) => (
          <button
            key={p.label}
            onClick={() => setActivePeriod(i)}
            style={{
              padding: "2px 8px",
              fontSize: 11,
              border: "none",
              borderRadius: 4,
              cursor: "pointer",
              background: activePeriod === i ? "#3b82f6" : "transparent",
              color: activePeriod === i ? "#fff" : "#555",
              transition: "all 0.15s",
            }}
          >
            {p.label}
          </button>
        ))}
        <span style={{ marginLeft: "auto", fontSize: 10, color: "#333" }}>
          <span style={{ color: "#f59e0b", marginRight: 8 }}>— MA20</span>
          <span style={{ color: "#3b82f6" }}>— MA50</span>
        </span>
      </div>
      <div style={{ position: "relative" }}>
        <div ref={containerRef} />
        {loading && (
          <div style={{
            position: "absolute", inset: 0, display: "flex",
            alignItems: "center", justifyContent: "center",
            background: "#16161688", color: "#555", fontSize: 12,
          }}>
            Loading…
          </div>
        )}
      </div>
    </div>
  );
}
