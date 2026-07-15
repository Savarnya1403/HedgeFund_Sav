'use client';

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, fmt, changeClass, changeSign, fmtCrore, type StockQuote, type IndexData } from "@/lib/api";

function StatCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div style={{
      background: "#111", border: "1px solid #1e1e1e", borderRadius: 8,
      padding: "14px 16px", flex: 1,
    }}>
      <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.05em", marginBottom: 6 }}>{label}</div>
      <div className="num" style={{ fontSize: 20, fontWeight: 600, color: color || "#e5e5e5" }}>{value}</div>
      {sub && <div className="num" style={{ fontSize: 11, color: "#555", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function StockRow({ stock }: { stock: StockQuote }) {
  const router = useRouter();
  return (
    <tr
      onClick={() => router.push(`/stock/${stock.symbol}`)}
      style={{ cursor: "pointer", borderBottom: "1px solid #1a1a1a" }}
      onMouseEnter={e => (e.currentTarget.style.background = "#161616")}
      onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
    >
      <td style={{ padding: "8px 12px" }}>
        <div style={{ fontSize: 12, fontWeight: 500, color: "#e5e5e5" }}>{stock.symbol}</div>
        <div style={{ fontSize: 10, color: "#555" }}>{fmtCrore(stock.market_cap)}</div>
      </td>
      <td className="num" style={{ padding: "8px 12px", textAlign: "right", fontSize: 12, color: "#e5e5e5" }}>
        ₹{fmt(stock.price)}
      </td>
      <td className={`num ${changeClass(stock.change_pct)}`} style={{ padding: "8px 12px", textAlign: "right", fontSize: 12 }}>
        {changeSign(stock.change_pct)}{fmt(stock.change_pct)}%
      </td>
      <td className="num" style={{ padding: "8px 12px", textAlign: "right", fontSize: 11, color: "#555" }}>
        {(stock.volume / 1e6).toFixed(1)}M
      </td>
    </tr>
  );
}

export default function MarketOverview() {
  const [gainers, setGainers] = useState<StockQuote[]>([]);
  const [losers, setLosers] = useState<StockQuote[]>([]);
  const [fiiDii, setFiiDii] = useState<{ category: string; buyValue: number; sellValue: number; netValue: number }[] | null>(null);
  const [tab, setTab] = useState<"gainers" | "losers" | "all">("gainers");
  const [nifty50, setNifty50] = useState<StockQuote[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const [g, l, n] = await Promise.all([
          api.gainers(),
          api.losers(),
          api.nifty50(),
        ]);
        setGainers(g || []);
        setLosers(l || []);
        setNifty50(n || []);
      } catch (e) {
        console.error(e);
      }
      try {
        const fiidii = await api.fiiDii() as { data?: { category: string; buyValue: number; sellValue: number; netValue: number }[] };
        if (fiidii?.data) setFiiDii(fiidii.data);
      } catch {}
      setLoading(false);
    };
    load();
    const id = setInterval(load, 120000);
    return () => clearInterval(id);
  }, []);

  const displayList = tab === "gainers" ? gainers : tab === "losers" ? losers : nifty50;

  const totalGainers = nifty50.filter(s => s.change_pct > 0).length;
  const totalLosers = nifty50.filter(s => s.change_pct < 0).length;

  return (
    <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
      {/* Stats bar */}
      <div style={{
        display: "flex", gap: 12, padding: "12px 16px",
        borderBottom: "1px solid #1e1e1e", background: "#0d0d0d",
      }}>
        <StatCard
          label="ADVANCES"
          value={totalGainers.toString()}
          sub={`${nifty50.length} tracked`}
          color="#22c55e"
        />
        <StatCard
          label="DECLINES"
          value={totalLosers.toString()}
          sub={`A/D: ${totalGainers}/${totalLosers}`}
          color="#ef4444"
        />
        {fiiDii && fiiDii.map(f => (
          <StatCard
            key={f.category}
            label={f.category}
            value={`₹${Math.abs(f.netValue / 100).toFixed(0)} Cr`}
            sub={f.netValue >= 0 ? "Net Buy" : "Net Sell"}
            color={f.netValue >= 0 ? "#22c55e" : "#ef4444"}
          />
        ))}
      </div>

      {/* Content area */}
      <div style={{ flex: 1, overflow: "hidden", display: "flex" }}>
        {/* Main table */}
        <div style={{ flex: 1, overflow: "auto" }}>
          {/* Tabs */}
          <div style={{
            display: "flex", gap: 0, padding: "0 16px",
            borderBottom: "1px solid #1e1e1e",
            background: "#0d0d0d",
          }}>
            {[
              { key: "gainers", label: `Top Gainers (${gainers.length})` },
              { key: "losers", label: `Top Losers (${losers.length})` },
              { key: "all", label: "NIFTY 50" },
            ].map(t => (
              <button
                key={t.key}
                onClick={() => setTab(t.key as typeof tab)}
                style={{
                  padding: "10px 16px",
                  fontSize: 11,
                  border: "none",
                  borderBottom: tab === t.key ? "2px solid #3b82f6" : "2px solid transparent",
                  background: "transparent",
                  color: tab === t.key ? "#e5e5e5" : "#555",
                  cursor: "pointer",
                  fontWeight: tab === t.key ? 600 : 400,
                  transition: "all 0.15s",
                }}
              >
                {t.label}
              </button>
            ))}
          </div>

          {loading ? (
            <div style={{ padding: 16 }}>
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="skeleton" style={{ height: 40, marginBottom: 6, borderRadius: 4 }} />
              ))}
            </div>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ background: "#111" }}>
                  <th style={{ padding: "8px 12px", textAlign: "left", fontSize: 10, color: "#555", fontWeight: 500 }}>SYMBOL</th>
                  <th style={{ padding: "8px 12px", textAlign: "right", fontSize: 10, color: "#555", fontWeight: 500 }}>PRICE</th>
                  <th style={{ padding: "8px 12px", textAlign: "right", fontSize: 10, color: "#555", fontWeight: 500 }}>CHANGE</th>
                  <th style={{ padding: "8px 12px", textAlign: "right", fontSize: 10, color: "#555", fontWeight: 500 }}>VOLUME</th>
                </tr>
              </thead>
              <tbody>
                {displayList.map(s => <StockRow key={s.symbol} stock={s} />)}
              </tbody>
            </table>
          )}
        </div>

        {/* Right sidebar: FII/DII + market breadth */}
        <div style={{
          width: 280, borderLeft: "1px solid #1e1e1e",
          background: "#0d0d0d", flexShrink: 0, overflow: "auto",
          display: "flex", flexDirection: "column", gap: 0,
        }}>
          {/* FII/DII detail */}
          {fiiDii && (
            <div style={{ padding: 16, borderBottom: "1px solid #1e1e1e" }}>
              <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.06em", marginBottom: 12 }}>FII / DII ACTIVITY</div>
              {fiiDii.map(f => (
                <div key={f.category} style={{ marginBottom: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontSize: 11, color: "#aaa" }}>{f.category}</span>
                    <span className={`num ${f.netValue >= 0 ? "gain" : "loss"}`} style={{ fontSize: 11, fontWeight: 600 }}>
                      {f.netValue >= 0 ? "+" : ""}₹{(f.netValue / 100).toFixed(0)} Cr
                    </span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#555" }}>
                    <span>Buy: ₹{(f.buyValue / 100).toFixed(0)} Cr</span>
                    <span>Sell: ₹{(f.sellValue / 100).toFixed(0)} Cr</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Market Breadth */}
          {nifty50.length > 0 && (
            <div style={{ padding: 16, borderBottom: "1px solid #1e1e1e" }}>
              <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.06em", marginBottom: 12 }}>MARKET BREADTH</div>
              <div style={{ display: "flex", height: 8, borderRadius: 4, overflow: "hidden", marginBottom: 8 }}>
                <div style={{ width: `${(totalGainers / nifty50.length) * 100}%`, background: "#22c55e" }} />
                <div style={{ width: `${(totalLosers / nifty50.length) * 100}%`, background: "#ef4444" }} />
                <div style={{ flex: 1, background: "#333" }} />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10 }}>
                <span className="gain">▲ {totalGainers} Adv</span>
                <span style={{ color: "#555" }}>{nifty50.length - totalGainers - totalLosers} Unch</span>
                <span className="loss">▼ {totalLosers} Dec</span>
              </div>
            </div>
          )}

          {/* How to use */}
          <div style={{ padding: 16 }}>
            <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.06em", marginBottom: 8 }}>QUICK GUIDE</div>
            <div style={{ fontSize: 11, color: "#444", lineHeight: 1.6 }}>
              <p>• Click any stock in the watchlist or table to view detailed charts + analysis</p>
              <p style={{ marginTop: 4 }}>• Run multi-agent AI analysis on any stock page</p>
              <p style={{ marginTop: 4 }}>• View live option chains and institutional data</p>
              <p style={{ marginTop: 4 }}>• Paper trade on the Portfolio tab</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
