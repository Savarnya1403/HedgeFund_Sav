'use client';

import { useState, useEffect } from "react";
import IndexBar from "@/components/IndexBar";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

interface HistoricalEvent {
  id: string;
  name: string;
  category: string;
  start: string;
  end: string;
  description: string;
}

interface SectorPerformance {
  return_pct: number;
  signal: string;
  start_price?: number;
  end_price?: number;
}

interface EventAnalysis {
  id: string;
  name: string;
  start: string;
  end: string;
  performance: Record<string, SectorPerformance>;
}

const CATEGORY_COLORS: Record<string, string> = {
  pandemic: "#ff3b3b",
  geopolitical: "#f97316",
  monetary: "#3b82f6",
  policy: "#a855f7",
  financial: "#ff3b3b",
  commodity: "#f59e0b",
  recovery: "#00d084",
  corporate: "#6b7280",
};

function categoryColor(cat: string): string {
  return CATEGORY_COLORS[cat] ?? "#6b7280";
}

function daysBetween(start: string, end: string): number {
  const a = new Date(start).getTime();
  const b = new Date(end).getTime();
  return Math.round(Math.abs(b - a) / 86400000);
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function BarRow({ label, returnPct, isIndex }: { label: string; returnPct: number; isIndex: boolean }) {
  const maxBar = 60;
  const pct = Math.abs(returnPct);
  const barWidth = Math.min(pct * 1.2, maxBar);
  const positive = returnPct >= 0;
  const barColor = isIndex ? "#3b82f6" : positive ? "#00d084" : "#ff3b3b";
  const badge = isIndex ? "INDEX" : positive ? "OUTPERFORM" : "UNDERPERFORM";
  const badgeColor = isIndex ? "#3b82f6" : positive ? "#00d084" : "#ff3b3b";

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "140px 1fr 80px 90px",
      alignItems: "center",
      gap: 10,
      padding: "5px 0",
      borderBottom: "1px solid #111",
    }}>
      <span style={{ fontSize: 11, color: isIndex ? "#3b82f6" : "#ccc", fontFamily: "monospace", fontWeight: isIndex ? 700 : 400 }}>
        {label}
      </span>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <div style={{
          width: barWidth,
          height: 8,
          background: barColor,
          borderRadius: 2,
          opacity: 0.85,
          flexShrink: 0,
        }} />
        <span className="num" style={{ fontSize: 11, color: barColor, fontWeight: 700 }}>
          {positive && !isIndex ? "+" : ""}{returnPct.toFixed(1)}%
        </span>
      </div>
      <span style={{
        fontSize: 9,
        letterSpacing: "0.06em",
        color: badgeColor,
        border: `1px solid ${badgeColor}33`,
        padding: "1px 5px",
        borderRadius: 3,
        textAlign: "center",
      }}>
        {badge}
      </span>
      <span style={{ fontSize: 9, color: "#333", textAlign: "right", fontFamily: "monospace" }}>
        {/* placeholder for price range if available */}
      </span>
    </div>
  );
}

