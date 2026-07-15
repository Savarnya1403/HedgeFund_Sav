'use client';

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import IndexBar from "@/components/IndexBar";
import { api, type NewsArticle } from "@/lib/api";

const TAG_COLORS: Record<string, string> = {
  earnings: "#f59e0b", order: "#22c55e", ma: "#3b82f6",
  analyst: "#8b5cf6", dividend: "#06b6d4", expansion: "#10b981", general: "#555",
};
const TAG_LABELS: Record<string, string> = {
  earnings: "Earnings", order: "Order Win", ma: "M&A",
  analyst: "Analyst", dividend: "Dividend", expansion: "Expansion", general: "Market News",
};

const QUICK_SEARCHES = [
  "HDFCBANK", "RELIANCE", "TCS", "NTPC", "SBIN", "INFY", "ONGC", "HAL",
  "IRCTC", "ZOMATO", "ADANIENT", "COALINDIA",
];

function NewsCard({ article }: { article: NewsArticle }) {
  const primaryTag = article.tags[0] || "general";
  const tagColor = TAG_COLORS[primaryTag] || "#555";
  const tagLabel = TAG_LABELS[primaryTag] || primaryTag;
  const sentColor = article.sentiment === "positive" ? "#22c55e"
    : article.sentiment === "negative" ? "#ef4444" : "#555";

  return (
    <a href={article.url} target="_blank" rel="noopener noreferrer"
      style={{
        display: "block", background: "#111", border: "1px solid #1e1e1e",
        borderLeft: `3px solid ${sentColor}33`, borderRadius: 6,
        padding: "12px 14px", marginBottom: 8, textDecoration: "none",
      }}
      onMouseEnter={e => (e.currentTarget.style.backgroundColor = "#141414")}
      onMouseLeave={e => (e.currentTarget.style.backgroundColor = "#111")}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", gap: 6, marginBottom: 5, flexWrap: "wrap", alignItems: "center" }}>
            <span style={{
              fontSize: 10, fontWeight: 600, color: tagColor,
              background: tagColor + "18", padding: "1px 6px", borderRadius: 3, textTransform: "uppercase",
            }}>{tagLabel}</span>
            <span style={{ fontSize: 10, color: "#444", marginLeft: "auto" }}>
              {article.age_days === 0 ? `${article.age_hours}h ago`
               : article.age_days === 1 ? "Yesterday" : `${article.age_days}d ago`}
            </span>
          </div>
          <p style={{ margin: "0 0 4px", fontSize: 13, color: "#e5e5e5", lineHeight: 1.4, fontWeight: 500 }}>
            {article.title}
          </p>
          {article.summary && (
            <p style={{ margin: 0, fontSize: 11, color: "#666", lineHeight: 1.5 }}>
              {article.summary.slice(0, 160)}…
            </p>
          )}
          <div style={{ fontSize: 10, color: "#444", marginTop: 4 }}>{article.source}</div>
        </div>
        <div style={{ width: 6, height: 6, borderRadius: "50%", background: sentColor, flexShrink: 0, marginTop: 4 }} />
      </div>
    </a>
  );
}

