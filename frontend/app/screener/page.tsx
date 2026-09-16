'use client';

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import IndexBar from "@/components/IndexBar";
import { api, fmt, changeClass, changeSign } from "@/lib/api";

type Tab = "momentum" | "meanrev" | "breakout" | "volume";

const SIGNAL_COLORS: Record<string, string> = {
  strong_buy: "#22c55e", oversold: "#86efac",
  strong_sell: "#ef4444", overbought: "#fca5a5",
  neutral: "#555",
};
const SIGNAL_LABELS: Record<string, string> = {
  strong_buy: "Strong Buy", oversold: "Oversold",
  strong_sell: "Strong Sell", overbought: "Overbought",
  neutral: "Neutral",
};
const BTYPE_LABELS: Record<string, string> = {
  "52w_high_breakout": "52W Breakout 🔥",
  resistance_break: "Resistance Break",
  near_52w_high: "Near 52W High",
};
const BTYPE_COLORS: Record<string, string> = {
  "52w_high_breakout": "#22c55e",
  resistance_break: "#f59e0b",
  near_52w_high: "#3b82f6",
};

function Tag({ label, color }: { label: string; color: string }) {
  return (
    <span style={{
      display: "inline-block", padding: "1px 7px", fontSize: 9, fontWeight: 600,
      background: color + "20", color, borderRadius: 3, textTransform: "uppercase",
    }}>{label}</span>
  );
}

function ScreenerRow({ item, type, rank, onClick }: {
  item: Record<string, unknown>; type: Tab; rank?: number; onClick: () => void;
}) {
  const sym = item.symbol as string;
  const company = item.company as string;
  const price = item.price as number;
  const chg = item.change_pct as number;

  return (
    <tr
      onClick={onClick}
      style={{ cursor: "pointer", borderBottom: "1px solid #1a1a1a" }}
      onMouseEnter={e => (e.currentTarget.style.background = "#141414")}
      onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
    >
      {rank !== undefined && (
        <td style={{ padding: "8px 12px", fontSize: 11, color: "#444", fontFamily: "monospace" }}>#{rank}</td>
      )}
      <td style={{ padding: "8px 12px" }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: "#e5e5e5" }}>{sym}</div>
        <div style={{ fontSize: 10, color: "#555" }}>{company}</div>
      </td>
      <td style={{ padding: "8px 12px", textAlign: "right" }}>
        <div className="num" style={{ fontSize: 12, color: "#e5e5e5" }}>₹{fmt(price)}</div>
        <div className={`num ${changeClass(chg)}`} style={{ fontSize: 10 }}>
          {changeSign(chg)}{fmt(Math.abs(chg))}%
        </div>
      </td>

      {type === "momentum" && (
        <>
          <td style={{ padding: "8px 12px", textAlign: "right" }}>
            <span className="num" style={{ fontSize: 12, fontWeight: 600, color: (item.rs_score as number) > 0 ? "#22c55e" : "#ef4444", fontFamily: "monospace" }}>
              {item.rs_score != null ? (item.rs_score as number).toFixed(1) : "—"}
            </span>
          </td>
          <td className="num" style={{ padding: "8px 12px", textAlign: "right", fontSize: 11, color: (item.ret_65d as number) > 0 ? "#22c55e" : "#ef4444" }}>
            {item.ret_65d != null ? `${changeSign(item.ret_65d as number)}${fmt(Math.abs(item.ret_65d as number))}%` : "—"}
          </td>
          <td className="num" style={{ padding: "8px 12px", textAlign: "right", fontSize: 11, color: (item.ret_252d as number) > 0 ? "#22c55e" : "#ef4444" }}>
            {item.ret_252d != null ? `${changeSign(item.ret_252d as number)}${fmt(Math.abs(item.ret_252d as number))}%` : "—"}
          </td>
        </>
      )}

      {type === "meanrev" && (
        <>
          <td style={{ padding: "8px 12px" }}>
            <Tag label={SIGNAL_LABELS[item.signal as string] || (item.signal as string)} color={SIGNAL_COLORS[item.signal as string] || "#555"} />
          </td>
          <td className="num" style={{ padding: "8px 12px", textAlign: "right", fontSize: 11, color: "#888" }}>
            {item.zscore != null ? `${(item.zscore as number).toFixed(2)}σ` : "—"}
          </td>
          <td className="num" style={{ padding: "8px 12px", textAlign: "right", fontSize: 11, color: "#888" }}>
            {item.rsi != null ? `RSI ${(item.rsi as number).toFixed(1)}` : "—"}
          </td>
          <td className="num" style={{ padding: "8px 12px", textAlign: "right", fontSize: 11, color: "#888" }}>
            {item.bb_pct != null ? `BB ${((item.bb_pct as number) * 100).toFixed(0)}%` : "—"}
          </td>
        </>
      )}

      {type === "breakout" && (
        <>
          <td style={{ padding: "8px 12px" }}>
            <Tag label={BTYPE_LABELS[item.type as string] || (item.type as string)} color={BTYPE_COLORS[item.type as string] || "#555"} />
          </td>
          <td className="num" style={{ padding: "8px 12px", textAlign: "right", fontSize: 11, color: "#888" }}>
            {item.distance_52wh_pct != null ? `${(item.distance_52wh_pct as number).toFixed(1)}% from 52W High` : "—"}
          </td>
          <td className="num" style={{ padding: "8px 12px", textAlign: "right", fontSize: 11, color: (item.vol_ratio as number) > 2 ? "#f59e0b" : "#888" }}>
            {item.vol_ratio != null ? `${(item.vol_ratio as number).toFixed(1)}x Vol` : "—"}
          </td>
        </>
      )}

      {type === "volume" && (
        <>
          <td className="num" style={{ padding: "8px 12px", textAlign: "right", fontSize: 12, fontWeight: 700, color: "#f59e0b" }}>
            {item.vol_ratio != null ? `${(item.vol_ratio as number).toFixed(1)}x` : "—"}
          </td>
          <td className="num" style={{ padding: "8px 12px", textAlign: "right", fontSize: 11, color: "#888" }}>
            {item.today_volume != null ? `${((item.today_volume as number) / 1e6).toFixed(2)}M` : "—"}
          </td>
          <td className="num" style={{ padding: "8px 12px", textAlign: "right", fontSize: 11, color: "#555" }}>
            {item.avg_volume != null ? `avg ${((item.avg_volume as number) / 1e6).toFixed(2)}M` : "—"}
          </td>
        </>
      )}
    </tr>
  );
}

