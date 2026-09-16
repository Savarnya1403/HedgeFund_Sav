'use client';

import { useState, useEffect, useCallback, useRef } from "react";
import IndexBar from "@/components/IndexBar";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

// ─── Types ────────────────────────────────────────────────────────────────────

type Regime = "BULL" | "SIDEWAYS" | "BEAR";

interface RegimeState {
  current_regime: Regime;
  current_color: string;
  transition_matrix: Record<Regime, Record<Regime, number>>;
  regime_probabilities_20d: Record<Regime, number>;
  regime_probabilities_63d: Record<Regime, number>;
  steady_state: Record<Regime, number>;
  expected_duration_periods: Record<Regime, number>;
  state_returns: Record<Regime, { mean_pct: number; std_pct: number }>;
}

interface VolatilityRegime {
  current_vol_pct: number;
  long_run_vol_pct: number;
  vol_percentile: number;
  regime: string;
  color: string;
  signal: string;
  vol_series_daily: number[];
  is_rising: boolean;
}

interface ArbitrageOpportunity {
  name: string;
  sym1: string;
  sym2: string;
  zscore: number;
  signal: string;
  color: string;
  action: string;
  half_life_days: number;
  type: string;
}

interface ArbitrageScan {
  opportunities: ArbitrageOpportunity[];
  active_signals: ArbitrageOpportunity[];
  summary: { total_scanned: number; active_signals: number };
}

interface Pattern {
  id: string;
  name: string;
  description: string;
  sectors: string[];
  avg_return_pct: number;
  reliability_pct: number;
  trigger: string;
  action: string;
  status?: string;
  urgency?: string;
}

interface PatternsData {
  all_patterns: Pattern[];
  currently_active: Pattern[];
  macro_regime: string;
  fii_sentiment: string;
}

interface FactorScores {
  momentum: number;
  value: number;
  quality: number;
  low_vol: number;
  size: number;
}

interface FactorModel {
  factor_scores: FactorScores;
  composite_score: number;
  factor_interpretation: Record<string, string>;
  composite_label: string;
  composite_color: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const REGIMES: Regime[] = ["BULL", "SIDEWAYS", "BEAR"];
const REGIME_COLORS: Record<Regime, string> = {
  BULL: "#00d084",
  SIDEWAYS: "#f59e0b",
  BEAR: "#ff3b3b",
};

function sectionHeader(title: string) {
  return (
    <div style={{
      padding: "10px 20px 8px",
      borderBottom: "1px solid #141414",
      background: "#000",
    }}>
      <span style={{
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: "0.12em",
        color: "#555",
        fontFamily: "monospace",
        textTransform: "uppercase" as const,
      }}>{title}</span>
    </div>
  );
}

function LoadingBar() {
  return (
    <div style={{ padding: 32, textAlign: "center", color: "#333", fontFamily: "monospace", fontSize: 11 }}>
      LOADING…
    </div>
  );
}

// ─── Transition Matrix ────────────────────────────────────────────────────────

function TransitionMatrix({ matrix }: { matrix: Record<Regime, Record<Regime, number>> }) {
  const [tooltip, setTooltip] = useState<{ from: Regime; to: Regime; val: number } | null>(null);

  return (
    <div>
      <div style={{ fontSize: 9, color: "#444", marginBottom: 6, fontFamily: "monospace", letterSpacing: "0.08em" }}>
        TRANSITION MATRIX (ROW = FROM, COL = TO)
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "60px 1fr 1fr 1fr", gap: 2, fontSize: 9, fontFamily: "monospace" }}>
        {/* header row */}
        <div style={{ color: "#333" }} />
        {REGIMES.map(r => (
          <div key={r} style={{ textAlign: "center", color: REGIME_COLORS[r], fontWeight: 700, padding: "3px 0" }}>
            {r.slice(0, 4)}
          </div>
        ))}
        {/* data rows */}
        {REGIMES.map(from => (
          <>
            <div key={`lbl-${from}`} style={{ color: REGIME_COLORS[from], fontWeight: 700, lineHeight: "24px" }}>
              {from.slice(0, 4)}
            </div>
            {REGIMES.map(to => {
              const val = matrix[from]?.[to] ?? 0;
              const intensity = Math.round(val * 255);
              const isGreen = to === "BULL";
              const isRed = to === "BEAR";
              const bg = isGreen
                ? `rgba(0,208,132,${val * 0.6})`
                : isRed
                ? `rgba(255,59,59,${val * 0.6})`
                : `rgba(245,158,11,${val * 0.5})`;
              void intensity;
              return (
                <div
                  key={`${from}-${to}`}
                  onMouseEnter={() => setTooltip({ from, to, val })}
                  onMouseLeave={() => setTooltip(null)}
                  style={{
                    background: bg,
                    border: "1px solid #1e1e1e",
                    borderRadius: 3,
                    textAlign: "center",
                    padding: "4px 2px",
                    cursor: "default",
                    color: val > 0.5 ? "#fff" : "#aaa",
                    fontWeight: val > 0.5 ? 700 : 400,
                    position: "relative" as const,
                    transition: "border-color 0.15s",
                  }}
                >
                  {(val * 100).toFixed(0)}%
                </div>
              );
            })}
          </>
        ))}
      </div>
      {tooltip && (
        <div style={{
          marginTop: 6,
          fontSize: 10,
          color: "#888",
          fontFamily: "monospace",
          background: "#111",
          border: "1px solid #2e2e2e",
          borderRadius: 4,
          padding: "4px 8px",
          display: "inline-block",
        }}>
          {tooltip.from} → {tooltip.to}: <span style={{ color: "#e5e5e5", fontWeight: 600 }}>{(tooltip.val * 100).toFixed(1)}%</span>
        </div>
      )}
    </div>
  );
}

