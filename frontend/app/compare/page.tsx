'use client';

import { useEffect, useRef, useState, useCallback } from "react";
import {
  createChart,
  LineSeries,
  type IChartApi,
  type Time,
} from "lightweight-charts";
import IndexBar from "@/components/IndexBar";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

const PERIODS = ["1W", "1M", "3M", "6M", "1Y", "3Y", "5Y"] as const;
type Period = (typeof PERIODS)[number];

interface CompareData {
  sym1: string;
  sym2: string;
  period: string;
  correlation: number;
  correlation_score: number;
  beta: number;
  label: string;
  data_points: number;
  ret1: number;
  ret2: number;
  vol1: number;
  vol2: number;
  chart: { date: string; [key: string]: string | number }[];
}

function correlationColor(score: number): string {
  if (score >= 50) return "#00d084";
  if (score >= 0) return "#f59e0b";
  if (score >= -50) return "#f97316";
  return "#ff3b3b";
}

function sign(n: number): string {
  return n > 0 ? "+" : "";
}

function fmtPct(n: number | undefined | null): string {
  if (n == null || isNaN(n)) return "—";
  return `${sign(n)}${n.toFixed(1)}%`;
}

function fmtNum(n: number | undefined | null, dec = 2): string {
  if (n == null || isNaN(n)) return "—";
  return n.toFixed(dec);
}

interface NormalizedChartProps {
  data: CompareData["chart"];
  sym1: string;
  sym2: string;
}

function NormalizedChart({ data, sym1, sym2 }: NormalizedChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return;

    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight || 320,
      layout: {
        background: { color: "#161616" },
        textColor: "#737373",
        fontSize: 10,
        fontFamily: "monospace",
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
        timeVisible: false,
        secondsVisible: false,
      },
    });

    chartRef.current = chart;

    const series1 = chart.addSeries(LineSeries, {
      color: "#3b82f6",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      title: sym1,
    });

    const series2 = chart.addSeries(LineSeries, {
      color: "#f97316",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      title: sym2,
    });

    const pts1 = data
      .filter((d) => d[sym1] != null)
      .map((d) => ({ time: d.date as Time, value: Number(d[sym1]) }));

    const pts2 = data
      .filter((d) => d[sym2] != null)
      .map((d) => ({ time: d.date as Time, value: Number(d[sym2]) }));

    if (pts1.length > 0) series1.setData(pts1);
    if (pts2.length > 0) series2.setData(pts2);

    chart.timeScale().fitContent();

    let destroyed = false;
    const obs = new ResizeObserver(() => {
      if (!destroyed && containerRef.current) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight || 320,
        });
      }
    });
    obs.observe(containerRef.current);

    return () => {
      destroyed = true;
      obs.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [data, sym1, sym2]);

  return <div ref={containerRef} style={{ width: "100%", height: "100%" }} />;
}