export default function NewsPage() {
  const router = useRouter();
  const [marketNews, setMarketNews] = useState<NewsArticle[]>([]);
  const [stockNews, setStockNews] = useState<NewsArticle[]>([]);
  const [activeStock, setActiveStock] = useState<string | null>(null);
  const [loadingMarket, setLoadingMarket] = useState(true);
  const [loadingStock, setLoadingStock] = useState(false);
  const [searchQ, setSearchQ] = useState("");
  const [activeTag, setActiveTag] = useState("all");
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    api.marketNews()
      .then(res => { setMarketNews(res.articles || []); setLoadingMarket(false); })
      .catch(() => setLoadingMarket(false));
  }, []);

  const loadStockNews = useCallback(async (sym: string) => {
    setActiveStock(sym);
    setLoadingStock(true);
    try {
      const res = await api.news(sym);
      setStockNews(res.articles || []);
    } catch {
      setStockNews([]);
    } finally {
      setLoadingStock(false);
    }
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const q = searchQ.trim().toUpperCase();
    if (q) loadStockNews(q);
  };

  const refresh = async () => {
    setRefreshing(true);
    try {
      const res = await api.marketNews();
      setMarketNews(res.articles || []);
    } finally {
      setRefreshing(false);
    }
  };

  const displayedMarket = activeTag === "all"
    ? marketNews
    : marketNews.filter(a => a.tags.includes(activeTag));

  const allTags = Array.from(new Set([...marketNews, ...stockNews].flatMap(a => a.tags)));

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden" }}>
      <IndexBar />
      <div style={{ flex: 1, overflow: "auto", background: "#080808" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", padding: "16px 20px" }}>
          {/* Header */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
            <button onClick={() => router.push("/")}
              style={{ background: "none", border: "none", color: "#555", cursor: "pointer", fontSize: 16 }}>
              ←
            </button>
            <div>
              <h1 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "#e5e5e5" }}>
                Market Intelligence Feed
              </h1>
              <div style={{ fontSize: 11, color: "#555" }}>
                Aggregated from ET, Business Standard, Moneycontrol, Mint, NDTV Profit &amp; more
              </div>
            </div>
            <button onClick={refresh} disabled={refreshing}
              style={{
                marginLeft: "auto", background: "#1a1a1a", border: "1px solid #2e2e2e",
                color: refreshing ? "#555" : "#e5e5e5", borderRadius: 6, padding: "5px 12px",
                fontSize: 11, cursor: "pointer",
              }}>
              {refreshing ? "Refreshing…" : "↻ Refresh"}
            </button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: 20 }}>
            {/* Left sidebar: stock search + quick picks */}
            <div>
              <div style={{
                background: "#111", border: "1px solid #1e1e1e", borderRadius: 8,
                padding: 14, marginBottom: 12,
              }}>
                <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.06em", marginBottom: 10 }}>
                  STOCK NEWS
                </div>
                <form onSubmit={handleSearch} style={{ display: "flex", gap: 6, marginBottom: 12 }}>
                  <input
                    value={searchQ}
                    onChange={e => setSearchQ(e.target.value)}
                    placeholder="Enter NSE symbol…"
                    style={{
                      flex: 1, background: "#1a1a1a", border: "1px solid #2e2e2e",
                      borderRadius: 5, padding: "6px 10px", fontSize: 12,
                      color: "#e5e5e5", outline: "none",
                    }}
                  />
                  <button type="submit" style={{
                    background: "#3b82f6", color: "#fff", border: "none",
                    borderRadius: 5, padding: "6px 12px", fontSize: 12, cursor: "pointer",
                  }}>→</button>
                </form>
                <div style={{ fontSize: 10, color: "#555", marginBottom: 6 }}>QUICK PICKS</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {QUICK_SEARCHES.map(s => (
                    <button
                      key={s}
                      onClick={() => loadStockNews(s)}
                      style={{
                        padding: "3px 8px", fontSize: 10, border: "none", borderRadius: 4,
                        cursor: "pointer",
                        background: activeStock === s ? "#3b82f6" : "#1e1e1e",
                        color: activeStock === s ? "#fff" : "#888",
                        fontWeight: activeStock === s ? 600 : 400,
                      }}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>

              {/* Stock-specific news */}
              {activeStock && (
                <div style={{
                  background: "#111", border: "1px solid #1e1e1e", borderRadius: 8, overflow: "hidden",
                }}>
                  <div style={{
                    padding: "10px 14px", borderBottom: "1px solid #1e1e1e",
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                  }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: "#e5e5e5" }}>{activeStock}</span>
                    <button onClick={() => router.push(`/stock/${activeStock}`)}
                      style={{ fontSize: 10, color: "#3b82f6", background: "none", border: "none",
                        cursor: "pointer" }}>
                      View Stock →
                    </button>
                  </div>
                  <div style={{ padding: "8px 10px", maxHeight: 400, overflow: "auto" }}>
                    {loadingStock ? (
                      Array.from({ length: 3 }).map((_, i) => (
                        <div key={i} className="skeleton" style={{ height: 60, marginBottom: 6, borderRadius: 5 }} />
                      ))
                    ) : stockNews.length === 0 ? (
                      <div style={{ padding: 16, textAlign: "center", color: "#555", fontSize: 11 }}>
                        No recent news for {activeStock}
                      </div>
                    ) : (
                      stockNews.slice(0, 10).map((a, i) => (
                        <a key={i} href={a.url} target="_blank" rel="noopener noreferrer"
                          style={{ display: "block", padding: "8px 0", borderBottom: "1px solid #1a1a1a",
                            textDecoration: "none" }}>
                          <p style={{ margin: "0 0 2px", fontSize: 12, color: "#d4d4d4", lineHeight: 1.4 }}>
                            {a.title}
                          </p>
                          <span style={{ fontSize: 10, color: "#444" }}>
                            {a.source} · {a.age_days}d ago
                          </span>
                        </a>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Right: Market news feed */}
            <div>
              {/* Tag filters */}
              <div style={{ display: "flex", gap: 6, marginBottom: 12, flexWrap: "wrap" }}>
                {["all", ...allTags.filter(t => t !== "general")].map(tag => (
                  <button
                    key={tag}
                    onClick={() => setActiveTag(tag)}
                    style={{
                      padding: "4px 12px", fontSize: 10, border: "none", borderRadius: 12,
                      cursor: "pointer", fontWeight: 500,
                      background: activeTag === tag
                        ? (TAG_COLORS[tag] || "#3b82f6") + "22" : "#1a1a1a",
                      color: activeTag === tag
                        ? (TAG_COLORS[tag] || "#3b82f6") : "#555",
                      outline: activeTag === tag
                        ? `1px solid ${(TAG_COLORS[tag] || "#3b82f6")}44` : "none",
                    }}
                  >
                    {tag === "all" ? "All News" : (TAG_LABELS[tag] || tag)}
                  </button>
                ))}
                <span style={{ marginLeft: "auto", fontSize: 11, color: "#555", lineHeight: "28px" }}>
                  {displayedMarket.length} articles
                </span>
              </div>

              {/* News feed */}
              {loadingMarket ? (
                Array.from({ length: 8 }).map((_, i) => (
                  <div key={i} className="skeleton" style={{ height: 80, marginBottom: 8, borderRadius: 6 }} />
                ))
              ) : displayedMarket.length === 0 ? (
                <div style={{ padding: 32, textAlign: "center", color: "#555" }}>
                  No articles found
                </div>
              ) : (
                displayedMarket.map((a, i) => <NewsCard key={i} article={a} />)
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
