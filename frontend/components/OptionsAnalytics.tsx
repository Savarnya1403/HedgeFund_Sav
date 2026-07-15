'use client';

import { useState, useEffect } from "react";
import { api, fmt } from "@/lib/api";

interface OIRow {
  strike: number;
  call_oi: number; put_oi: number;
  call_oi_chg: number; put_oi_chg: number;
  call_ltp: number; put_ltp: number;
  call_iv: number; put_iv: number;
}

interface OptionsAnalyticsData {
  symbol: string;
  underlying: number;
  pcr: number;
  pcr_signal: string;
  pcr_color: string;
  max_pain: number;
  max_pain_pct: number;
  gamma_wall: number | null;
  total_call_oi: number;
  total_put_oi: number;
  call_oi_chg: number;
  put_oi_chg: number;
  atm_iv: number;
  key_resistance: number[];
  key_support: number[];
  oi_distribution: OIRow[];
}

function PCRGauge({ pcr, signal, color }: { pcr: number; signal: string; color: string }) {
  // PCR meaningful range: 0.3 to 2.5 (bearish to bullish)
  const pct = Math.min(Math.max(((pcr - 0.3) / 2.2) * 100, 0), 100);
  const r = 36;
  const circ = Math.PI * r;
  const dash = (pct / 100) * circ;

  return (
    <div style={{ textAlign: "center" }}>
      <svg width="96" height="56" viewBox="0 0 96 56">
        <path d={`M 10 52 A ${r} ${r} 0 0 1 86 52`} fill="none" stroke="#1e1e1e" strokeWidth="8" strokeLinecap="round" />
        <path d={`M 10 52 A ${r} ${r} 0 0 1 86 52`} fill="none" stroke={color} strokeWidth="8" strokeLinecap="round"
          strokeDasharray={`${dash} ${circ}`} style={{ transition: "stroke-dasharray 0.6s" }} />
        <text x="48" y="48" textAnchor="middle" fill="#e5e5e5" fontSize="16" fontWeight="700" fontFamily="monospace">{pcr.toFixed(2)}</text>
      </svg>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 9, color: "#444", marginTop: -4 }}>
        <span>Bearish 0.3</span><span>Neutral 1.0</span><span>Bullish 2.5</span>
      </div>
      <div style={{ fontSize: 13, fontWeight: 700, color, marginTop: 4 }}>{signal}</div>
      <div style={{ fontSize: 10, color: "#555" }}>Put/Call Ratio (OI)</div>
    </div>
  );
}

function OIBar({ callOI, putOI, strike, underlying, maxOI }: {
  callOI: number; putOI: number; strike: number; underlying: number; maxOI: number;
}) {
  const callW = maxOI > 0 ? (callOI / maxOI) * 100 : 0;
  const putW = maxOI > 0 ? (putOI / maxOI) * 100 : 0;
  const isATM = Math.abs(strike - underlying) / underlying < 0.005;

  return (
    <div style={{
      display: "grid", gridTemplateColumns: "1fr 72px 1fr", gap: 4, alignItems: "center",
      padding: "3px 0",
      background: isATM ? "#1e2030" : "transparent",
      borderRadius: 3,
    }}>
      {/* Call OI — right aligned, grows left */}
      <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 6 }}>
        <span style={{ fontSize: 10, color: "#ef4444", fontFamily: "monospace", minWidth: 40, textAlign: "right" }}>
          {callOI > 0 ? (callOI / 1000).toFixed(0) + "k" : "—"}
        </span>
        <div style={{ height: 10, width: `${callW}%`, maxWidth: "100%", background: "#ef444430", borderRadius: 2 }} />
      </div>

      {/* Strike */}
      <div style={{
        textAlign: "center", fontSize: 11, fontWeight: isATM ? 700 : 400,
        color: isATM ? "#f59e0b" : "#888", fontFamily: "monospace",
      }}>
        {strike.toLocaleString("en-IN")}
        {isATM && <span style={{ fontSize: 8, color: "#f59e0b", display: "block" }}>ATM</span>}
      </div>

      {/* Put OI — left aligned, grows right */}
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <div style={{ height: 10, width: `${putW}%`, maxWidth: "100%", background: "#22c55e30", borderRadius: 2 }} />
        <span style={{ fontSize: 10, color: "#22c55e", fontFamily: "monospace", minWidth: 40 }}>
          {putOI > 0 ? (putOI / 1000).toFixed(0) + "k" : "—"}
        </span>
      </div>
    </div>
  );
}

