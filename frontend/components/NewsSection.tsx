'use client';

import { useState, useEffect } from "react";
import { api, type NewsArticle } from "@/lib/api";

const TAG_COLORS: Record<string, string> = {
  earnings: "#f59e0b",
  order: "#22c55e",
  ma: "#3b82f6",
  analyst: "#8b5cf6",
  dividend: "#06b6d4",
  expansion: "#10b981",
  general: "#555",
};

const TAG_LABELS: Record<string, string> = {
  earnings: "Earnings",
  order: "Order Win",
  ma: "M&A",
  analyst: "Analyst",
  dividend: "Dividend",
  expansion: "Expansion",
  general: "News",
};

function NewsCard({ article, compact }: { article: NewsArticle; compact?: boolean }) {
  const sentColor = article.sentiment === "positive"
    ? "#22c55e" : article.sentiment === "negative" ? "#ef4444" : "#555";
  const primaryTag = article.tags[0] || "general";
  const tagColor = TAG_COLORS[primaryTag] || "#555";
  const tagLabel = TAG_LABELS[primaryTag] || primaryTag;

  return (
    <a
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
      style={{
        display: "block",
        background: "#111",
        border: "1px solid #1e1e1e",
        borderLeft: `3px solid ${sentColor}33`,
        borderRadius: 6,
        padding: compact ? "10px 12px" : "12px 16px",
        marginBottom: 8,
        textDecoration: "none",
        transition: "border-color 0.15s",
      }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = "#2e2e2e")}
      onMouseLeave={e => (e.currentTarget.style.borderColor = "#1e1e1e")}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4, flexWrap: "wrap" }}>
            <span style={{
              fontSize: 10, fontWeight: 600, color: tagColor,
              background: tagColor + "18", padding: "1px 6px", borderRadius: 3,
              textTransform: "uppercase", letterSpacing: "0.04em",
            }}>
              {tagLabel}
            </span>
            {article.tags.slice(1, 3).map(t => (
              <span key={t} style={{
                fontSize: 10, color: "#444",
                background: "#1a1a1a", padding: "1px 5px", borderRadius: 3,
              }}>
                {TAG_LABELS[t] || t}
              </span>
            ))}
            <span style={{ fontSize: 10, color: "#444", marginLeft: "auto" }}>
              {article.age_days === 0 ? `${article.age_hours}h ago`
               : article.age_days === 1 ? "Yesterday"
               : `${article.age_days}d ago`}
            </span>
          </div>
          <p style={{
            fontSize: compact ? 12 : 13, color: "#d4d4d4",
            margin: 0, lineHeight: 1.4, fontWeight: 500,
            overflow: "hidden", display: "-webkit-box",
            WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
          }}>
            {article.title}
          </p>
          {!compact && article.summary && (
            <p style={{
              fontSize: 11, color: "#666", margin: "4px 0 0", lineHeight: 1.5,
              overflow: "hidden", display: "-webkit-box",
              WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
            }}>
              {article.summary}
            </p>
          )}
          <div style={{ fontSize: 10, color: "#444", marginTop: 4 }}>
            {article.source}
          </div>
        </div>
        <div style={{
          width: 6, height: 6, borderRadius: "50%",
          background: sentColor, flexShrink: 0, marginTop: 4,
        }} />
      </div>
    </a>
  );
}

function FilterPill({ label, active, color, onClick }: {
  label: string; active: boolean; color?: string; onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: "3px 10px", fontSize: 10, border: "none", borderRadius: 12,
        cursor: "pointer", fontWeight: 500,
        background: active ? (color || "#3b82f6") + "22" : "#1a1a1a",
        color: active ? (color || "#3b82f6") : "#555",
        outline: active ? `1px solid ${color || "#3b82f6"}44` : "none",
      }}
    >
      {label}
    </button>
  );
}

interface NewsSectionProps {
  symbol: string;
  compact?: boolean;
  maxItems?: number;
}

