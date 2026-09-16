"use client";
import { useState, useEffect } from "react";

const API = "http://localhost:8001";

function FearGreedMeter({ score, label }: { score: number; label: string }) {
  const colors = ["#ef4444","#f97316","#f59e0b","#84cc16","#22c55e"];
  const idx = Math.min(4, Math.floor(score / 20));
  const color = colors[idx];
  const r = 80; const cx = 100; const cy = 100;
  const rad = (d: number) => d * Math.PI / 180;
  const angle = -135 + (score / 100) * 270;
  const nx = cx + r * Math.cos(rad(angle - 90));
  const ny = cy + r * Math.sin(rad(angle - 90));
  return (
    <div className="flex flex-col items-center bg-gray-900 border border-gray-700 rounded-xl p-6">
      <div className="text-sm text-gray-400 mb-2">India Fear & Greed Index</div>
      <svg viewBox="0 0 200 140" className="w-52">
        {[["#ef4444",-135,-45],["#f59e0b",-45,45],["#22c55e",45,135]].map(([c,s,e],i) => {
          const a1 = rad(Number(s)-90); const a2 = rad(Number(e)-90);
          return <path key={i} d={`M ${cx+r*Math.cos(a1)} ${cy+r*Math.sin(a1)} A ${r} ${r} 0 0 1 ${cx+r*Math.cos(a2)} ${cy+r*Math.sin(a2)}`} fill="none" stroke={String(c)} strokeWidth="16" strokeLinecap="round" />;
        })}
        <line x1={cx} y1={cy} x2={nx} y2={ny} stroke={color} strokeWidth="4" strokeLinecap="round" />
        <circle cx={cx} cy={cy} r="8" fill={color} />
        <text x={cx} y={cy+22} textAnchor="middle" fill="white" fontSize="24" fontWeight="bold">{score.toFixed(0)}</text>
      </svg>
      <div className="text-xl font-bold mt-2" style={{ color }}>{label.replace(/_/g," ")}</div>
      <div className="flex justify-between w-full text-xs text-gray-500 mt-2 px-2">
        <span>Extreme Fear</span><span>Neutral</span><span>Extreme Greed</span>
      </div>
    </div>
  );
}