export default function OptionsAnalytics({ symbol }: { symbol: string }) {
  const [data, setData] = useState<OptionsAnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.optionsAnalytics(symbol)
      .then(res => setData(res as OptionsAnalyticsData))
      .catch((e: Error) => setError(e?.message || "NSE option chain unavailable"))
      .finally(() => setLoading(false));
  }, [symbol]);

  if (loading) {
    return (
      <div style={{ padding: 16 }}>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="skeleton" style={{ height: 40, marginBottom: 8, borderRadius: 6 }} />
        ))}
        <p style={{ textAlign: "center", color: "#555", fontSize: 11 }}>Fetching live NSE option chain…</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={{ padding: 32, textAlign: "center" }}>
        <div style={{ color: "#555", fontSize: 14, marginBottom: 8 }}>Option Chain Unavailable</div>
        <div style={{ color: "#333", fontSize: 11 }}>{error || "NSE requires an active trading session"}</div>
      </div>
    );
  }

  const maxOI = Math.max(...data.oi_distribution.map(r => Math.max(r.call_oi, r.put_oi)));
  const netOIBias = data.total_put_oi - data.total_call_oi;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: 20 }}>
      {/* Left panel */}
      <div>
        {/* PCR Gauge */}
        <div style={{ background: "#111", border: "1px solid #1e1e1e", borderRadius: 8, padding: 16, marginBottom: 12 }}>
          <PCRGauge pcr={data.pcr} signal={data.pcr_signal} color={data.pcr_color} />
        </div>

        {/* Key levels */}
        <div style={{ background: "#111", border: "1px solid #1e1e1e", borderRadius: 8, padding: 14, marginBottom: 12 }}>
          <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.05em", marginBottom: 10 }}>KEY LEVELS</div>
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 10, color: "#555", marginBottom: 4 }}>UNDERLYING</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: "#e5e5e5", fontFamily: "monospace" }}>
              ₹{fmt(data.underlying)}
            </div>
          </div>
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 10, color: "#ef4444", marginBottom: 2 }}>MAX PAIN</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#ef4444", fontFamily: "monospace" }}>
              ₹{data.max_pain?.toLocaleString("en-IN") ?? "—"}
            </div>
            {data.max_pain && (
              <div style={{ fontSize: 10, color: "#555" }}>{data.max_pain_pct > 0 ? "+" : ""}{data.max_pain_pct}% from spot</div>
            )}
          </div>
          {data.gamma_wall && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ fontSize: 10, color: "#f59e0b", marginBottom: 2 }}>GAMMA WALL</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: "#f59e0b", fontFamily: "monospace" }}>
                ₹{data.gamma_wall.toLocaleString("en-IN")}
              </div>
            </div>
          )}
          <div>
            <div style={{ fontSize: 10, color: "#8b5cf6", marginBottom: 2 }}>ATM IV</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#8b5cf6", fontFamily: "monospace" }}>{data.atm_iv}%</div>
          </div>
        </div>

        {/* OI Flow */}
        <div style={{ background: "#111", border: "1px solid #1e1e1e", borderRadius: 8, padding: 14 }}>
          <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.05em", marginBottom: 10 }}>OI FLOW</div>
          <div style={{ marginBottom: 6 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
              <span style={{ color: "#ef4444" }}>Call OI</span>
              <span style={{ color: "#ef4444", fontFamily: "monospace" }}>{(data.total_call_oi / 100000).toFixed(1)}L</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#555" }}>
              <span>Change</span>
              <span style={{ color: data.call_oi_chg > 0 ? "#ef4444" : "#22c55e", fontFamily: "monospace" }}>
                {data.call_oi_chg > 0 ? "+" : ""}{(data.call_oi_chg / 1000).toFixed(0)}k
              </span>
            </div>
          </div>
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
              <span style={{ color: "#22c55e" }}>Put OI</span>
              <span style={{ color: "#22c55e", fontFamily: "monospace" }}>{(data.total_put_oi / 100000).toFixed(1)}L</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#555" }}>
              <span>Change</span>
              <span style={{ color: data.put_oi_chg > 0 ? "#22c55e" : "#ef4444", fontFamily: "monospace" }}>
                {data.put_oi_chg > 0 ? "+" : ""}{(data.put_oi_chg / 1000).toFixed(0)}k
              </span>
            </div>
          </div>
          <div style={{
            marginTop: 8, paddingTop: 8, borderTop: "1px solid #1e1e1e",
            fontSize: 10, color: netOIBias > 0 ? "#22c55e" : "#ef4444",
            fontWeight: 600,
          }}>
            {netOIBias > 0 ? "▲ NET PUT BUILDUP" : "▼ NET CALL BUILDUP"}
          </div>
        </div>
      </div>

      {/* Right: OI Distribution */}
      <div style={{ background: "#111", border: "1px solid #1e1e1e", borderRadius: 8, padding: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
          <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.05em" }}>OPEN INTEREST DISTRIBUTION</div>
          <div style={{ display: "flex", gap: 16, fontSize: 10 }}>
            <span style={{ color: "#ef4444" }}>■ Call OI (Resistance)</span>
            <span style={{ color: "#22c55e" }}>■ Put OI (Support)</span>
          </div>
        </div>

        {/* Header */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 72px 1fr", fontSize: 9, color: "#444", marginBottom: 6, padding: "0 4px" }}>
          <div style={{ textAlign: "right" }}>CALL OI ↓</div>
          <div style={{ textAlign: "center" }}>STRIKE</div>
          <div>↑ PUT OI</div>
        </div>

        <div style={{ maxHeight: 500, overflow: "auto" }}>
          {data.oi_distribution.map((row) => (
            <OIBar
              key={row.strike}
              callOI={row.call_oi}
              putOI={row.put_oi}
              strike={row.strike}
              underlying={data.underlying}
              maxOI={maxOI}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
