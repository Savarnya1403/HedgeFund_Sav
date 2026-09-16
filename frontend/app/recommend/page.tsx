'use client';

import { useState, useEffect, useCallback } from "react";
import IndexBar from "@/components/IndexBar";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

// ─── Types ───────────────────────────────────────────────────────────────────

type Action = "STRONG BUY" | "BUY" | "HOLD" | "SELL" | "STRONG SELL";
type Conviction = "HIGH" | "MEDIUM" | "LOW";
type RiskReward = "FAVORABLE" | "NEUTRAL" | "UNFAVORABLE";

interface PillarScores {
  technical: number;
  fundamental: number;
  macro: number;
  quality: number;
  momentum: number;
  risk: number;
}

interface RankedStock {
  symbol: string;
  composite_score: number;
  action: Action;
  color: string;
  pillar_scores: PillarScores;
  top_reason: string;
  price: number;
  change_pct: number;
  sector: string;
}

interface SectorRotation {
  preferred_sectors: string[];
  avoid_sectors: string[];
  reasoning: string;
}

interface UniverseResponse {
  ranked: RankedStock[];
  sector_rotation: SectorRotation;
  total: number;
}

interface DetailResponse {
  symbol: string;
  action: Action;
  color: string;
  icon: string;
  composite_score: number;
  conviction: Conviction;
  risk_reward: RiskReward;
  pillar_scores: PillarScores;
  pillar_weights: PillarScores;
  bull_arguments: string[];
  bear_arguments: string[];
  target_price: number | null;
  stop_loss: number | null;
  upside_pct: number;
  time_horizon: string;
  position_size_suggestion: string;
  summary: string;
}

interface SectorRotationResponse {
  preferred_sectors: string[];
  avoid_sectors: string[];
  all_scores: Record<string, number>;
  macro_regime: string;
  reasoning: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const ACTION_COLORS: Record<string, string> = {
  "STRONG BUY": "#00d084",
  "BUY": "#22c55e",
  "HOLD": "#f59e0b",
  "SELL": "#ef4444",
  "STRONG SELL": "#ff3b3b",
};

const PILLAR_LABELS: (keyof PillarScores)[] = [
  "technical", "fundamental", "macro", "quality", "momentum", "risk",
];

// ─── Utility components ───────────────────────────────────────────────────────

function scoreColor(score: number): string {
  if (score >= 60) return "#22c55e";
  if (score >= 40) return "#f59e0b";
  return "#ef4444";
}

function scoreBarGradient(score: number): string {
  // Gradient from red→amber→green based on score position
  const pct = score; // 0-100
  if (pct >= 60) return `linear-gradient(90deg, #ef4444 0%, #f59e0b 40%, #22c55e ${pct}%, #1a1a1a ${pct}%)`;
  if (pct >= 40) return `linear-gradient(90deg, #ef4444 0%, #f59e0b ${pct}%, #1a1a1a ${pct}%)`;
  return `linear-gradient(90deg, #ef4444 ${pct}%, #1a1a1a ${pct}%)`;
}

function MiniScoreBar({ score, width = 60 }: { score: number; width?: number }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{
        width, height: 5, borderRadius: 3,
        background: scoreBarGradient(score),
        border: "1px solid #2a2a2a",
      }} />
      <span style={{ fontSize: 10, color: scoreColor(score), fontWeight: 600, minWidth: 24 }}>
        {score.toFixed(0)}
      </span>
    </div>
  );
}

function ActionBadge({ action }: { action: Action }) {
  const color = ACTION_COLORS[action] || "#888";
  return (
    <span style={{
      display: "inline-block",
      padding: "2px 6px",
      fontSize: 9,
      fontWeight: 700,
      background: color + "22",
      color,
      border: `1px solid ${color}44`,
      borderRadius: 3,
      letterSpacing: "0.05em",
      whiteSpace: "nowrap",
    }}>
      {action}
    </span>
  );
}

function PillarBar({ label, score, weight }: { label: string; score: number; weight: number }) {
  const color = scoreColor(score);
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
        <span style={{ fontSize: 10, color: "#888", textTransform: "capitalize" }}>
          {label}
          <span style={{ color: "#444", marginLeft: 4 }}>({Math.round(weight * 100)}% wt)</span>
        </span>
        <span style={{ fontSize: 10, color, fontWeight: 600 }}>{score}</span>
      </div>
      <div style={{ height: 4, background: "#1a1a1a", borderRadius: 2, overflow: "hidden" }}>
        <div style={{
          height: "100%",
          width: `${score}%`,
          background: color,
          borderRadius: 2,
          transition: "width 0.4s ease",
        }} />
      </div>
    </div>
  );
}