export default function PatternsPage() {
  const [events, setEvents] = useState<HistoricalEvent[]>([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [eventsError, setEventsError] = useState<string | null>(null);

  const [selectedEvent, setSelectedEvent] = useState<HistoricalEvent | null>(null);
  const [analysis, setAnalysis] = useState<EventAnalysis | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  const [lastUpdated] = useState(() => {
    const now = new Date();
    return now.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
  });

  useEffect(() => {
    setEventsLoading(true);
    fetch(`${BASE_URL}/api/events`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        setEvents(data.events || []);
        setEventsLoading(false);
      })
      .catch(err => {
        setEventsError(err.message || "Failed to load events");
        setEventsLoading(false);
      });
  }, []);

  function selectEvent(ev: HistoricalEvent) {
    if (selectedEvent?.id === ev.id) {
      setSelectedEvent(null);
      setAnalysis(null);
      setAnalysisError(null);
      return;
    }
    setSelectedEvent(ev);
    setAnalysis(null);
    setAnalysisError(null);
    setAnalysisLoading(true);

    fetch(`${BASE_URL}/api/event-analysis/${ev.id}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        setAnalysis(data);
        setAnalysisLoading(false);
      })
      .catch(err => {
        setAnalysisError(err.message || "Failed to load event analysis");
        setAnalysisLoading(false);
      });
  }

  const sortedSectors: Array<[string, SectorPerformance]> = analysis
    ? Object.entries(analysis.performance).sort((a, b) => b[1].return_pct - a[1].return_pct)
    : [];

  const nifty50Entry = sortedSectors.find(([k]) => k === "Nifty50");
  const sectorEntries = sortedSectors.filter(([k]) => k !== "Nifty50");
  const outperformers = sectorEntries.filter(([, v]) => v.signal === "bullish" || v.return_pct >= 0);
  const underperformers = sectorEntries.filter(([, v]) => v.signal === "bearish" || v.return_pct < 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden", background: "#050505", fontFamily: "monospace" }}>
      <IndexBar />

      <div style={{ flex: 1, overflow: "auto" }}>
        <div style={{ maxWidth: 1280, margin: "0 auto", padding: "0 20px 40px" }}>

          {/* Page Header */}
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "14px 0 12px",
            borderBottom: "1px solid #141414",
          }}>
            <div>
              <span style={{ fontSize: 13, fontWeight: 700, color: "#e5e5e5", letterSpacing: "0.08em" }}>HISTORICAL MARKET PATTERNS</span>
              <span style={{ fontSize: 10, color: "#333", marginLeft: 10 }}>EVENT ANALYSIS & SECTOR IMPACT</span>
            </div>
            <span style={{ fontSize: 9, color: "#333" }}>Last updated: {lastUpdated} IST</span>
          </div>

          {/* Events Catalog */}
          <div style={{ padding: "16px 0 12px" }}>
            <div style={{ fontSize: 9, color: "#444", letterSpacing: "0.1em", marginBottom: 10 }}>EVENTS CATALOG</div>

            {eventsLoading && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 8 }}>
                {Array.from({ length: 8 }).map((_, i) => (
                  <div key={i} style={{ height: 100, background: "#111", borderRadius: 6, border: "1px solid #1a1a1a", animation: "pulse 1.5s ease-in-out infinite" }} />
                ))}
              </div>
            )}

            {eventsError && (
              <div style={{
                background: "#1a0a0a", border: "1px solid #ff3b3b33", borderRadius: 6,
                padding: "14px 16px", color: "#ff3b3b", fontSize: 11,
              }}>
                Failed to load events: {eventsError}
              </div>
            )}

            {!eventsLoading && !eventsError && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 8 }}>
                {events.map(ev => {
                  const isSelected = selectedEvent?.id === ev.id;
                  const catColor = categoryColor(ev.category);
                  const days = daysBetween(ev.start, ev.end);
                  return (
                    <div
                      key={ev.id}
                      onClick={() => selectEvent(ev)}
                      style={{
                        background: isSelected ? "#0d1117" : "#0a0a0a",
                        border: `1px solid ${isSelected ? catColor + "66" : "#161616"}`,
                        borderRadius: 6,
                        padding: "12px 14px",
                        cursor: "pointer",
                        outline: isSelected ? `1px solid ${catColor}44` : "none",
                        transition: "border-color 0.15s, background 0.15s",
                        position: "relative",
                      }}
                      onMouseEnter={e => {
                        if (!isSelected) {
                          (e.currentTarget as HTMLDivElement).style.borderColor = "#252525";
                          (e.currentTarget as HTMLDivElement).style.background = "#0d0d0d";
                        }
                      }}
                      onMouseLeave={e => {
                        if (!isSelected) {
                          (e.currentTarget as HTMLDivElement).style.borderColor = "#161616";
                          (e.currentTarget as HTMLDivElement).style.background = "#0a0a0a";
                        }
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 6, gap: 8 }}>
                        <span style={{ fontSize: 12, fontWeight: 700, color: "#e5e5e5", lineHeight: 1.2 }}>{ev.name}</span>
                        <span style={{
                          fontSize: 8, letterSpacing: "0.06em", fontWeight: 700,
                          color: catColor, border: `1px solid ${catColor}44`,
                          padding: "1px 5px", borderRadius: 3, flexShrink: 0, textTransform: "uppercase",
                        }}>{ev.category}</span>
                      </div>
                      <div style={{ fontSize: 9, color: "#444", marginBottom: 6, fontFamily: "monospace" }}>
                        {formatDate(ev.start)} – {formatDate(ev.end)} · {days}d
                      </div>
                      <div style={{ fontSize: 10, color: "#555", lineHeight: 1.4, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                        {ev.description}
                      </div>
                      {isSelected && (
                        <div style={{
                          position: "absolute", top: 8, right: 8,
                          width: 6, height: 6, borderRadius: "50%",
                          background: catColor,
                        }} />
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Divider */}
          {selectedEvent && (
            <div style={{ borderTop: "1px solid #141414", marginBottom: 0 }} />
          )}

          {/* Event Analysis Panel */}
          {selectedEvent && (
            <div style={{ padding: "16px 0" }}>

              {/* Event meta header */}
              <div style={{
                display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap",
                marginBottom: 12, paddingBottom: 12, borderBottom: "1px solid #111",
              }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: "#e5e5e5" }}>EVENT:</span>
                <span style={{ fontSize: 13, fontWeight: 700, color: categoryColor(selectedEvent.category) }}>
                  {selectedEvent.name}
                </span>
                <span style={{ fontSize: 9, color: "#333" }}>|</span>
                <span style={{ fontSize: 10, color: "#555", fontFamily: "monospace" }}>
                  {formatDate(selectedEvent.start)} – {formatDate(selectedEvent.end)}
                </span>
                <span style={{ fontSize: 9, color: "#333" }}>|</span>
                <span style={{ fontSize: 10, color: "#444", fontFamily: "monospace" }}>
                  {daysBetween(selectedEvent.start, selectedEvent.end)} days
                </span>
                <span style={{
                  fontSize: 8, letterSpacing: "0.06em", fontWeight: 700,
                  color: categoryColor(selectedEvent.category),
                  border: `1px solid ${categoryColor(selectedEvent.category)}44`,
                  padding: "1px 6px", borderRadius: 3, textTransform: "uppercase",
                }}>{selectedEvent.category}</span>
              </div>

              <div style={{ fontSize: 11, color: "#555", marginBottom: 16, fontStyle: "italic" }}>
                "{selectedEvent.description}"
              </div>

              {/* Loading state */}
              {analysisLoading && (
                <div style={{
                  background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: 6,
                  padding: "28px 20px", textAlign: "center",
                }}>
                  <div style={{ marginBottom: 10 }}>
                    <div style={{
                      display: "inline-block", width: 20, height: 20, borderRadius: "50%",
                      border: "2px solid #1a1a1a", borderTopColor: "#3b82f6",
                      animation: "spin 0.8s linear infinite",
                    }} />
                  </div>
                  <div style={{ fontSize: 11, color: "#555", marginBottom: 4 }}>
                    Fetching historical price data from Yahoo Finance...
                  </div>
                  <div style={{ fontSize: 10, color: "#333" }}>
                    (may take up to 20s for cold start)
                  </div>
                </div>
              )}

              {/* Error state */}
              {analysisError && !analysisLoading && (
                <div style={{
                  background: "#1a0a0a", border: "1px solid #ff3b3b33", borderRadius: 6,
                  padding: "14px 16px",
                }}>
                  <div style={{ fontSize: 10, color: "#ff3b3b", marginBottom: 4 }}>ANALYSIS FAILED</div>
                  <div style={{ fontSize: 11, color: "#666" }}>{analysisError}</div>
                </div>
              )}

              {/* Analysis data */}
              {analysis && !analysisLoading && (
                <div>
                  <div style={{ fontSize: 9, color: "#444", letterSpacing: "0.1em", marginBottom: 12 }}>
                    SECTOR PERFORMANCE DURING EVENT
                  </div>

                  {/* Nifty50 benchmark first */}
                  {nifty50Entry && (
                    <div style={{
                      marginBottom: 12, paddingBottom: 10, borderBottom: "1px solid #141414",
                    }}>
                      <BarRow label={nifty50Entry[0]} returnPct={nifty50Entry[1].return_pct} isIndex />
                    </div>
                  )}

                  {/* All sectors sorted */}
                  <div style={{ marginBottom: 20 }}>
                    {sectorEntries.map(([name, perf]) => (
                      <BarRow key={name} label={name} returnPct={perf.return_pct} isIndex={false} />
                    ))}
                  </div>

                  {/* Outperform / Underperform split */}
                  <div style={{
                    display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 8,
                  }}>
                    <div style={{
                      background: "#040d07", border: "1px solid #00d08422", borderRadius: 6,
                      padding: "12px 14px",
                    }}>
                      <div style={{ fontSize: 9, color: "#00d084", letterSpacing: "0.08em", marginBottom: 10 }}>
                        SECTORS THAT OUTPERFORMED
                      </div>
                      {outperformers.length === 0 && (
                        <div style={{ fontSize: 10, color: "#333" }}>None</div>
                      )}
                      {outperformers.map(([name, perf]) => (
                        <div key={name} style={{
                          display: "flex", justifyContent: "space-between", alignItems: "center",
                          padding: "3px 0", borderBottom: "1px solid #0d1a0d",
                        }}>
                          <span style={{ fontSize: 11, color: "#ccc" }}>{name}</span>
                          <span className="num" style={{ fontSize: 11, color: "#00d084", fontWeight: 700 }}>
                            +{perf.return_pct.toFixed(1)}%
                          </span>
                        </div>
                      ))}
                    </div>

                    <div style={{
                      background: "#0d0404", border: "1px solid #ff3b3b22", borderRadius: 6,
                      padding: "12px 14px",
                    }}>
                      <div style={{ fontSize: 9, color: "#ff3b3b", letterSpacing: "0.08em", marginBottom: 10 }}>
                        SECTORS THAT UNDERPERFORMED
                      </div>
                      {underperformers.length === 0 && (
                        <div style={{ fontSize: 10, color: "#333" }}>None</div>
                      )}
                      {[...underperformers].reverse().map(([name, perf]) => (
                        <div key={name} style={{
                          display: "flex", justifyContent: "space-between", alignItems: "center",
                          padding: "3px 0", borderBottom: "1px solid #1a0d0d",
                        }}>
                          <span style={{ fontSize: 11, color: "#ccc" }}>{name}</span>
                          <span className="num" style={{ fontSize: 11, color: "#ff3b3b", fontWeight: 700 }}>
                            {perf.return_pct.toFixed(1)}%
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Divider */}
          <div style={{ borderTop: "1px solid #141414", marginBottom: 0 }} />

          {/* Section 3: Currently Similar Events */}
          <div style={{ padding: "16px 0" }}>
            <div style={{ fontSize: 9, color: "#444", letterSpacing: "0.1em", marginBottom: 12 }}>CURRENT MARKET PATTERN SIMILARITY</div>
            <SimilarityPanel />
          </div>

        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 0.8; } }
        .num { font-family: monospace; }
      `}</style>
    </div>
  );
}

function SimilarityPanel() {
  const [data, setData] = useState<{ similar_event?: string; reasoning?: string; vix?: number; momentum?: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${BASE_URL}/api/patterns/NIFTY`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(d => { setData(d); setLoading(false); })
      .catch(err => { setError(err.message); setLoading(false); });
  }, []);

  if (loading) {
    return (
      <div style={{
        background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: 6,
        padding: "16px 18px",
      }}>
        <div style={{ fontSize: 10, color: "#333" }}>Loading pattern similarity data...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={{
        background: "#0a0a0a", border: "1px solid #1e2a3a", borderRadius: 6,
        padding: "16px 18px",
      }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
          <div style={{
            width: 6, height: 6, borderRadius: "50%", background: "#3b82f6",
            marginTop: 3, flexShrink: 0,
          }} />
          <div>
            <div style={{ fontSize: 11, color: "#3b82f6", marginBottom: 6, fontWeight: 700 }}>
              PATTERN SIMILARITY ENGINE
            </div>
            <div style={{ fontSize: 10, color: "#555", lineHeight: 1.6 }}>
              This module compares current market conditions (VIX levels, price momentum, volume profile, and breadth indicators) against historical events to identify structural similarities.
            </div>
            <div style={{ marginTop: 10, fontSize: 10, color: "#333" }}>
              Endpoint <span style={{ color: "#444", fontFamily: "monospace" }}>/api/patterns/NIFTY</span> is not available. Connect the backend to enable live pattern matching.
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{
      background: "#05080d", border: "1px solid #1e2a3a", borderRadius: 6,
      padding: "16px 18px",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#3b82f6" }} />
        <span style={{ fontSize: 11, color: "#3b82f6", fontWeight: 700 }}>MARKET CONDITIONS NOW RESEMBLE</span>
      </div>
      {data.similar_event && (
        <div style={{ fontSize: 16, fontWeight: 700, color: "#e5e5e5", marginBottom: 6 }}>
          {data.similar_event}
        </div>
      )}
      {data.vix !== undefined && (
        <div style={{ fontSize: 10, color: "#555", marginBottom: 8, fontFamily: "monospace" }}>
          VIX: <span style={{ color: "#f59e0b" }}>{data.vix.toFixed(2)}</span>
          {data.momentum && <> · Momentum: <span style={{ color: data.momentum === "bullish" ? "#00d084" : "#ff3b3b" }}>{data.momentum.toUpperCase()}</span></>}
        </div>
      )}
      {data.reasoning && (
        <div style={{ fontSize: 11, color: "#555", lineHeight: 1.6 }}>{data.reasoning}</div>
      )}
    </div>
  );
}