export default function ScreenerPage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("momentum");
  const [results, setResults] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string>("");

  const load = useCallback(async (t: Tab) => {
    setLoading(true);
    setError(null);
    try {
      let res: { results: Record<string, unknown>[] };
      if (t === "momentum") res = await api.screenerMomentum();
      else if (t === "meanrev") res = await api.screenerMeanRev();
      else if (t === "breakout") res = await api.screenerBreakout();
      else res = await api.screenerVolume();
      setResults(res.results || []);
      setLastUpdate(new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }));
    } catch (e) {
      setError((e as Error).message || "Failed to load");
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(tab); }, [tab, load]);

  const TABS: { key: Tab; label: string; desc: string }[] = [
    { key: "momentum", label: "Momentum", desc: "IBD RS Rank — 65d/125d/252d weighted return across Nifty 100 + PSU" },
    { key: "meanrev", label: "Mean Reversion", desc: "Stocks ranked by Z-score deviation + RSI + Bollinger Band extremes" },
    { key: "breakout", label: "Breakout Scanner", desc: "52W high breakouts & resistance breaks with volume confirmation" },
    { key: "volume", label: "Volume Surge", desc: "Stocks trading at 1.5x+ their 20-day average volume today" },
  ];

  const activeDesc = TABS.find(t => t.key === tab)?.desc ?? "";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden" }}>
      <IndexBar />
      <div style={{ flex: 1, overflow: "auto", background: "#080808" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "16px 20px" }}>
          {/* Header */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
            <button onClick={() => router.push("/")} style={{ background: "none", border: "none", color: "#555", cursor: "pointer", fontSize: 16 }}>←</button>
            <div>
              <h1 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "#e5e5e5" }}>Stock Screener</h1>
              <div style={{ fontSize: 11, color: "#555" }}>{activeDesc}</div>
            </div>
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12 }}>
              {lastUpdate && <span style={{ fontSize: 10, color: "#333" }}>Updated {lastUpdate}</span>}
              <button onClick={() => load(tab)} style={{
                background: "#1a1a1a", border: "1px solid #2e2e2e", color: "#e5e5e5",
                borderRadius: 6, padding: "5px 12px", fontSize: 11, cursor: "pointer",
              }}>↻ Refresh</button>
            </div>
          </div>

          {/* Tabs */}
          <div style={{ display: "flex", gap: 4, marginBottom: 16 }}>
            {TABS.map(t => (
              <button key={t.key} onClick={() => setTab(t.key)} style={{
                padding: "6px 16px", fontSize: 12, border: "none", borderRadius: 6, cursor: "pointer",
                background: tab === t.key ? "#3b82f6" : "#111",
                color: tab === t.key ? "#fff" : "#555",
                fontWeight: tab === t.key ? 600 : 400,
                outline: tab === t.key ? "none" : "1px solid #1e1e1e",
              }}>{t.label}</button>
            ))}
            <span style={{ marginLeft: "auto", fontSize: 11, color: "#444", lineHeight: "34px" }}>
              {results.length} stocks
            </span>
          </div>

          {/* Table */}
          {loading ? (
            <div>
              {Array.from({ length: 12 }).map((_, i) => (
                <div key={i} className="skeleton" style={{ height: 48, marginBottom: 4, borderRadius: 6 }} />
              ))}
              <p style={{ color: "#555", fontSize: 11, textAlign: "center", marginTop: 12 }}>
                Scanning {tab === "momentum" ? "252d" : tab === "meanrev" ? "6mo" : "1y"} history across 120+ symbols…
                <br />
                <span style={{ color: "#333" }}>First run may take up to 60s while data is fetched</span>
              </p>
            </div>
          ) : error ? (
            <div style={{ padding: 48, textAlign: "center" }}>
              <div style={{ color: "#ef4444", fontSize: 12, marginBottom: 8 }}>Failed to load screener</div>
              <div style={{ color: "#555", fontSize: 11, marginBottom: 16 }}>{error}</div>
              <button onClick={() => load(tab)} style={{
                background: "#1a1a1a", border: "1px solid #2e2e2e", color: "#e5e5e5",
                borderRadius: 6, padding: "6px 16px", fontSize: 11, cursor: "pointer",
              }}>Retry</button>
            </div>
          ) : results.length === 0 ? (
            <div style={{ padding: 48, textAlign: "center", color: "#555" }}>
              No signals found for current market conditions
            </div>
          ) : (
            <div style={{ background: "#111", border: "1px solid #1e1e1e", borderRadius: 8, overflow: "hidden" }}>
              <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 520 }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #1e1e1e" }}>
                    {tab === "momentum" && <th style={th}>#</th>}
                    <th style={{ ...th, textAlign: "left" }}>Stock</th>
                    <th style={{ ...th, textAlign: "right" }}>Price</th>
                    {tab === "momentum" && <>
                      <th style={{ ...th, textAlign: "right" }}>RS Score</th>
                      <th style={{ ...th, textAlign: "right" }}>65D Ret</th>
                      <th style={{ ...th, textAlign: "right" }}>252D Ret</th>
                    </>}
                    {tab === "meanrev" && <>
                      <th style={th}>Signal</th>
                      <th style={{ ...th, textAlign: "right" }}>Z-Score</th>
                      <th style={{ ...th, textAlign: "right" }}>RSI</th>
                      <th style={{ ...th, textAlign: "right" }}>BB%</th>
                    </>}
                    {tab === "breakout" && <>
                      <th style={th}>Type</th>
                      <th style={{ ...th, textAlign: "right" }}>vs 52W High</th>
                      <th style={{ ...th, textAlign: "right" }}>Vol Surge</th>
                    </>}
                    {tab === "volume" && <>
                      <th style={{ ...th, textAlign: "right" }}>Vol Ratio</th>
                      <th style={{ ...th, textAlign: "right" }}>Today Vol</th>
                      <th style={{ ...th, textAlign: "right" }}>Avg Vol</th>
                    </>}
                  </tr>
                </thead>
                <tbody>
                  {results.slice(0, 50).map((item, i) => (
                    <ScreenerRow
                      key={item.symbol as string}
                      item={item}
                      type={tab}
                      rank={tab === "momentum" ? i + 1 : undefined}
                      onClick={() => router.push(`/stock/${item.symbol}`)}
                    />
                  ))}
                </tbody>
              </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const th: React.CSSProperties = {
  padding: "8px 12px",
  fontSize: 10,
  color: "#444",
  fontWeight: 600,
  letterSpacing: "0.04em",
  textTransform: "uppercase" as const,
};