function FilterButton({
  label, active, onClick,
}: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: "4px 10px",
        fontSize: 10,
        fontWeight: 600,
        border: "1px solid",
        borderColor: active ? "#3b82f6" : "#2a2a2a",
        background: active ? "#3b82f620" : "transparent",
        color: active ? "#3b82f6" : "#555",
        borderRadius: 4,
        cursor: "pointer",
        letterSpacing: "0.05em",
        fontFamily: "inherit",
      }}
    >
      {label}
    </button>
  );
}

function SortButton({
  label, active, onClick,
}: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: "3px 8px",
        fontSize: 10,
        border: "none",
        background: active ? "#1e1e1e" : "transparent",
        color: active ? "#e5e5e5" : "#555",
        borderRadius: 3,
        cursor: "pointer",
        fontFamily: "inherit",
      }}
    >
      {label}
    </button>
  );
}

// ─── Detail Panel ─────────────────────────────────────────────────────────────

function DetailPanel({
  detail,
  onClose,
}: {
  detail: DetailResponse;
  onClose: () => void;
}) {
  const actionColor = ACTION_COLORS[detail.action] || detail.color;
  const rrColor =
    detail.risk_reward === "FAVORABLE" ? "#22c55e" :
    detail.risk_reward === "UNFAVORABLE" ? "#ef4444" : "#f59e0b";
  const convColor =
    detail.conviction === "HIGH" ? "#22c55e" :
    detail.conviction === "LOW" ? "#ef4444" : "#f59e0b";

  return (
    <div style={{
      background: "#0a0a0a",
      border: "1px solid #1e3a5f",
      borderRadius: 8,
      padding: 16,
      marginTop: 12,
      fontFamily: "inherit",
    }}>
      {/* Header row */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span style={{ fontSize: 18, fontWeight: 700, color: "#e5e5e5" }}>{detail.symbol}</span>
          <span style={{ fontSize: 15, color: actionColor, fontWeight: 700 }}>
            {detail.icon} {detail.action}
          </span>
          <span style={{
            fontSize: 10, padding: "2px 7px", borderRadius: 3,
            background: "#1e1e1e", color: "#888",
          }}>
            SCORE <span style={{ color: scoreColor(detail.composite_score), fontWeight: 700 }}>
              {detail.composite_score.toFixed(1)}/100
            </span>
          </span>
          <span style={{
            fontSize: 10, padding: "2px 7px", borderRadius: 3,
            background: convColor + "22", color: convColor, fontWeight: 600,
          }}>
            {detail.conviction} CONVICTION
          </span>
          <span style={{
            fontSize: 10, padding: "2px 7px", borderRadius: 3,
            background: rrColor + "22", color: rrColor, fontWeight: 600,
          }}>
            {detail.risk_reward}
          </span>
        </div>
        <button
          onClick={onClose}
          style={{
            background: "none", border: "none", color: "#444",
            cursor: "pointer", fontSize: 16, lineHeight: 1,
          }}
        >
          ✕
        </button>
      </div>

      {/* Summary */}
      <p style={{ fontSize: 11, color: "#aaa", margin: "0 0 14px 0", lineHeight: 1.6 }}>
        {detail.summary}
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: 16 }}>
        {/* Pillar scores */}
        <div>
          <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.08em", marginBottom: 10, fontWeight: 600 }}>
            PILLAR SCORES
          </div>
          {PILLAR_LABELS.map(key => (
            <PillarBar
              key={key}
              label={key}
              score={detail.pillar_scores[key]}
              weight={detail.pillar_weights[key]}
            />
          ))}
        </div>

        {/* Right column */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {/* Bull vs Bear */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <div style={{ fontSize: 10, color: "#22c55e", letterSpacing: "0.08em", marginBottom: 8, fontWeight: 600 }}>
                BULL ARGUMENTS
              </div>
              {detail.bull_arguments.map((arg, i) => (
                <div key={i} style={{ display: "flex", gap: 6, marginBottom: 5 }}>
                  <span style={{ color: "#22c55e", fontSize: 10, marginTop: 1, flexShrink: 0 }}>▲</span>
                  <span style={{ fontSize: 10, color: "#aaa", lineHeight: 1.5 }}>{arg}</span>
                </div>
              ))}
            </div>
            <div>
              <div style={{ fontSize: 10, color: "#ef4444", letterSpacing: "0.08em", marginBottom: 8, fontWeight: 600 }}>
                BEAR ARGUMENTS
              </div>
              {detail.bear_arguments.map((arg, i) => (
                <div key={i} style={{ display: "flex", gap: 6, marginBottom: 5 }}>
                  <span style={{ color: "#ef4444", fontSize: 10, marginTop: 1, flexShrink: 0 }}>▼</span>
                  <span style={{ fontSize: 10, color: "#aaa", lineHeight: 1.5 }}>{arg}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Trade Plan */}
          <div style={{
            background: "#111",
            border: "1px solid #1e1e1e",
            borderRadius: 6,
            padding: 12,
          }}>
            <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.08em", marginBottom: 10, fontWeight: 600 }}>
              TRADE PLAN
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 10 }}>
              {[
                {
                  label: "TARGET PRICE",
                  value: detail.target_price != null
                    ? `₹${detail.target_price.toLocaleString("en-IN", { maximumFractionDigits: 1 })}`
                    : "—",
                  color: "#22c55e",
                },
                {
                  label: "STOP LOSS",
                  value: detail.stop_loss != null
                    ? `₹${detail.stop_loss.toLocaleString("en-IN", { maximumFractionDigits: 1 })}`
                    : "—",
                  color: "#ef4444",
                },
                {
                  label: "UPSIDE",
                  value: `${detail.upside_pct >= 0 ? "+" : ""}${(detail.upside_pct ?? 0).toFixed(1)}%`,
                  color: (detail.upside_pct ?? 0) >= 0 ? "#22c55e" : "#ef4444",
                },
              ].map(card => (
                <div key={card.label} style={{
                  background: "#0d0d0d",
                  border: "1px solid #1e1e1e",
                  borderRadius: 4,
                  padding: "8px 10px",
                  textAlign: "center",
                }}>
                  <div style={{ fontSize: 9, color: "#555", marginBottom: 4, letterSpacing: "0.06em" }}>
                    {card.label}
                  </div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: card.color }}>
                    {card.value}
                  </div>
                </div>
              ))}
            </div>
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
              <div>
                <span style={{ fontSize: 9, color: "#444" }}>HORIZON </span>
                <span style={{ fontSize: 10, color: "#aaa" }}>{detail.time_horizon}</span>
              </div>
              <div>
                <span style={{ fontSize: 9, color: "#444" }}>POSITION SIZE </span>
                <span style={{ fontSize: 10, color: "#aaa" }}>{detail.position_size_suggestion}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Sector Rotation Panel ────────────────────────────────────────────────────

function SectorRotationPanel({ data }: { data: SectorRotationResponse }) {
  return (
    <div style={{
      width: 260,
      flexShrink: 0,
      background: "#0a0a0a",
      border: "1px solid #1a1a1a",
      borderRadius: 8,
      padding: 14,
      display: "flex",
      flexDirection: "column",
      gap: 14,
    }}>
      <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.1em", fontWeight: 700 }}>
        SECTOR ROTATION
      </div>

      {/* Macro regime */}
      <div>
        <div style={{ fontSize: 9, color: "#444", marginBottom: 5 }}>MACRO REGIME</div>
        <span style={{
          display: "inline-block",
          padding: "3px 9px",
          fontSize: 10,
          fontWeight: 700,
          background: data.macro_regime.includes("RISK-ON") ? "#22c55e22" : "#ef444422",
          color: data.macro_regime.includes("RISK-ON") ? "#22c55e" : "#ef4444",
          border: `1px solid ${data.macro_regime.includes("RISK-ON") ? "#22c55e44" : "#ef444444"}`,
          borderRadius: 4,
        }}>
          {data.macro_regime}
        </span>
      </div>

      {/* Preferred sectors */}
      <div>
        <div style={{ fontSize: 9, color: "#444", marginBottom: 6 }}>PREFERRED</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
          {data.preferred_sectors.map(s => (
            <span key={s} style={{
              fontSize: 10,
              padding: "2px 7px",
              background: "#22c55e18",
              color: "#22c55e",
              border: "1px solid #22c55e33",
              borderRadius: 3,
            }}>
              {s}
            </span>
          ))}
        </div>
      </div>

      {/* Avoid sectors */}
      <div>
        <div style={{ fontSize: 9, color: "#444", marginBottom: 6 }}>AVOID</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
          {data.avoid_sectors.map(s => (
            <span key={s} style={{
              fontSize: 10,
              padding: "2px 7px",
              background: "#ef444418",
              color: "#ef4444",
              border: "1px solid #ef444433",
              borderRadius: 3,
            }}>
              {s}
            </span>
          ))}
        </div>
      </div>

      {/* Sector scores */}
      {Object.keys(data.all_scores).length > 0 && (
        <div>
          <div style={{ fontSize: 9, color: "#444", marginBottom: 6 }}>SECTOR SCORES</div>
          {Object.entries(data.all_scores)
            .sort(([, a], [, b]) => b - a)
            .map(([sector, score]) => {
              const isPref = data.preferred_sectors.includes(sector);
              const isAvoid = data.avoid_sectors.includes(sector);
              const barColor = isPref ? "#22c55e" : isAvoid ? "#ef4444" : "#555";
              const maxScore = Math.max(...Object.values(data.all_scores));
              return (
                <div key={sector} style={{ marginBottom: 5 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                    <span style={{ fontSize: 9, color: barColor }}>{sector}</span>
                    <span style={{ fontSize: 9, color: barColor, fontWeight: 600 }}>{score}</span>
                  </div>
                  <div style={{ height: 3, background: "#1a1a1a", borderRadius: 2 }}>
                    <div style={{
                      height: "100%",
                      width: `${(score / maxScore) * 100}%`,
                      background: barColor,
                      borderRadius: 2,
                    }} />
                  </div>
                </div>
              );
            })}
        </div>
      )}

      {/* Reasoning */}
      <div>
        <div style={{ fontSize: 9, color: "#444", marginBottom: 5 }}>REASONING</div>
        <p style={{ fontSize: 10, color: "#555", lineHeight: 1.6, margin: 0 }}>
          {data.reasoning}
        </p>
      </div>
    </div>
  );
}

// ─── Universe Table Row ───────────────────────────────────────────────────────

function UniverseRow({
  stock,
  rank,
  isSelected,
  onClick,
}: {
  stock: RankedStock;
  rank: number;
  isSelected: boolean;
  onClick: () => void;
}) {
  const [hovered, setHovered] = useState(false);
  const changeColor = stock.change_pct >= 0 ? "#22c55e" : "#ef4444";

  return (
    <tr
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        cursor: "pointer",
        background: isSelected ? "#1e3a5f22" : hovered ? "#141414" : "transparent",
        borderBottom: "1px solid #111",
        transition: "background 0.1s",
      }}
    >
      <td style={{ padding: "7px 8px", fontSize: 10, color: "#444", textAlign: "center", width: 36 }}>
        {rank}
      </td>
      <td style={{ padding: "7px 8px", fontSize: 11, fontWeight: 700, color: "#e5e5e5", minWidth: 100 }}>
        {stock.symbol}
      </td>
      <td style={{ padding: "7px 8px", minWidth: 90 }}>
        <MiniScoreBar score={stock.composite_score} width={55} />
      </td>
      <td style={{ padding: "7px 8px" }}>
        <ActionBadge action={stock.action} />
      </td>
      <td style={{ padding: "7px 8px", fontSize: 11, color: "#e5e5e5", textAlign: "right", minWidth: 70 }}>
        ₹{stock.price.toLocaleString("en-IN", { maximumFractionDigits: 1 })}
      </td>
      <td style={{
        padding: "7px 8px", fontSize: 11, color: changeColor,
        textAlign: "right", fontWeight: 500, minWidth: 60,
      }}>
        {stock.change_pct >= 0 ? "+" : ""}{stock.change_pct.toFixed(2)}%
      </td>
      <td style={{ padding: "7px 8px", fontSize: 10, color: "#666", minWidth: 90 }}>
        {stock.sector}
      </td>
      <td style={{ padding: "7px 8px", fontSize: 10, color: "#555", maxWidth: 220 }}>
        <span style={{
          display: "block",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}>
          {stock.top_reason}
        </span>
      </td>
    </tr>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

type FilterType = "ALL" | "STRONG BUY" | "BUY" | "HOLD" | "SELL";
type SortType = "score" | "price" | "change";

export default function RecommendPage() {
  const [universe, setUniverse] = useState<RankedStock[]>([]);
  const [sectorRotation, setSectorRotation] = useState<SectorRotationResponse | null>(null);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [detail, setDetail] = useState<DetailResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastComputed, setLastComputed] = useState<string>("");
  const [filter, setFilter] = useState<FilterType>("ALL");
  const [sort, setSort] = useState<SortType>("score");

  // Fetch universe on mount
  useEffect(() => {
    setLoading(true);
    setError(null);

    Promise.all([
      fetch(`${API_BASE}/api/recommendations?limit=50`).then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<UniverseResponse>;
      }),
      fetch(`${API_BASE}/api/sector-rotation`).then(r => {
        if (!r.ok) return null;
        return r.json() as Promise<SectorRotationResponse>;
      }).catch(() => null),
    ])
      .then(([univData, rotData]) => {
        setUniverse(univData.ranked || []);
        setLastComputed(new Date().toLocaleTimeString("en-IN", { hour12: false }));
        if (rotData) {
          setSectorRotation(rotData);
        } else if (univData.sector_rotation) {
          // Fallback: build from embedded sector_rotation
          const sr = univData.sector_rotation;
          setSectorRotation({
            preferred_sectors: sr.preferred_sectors,
            avoid_sectors: sr.avoid_sectors,
            all_scores: {},
            macro_regime: "UNKNOWN",
            reasoning: sr.reasoning,
          });
        }
      })
      .catch(err => {
        setError(err.message || "Failed to load recommendations");
      })
      .finally(() => setLoading(false));
  }, []);

  // Fetch detail when symbol selected
  const fetchDetail = useCallback((symbol: string) => {
    setDetailLoading(true);
    setDetail(null);
    fetch(`${API_BASE}/api/recommend/${symbol}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<DetailResponse>;
      })
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setDetailLoading(false));
  }, []);

  const handleRowClick = useCallback((symbol: string) => {
    if (selectedSymbol === symbol) {
      setSelectedSymbol(null);
      setDetail(null);
    } else {
      setSelectedSymbol(symbol);
      fetchDetail(symbol);
    }
  }, [selectedSymbol, fetchDetail]);

  // Filter + sort
  const filteredStocks = universe
    .filter(s => {
      if (filter === "ALL") return true;
      return s.action === filter;
    })
    .sort((a, b) => {
      if (sort === "score") return b.composite_score - a.composite_score;
      if (sort === "price") return b.price - a.price;
      if (sort === "change") return b.change_pct - a.change_pct;
      return 0;
    });

  const filterOptions: FilterType[] = ["ALL", "STRONG BUY", "BUY", "HOLD", "SELL"];

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      height: "100vh",
      overflow: "hidden",
      background: "#000",
      fontFamily: "'Courier New', Courier, monospace",
      color: "#e5e5e5",
    }}>
      <IndexBar />

      <div style={{ flex: 1, overflow: "auto", padding: "12px 16px" }}>
        {/* Page Header */}
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 14,
          paddingBottom: 10,
          borderBottom: "1px solid #1a1a1a",
        }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: "#e5e5e5", letterSpacing: "0.08em" }}>
              AI RECOMMENDATION ENGINE
            </h1>
            <div style={{ fontSize: 10, color: "#444", marginTop: 3 }}>
              Multi-factor scoring: Technical · Fundamental · Macro · Quality · Momentum · Risk
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            {lastComputed && (
              <div style={{ fontSize: 10, color: "#555" }}>
                COMPUTED <span style={{ color: "#888" }}>{lastComputed}</span>
              </div>
            )}
            {universe.length > 0 && (
              <div style={{ fontSize: 10, color: "#444", marginTop: 2 }}>
                {universe.length} STOCKS RANKED
              </div>
            )}
          </div>
        </div>

        {/* Error state */}
        {error && (
          <div style={{
            background: "#1a0a0a",
            border: "1px solid #ef444433",
            borderRadius: 6,
            padding: "12px 16px",
            fontSize: 11,
            color: "#ef4444",
            marginBottom: 12,
          }}>
            ERROR: {error}
          </div>
        )}

        {/* Loading state */}
        {loading && (
          <div style={{ textAlign: "center", color: "#444", fontSize: 12, padding: 40 }}>
            LOADING RECOMMENDATIONS...
          </div>
        )}

        {/* Main content */}
        {!loading && !error && (
          <div style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
            {/* Sector Rotation Panel */}
            {sectorRotation && (
              <SectorRotationPanel data={sectorRotation} />
            )}

            {/* Universe Table */}
            <div style={{ flex: 1, minWidth: 0 }}>
              {/* Controls */}
              <div style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                marginBottom: 10,
                flexWrap: "wrap",
              }}>
                {/* Filter buttons */}
                <div style={{ display: "flex", gap: 4 }}>
                  {filterOptions.map(f => (
                    <FilterButton
                      key={f}
                      label={f}
                      active={filter === f}
                      onClick={() => setFilter(f)}
                    />
                  ))}
                </div>

                <div style={{ flex: 1 }} />

                {/* Sort buttons */}
                <div style={{
                  display: "flex",
                  gap: 2,
                  background: "#0d0d0d",
                  border: "1px solid #1a1a1a",
                  borderRadius: 4,
                  padding: 2,
                  fontSize: 9,
                  color: "#444",
                  alignItems: "center",
                }}>
                  <span style={{ paddingLeft: 6, fontSize: 9 }}>SORT</span>
                  {(["score", "price", "change"] as SortType[]).map(s => (
                    <SortButton
                      key={s}
                      label={s.toUpperCase()}
                      active={sort === s}
                      onClick={() => setSort(s)}
                    />
                  ))}
                </div>

                <div style={{ fontSize: 10, color: "#444" }}>
                  {filteredStocks.length} RESULTS
                </div>
              </div>

              {/* Table */}
              <div style={{
                background: "#080808",
                border: "1px solid #1a1a1a",
                borderRadius: 8,
                overflow: "hidden",
              }}>
                <div style={{ overflowX: "auto" }}>
                <table style={{
                  width: "100%",
                  borderCollapse: "collapse",
                  tableLayout: "fixed",
                  minWidth: 680,
                }}>
                  <colgroup>
                    <col style={{ width: 36 }} />
                    <col style={{ width: "10%" }} />
                    <col style={{ width: 110 }} />
                    <col style={{ width: 100 }} />
                    <col style={{ width: "9%" }} />
                    <col style={{ width: "7%" }} />
                    <col style={{ width: "10%" }} />
                    <col />
                  </colgroup>
                  <thead>
                    <tr style={{ borderBottom: "1px solid #1e1e1e", background: "#0d0d0d" }}>
                      {["#", "SYMBOL", "SCORE", "ACTION", "PRICE", "CHG%", "SECTOR", "TOP REASON"].map((h, i) => (
                        <th key={h} style={{
                          padding: "7px 8px",
                          fontSize: 9,
                          color: "#444",
                          textAlign: i >= 4 && i <= 5 ? "right" : "left",
                          fontWeight: 600,
                          letterSpacing: "0.08em",
                        }}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredStocks.map((stock, idx) => (
                      <UniverseRow
                        key={stock.symbol}
                        stock={stock}
                        rank={idx + 1}
                        isSelected={selectedSymbol === stock.symbol}
                        onClick={() => handleRowClick(stock.symbol)}
                      />
                    ))}
                    {filteredStocks.length === 0 && (
                      <tr>
                        <td colSpan={8} style={{ textAlign: "center", padding: 32, color: "#333", fontSize: 11 }}>
                          NO STOCKS MATCH FILTER
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
                </div>
              </div>

              {/* Detail Panel */}
              {selectedSymbol && (
                <div>
                  {detailLoading && (
                    <div style={{
                      textAlign: "center",
                      color: "#444",
                      fontSize: 11,
                      padding: 20,
                      marginTop: 12,
                      background: "#0a0a0a",
                      border: "1px solid #1a1a1a",
                      borderRadius: 8,
                    }}>
                      LOADING {selectedSymbol}...
                    </div>
                  )}
                  {!detailLoading && detail && (
                    <DetailPanel
                      detail={detail}
                      onClose={() => {
                        setSelectedSymbol(null);
                        setDetail(null);
                      }}
                    />
                  )}
                  {!detailLoading && !detail && (
                    <div style={{
                      textAlign: "center",
                      color: "#444",
                      fontSize: 11,
                      padding: 20,
                      marginTop: 12,
                      background: "#0a0a0a",
                      border: "1px solid #1a1a1a",
                      borderRadius: 8,
                    }}>
                      FAILED TO LOAD DETAIL FOR {selectedSymbol}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
