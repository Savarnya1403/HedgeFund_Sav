'use client';

import { useState, useEffect } from "react";
import { api, fmt, changeClass, changeSign, type AnalysisResult } from "@/lib/api";

function ConfidenceBadge({ value, signal }: { value: number; signal: string }) {
  const color = signal === "BULLISH" || signal === "APPROVED"
    ? "#22c55e"
    : signal === "BEARISH"
    ? "#ef4444"
    : "#f59e0b";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{
        width: 50, height: 4, background: "#222", borderRadius: 2, overflow: "hidden"
      }}>
        <div style={{ width: `${value * 100}%`, height: "100%", background: color, borderRadius: 2 }} />
      </div>
      <span style={{ fontSize: 10, color, fontWeight: 600 }}>{(value * 100).toFixed(0)}%</span>
    </div>
  );
}

function AgentCard({ agent }: { agent: { agent: string; signal: string; confidence: number; summary: string; findings: string[] } }) {
  const [open, setOpen] = useState(false);
  const borderColor = agent.signal === "BULLISH" || agent.signal === "APPROVED"
    ? "#22c55e33"
    : agent.signal === "BEARISH"
    ? "#ef444433"
    : "#f59e0b33";

  return (
    <div style={{
      border: `1px solid ${borderColor}`,
      borderRadius: 6,
      marginBottom: 8,
      background: "#111",
      overflow: "hidden",
    }}>
      <div
        onClick={() => setOpen(!open)}
        style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "10px 12px", cursor: "pointer",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: "#e5e5e5" }}>{agent.agent}</span>
          <span className={
            agent.signal === "BULLISH" || agent.signal === "APPROVED" ? "badge-gain"
            : agent.signal === "BEARISH" ? "badge-loss"
            : "badge-neutral"
          }>
            {agent.signal}
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <ConfidenceBadge value={agent.confidence} signal={agent.signal} />
          <span style={{ color: "#333", fontSize: 12 }}>{open ? "▲" : "▼"}</span>
        </div>
      </div>
      {open && (
        <div style={{ borderTop: "1px solid #1e1e1e", padding: "10px 12px" }}>
          <p style={{ fontSize: 11, color: "#aaa", marginBottom: 8, lineHeight: 1.6 }}>{agent.summary}</p>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {agent.findings.map((f, i) => (
              <li key={i} style={{
                fontSize: 11, color: "#777", padding: "3px 0",
                display: "flex", gap: 6,
              }}>
                <span style={{ color: "#333", flexShrink: 0 }}>•</span>
                <span>{f}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function AnalysisPanel({ symbol }: { symbol: string }) {
  const [data, setData] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const run = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.analysis(symbol);
      setData(res);
    } catch (e) {
      setError("Analysis failed. Check backend.");
    } finally {
      setLoading(false);
    }
  };

  if (!data && !loading) {
    return (
      <div style={{ padding: 24, textAlign: "center" }}>
        <p style={{ color: "#555", fontSize: 12, marginBottom: 16 }}>
          Run multi-agent analysis to get AI-driven insights including fundamentals,
          technicals, macro analysis, risk assessment and a final trade decision.
        </p>
        <button
          onClick={run}
          style={{
            background: "#3b82f6", color: "#fff", border: "none",
            borderRadius: 6, padding: "8px 20px", fontSize: 12,
            cursor: "pointer", fontWeight: 500,
          }}
        >
          Run Analysis
        </button>
        {error && <p style={{ color: "#ef4444", fontSize: 11, marginTop: 8 }}>{error}</p>}
      </div>
    );
  }

  if (loading) {
    return (
      <div style={{ padding: 24 }}>
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="skeleton" style={{ height: 44, marginBottom: 8, borderRadius: 6 }} />
        ))}
        <p style={{ color: "#555", fontSize: 11, textAlign: "center", marginTop: 8 }}>
          Running multi-agent analysis…
        </p>
      </div>
    );
  }

  if (!data) return null;

  const dec = data.final_decision;
  const debate = data.debate;
  const decisionColor = dec.decision === "BUY" ? "#22c55e" : dec.decision === "SELL" ? "#ef4444" : "#f59e0b";

  return (
    <div style={{ padding: 16 }}>
      {/* Final Decision Card */}
      <div style={{
        background: "#111",
        border: `1px solid ${decisionColor}33`,
        borderRadius: 8,
        padding: 16,
        marginBottom: 16,
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <span style={{ fontSize: 11, color: "#555", letterSpacing: "0.06em" }}>FINAL DECISION</span>
          <span style={{
            fontSize: 14, fontWeight: 700, color: decisionColor,
            border: `1px solid ${decisionColor}44`,
            padding: "2px 10px", borderRadius: 4,
          }}>
            {dec.decision}
          </span>
        </div>
        <div style={{
          display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 12
        }}>
          {[
            { label: "Entry", value: `₹${fmt(dec.entry_price)}` },
            { label: "Stop Loss", value: `₹${fmt(dec.stop_loss)}`, cls: "loss" },
            { label: "Target", value: `₹${fmt(dec.target_price)}`, cls: "gain" },
            { label: "Position", value: `${dec.position_size_pct}%` },
            { label: "R/R Ratio", value: `${dec.risk_reward}:1` },
            { label: "Votes", value: `${data.agents ? Object.values(data.agents).filter((a: { signal: string }) => a.signal === "BULLISH").length : 0}/4 Bullish` },
          ].map(item => (
            <div key={item.label}>
              <div style={{ fontSize: 10, color: "#555", marginBottom: 2 }}>{item.label}</div>
              <div className={`num ${item.cls || ""}`} style={{ fontSize: 13, fontWeight: 600, color: item.cls ? undefined : "#e5e5e5" }}>
                {item.value}
              </div>
            </div>
          ))}
        </div>
        <p style={{ fontSize: 11, color: "#777", lineHeight: 1.5 }}>{dec.rationale}</p>
      </div>

      {/* Bull vs Bear Debate */}
      <div style={{
        background: "#111", border: "1px solid #222", borderRadius: 8,
        padding: 14, marginBottom: 16,
      }}>
        <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.06em", marginBottom: 10 }}>
          BULL vs BEAR DEBATE — Consensus: <span style={{ color: debate.consensus === "Bullish" ? "#22c55e" : debate.consensus === "Bearish" ? "#ef4444" : "#f59e0b" }}>{debate.consensus.toUpperCase()}</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          {/* Bull */}
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
              <span style={{ fontSize: 11, color: "#22c55e", fontWeight: 600 }}>Bull Case</span>
              <span className="num" style={{ fontSize: 10, color: "#22c55e" }}>
                {(debate.bull_confidence * 100).toFixed(0)}%
              </span>
            </div>
            <div className="num" style={{ fontSize: 12, color: "#22c55e", marginBottom: 6 }}>
              Target: ₹{fmt(debate.bull_target)}
            </div>
            {debate.bull_arguments.slice(0, 3).map((arg, i) => (
              <div key={i} style={{ fontSize: 10, color: "#555", padding: "2px 0", display: "flex", gap: 4 }}>
                <span style={{ color: "#22c55e44" }}>↑</span>{arg}
              </div>
            ))}
          </div>
          {/* Bear */}
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
              <span style={{ fontSize: 11, color: "#ef4444", fontWeight: 600 }}>Bear Case</span>
              <span className="num" style={{ fontSize: 10, color: "#ef4444" }}>
                {(debate.bear_confidence * 100).toFixed(0)}%
              </span>
            </div>
            <div className="num" style={{ fontSize: 12, color: "#ef4444", marginBottom: 6 }}>
              Target: ₹{fmt(debate.bear_target)}
            </div>
            {debate.bear_arguments.slice(0, 3).map((arg, i) => (
              <div key={i} style={{ fontSize: 10, color: "#555", padding: "2px 0", display: "flex", gap: 4 }}>
                <span style={{ color: "#ef444444" }}>↓</span>{arg}
              </div>
            ))}
          </div>
        </div>
        <div style={{
          marginTop: 10, paddingTop: 10, borderTop: "1px solid #1e1e1e",
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <span style={{ fontSize: 10, color: "#555" }}>Expected Value</span>
          <span className="num" style={{ fontSize: 13, fontWeight: 600, color: "#e5e5e5" }}>
            ₹{fmt(debate.expected_value)}
          </span>
        </div>
      </div>

      {/* Agent Reports */}
      <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.06em", marginBottom: 10 }}>AGENT REPORTS</div>
      {Object.values(data.agents).map((agent) => (
        <AgentCard key={agent.agent} agent={agent} />
      ))}

      <button
        onClick={run}
        style={{
          width: "100%", background: "transparent", color: "#555",
          border: "1px solid #222", borderRadius: 6, padding: "7px",
          fontSize: 11, cursor: "pointer", marginTop: 8,
        }}
      >
        Refresh Analysis
      </button>

      <div style={{ textAlign: "right", marginTop: 8 }}>
        <span style={{ fontSize: 10, color: "#333" }}>
          {new Date(data.timestamp).toLocaleString("en-IN")}
        </span>
      </div>
    </div>
  );
}