export default function ComparePage() {
  const [sym1Input, setSym1Input] = useState("HDFCBANK");
  const [sym2Input, setSym2Input] = useState("ICICIBANK");
  const [sym1, setSym1] = useState("HDFCBANK");
  const [sym2, setSym2] = useState("ICICIBANK");
  const [period, setPeriod] = useState<Period>("1Y");
  const [data, setData] = useState<CompareData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(
    async (s1: string, s2: string, p: Period) => {
      if (!s1 || !s2) return;
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(
          `${API_BASE}/api/compare/${encodeURIComponent(s1)}/${encodeURIComponent(s2)}?period=${p}`
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json: CompareData = await res.json();
        setData(json);
      } catch (e) {
        setError((e as Error).message);
        setData(null);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    fetchData(sym1, sym2, period);
  }, [sym1, sym2, period, fetchData]);

  function handleSym1Key(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      const v = sym1Input.trim().toUpperCase();
      if (v) setSym1(v);
    }
  }

  function handleSym2Key(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      const v = sym2Input.trim().toUpperCase();
      if (v) setSym2(v);
    }
  }

  const scoreColor = data ? correlationColor(data.correlation_score) : "#555";
  const absScore = data ? Math.abs(Math.round(data.correlation_score)) : null;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        overflow: "hidden",
        background: "#050505",
        fontFamily: "monospace",
      }}
    >
      <IndexBar />

      {/* Input bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 0,
          padding: "0 12px",
          height: 40,
          borderBottom: "1px solid #141414",
          flexShrink: 0,
        }}
      >
        <input
          value={sym1Input}
          onChange={(e) => setSym1Input(e.target.value.toUpperCase())}
          onKeyDown={handleSym1Key}
          placeholder="SYM1"
          style={{
            background: "#0d0d0d",
            border: "1px solid #1e1e1e",
            color: "#3b82f6",
            fontFamily: "monospace",
            fontSize: 13,
            fontWeight: 700,
            padding: "4px 10px",
            width: 120,
            outline: "none",
            letterSpacing: "0.04em",
          }}
        />
        <span
          style={{
            fontSize: 10,
            color: "#333",
            padding: "0 10px",
            letterSpacing: "0.08em",
          }}
        >
          VS
        </span>
        <input
          value={sym2Input}
          onChange={(e) => setSym2Input(e.target.value.toUpperCase())}
          onKeyDown={handleSym2Key}
          placeholder="SYM2"
          style={{
            background: "#0d0d0d",
            border: "1px solid #1e1e1e",
            color: "#f97316",
            fontFamily: "monospace",
            fontSize: 13,
            fontWeight: 700,
            padding: "4px 10px",
            width: 120,
            outline: "none",
            letterSpacing: "0.04em",
          }}
        />
        <div
          style={{
            width: 1,
            height: 20,
            background: "#1e1e1e",
            margin: "0 14px",
          }}
        />
        <div style={{ display: "flex", gap: 2 }}>
          {PERIODS.map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              style={{
                padding: "3px 10px",
                background: period === p ? "#141414" : "none",
                border: "none",
                cursor: "pointer",
                fontSize: 10,
                fontWeight: period === p ? 700 : 400,
                color: period === p ? "#e5e5e5" : "#333",
                borderBottom:
                  period === p ? "2px solid #3b82f6" : "2px solid transparent",
                letterSpacing: "0.05em",
              }}
            >
              {p}
            </button>
          ))}
        </div>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 9, color: "#2a2a2a" }}>
          Press Enter to search
        </span>
      </div>

      {/* Correlation score bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 20,
          padding: "0 16px",
          height: 48,
          borderBottom: "1px solid #141414",
          flexShrink: 0,
          background: "#030303",
        }}
      >
        {loading ? (
          <div
            style={{ fontSize: 10, color: "#333", letterSpacing: "0.08em" }}
          >
            LOADING…
          </div>
        ) : error ? (
          <div style={{ fontSize: 10, color: "#ff3b3b" }}>
            ERROR: {error}
          </div>
        ) : data ? (
          <>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
              <span
                style={{ fontSize: 9, color: "#333", letterSpacing: "0.1em" }}
              >
                CORRELATION
              </span>
              <span
                className="num"
                style={{
                  fontSize: 32,
                  fontWeight: 800,
                  color: scoreColor,
                  lineHeight: 1,
                  letterSpacing: "-0.03em",
                }}
              >
                {absScore != null
                  ? (data.correlation_score >= 0 ? "+" : "-") + absScore
                  : "—"}
              </span>
            </div>
            <div
              style={{
                width: 1,
                height: 24,
                background: "#1e1e1e",
              }}
            />
            <div>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 700,
                  color: scoreColor,
                  letterSpacing: "0.02em",
                }}
              >
                {data.label}
              </div>
              <div style={{ fontSize: 9, color: "#444", marginTop: 2 }}>
                r = {fmtNum(data.correlation, 3)}
              </div>
            </div>
            <div
              style={{
                width: 1,
                height: 24,
                background: "#1e1e1e",
              }}
            />
            <div>
              <span style={{ fontSize: 9, color: "#333" }}>β = </span>
              <span
                className="num"
                style={{ fontSize: 16, fontWeight: 700, color: "#e5e5e5" }}
              >
                {fmtNum(data.beta, 2)}
              </span>
            </div>
            <div
              style={{
                width: 1,
                height: 24,
                background: "#1e1e1e",
              }}
            />
            <div style={{ display: "flex", gap: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <div
                  style={{
                    width: 20,
                    height: 2,
                    background: "#3b82f6",
                    borderRadius: 1,
                  }}
                />
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    color: "#3b82f6",
                    letterSpacing: "0.04em",
                  }}
                >
                  {sym1}
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <div
                  style={{
                    width: 20,
                    height: 2,
                    background: "#f97316",
                    borderRadius: 1,
                  }}
                />
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    color: "#f97316",
                    letterSpacing: "0.04em",
                  }}
                >
                  {sym2}
                </span>
              </div>
            </div>
          </>
        ) : null}
      </div>

      {/* Chart */}
      <div style={{ flex: 1, minHeight: 0, position: "relative" }}>
        {data && data.chart.length > 0 ? (
          <NormalizedChart data={data.chart} sym1={sym1} sym2={sym2} />
        ) : !loading && !error ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              height: "100%",
              fontSize: 11,
              color: "#2a2a2a",
            }}
          >
            No chart data
          </div>
        ) : null}
        {loading && (
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "#05050588",
              fontSize: 11,
              color: "#444",
              letterSpacing: "0.08em",
            }}
          >
            FETCHING DATA…
          </div>
        )}
      </div>

      {/* Stats table */}
      {data && (
        <div
          style={{
            flexShrink: 0,
            borderTop: "1px solid #141414",
            background: "#030303",
            overflowX: "auto",
          }}
        >
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontFamily: "monospace",
              fontSize: 11,
            }}
          >
            <thead>
              <tr style={{ borderBottom: "1px solid #141414" }}>
                <th
                  style={{
                    padding: "6px 16px",
                    textAlign: "left",
                    fontSize: 9,
                    color: "#333",
                    fontWeight: 700,
                    letterSpacing: "0.1em",
                    width: 160,
                  }}
                >
                  METRIC
                </th>
                <th
                  style={{
                    padding: "6px 24px",
                    textAlign: "right",
                    fontSize: 9,
                    color: "#3b82f6",
                    fontWeight: 700,
                    letterSpacing: "0.06em",
                  }}
                >
                  {sym1}
                </th>
                <th
                  style={{
                    padding: "6px 24px",
                    textAlign: "right",
                    fontSize: 9,
                    color: "#f97316",
                    fontWeight: 700,
                    letterSpacing: "0.06em",
                  }}
                >
                  {sym2}
                </th>
                <th style={{ flex: 1 }} />
              </tr>
            </thead>
            <tbody>
              {[
                {
                  label: "Period Return",
                  v1: fmtPct(data.ret1),
                  v2: fmtPct(data.ret2),
                  c1:
                    data.ret1 > 0
                      ? "#00d084"
                      : data.ret1 < 0
                      ? "#ff3b3b"
                      : "#888",
                  c2:
                    data.ret2 > 0
                      ? "#00d084"
                      : data.ret2 < 0
                      ? "#ff3b3b"
                      : "#888",
                },
                {
                  label: "Ann. Volatility",
                  v1: fmtPct(data.vol1),
                  v2: fmtPct(data.vol2),
                  c1: "#888",
                  c2: "#888",
                },
                {
                  label: "Data Points",
                  v1: String(data.data_points),
                  v2: String(data.data_points),
                  c1: "#555",
                  c2: "#555",
                },
              ].map((row, i) => (
                <tr
                  key={i}
                  style={{ borderBottom: "1px solid #0d0d0d" }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.background = "#0a0a0a")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.background = "transparent")
                  }
                >
                  <td
                    style={{
                      padding: "7px 16px",
                      fontSize: 10,
                      color: "#444",
                      letterSpacing: "0.04em",
                    }}
                  >
                    {row.label}
                  </td>
                  <td
                    className="num"
                    style={{
                      padding: "7px 24px",
                      textAlign: "right",
                      fontSize: 12,
                      fontWeight: 700,
                      color: row.c1,
                    }}
                  >
                    {row.v1}
                  </td>
                  <td
                    className="num"
                    style={{
                      padding: "7px 24px",
                      textAlign: "right",
                      fontSize: 12,
                      fontWeight: 700,
                      color: row.c2,
                    }}
                  >
                    {row.v2}
                  </td>
                  <td />
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