export default function NewsSection({ symbol, compact = false, maxItems = 20 }: NewsSectionProps) {
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTag, setActiveTag] = useState<string>("all");
  const [activeSentiment, setActiveSentiment] = useState<string>("all");

  useEffect(() => {
    setLoading(true);
    api.news(symbol)
      .then(res => {
        setArticles(res.articles || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [symbol]);

  const allTags = Array.from(new Set(articles.flatMap(a => a.tags)));
  const filtered = articles
    .filter(a => activeTag === "all" || a.tags.includes(activeTag))
    .filter(a => activeSentiment === "all" || a.sentiment === activeSentiment)
    .slice(0, maxItems);

  const stats = {
    pos: articles.filter(a => a.sentiment === "positive").length,
    neg: articles.filter(a => a.sentiment === "negative").length,
    neu: articles.filter(a => a.sentiment === "neutral").length,
  };

  if (loading) {
    return (
      <div style={{ padding: 16 }}>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="skeleton" style={{ height: 72, marginBottom: 8, borderRadius: 6 }} />
        ))}
      </div>
    );
  }

  if (!articles.length) {
    return (
      <div style={{ padding: 32, textAlign: "center", color: "#555", fontSize: 12 }}>
        No recent news found for {symbol}
      </div>
    );
  }

  return (
    <div>
      {/* Sentiment summary bar */}
      {!compact && (
        <div style={{
          display: "flex", gap: 16, padding: "10px 16px",
          borderBottom: "1px solid #1e1e1e", alignItems: "center",
        }}>
          <span style={{ fontSize: 10, color: "#555" }}>SENTIMENT</span>
          <span style={{ fontSize: 12, color: "#22c55e", fontWeight: 600 }}>{stats.pos} Positive</span>
          <span style={{ fontSize: 12, color: "#ef4444", fontWeight: 600 }}>{stats.neg} Negative</span>
          <span style={{ fontSize: 12, color: "#555" }}>{stats.neu} Neutral</span>
          <div style={{
            flex: 1, height: 4, background: "#1e1e1e", borderRadius: 2, overflow: "hidden",
            display: "flex",
          }}>
            {stats.pos > 0 && <div style={{ width: `${stats.pos / articles.length * 100}%`, background: "#22c55e", height: "100%" }} />}
            {stats.neg > 0 && <div style={{ width: `${stats.neg / articles.length * 100}%`, background: "#ef4444", height: "100%" }} />}
          </div>
        </div>
      )}

      {/* Filters */}
      <div style={{
        display: "flex", gap: 6, padding: "8px 12px",
        borderBottom: "1px solid #1e1e1e", flexWrap: "wrap",
        alignItems: "center",
      }}>
        <FilterPill label="All" active={activeTag === "all"} onClick={() => setActiveTag("all")} />
        {allTags.map(t => (
          <FilterPill
            key={t} label={TAG_LABELS[t] || t}
            active={activeTag === t} color={TAG_COLORS[t]}
            onClick={() => setActiveTag(t === activeTag ? "all" : t)}
          />
        ))}
        <div style={{ marginLeft: "auto", display: "flex", gap: 4 }}>
          <FilterPill label="▲" active={activeSentiment === "positive"} color="#22c55e"
            onClick={() => setActiveSentiment(activeSentiment === "positive" ? "all" : "positive")} />
          <FilterPill label="▼" active={activeSentiment === "negative"} color="#ef4444"
            onClick={() => setActiveSentiment(activeSentiment === "negative" ? "all" : "negative")} />
        </div>
      </div>

      {/* Articles */}
      <div style={{ padding: "8px 12px" }}>
        {filtered.length === 0 ? (
          <div style={{ padding: 16, textAlign: "center", color: "#555", fontSize: 11 }}>
            No articles match the selected filters
          </div>
        ) : (
          filtered.map((a, i) => <NewsCard key={i} article={a} compact={compact} />)
        )}
      </div>
    </div>
  );
}
