'use client';

import { useState, useEffect } from "react";
import { api, fmt, type TrendScore, type AnalystData, type NewsArticle } from "@/lib/api";

function GaugeArc({ score, color }: { score: number; color: string }) {
  const r = 40;
  const circ = Math.PI * r;
  const dash = (score / 100) * circ;
  return (
    <svg width="100" height="60" viewBox="0 0 100 60">
      <path
        d={`M 10 55 A ${r} ${r} 0 0 1 90 55`}
        fill="none" stroke="#1e1e1e" strokeWidth="8" strokeLinecap="round"
      />
      <path
        d={`M 10 55 A ${r} ${r} 0 0 1 90 55`}
        fill="none" stroke={color} strokeWidth="8" strokeLinecap="round"
        strokeDasharray={`${dash} ${circ}`}
        style={{ transition: "stroke-dasharray 0.6s ease" }}
      />
      <text x="50" y="52" textAnchor="middle" fill="#e5e5e5" fontSize="18" fontWeight="700"
        fontFamily="monospace">
        {score}
      </text>
    </svg>
  );
}

function BarRow({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
        <span style={{ fontSize: 10, color: "#555" }}>{label}</span>
        <span style={{ fontSize: 10, color, fontWeight: 600 }}>{value}/{max}</span>
      </div>
      <div style={{ height: 3, background: "#1e1e1e", borderRadius: 2, overflow: "hidden" }}>
        <div style={{ width: `${(value / max) * 100}%`, height: "100%", background: color, borderRadius: 2,
          transition: "width 0.5s ease" }} />
      </div>
    </div>
  );
}

