'use client';

import { useState, useEffect } from "react";
import { api, fmt, type OptionData } from "@/lib/api";

export default function OptionChain({ symbol }: { symbol: string }) {
  const [data, setData] = useState<{
    underlying_value: number;
    expiry_dates: string[];
    data: OptionData[];
  } | null>(null);
  const [selectedExpiry, setSelectedExpiry] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    api.options(symbol)
      .then(res => {
        setData(res);
        if (res.expiry_dates?.[0]) setSelectedExpiry(res.expiry_dates[0]);
        setLoading(false);
      })
      .catch(() => {
        setError("Option chain unavailable");
        setLoading(false);
      });
  }, [symbol]);

  if (loading) return (
    <div style={{ padding: 16 }}>
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="skeleton" style={{ height: 28, marginBottom: 4 }} />
      ))}
    </div>
  );

  if (error || !data) return (
    <div style={{ padding: 24, color: "#555", fontSize: 12, textAlign: "center" }}>{error || "No data"}</div>
  );

  const rows = selectedExpiry
    ? data.data.filter(d => d.expiry === selectedExpiry)
    : data.data.slice(0, 30);

  const atm = data.underlying_value;
  const maxCEOI = Math.max(...rows.map(r => r.ce_oi));
  const maxPEOI = Math.max(...rows.map(r => r.pe_oi));

  const headerStyle: React.CSSProperties = {
    fontSize: 10, color: "#555", padding: "4px 8px",
    textAlign: "right" as const, fontWeight: 500,
    letterSpacing: "0.04em",
  };
  const cellStyle: React.CSSProperties = {
    fontSize: 11, padding: "5px 8px",
    textAlign: "right" as const, color: "#aaa",
    borderBottom: "1px solid #1a1a1a",
  };

  return (
    <div style={{ overflow: "auto" }}>
      {/* Expiry selector */}
      {(data.expiry_dates?.length ?? 0) > 0 && (
        <div style={{ display: "flex", gap: 6, padding: "10px 12px", borderBottom: "1px solid #1e1e1e" }}>
          <span style={{ fontSize: 10, color: "#555", marginRight: 6 }}>EXPIRY</span>
          {data.expiry_dates.map(exp => (
            <button
              key={exp}
              onClick={() => setSelectedExpiry(exp)}
              style={{
                padding: "2px 8px", fontSize: 10, border: "none",
                borderRadius: 4, cursor: "pointer",
                background: selectedExpiry === exp ? "#3b82f6" : "#1e1e1e",
                color: selectedExpiry === exp ? "#fff" : "#777",
              }}
            >
              {exp}
            </button>
          ))}
          <span style={{ marginLeft: "auto", fontSize: 10, color: "#555" }}>
            Spot: <span className="num" style={{ color: "#e5e5e5" }}>₹{fmt(atm)}</span>
          </span>
        </div>
      )}

      <table style={{ width: "100%", fontSize: 11 }}>
        <thead>
          <tr style={{ background: "#111" }}>
            {/* CE side */}
            <th style={headerStyle}>OI</th>
            <th style={headerStyle}>Chg OI</th>
            <th style={headerStyle}>IV</th>
            <th style={headerStyle}>LTP</th>
            <th style={headerStyle}>Vol</th>
            {/* Strike */}
            <th style={{ ...headerStyle, textAlign: "center", color: "#e5e5e5", fontSize: 12 }}>STRIKE</th>
            {/* PE side */}
            <th style={headerStyle}>Vol</th>
            <th style={headerStyle}>LTP</th>
            <th style={headerStyle}>IV</th>
            <th style={headerStyle}>Chg OI</th>
            <th style={headerStyle}>OI</th>
          </tr>
          <tr style={{ background: "#0d0d0d" }}>
            <th colSpan={5} style={{ ...headerStyle, textAlign: "center", color: "#22c55e", fontSize: 10 }}>CALLS</th>
            <th />
            <th colSpan={5} style={{ ...headerStyle, textAlign: "center", color: "#ef4444", fontSize: 10 }}>PUTS</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const isATM = Math.abs(row.strike - atm) < (atm * 0.005);
            const rowStyle: React.CSSProperties = {
              background: isATM ? "#1a1a1a" : "transparent",
            };
            const ceBarWidth = maxCEOI > 0 ? (row.ce_oi / maxCEOI) * 100 : 0;
            const peBarWidth = maxPEOI > 0 ? (row.pe_oi / maxPEOI) * 100 : 0;

            return (
              <tr key={`${row.strike}-${row.expiry}`} style={rowStyle}>
                {/* CE OI with bar */}
                <td style={{ ...cellStyle, position: "relative" }}>
                  <div style={{
                    position: "absolute", right: 0, top: 0, bottom: 0,
                    width: `${ceBarWidth}%`, background: "#22c55e08",
                  }} />
                  <span className="num">{(row.ce_oi / 1000).toFixed(1)}K</span>
                </td>
                <td style={{ ...cellStyle, color: row.ce_change_oi > 0 ? "#22c55e" : "#ef4444" }} className="num">
                  {row.ce_change_oi > 0 ? "+" : ""}{(row.ce_change_oi / 1000).toFixed(1)}K
                </td>
                <td style={cellStyle} className="num">{fmt(row.ce_iv, 1)}%</td>
                <td style={{ ...cellStyle, fontWeight: 500, color: "#e5e5e5" }} className="num">₹{fmt(row.ce_ltp)}</td>
                <td style={cellStyle} className="num">{(row.ce_volume / 1000).toFixed(1)}K</td>

                {/* Strike */}
                <td style={{
                  ...cellStyle, textAlign: "center",
                  fontWeight: isATM ? 700 : 500,
                  color: isATM ? "#3b82f6" : "#e5e5e5",
                  fontSize: isATM ? 12 : 11,
                }} className="num">
                  {fmt(row.strike, 0)}
                  {isATM && <span style={{ color: "#3b82f6", fontSize: 9, marginLeft: 4 }}>ATM</span>}
                </td>

                {/* PE */}
                <td style={cellStyle} className="num">{(row.pe_volume / 1000).toFixed(1)}K</td>
                <td style={{ ...cellStyle, fontWeight: 500, color: "#e5e5e5" }} className="num">₹{fmt(row.pe_ltp)}</td>
                <td style={cellStyle} className="num">{fmt(row.pe_iv, 1)}%</td>
                <td style={{ ...cellStyle, color: row.pe_change_oi > 0 ? "#22c55e" : "#ef4444" }} className="num">
                  {row.pe_change_oi > 0 ? "+" : ""}{(row.pe_change_oi / 1000).toFixed(1)}K
                </td>
                <td style={{ ...cellStyle, position: "relative" }}>
                  <div style={{
                    position: "absolute", left: 0, top: 0, bottom: 0,
                    width: `${peBarWidth}%`, background: "#ef444408",
                  }} />
                  <span className="num">{(row.pe_oi / 1000).toFixed(1)}K</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