// ─── Z-Score Bar ──────────────────────────────────────────────────────────────

function ZScoreBar({ zscore, strong }: { zscore: number; strong: boolean }) {
  const clamp = Math.max(-3, Math.min(3, zscore));
  const pct = ((clamp + 3) / 6) * 100;
  const barColor = zscore > 0 ? "#00d084" : "#ff3b3b";

  return (
    <div style={{ position: "relative" as const, width: "100%", height: 16 }}>
      {/* track */}
      <div style={{
        position: "absolute" as const, top: 6, left: 0, right: 0, height: 4,
        background: "#1a1a1a", borderRadius: 2,
        boxShadow: strong ? `0 0 6px ${barColor}55` : "none",
      }} />
      {/* center line */}
      <div style={{
        position: "absolute" as const, top: 4, left: "50%", width: 1, height: 8,
        background: "#444",
      }} />
      {/* bar from center to value */}
      <div style={{
        position: "absolute" as const, top: 6, height: 4,
        left: clamp >= 0 ? "50%" : `${pct}%`,
        width: `${Math.abs(clamp) / 6 * 100}%`,
        background: barColor,
        borderRadius: 2,
        opacity: strong ? 1 : 0.6,
      }} />
      {/* dot */}
      <div style={{
        position: "absolute" as const, top: 3, left: `calc(${pct}% - 4px)`,
        width: 8, height: 10,
        background: barColor,
        borderRadius: 2,
        boxShadow: strong ? `0 0 8px ${barColor}` : "none",
      }} />
      {/* labels */}
      <div style={{
        position: "absolute" as const, top: 13, left: 0, right: 0,
        display: "flex", justifyContent: "space-between",
        fontSize: 8, color: "#333", fontFamily: "monospace",
      }}>
        <span>-3</span><span>0</span><span>+3</span>
      </div>
    </div>
  );
}

// ─── Factor Bar ───────────────────────────────────────────────────────────────

function FactorBar({ label, score, interpretation }: { label: string; score: number | null; interpretation: string }) {
  const s = score ?? 0;
  const color = s > 60 ? "#22c55e" : s >= 40 ? "#f59e0b" : "#ef4444";
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ fontSize: 10, color: "#888", fontFamily: "monospace", letterSpacing: "0.06em", textTransform: "uppercase" as const }}>
          {label}
        </span>
        <span style={{ fontSize: 12, fontWeight: 700, color, fontFamily: "monospace" }}>{s.toFixed(0)}</span>
      </div>
      <div style={{ height: 6, background: "#1a1a1a", borderRadius: 3, overflow: "hidden" }}>
        <div style={{
          height: "100%", width: `${s}%`, background: color,
          borderRadius: 3, transition: "width 0.5s ease",
        }} />
      </div>
      <div style={{ fontSize: 9, color: "#444", marginTop: 3, fontFamily: "monospace" }}>{interpretation}</div>
    </div>
  );
}

// ─── Pattern Card ─────────────────────────────────────────────────────────────