function AnalystDonut({ data }: { data: AnalystData }) {
  const total = data.total_analysts || 1;
  const segments = [
    { count: data.strong_buy, color: "#15803d", label: "Strong Buy" },
    { count: data.buy, color: "#22c55e", label: "Buy" },
    { count: data.hold, color: "#f59e0b", label: "Hold" },
    { count: data.sell, color: "#ef4444", label: "Sell" },
    { count: data.strong_sell, color: "#991b1b", label: "Strong Sell" },
  ].filter(s => s.count > 0);

  const recColor = data.recommendation?.includes("Buy") || data.recommendation === "strongBuy" || data.recommendation === "buy"
    ? "#22c55e"
    : data.recommendation === "hold" ? "#f59e0b" : "#ef4444";

  return (
    <div>
      <div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 12 }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 22, fontWeight: 700, color: recColor }}>
            {data.bull_pct}%
          </div>
          <div style={{ fontSize: 10, color: "#555" }}>Bullish</div>
          <div style={{ fontSize: 11, color: recColor, fontWeight: 600, textTransform: "uppercase" }}>
            {data.recommendation || "—"}
          </div>
        </div>
        <div style={{ flex: 1 }}>
          {segments.map(s => (
            <div key={s.label} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
              <div style={{ width: 8, height: 8, borderRadius: 2, background: s.color, flexShrink: 0 }} />
              <div style={{ flex: 1, height: 12, background: "#1a1a1a", borderRadius: 2, overflow: "hidden" }}>
                <div style={{
                  width: `${(s.count / total) * 100}%`, height: "100%",
                  background: s.color + "66", borderRadius: 2,
                }} />
              </div>
              <span style={{ fontSize: 10, color: "#555", width: 20, textAlign: "right" }}>{s.count}</span>
              <span style={{ fontSize: 10, color: "#444", width: 64 }}>{s.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function TrendPanel({ symbol }: { symbol: string }) {
  const [data, setData] = useState<{
    trend: TrendScore;
    analysts: AnalystData;
    news_preview: NewsArticle[];
  } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.trends(symbol)
      .then(res => {
        setData({ trend: res.trend, analysts: res.analysts, news_preview: res.news_preview });
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [symbol]);

  if (loading) {
    return (
      <div style={{ padding: 16 }}>
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="skeleton" style={{ height: 60, marginBottom: 10, borderRadius: 6 }} />
        ))}
        <p style={{ textAlign: "center", color: "#555", fontSize: 11 }}>Computing trend signals…</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div style={{ padding: 32, textAlign: "center", color: "#555", fontSize: 12 }}>
        Trend data unavailable for {symbol}
      </div>
    );
  }

  const { trend, analysts, news_preview } = data;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 20 }}>
      {/* Left: Trend Score */}
      <div>
        {/* Score Gauge */}
        <div style={{
          background: "#111", border: "1px solid #1e1e1e", borderRadius: 8,
          padding: 16, marginBottom: 12, textAlign: "center",
        }}>
          <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.06em", marginBottom: 8 }}>
            TREND SCORE
          </div>
          <GaugeArc score={trend.overall} color={trend.color} />
          <div style={{ fontSize: 14, fontWeight: 700, color: trend.color, marginTop: 4 }}>
            {trend.label}
          </div>
          <div style={{ fontSize: 10, color: "#555", marginTop: 2 }}>
            {trend.news_count} articles · {trend.positive_news} pos / {trend.negative_news} neg
          </div>
        </div>

        {/* Score Breakdown */}
        <div style={{
          background: "#111", border: "1px solid #1e1e1e", borderRadius: 8, padding: 14,
        }}>
          <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.06em", marginBottom: 10 }}>
            SCORE BREAKDOWN
          </div>
          <BarRow label="Technical" value={trend.breakdown.technical} max={40} color="#3b82f6" />
          <BarRow label="Momentum" value={trend.breakdown.momentum} max={25} color="#f59e0b" />
          <BarRow label="Analyst Consensus" value={trend.breakdown.analyst} max={25} color="#8b5cf6" />
          <BarRow label="News Sentiment" value={trend.breakdown.sentiment} max={10} color="#22c55e" />
        </div>
      </div>

      {/* Right: Signals + Analysts */}
      <div>
        {/* Key Signals */}
        <div style={{
          background: "#111", border: "1px solid #1e1e1e", borderRadius: 8,
          padding: 14, marginBottom: 12,
        }}>
          <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.06em", marginBottom: 10 }}>
            KEY TREND SIGNALS
          </div>
          {trend.signals.length === 0 ? (
            <div style={{ color: "#555", fontSize: 11 }}>No strong signals detected</div>
          ) : (
            trend.signals.map((s, i) => {
              const isBull = /bullish|uptrend|positive|buy|upgrade|above|high|win|surge/i.test(s);
              const isBear = /bearish|downtrend|negative|sell|downgrade|below|loss|bear/i.test(s);
              return (
                <div key={i} style={{
                  display: "flex", alignItems: "flex-start", gap: 8,
                  padding: "6px 0", borderBottom: i < trend.signals.length - 1 ? "1px solid #1a1a1a" : "none",
                }}>
                  <span style={{ color: isBull ? "#22c55e" : isBear ? "#ef4444" : "#f59e0b", fontSize: 12 }}>
                    {isBull ? "▲" : isBear ? "▼" : "●"}
                  </span>
                  <span style={{ fontSize: 12, color: "#ccc", lineHeight: 1.4 }}>{s}</span>
                </div>
              );
            })
          )}
        </div>

        {/* Analyst Ratings */}
        {analysts && analysts.total_analysts > 0 && (
          <div style={{
            background: "#111", border: "1px solid #1e1e1e", borderRadius: 8,
            padding: 14, marginBottom: 12,
          }}>
            <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.06em", marginBottom: 10 }}>
              ANALYST RATINGS ({analysts.total_analysts} analysts)
            </div>
            <AnalystDonut data={analysts} />

            {analysts.recent_ratings.length > 0 && (
              <>
                <div style={{ fontSize: 10, color: "#333", letterSpacing: "0.06em", marginBottom: 8, marginTop: 12 }}>
                  RECENT RATING CHANGES
                </div>
                {analysts.recent_ratings.slice(0, 6).map((r, i) => {
                  const isUp = r.action === "up" || r.action === "init";
                  return (
                    <div key={i} style={{
                      display: "flex", alignItems: "center", gap: 8,
                      padding: "5px 0", borderBottom: "1px solid #1a1a1a",
                      fontSize: 11,
                    }}>
                      <span style={{ color: isUp ? "#22c55e" : "#ef4444" }}>
                        {isUp ? "↑" : "↓"}
                      </span>
                      <span style={{ color: "#e5e5e5", fontWeight: 600, minWidth: 120 }}>{r.firm || "—"}</span>
                      <span style={{ color: "#555", flex: 1 }}>
                        {r.from_grade && r.to_grade ? `${r.from_grade} → ${r.to_grade}` : r.to_grade || r.from_grade}
                      </span>
                      <span style={{ color: "#444", fontSize: 10 }}>{r.date}</span>
                    </div>
                  );
                })}
              </>
            )}
          </div>
        )}

        {/* News Preview */}
        {news_preview.length > 0 && (
          <div style={{
            background: "#111", border: "1px solid #1e1e1e", borderRadius: 8, padding: 14,
          }}>
            <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.06em", marginBottom: 8 }}>
              RECENT NEWS
            </div>
            {news_preview.map((n, i) => {
              const sentColor = n.sentiment === "positive" ? "#22c55e"
                : n.sentiment === "negative" ? "#ef4444" : "#555";
              return (
                <a key={i} href={n.url} target="_blank" rel="noopener noreferrer"
                  style={{ display: "block", padding: "6px 0", borderBottom: "1px solid #1a1a1a",
                    textDecoration: "none" }}>
                  <div style={{ display: "flex", gap: 6, alignItems: "flex-start" }}>
                    <div style={{ width: 5, height: 5, borderRadius: "50%", background: sentColor,
                      flexShrink: 0, marginTop: 4 }} />
                    <div>
                      <p style={{ margin: 0, fontSize: 11, color: "#d4d4d4", lineHeight: 1.4 }}>
                        {n.title}
                      </p>
                      <span style={{ fontSize: 10, color: "#444" }}>{n.source} · {n.age_days}d ago</span>
                    </div>
                  </div>
                </a>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