function MacroCard({ title, items }: { title: string; items: { label: string; value: string; change?: number }[] }) {
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
      <div className="text-sm font-semibold text-gray-200 mb-3">{title}</div>
      <div className="space-y-2">
        {items.map(item => (
          <div key={item.label} className="flex items-center justify-between">
            <span className="text-xs text-gray-400">{item.label}</span>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-white">{item.value}</span>
              {item.change != null && (
                <span className={`text-xs font-medium ${item.change >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {item.change >= 0 ? "+" : ""}{item.change.toFixed(2)}%
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function NewsFeed({ items }: { items: any[] }) {
  if (!items?.length) return <div className="text-gray-500 text-sm text-center py-8">No news available</div>;
  return (
    <div className="space-y-3">
      {items.map((n: any, i: number) => (
        <a key={i} href={n.url} target="_blank" rel="noopener noreferrer"
          className="block bg-gray-900 border border-gray-700 rounded-lg p-4 hover:border-gray-500 transition-colors">
          <div className="flex items-start gap-3">
            <span className={`mt-0.5 px-2 py-0.5 rounded text-xs font-bold shrink-0 ${
              n.sentiment?.label === "POSITIVE" ? "bg-green-900 text-green-300" :
              n.sentiment?.label === "NEGATIVE" ? "bg-red-900 text-red-300" : "bg-gray-800 text-gray-400"
            }`}>{n.sentiment?.label ?? "NEUTRAL"}</span>
            <div>
              <div className="text-sm text-gray-100 font-medium leading-tight">{n.title}</div>
              <div className="text-xs text-gray-500 mt-1">{n.source} • {n.published_at?.slice(0,16)}</div>
            </div>
          </div>
        </a>
      ))}
    </div>
  );
}

export default function AlternativePage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("fear_greed");
  const [symbol, setSymbol] = useState("RELIANCE");
  const [stockData, setStockData] = useState<any>(null);
  const [stockLoading, setStockLoading] = useState(false);

  useEffect(() => {
    fetch(`${API}/api/alternative/snapshot`).then(r => r.json()).then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const loadStock = async (sym: string) => {
    setStockLoading(true);
    try {
      const r = await fetch(`${API}/api/alternative/stock/${sym}`);
      if (r.ok) setStockData(await r.json());
    } catch { }
    setStockLoading(false);
  };

  const d = data ?? {};
  const breadth = d.market_breadth ?? {};
  const fiiSent = d.fii_sentiment ?? {};
  const fg = d.fear_greed ?? {};
  const indiaMacro = d.india_macro ?? {};
  const usMacro = d.us_macro ?? {};
  const cpi = d.india_cpi ?? {};
  const gdp = d.india_gdp ?? {};

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-1">Alternative & Economic Data</h1>
          <p className="text-gray-400">Fear/Greed Index • Market Breadth • FII Sentiment • Google Trends • Economic Indicators • News Sentiment</p>
        </div>

        {loading && <div className="text-center py-20 text-gray-400">Loading alternative data…</div>}

        {!loading && (
          <>
            {/* Tabs */}
            <div className="flex gap-2 mb-6 border-b border-gray-800 overflow-x-auto">
              {["fear_greed","breadth","macro","news","stock_intel"].map(t => (
                <button key={t} onClick={() => setTab(t)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px whitespace-nowrap ${tab === t ? "border-blue-500 text-white" : "border-transparent text-gray-400 hover:text-white"}`}>
                  {t.replace(/_/g," ").split(" ").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ")}
                </button>
              ))}
            </div>

            {tab === "fear_greed" && (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <FearGreedMeter score={fg.score ?? 50} label={fg.label ?? "NEUTRAL"} />
                <div className="lg:col-span-2 space-y-4">
                  <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                    <h3 className="text-sm font-semibold text-gray-200 mb-3">Components</h3>
                    {Object.entries(fg.components ?? {}).filter(([k]) => !k.includes("_level")).map(([k, v]) => (
                      <div key={k} className="mb-3">
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-gray-400">{k.replace(/_/g," ").replace(/\b\w/g,c=>c.toUpperCase())}</span>
                          <span className="text-white">{(v as number).toFixed(0)}/100</span>
                        </div>
                        <div className="w-full bg-gray-700 rounded-full h-2">
                          <div className={`h-2 rounded-full ${(v as number) >= 55 ? "bg-green-500" : (v as number) <= 45 ? "bg-red-500" : "bg-yellow-500"}`}
                            style={{ width: `${v}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                    <p className="text-sm text-gray-200">{fg.interpretation}</p>
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 text-center">
                      <div className="text-xs text-gray-400">FII Sentiment Score</div>
                      <div className={`text-2xl font-bold mt-1 ${(fiiSent.score ?? 50) >= 55 ? "text-green-400" : "text-red-400"}`}>{fiiSent.score ?? "N/A"}</div>
                      <div className="text-xs text-gray-400">{fiiSent.sentiment}</div>
                    </div>
                    <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 text-center">
                      <div className="text-xs text-gray-400">India VIX</div>
                      <div className="text-2xl font-bold mt-1 text-yellow-400">{(fg.components?.vix_level ?? 0).toFixed(1)}</div>
                    </div>
                    <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 text-center">
                      <div className="text-xs text-gray-400">FII Net 5D (₹Cr)</div>
                      <div className={`text-2xl font-bold mt-1 ${(fiiSent.net_5d_cr ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {(fiiSent.net_5d_cr ?? 0) >= 0 ? "+" : ""}{(fiiSent.net_5d_cr ?? 0).toLocaleString()}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {tab === "breadth" && (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {[
                  ["Advances", breadth.advances, "text-green-400"],["Declines", breadth.declines, "text-red-400"],
                  ["A/D Ratio", breadth.advance_decline_ratio?.toFixed(2), breadth.advance_decline_ratio >= 1 ? "text-green-400" : "text-red-400"],
                  ["% Above 50DMA", `${breadth.pct_above_50dma ?? 0}%`, breadth.pct_above_50dma >= 50 ? "text-green-400" : "text-red-400"],
                  ["% Above 200DMA", `${breadth.pct_above_200dma ?? 0}%`, breadth.pct_above_200dma >= 50 ? "text-green-400" : "text-red-400"],
                  ["New 52W Highs", breadth.new_52w_highs, "text-green-400"],["New 52W Lows", breadth.new_52w_lows, "text-red-400"],
                  ["Signal", breadth.breadth_signal, breadth.breadth_signal === "BULLISH" ? "text-green-400" : breadth.breadth_signal === "BEARISH" ? "text-red-400" : "text-yellow-400"],
                ].map(([l,v,c]) => (
                  <div key={String(l)} className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                    <div className="text-xs text-gray-400">{l}</div>
                    <div className={`text-2xl font-bold mt-1 ${c}`}>{v ?? "N/A"}</div>
                  </div>
                ))}
              </div>
            )}

            {tab === "macro" && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <MacroCard title="India Market Indices" items={Object.entries(indiaMacro).filter(([k]) => !k.includes("inr") && !k.includes("eur")).map(([k, v]: any) => ({
                  label: k.replace(/_/g," ").toUpperCase(),
                  value: v.price?.toLocaleString(undefined,{maximumFractionDigits:2}) ?? "N/A",
                  change: v.chg_1d_pct,
                }))} />
                <MacroCard title="India FX & Rates" items={Object.entries(indiaMacro).filter(([k]) => k.includes("inr") || k.includes("eur")).map(([k, v]: any) => ({
                  label: k.toUpperCase(),
                  value: v.price?.toFixed(4) ?? "N/A",
                  change: v.chg_1d_pct,
                }))} />
                <MacroCard title="US Macro Indicators" items={Object.entries(usMacro).filter(([k]) => k !== "yield_curve").map(([k, v]: any) => ({
                  label: k.replace(/_/g," ").toUpperCase(),
                  value: v.price?.toLocaleString(undefined,{maximumFractionDigits:3}) ?? "N/A",
                  change: v.chg_1d_pct,
                }))} />
                <div className="space-y-4">
                  <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                    <div className="text-sm font-semibold text-gray-200 mb-3">India Economic Data</div>
                    {[["GDP Growth (Latest)", `${cpi?.latest_cpi_yoy_pct ?? "N/A"}% YoY`],["CPI Inflation", `${cpi?.latest_cpi_yoy_pct ?? "N/A"}%`],["vs RBI Target", `${cpi?.rbi_target ?? 4}%`],["CPI Trend", cpi?.trend ?? "N/A"]].map(([l,v]) => (
                      <div key={String(l)} className="flex justify-between py-1.5 border-b border-gray-800 last:border-0">
                        <span className="text-gray-400 text-sm">{l}</span>
                        <span className="text-white text-sm">{v}</span>
                      </div>
                    ))}
                  </div>
                  {usMacro.yield_curve && (
                    <div className={`p-4 rounded-lg border ${usMacro.yield_curve.inverted ? "bg-red-950 border-red-700" : "bg-green-950 border-green-700"}`}>
                      <div className="font-semibold text-sm mb-1">{usMacro.yield_curve.inverted ? "⚠️ US Yield Curve Inverted" : "✓ US Yield Curve Normal"}</div>
                      <div className="text-sm">10Y-2Y Spread: {usMacro.yield_curve.spread_10y_2y?.toFixed(3)}%</div>
                      <div className="text-xs text-gray-400 mt-1">{usMacro.yield_curve.signal?.replace(/_/g," ")}</div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {tab === "news" && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div>
                  <h3 className="text-sm font-semibold text-gray-200 mb-3">Market News</h3>
                  <NewsFeed items={d.market_news ?? []} />
                </div>
                <div>
                  <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 mb-3">
                    <div className="text-xs text-gray-400 mb-1">Aggregate News Sentiment</div>
                    <div className={`text-lg font-bold ${d.market_news_sentiment?.label === "POSITIVE" ? "text-green-400" : d.market_news_sentiment?.label === "NEGATIVE" ? "text-red-400" : "text-yellow-400"}`}>
                      {d.market_news_sentiment?.label ?? "NEUTRAL"} (score: {d.market_news_sentiment?.score?.toFixed(2) ?? "0"})
                    </div>
                    <div className="text-xs text-gray-400 mt-1">
                      +{d.market_news_sentiment?.positive ?? 0} Positive / -{d.market_news_sentiment?.negative ?? 0} Negative / {d.market_news_sentiment?.neutral ?? 0} Neutral
                    </div>
                  </div>
                </div>
              </div>
            )}

            {tab === "stock_intel" && (
              <div>
                <div className="flex gap-3 mb-6">
                  <input value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())} onKeyDown={e => e.key === "Enter" && loadStock(symbol)}
                    placeholder="NSE symbol…" className="bg-gray-800 border border-gray-600 rounded-lg px-4 py-2.5 text-white text-sm w-48" />
                  <button onClick={() => loadStock(symbol)} disabled={stockLoading}
                    className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2.5 rounded-lg text-sm font-medium">
                    {stockLoading ? "Loading…" : "Get Intel"}
                  </button>
                </div>
                {stockData && (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div>
                      <h3 className="text-sm font-semibold text-gray-200 mb-3">Google Trends — {stockData.company}</h3>
                      {stockData.search_trends?.error ? (
                        <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 text-gray-400">{stockData.search_trends.error}</div>
                      ) : (
                        <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                          <div className="grid grid-cols-3 gap-3 mb-4">
                            <div className="text-center"><div className="text-xs text-gray-400">Current</div><div className="text-2xl font-bold text-white">{stockData.search_trends?.current_interest?.toFixed(0) ?? "N/A"}</div></div>
                            <div className="text-center"><div className="text-xs text-gray-400">6M Avg</div><div className="text-2xl font-bold text-gray-300">{stockData.search_trends?.avg_6m?.toFixed(0) ?? "N/A"}</div></div>
                            <div className="text-center"><div className="text-xs text-gray-400">Trend</div><div className={`text-2xl font-bold ${stockData.search_trends?.direction === "RISING" ? "text-green-400" : stockData.search_trends?.direction === "FALLING" ? "text-red-400" : "text-yellow-400"}`}>{stockData.search_trends?.direction ?? "N/A"}</div></div>
                          </div>
                          {stockData.search_trends?.series?.length > 0 && (
                            <div className="flex items-end gap-0.5 h-24">
                              {stockData.search_trends.series.slice(-52).map((pt: any, i: number) => (
                                <div key={i} className="flex-1 bg-blue-600 rounded-t" style={{ height: `${pt.value}%` }} title={`${pt.date}: ${pt.value}`} />
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-gray-200 mb-3">News Sentiment — {stockData.symbol}</h3>
                      <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 mb-3">
                        <div className={`text-lg font-bold ${stockData.news_sentiment?.label === "POSITIVE" ? "text-green-400" : stockData.news_sentiment?.label === "NEGATIVE" ? "text-red-400" : "text-yellow-400"}`}>
                          {stockData.news_sentiment?.label ?? "NEUTRAL"}
                        </div>
                        <div className="text-xs text-gray-400 mt-1">Score: {stockData.news_sentiment?.score?.toFixed(2)} | +{stockData.news_sentiment?.positive ?? 0} / -{stockData.news_sentiment?.negative ?? 0}</div>
                      </div>
                      <NewsFeed items={stockData.news ?? []} />
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