function PatternCard({ pattern, isActive }: { pattern: Pattern; isActive: boolean }) {
  const [hovered, setHovered] = useState(false);

  const statusColor =
    pattern.status === "ACTIVE" ? "#00d084"
      : pattern.status === "APPROACHING" ? "#f59e0b"
        : pattern.status === "ONGOING" ? "#3b82f6"
          : isActive ? "#00d084"
            : "#444";

  const borderColor = isActive
    ? pattern.status === "ACTIVE" ? "#00d08440"
      : pattern.status === "APPROACHING" ? "#f59e0b40"
        : pattern.status === "ONGOING" ? "#3b82f640"
          : "#00d08430"
    : "#1e1e1e";

  const glowShadow = isActive
    ? `0 0 12px ${statusColor}30`
    : "none";

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: hovered ? "#141414" : "#000",
        border: `1px solid ${borderColor}`,
        borderRadius: 6,
        padding: 14,
        cursor: "default",
        transition: "background 0.15s, box-shadow 0.15s",
        boxShadow: hovered ? glowShadow : "none",
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: "#e5e5e5", fontFamily: "monospace", lineHeight: 1.3 }}>
          {pattern.name}
        </span>
        {(pattern.status || isActive) && (
          <span style={{
            fontSize: 8, fontWeight: 700, letterSpacing: "0.08em",
            color: statusColor,
            background: statusColor + "20",
            border: `1px solid ${statusColor}40`,
            borderRadius: 3,
            padding: "2px 6px",
            fontFamily: "monospace",
            whiteSpace: "nowrap" as const,
            boxShadow: pattern.status === "ACTIVE" ? `0 0 8px ${statusColor}60` : "none",
          }}>
            {pattern.status ?? (isActive ? "ACTIVE" : "")}
          </span>
        )}
      </div>

      {/* Description */}
      <div style={{
        fontSize: 10, color: "#666", fontFamily: "monospace", lineHeight: 1.5,
        marginBottom: 10,
        display: "-webkit-box" as unknown as undefined,
        WebkitLineClamp: 2,
        WebkitBoxOrient: "vertical" as unknown as undefined,
        overflow: "hidden",
      }}>
        {pattern.description}
      </div>

      {/* Stats */}
      <div style={{ display: "flex", gap: 16, marginBottom: 8 }}>
        <div>
          <div style={{ fontSize: 8, color: "#444", fontFamily: "monospace", letterSpacing: "0.06em" }}>AVG RETURN</div>
          <div style={{ fontSize: 13, fontWeight: 700, color: pattern.avg_return_pct >= 0 ? "#00d084" : "#ff3b3b", fontFamily: "monospace" }}>
            {pattern.avg_return_pct >= 0 ? "+" : ""}{pattern.avg_return_pct.toFixed(1)}%
          </div>
        </div>
        <div>
          <div style={{ fontSize: 8, color: "#444", fontFamily: "monospace", letterSpacing: "0.06em" }}>RELIABILITY</div>
          <div style={{ fontSize: 13, fontWeight: 700, color: pattern.reliability_pct >= 65 ? "#22c55e" : pattern.reliability_pct >= 50 ? "#f59e0b" : "#ef4444", fontFamily: "monospace" }}>
            {pattern.reliability_pct.toFixed(0)}%
          </div>
        </div>
      </div>

      {/* Trigger */}
      {pattern.trigger && (
        <div style={{ fontSize: 9, color: "#555", fontFamily: "monospace", marginBottom: 6 }}>
          <span style={{ color: "#444" }}>TRIGGER: </span>{pattern.trigger}
        </div>
      )}

      {/* Sectors */}
      {pattern.sectors?.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap" as const, gap: 4, marginBottom: 8 }}>
          {pattern.sectors.slice(0, 4).map(s => (
            <span key={s} style={{
              fontSize: 8, color: "#888", background: "#111",
              border: "1px solid #222", borderRadius: 3, padding: "1px 5px", fontFamily: "monospace",
            }}>{s}</span>
          ))}
        </div>
      )}

      {/* Action */}
      {pattern.action && (
        <div style={{ fontSize: 9, color: "#666", fontFamily: "monospace", fontStyle: "italic", borderTop: "1px solid #1a1a1a", paddingTop: 6 }}>
          {pattern.action}
        </div>
      )}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function QuantPage() {
  const [regime, setRegime] = useState<RegimeState | null>(null);
  const [volRegime, setVolRegime] = useState<VolatilityRegime | null>(null);
  const [arbScan, setArbScan] = useState<ArbitrageScan | null>(null);
  const [patterns, setPatterns] = useState<PatternsData | null>(null);
  const [factorModel, setFactorModel] = useState<FactorModel | null>(null);
  const [factorSymbol, setFactorSymbol] = useState("HDFCBANK");
  const [factorInput, setFactorInput] = useState("HDFCBANK");
  const [loadingRegime, setLoadingRegime] = useState(true);
  const [loadingVol, setLoadingVol] = useState(true);
  const [loadingArb, setLoadingArb] = useState(true);
  const [loadingPatterns, setLoadingPatterns] = useState(true);
  const [loadingFactor, setLoadingFactor] = useState(false);
  const [lastUpdate, setLastUpdate] = useState("");
  const factorTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchRegime = useCallback(async () => {
    setLoadingRegime(true);
    try {
      const r = await fetch(`${API_BASE}/api/market-regime/NIFTY50?period=1y`);
      if (r.ok) setRegime(await r.json());
    } catch { /* ignore */ } finally { setLoadingRegime(false); }
  }, []);

  const fetchVol = useCallback(async () => {
    setLoadingVol(true);
    try {
      const r = await fetch(`${API_BASE}/api/volatility-regime/NIFTY50`);
      if (r.ok) setVolRegime(await r.json());
    } catch { /* ignore */ } finally { setLoadingVol(false); }
  }, []);

  const fetchArb = useCallback(async () => {
    setLoadingArb(true);
    try {
      const r = await fetch(`${API_BASE}/api/arbitrage-scan`);
      if (r.ok) setArbScan(await r.json());
    } catch { /* ignore */ } finally { setLoadingArb(false); }
  }, []);

  const fetchPatterns = useCallback(async () => {
    setLoadingPatterns(true);
    try {
      const r = await fetch(`${API_BASE}/api/repeating-patterns`);
      if (r.ok) setPatterns(await r.json());
    } catch { /* ignore */ } finally { setLoadingPatterns(false); }
  }, []);

  const fetchFactor = useCallback(async (sym: string) => {
    setLoadingFactor(true);
    setFactorModel(null);
    try {
      const r = await fetch(`${API_BASE}/api/factor-model/${sym.trim().toUpperCase()}`);
      if (r.ok) setFactorModel(await r.json());
    } catch { /* ignore */ } finally { setLoadingFactor(false); }
  }, []);

  useEffect(() => {
    fetchRegime();
    fetchVol();
    fetchArb();
    fetchPatterns();
    fetchFactor("HDFCBANK");
    setLastUpdate(new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }));
  }, [fetchRegime, fetchVol, fetchArb, fetchPatterns, fetchFactor]);

  // Debounce factor symbol input
  useEffect(() => {
    if (factorTimerRef.current) clearTimeout(factorTimerRef.current);
    factorTimerRef.current = setTimeout(() => {
      if (factorInput.trim().length >= 2) {
        setFactorSymbol(factorInput.trim().toUpperCase());
        fetchFactor(factorInput.trim());
      }
    }, 600);
    return () => { if (factorTimerRef.current) clearTimeout(factorTimerRef.current); };
  }, [factorInput, fetchFactor]);

  // Collect all active pattern IDs for quick lookup
  const activePatternIds = new Set((patterns?.currently_active ?? []).map(p => p.id));

  const allPatterns: Pattern[] = patterns
    ? [
        ...patterns.currently_active,
        ...patterns.all_patterns.filter(p => !activePatternIds.has(p.id)),
      ]
    : [];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden", background: "#000", fontFamily: "monospace" }}>
      <IndexBar />

      <div style={{ flex: 1, overflow: "auto", background: "#000" }}>
        {/* Page Header */}
        <div style={{
          padding: "12px 20px",
          borderBottom: "1px solid #141414",
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: "#e5e5e5", letterSpacing: "0.1em", fontFamily: "monospace" }}>
              QUANTITATIVE MODELS HUB
            </h1>
            <div style={{ fontSize: 10, color: "#444", marginTop: 2, fontFamily: "monospace" }}>
              NIFTY50 · MARKOV · GARCH · ARBITRAGE · FACTOR MODELS
            </div>
          </div>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            {lastUpdate && (
              <span style={{ fontSize: 9, color: "#333", fontFamily: "monospace" }}>UPDATED {lastUpdate}</span>
            )}
            <button
              onClick={() => { fetchRegime(); fetchVol(); fetchArb(); fetchPatterns(); setLastUpdate(new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })); }}
              style={{
                background: "#111", border: "1px solid #2e2e2e", color: "#888",
                borderRadius: 4, padding: "4px 12px", fontSize: 10,
                cursor: "pointer", fontFamily: "monospace",
              }}
            >
              ↻ REFRESH
            </button>
          </div>
        </div>

        {/* ── Row 1: Regime + Vol side by side ── */}
        <div style={{ borderBottom: "1px solid #141414" }}>
          {sectionHeader("MARKOV CHAIN REGIME  ·  VOLATILITY REGIME")}
          <div style={{ display: "flex", gap: 0 }}>

            {/* Markov Regime */}
            <div style={{ flex: 1, padding: "16px 20px", borderRight: "1px solid #141414", minWidth: 0 }}>
              {loadingRegime ? <LoadingBar /> : regime ? (
                <>
                  {/* Current badge */}
                  <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
                    <span style={{
                      fontSize: 18, fontWeight: 700, color: regime.current_color,
                      fontFamily: "monospace", letterSpacing: "0.06em",
                      textShadow: `0 0 20px ${regime.current_color}60`,
                    }}>
                      {regime.current_regime}
                    </span>
                    <span style={{ fontSize: 9, color: "#555" }}>CURRENT REGIME</span>
                  </div>

                  {/* Transition matrix */}
                  <TransitionMatrix matrix={regime.transition_matrix} />

                  {/* 20D / 63D probs */}
                  <div style={{ display: "flex", gap: 20, marginTop: 14 }}>
                    {(["20d", "63d"] as const).map(horizon => {
                      const probs = horizon === "20d" ? regime.regime_probabilities_20d : regime.regime_probabilities_63d;
                      return (
                        <div key={horizon}>
                          <div style={{ fontSize: 9, color: "#444", marginBottom: 5, letterSpacing: "0.06em" }}>
                            {horizon.toUpperCase()} FORECAST
                          </div>
                          {REGIMES.map(r => (
                            <div key={r} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
                              <span style={{ fontSize: 8, color: REGIME_COLORS[r], fontFamily: "monospace", width: 52 }}>{r}</span>
                              <div style={{ width: 60, height: 4, background: "#1a1a1a", borderRadius: 2 }}>
                                <div style={{ height: "100%", width: `${((probs[r] ?? 0) * 100)}%`, background: REGIME_COLORS[r], borderRadius: 2, opacity: 0.8 }} />
                              </div>
                              <span style={{ fontSize: 9, color: "#888", fontFamily: "monospace" }}>{((probs[r] ?? 0) * 100).toFixed(0)}%</span>
                            </div>
                          ))}
                        </div>
                      );
                    })}

                    {/* Expected duration */}
                    <div>
                      <div style={{ fontSize: 9, color: "#444", marginBottom: 5, letterSpacing: "0.06em" }}>
                        EXP. DURATION
                      </div>
                      {REGIMES.map(r => (
                        <div key={r} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
                          <span style={{ fontSize: 8, color: REGIME_COLORS[r], fontFamily: "monospace", width: 52 }}>{r}</span>
                          <span style={{ fontSize: 9, color: "#888", fontFamily: "monospace" }}>
                            {(regime.expected_duration_periods[r] ?? 0).toFixed(1)} periods
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* State returns */}
                  <div style={{ marginTop: 12, display: "flex", gap: 16 }}>
                    {REGIMES.map(r => {
                      const ret = regime.state_returns[r];
                      if (!ret) return null;
                      return (
                        <div key={r}>
                          <div style={{ fontSize: 8, color: REGIME_COLORS[r], marginBottom: 2, fontFamily: "monospace" }}>{r}</div>
                          <div style={{ fontSize: 10, color: "#e5e5e5", fontFamily: "monospace" }}>
                            μ {ret.mean_pct >= 0 ? "+" : ""}{ret.mean_pct.toFixed(1)}%
                          </div>
                          <div style={{ fontSize: 9, color: "#555", fontFamily: "monospace" }}>
                            σ {ret.std_pct.toFixed(1)}%
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </>
              ) : (
                <div style={{ color: "#333", fontSize: 11, padding: 16 }}>Failed to load regime data</div>
              )}
            </div>

            {/* Volatility Regime */}
            <div style={{ flex: 1, padding: "16px 20px", minWidth: 0 }}>
              {loadingVol ? <LoadingBar /> : volRegime ? (
                <>
                  {/* Big vol number */}
                  <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 6 }}>
                    <span style={{
                      fontSize: 36, fontWeight: 700, color: volRegime.color,
                      fontFamily: "monospace", lineHeight: 1,
                      textShadow: `0 0 24px ${volRegime.color}50`,
                    }}>
                      {volRegime.current_vol_pct.toFixed(1)}%
                    </span>
                    <span style={{ fontSize: 11, color: "#555", fontFamily: "monospace" }}>ANNUALISED VOL</span>
                  </div>

                  {/* Regime badge */}
                  <div style={{ marginBottom: 12 }}>
                    <span style={{
                      fontSize: 10, fontWeight: 700, color: volRegime.color,
                      background: volRegime.color + "20",
                      border: `1px solid ${volRegime.color}40`,
                      borderRadius: 4, padding: "3px 10px", fontFamily: "monospace",
                      letterSpacing: "0.08em",
                    }}>
                      {volRegime.regime}
                    </span>
                  </div>

                  {/* Percentile bar */}
                  <div style={{ marginBottom: 12 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ fontSize: 9, color: "#444", fontFamily: "monospace" }}>PERCENTILE RANK</span>
                      <span style={{ fontSize: 10, fontWeight: 700, color: "#e5e5e5", fontFamily: "monospace" }}>
                        {volRegime.vol_percentile.toFixed(0)}th
                      </span>
                    </div>
                    <div style={{ height: 8, background: "#1a1a1a", borderRadius: 4, overflow: "hidden" }}>
                      <div style={{
                        height: "100%",
                        width: `${volRegime.vol_percentile}%`,
                        background: volRegime.vol_percentile > 75 ? "#ff3b3b"
                          : volRegime.vol_percentile > 50 ? "#f59e0b"
                            : "#00d084",
                        borderRadius: 4,
                        transition: "width 0.5s ease",
                      }} />
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 8, color: "#333", marginTop: 2 }}>
                      <span>0</span><span>25</span><span>50</span><span>75</span><span>100</span>
                    </div>
                  </div>

                  {/* Rising / Falling */}
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                    <span style={{
                      fontSize: 12,
                      color: volRegime.is_rising ? "#ff3b3b" : "#00d084",
                    }}>
                      {volRegime.is_rising ? "▲" : "▼"}
                    </span>
                    <span style={{ fontSize: 10, color: volRegime.is_rising ? "#ff3b3b" : "#00d084", fontFamily: "monospace" }}>
                      {volRegime.is_rising ? "RISING" : "FALLING"}
                    </span>
                    <span style={{ fontSize: 9, color: "#444", fontFamily: "monospace" }}>
                      long-run {volRegime.long_run_vol_pct.toFixed(1)}%
                    </span>
                  </div>

                  {/* Signal */}
                  <div style={{
                    background: "#111", border: "1px solid #1e1e1e", borderRadius: 4,
                    padding: "8px 12px", fontSize: 10, color: "#aaa", fontFamily: "monospace", lineHeight: 1.5,
                  }}>
                    {volRegime.signal}
                  </div>
                </>
              ) : (
                <div style={{ color: "#333", fontSize: 11, padding: 16 }}>Failed to load volatility data</div>
              )}
            </div>
          </div>
        </div>

        {/* ── Arbitrage Scanner ── */}
        <div style={{ borderBottom: "1px solid #141414" }}>
          {sectionHeader("CROSS-ASSET ARBITRAGE SCANNER")}
          <div style={{ padding: "12px 20px" }}>
            {loadingArb ? <LoadingBar /> : arbScan ? (
              <>
                {/* Summary */}
                <div style={{ display: "flex", gap: 20, marginBottom: 12 }}>
                  <div style={{ fontSize: 10, color: "#555", fontFamily: "monospace" }}>
                    <span style={{ color: "#888" }}>PAIRS SCANNED: </span>
                    <span style={{ color: "#e5e5e5", fontWeight: 700 }}>{arbScan.summary.total_scanned}</span>
                  </div>
                  <div style={{ fontSize: 10, color: "#555", fontFamily: "monospace" }}>
                    <span style={{ color: "#888" }}>ACTIVE SIGNALS: </span>
                    <span style={{ color: arbScan.summary.active_signals > 0 ? "#00d084" : "#555", fontWeight: 700 }}>
                      {arbScan.summary.active_signals}
                    </span>
                  </div>
                </div>

                {/* Table */}
                <div style={{ background: "#050505", border: "1px solid #1a1a1a", borderRadius: 6, overflow: "hidden" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse" }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid #1a1a1a" }}>
                        {["PAIR", "TYPE", "Z-SCORE", "SIGNAL", "ACTION", "HALF-LIFE"].map(h => (
                          <th key={h} style={{
                            padding: "7px 14px", fontSize: 9, color: "#444", fontWeight: 700,
                            letterSpacing: "0.08em", textAlign: h === "PAIR" || h === "TYPE" || h === "SIGNAL" || h === "ACTION" ? "left" : "center",
                            fontFamily: "monospace",
                          }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {arbScan.opportunities.map((opp, i) => {
                        const strong = Math.abs(opp.zscore) >= 2;
                        return (
                          <tr
                            key={i}
                            style={{
                              borderBottom: "1px solid #111",
                              boxShadow: strong ? `inset 0 0 0 1px ${opp.color}30` : "none",
                            }}
                            onMouseEnter={e => (e.currentTarget.style.background = "#0d0d0d")}
                            onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                          >
                            <td style={{ padding: "9px 14px", minWidth: 160 }}>
                              <div style={{ fontSize: 11, fontWeight: 600, color: "#e5e5e5", fontFamily: "monospace" }}>{opp.name}</div>
                              <div style={{ fontSize: 9, color: "#444", fontFamily: "monospace" }}>{opp.sym1} / {opp.sym2}</div>
                            </td>
                            <td style={{ padding: "9px 14px" }}>
                              <span style={{
                                fontSize: 8, color: "#888", background: "#1a1a1a",
                                border: "1px solid #2e2e2e", borderRadius: 3, padding: "2px 6px", fontFamily: "monospace",
                              }}>
                                {opp.type.replace(/_/g, " ").toUpperCase()}
                              </span>
                            </td>
                            <td style={{ padding: "9px 14px 9px", minWidth: 120 }}>
                              <div style={{ marginBottom: 2 }}>
                                <span style={{ fontSize: 11, fontWeight: 700, color: opp.color, fontFamily: "monospace" }}>
                                  {opp.zscore >= 0 ? "+" : ""}{opp.zscore.toFixed(2)}σ
                                </span>
                              </div>
                              <ZScoreBar zscore={opp.zscore} strong={strong} />
                            </td>
                            <td style={{ padding: "9px 14px" }}>
                              <span style={{
                                fontSize: 9, fontWeight: 700, color: opp.color,
                                background: opp.color + "15",
                                border: `1px solid ${opp.color}30`,
                                borderRadius: 3, padding: "2px 8px", fontFamily: "monospace",
                              }}>
                                {opp.signal}
                              </span>
                            </td>
                            <td style={{ padding: "9px 14px", fontSize: 10, color: "#888", fontFamily: "monospace", maxWidth: 180 }}>
                              {opp.action}
                            </td>
                            <td style={{ padding: "9px 14px", textAlign: "center" }}>
                              <span style={{ fontSize: 10, color: "#666", fontFamily: "monospace" }}>
                                {opp.half_life_days != null ? `${opp.half_life_days.toFixed(1)}d` : "—"}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <div style={{ color: "#333", fontSize: 11, padding: 16 }}>Failed to load arbitrage data</div>
            )}
          </div>
        </div>

        {/* ── Repeating Patterns ── */}
        <div style={{ borderBottom: "1px solid #141414" }}>
          {sectionHeader("REPEATING MARKET PATTERNS")}
          <div style={{ padding: "12px 20px" }}>
            {loadingPatterns ? <LoadingBar /> : patterns ? (
              <>
                {/* Macro regime info */}
                <div style={{ display: "flex", gap: 20, marginBottom: 14 }}>
                  <div style={{ fontSize: 10, color: "#555", fontFamily: "monospace" }}>
                    <span style={{ color: "#444" }}>MACRO REGIME: </span>
                    <span style={{ color: "#e5e5e5", fontWeight: 600 }}>{patterns.macro_regime}</span>
                  </div>
                  <div style={{ fontSize: 10, color: "#555", fontFamily: "monospace" }}>
                    <span style={{ color: "#444" }}>FII SENTIMENT: </span>
                    <span style={{
                      color: patterns.fii_sentiment?.toLowerCase().includes("bull") ? "#00d084"
                        : patterns.fii_sentiment?.toLowerCase().includes("bear") ? "#ff3b3b"
                          : "#f59e0b",
                      fontWeight: 600,
                    }}>{patterns.fii_sentiment}</span>
                  </div>
                  <div style={{ fontSize: 10, color: "#555", fontFamily: "monospace" }}>
                    <span style={{ color: "#444" }}>ACTIVE PATTERNS: </span>
                    <span style={{ color: "#00d084", fontWeight: 600 }}>{patterns.currently_active.length}</span>
                    <span style={{ color: "#333" }}> / {allPatterns.length}</span>
                  </div>
                </div>

                {/* Pattern grid */}
                <div style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(3, 1fr)",
                  gap: 10,
                }}>
                  {allPatterns.map(p => (
                    <PatternCard key={p.id} pattern={p} isActive={activePatternIds.has(p.id)} />
                  ))}
                </div>
              </>
            ) : (
              <div style={{ color: "#333", fontSize: 11, padding: 16 }}>Failed to load patterns data</div>
            )}
          </div>
        </div>

        {/* ── Factor Model ── */}
        <div style={{ borderBottom: "1px solid #141414" }}>
          {sectionHeader("MULTI-FACTOR MODEL")}
          <div style={{ padding: "16px 20px" }}>
            {/* Symbol input */}
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
              <span style={{ fontSize: 10, color: "#555", fontFamily: "monospace" }}>SYMBOL</span>
              <input
                value={factorInput}
                onChange={e => setFactorInput(e.target.value.toUpperCase())}
                onKeyDown={e => { if (e.key === "Enter") { setFactorSymbol(factorInput.trim().toUpperCase()); fetchFactor(factorInput.trim()); } }}
                placeholder="e.g. HDFCBANK"
                style={{
                  background: "#0d0d0d",
                  border: "1px solid #2e2e2e",
                  borderRadius: 4,
                  color: "#e5e5e5",
                  fontFamily: "monospace",
                  fontSize: 12,
                  padding: "5px 12px",
                  outline: "none",
                  width: 140,
                  letterSpacing: "0.06em",
                }}
              />
              <span style={{ fontSize: 9, color: "#333", fontFamily: "monospace" }}>
                {loadingFactor ? "LOADING…" : factorModel ? `SHOWING: ${factorSymbol}` : ""}
              </span>
            </div>

            {loadingFactor ? (
              <LoadingBar />
            ) : factorModel ? (
              <div style={{ display: "flex", gap: 32, flexWrap: "wrap" as const }}>
                {/* Factor bars */}
                <div style={{ flex: 2, minWidth: 260 }}>
                  <div style={{ fontSize: 9, color: "#444", marginBottom: 12, letterSpacing: "0.08em" }}>
                    FACTOR SCORES (0–100)
                  </div>
                  {(Object.entries(factorModel.factor_scores) as [string, number][]).map(([factor, score]) => (
                    <FactorBar
                      key={factor}
                      label={factor.replace(/_/g, " ")}
                      score={score}
                      interpretation={factorModel.factor_interpretation[factor] ?? ""}
                    />
                  ))}
                </div>

                {/* Composite score gauge */}
                <div style={{ flex: 1, minWidth: 160, display: "flex", flexDirection: "column" as const, alignItems: "center", justifyContent: "center" }}>
                  <div style={{ fontSize: 9, color: "#444", marginBottom: 12, letterSpacing: "0.08em", fontFamily: "monospace" }}>
                    COMPOSITE SCORE
                  </div>
                  {/* Circular-ish gauge — simple big number with ring context */}
                  <div style={{
                    width: 120, height: 120,
                    borderRadius: "50%",
                    border: `3px solid ${factorModel.composite_color}`,
                    boxShadow: `0 0 24px ${factorModel.composite_color}40, inset 0 0 24px ${factorModel.composite_color}10`,
                    display: "flex", flexDirection: "column" as const, alignItems: "center", justifyContent: "center",
                    marginBottom: 12,
                  }}>
                    <span style={{
                      fontSize: 32, fontWeight: 700, color: factorModel.composite_color,
                      fontFamily: "monospace", lineHeight: 1,
                    }}>
                      {factorModel.composite_score.toFixed(0)}
                    </span>
                    <span style={{ fontSize: 9, color: "#555", fontFamily: "monospace" }}>/ 100</span>
                  </div>
                  <span style={{
                    fontSize: 13, fontWeight: 700, color: factorModel.composite_color,
                    fontFamily: "monospace", letterSpacing: "0.08em",
                    background: factorModel.composite_color + "20",
                    border: `1px solid ${factorModel.composite_color}40`,
                    borderRadius: 4, padding: "4px 14px",
                  }}>
                    {factorModel.composite_label}
                  </span>
                </div>
              </div>
            ) : (
              <div style={{ color: "#333", fontSize: 11, padding: 16 }}>Enter a symbol to load factor model</div>
            )}
          </div>
        </div>

        {/* Bottom padding */}
        <div style={{ height: 40 }} />
      </div>
    </div>
  );
}
