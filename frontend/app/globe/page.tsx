'use client';

import { useState, useEffect, useCallback } from "react";
import { ComposableMap, Geographies, Geography, Marker, type Geography as GeoFeature } from "react-simple-maps";
import IndexBar from "@/components/IndexBar";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
const GEO_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";
const REFRESH_INTERVAL = 10 * 60 * 1000;

const CATEGORY_COLORS: Record<string, string> = {
  conflict:  "#ff3b3b",
  economic:  "#00d084",
  energy:    "#f59e0b",
  monetary:  "#3b82f6",
  political: "#a855f7",
  corporate: "#f59e0b",
  general:   "#555",
};

const CATEGORIES = ["All", "Conflict", "Economic", "Energy", "Monetary", "Political", "Corporate"];

interface GeoArticle {
  title: string;
  url: string;
  source: string;
  age_hours: number;
  country: string;
  lat: number;
  lng: number;
  category: string;
  summary?: string;
}

interface CountryMarker {
  country: string;
  lat: number;
  lng: number;
  count: number;
  dominantCategory: string;
}

function categoryColor(cat: string): string {
  return CATEGORY_COLORS[cat.toLowerCase()] || "#555";
}

function ageLabel(hours: number): string {
  if (hours < 1) return "<1h";
  if (hours < 24) return `${Math.floor(hours)}h`;
  const days = Math.floor(hours / 24);
  return `${days}d`;
}

function buildMarkers(articles: GeoArticle[]): CountryMarker[] {
  const map = new Map<string, { lat: number; lng: number; cats: string[] }>();
  for (const a of articles) {
    const existing = map.get(a.country);
    if (existing) {
      existing.cats.push(a.category);
    } else {
      map.set(a.country, { lat: a.lat, lng: a.lng, cats: [a.category] });
    }
  }
  return Array.from(map.entries()).map(([country, { lat, lng, cats }]) => {
    const freq: Record<string, number> = {};
    for (const c of cats) freq[c] = (freq[c] || 0) + 1;
    const dominantCategory = Object.entries(freq).sort((a, b) => b[1] - a[1])[0][0];
    return { country, lat, lng, count: cats.length, dominantCategory };
  });
}

function markerRadius(count: number): number {
  if (count > 5) return 8;
  if (count > 2) return 6;
  return 4;
}

function ArticleRow({ article, onClick }: { article: GeoArticle; onClick: () => void }) {
  const color = categoryColor(article.category);
  return (
    <a
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
      onClick={e => { e.stopPropagation(); }}
      style={{ display: "block", textDecoration: "none", padding: "8px 12px", borderBottom: "1px solid #111", cursor: "pointer" }}
      onMouseEnter={e => (e.currentTarget.style.backgroundColor = "#111")}
      onMouseLeave={e => (e.currentTarget.style.backgroundColor = "transparent")}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
        <div style={{ width: 6, height: 6, borderRadius: "50%", background: color, flexShrink: 0 }} />
        <span style={{ fontSize: 9, color: "#444", fontFamily: "monospace" }}>{article.source}</span>
        <span style={{ fontSize: 9, color: "#333", marginLeft: "auto", fontFamily: "monospace" }}>{ageLabel(article.age_hours)}</span>
      </div>
      <p style={{ margin: 0, fontSize: 11, color: "#d4d4d4", lineHeight: 1.4, fontWeight: 500 }}>
        {article.title}
      </p>
      <div style={{ fontSize: 9, color: "#444", marginTop: 3, fontFamily: "monospace" }}>
        {article.country} · <span style={{ color }}>{article.category.toUpperCase()}</span>
      </div>
    </a>
  );
}

function SkeletonRow() {
  return (
    <div style={{ padding: "8px 12px", borderBottom: "1px solid #111" }}>
      <div className="skeleton" style={{ height: 8, width: "60%", marginBottom: 6, borderRadius: 2 }} />
      <div className="skeleton" style={{ height: 12, width: "90%", marginBottom: 4, borderRadius: 2 }} />
      <div className="skeleton" style={{ height: 8, width: "40%", borderRadius: 2 }} />
    </div>
  );
}

interface TooltipState {
  visible: boolean;
  x: number;
  y: number;
  country: string;
  count: number;
}

export default function GlobePage() {
  const [articles, setArticles] = useState<GeoArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeCategory, setActiveCategory] = useState("All");
  const [selectedCountry, setSelectedCountry] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<TooltipState>({ visible: false, x: 0, y: 0, country: "", count: 0 });

  const fetchNews = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/geo-news`);
      const data = await res.json();
      setArticles(data.articles || []);
    } catch {
      setArticles([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchNews();
    const interval = setInterval(fetchNews, REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchNews]);

  const filtered = articles.filter(a => {
    const catMatch = activeCategory === "All" || a.category.toLowerCase() === activeCategory.toLowerCase();
    const countryMatch = !selectedCountry || a.country === selectedCountry;
    return catMatch && countryMatch;
  });

  const markers = buildMarkers(
    activeCategory === "All" ? articles : articles.filter(a => a.category.toLowerCase() === activeCategory.toLowerCase())
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden", background: "#000", fontFamily: "monospace" }}>
      <IndexBar />

      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Left panel */}
        <div style={{
          width: 270,
          flexShrink: 0,
          borderRight: "1px solid #141414",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}>
          {/* Panel header */}
          <div style={{ padding: "10px 12px", borderBottom: "1px solid #141414", flexShrink: 0 }}>
            <div style={{ fontSize: 9, color: "#444", letterSpacing: "0.1em", marginBottom: 8 }}>
              GEOPOLITICAL INTEL
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {CATEGORIES.map(cat => {
                const active = activeCategory === cat;
                const color = cat === "All" ? "#3b82f6" : categoryColor(cat);
                return (
                  <button
                    key={cat}
                    onClick={() => {
                      setActiveCategory(cat);
                      setSelectedCountry(null);
                    }}
                    style={{
                      padding: "2px 8px",
                      fontSize: 9,
                      border: "none",
                      borderRadius: 3,
                      cursor: "pointer",
                      background: active ? color + "22" : "#111",
                      color: active ? color : "#444",
                      outline: active ? `1px solid ${color}44` : "1px solid #1a1a1a",
                      fontFamily: "monospace",
                      letterSpacing: "0.05em",
                    }}
                  >
                    {cat.toUpperCase()}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Country filter indicator */}
          {selectedCountry && (
            <div style={{
              padding: "6px 12px",
              background: "#1e3a5f22",
              borderBottom: "1px solid #1e3a5f44",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexShrink: 0,
            }}>
              <span style={{ fontSize: 9, color: "#3b82f6" }}>▶ {selectedCountry.toUpperCase()}</span>
              <button
                onClick={() => setSelectedCountry(null)}
                style={{ background: "none", border: "none", color: "#444", cursor: "pointer", fontSize: 10 }}
              >
                ✕
              </button>
            </div>
          )}

          {/* Article count */}
          <div style={{ padding: "4px 12px", borderBottom: "1px solid #0d0d0d", flexShrink: 0 }}>
            <span style={{ fontSize: 9, color: "#333" }}>{filtered.length} ARTICLES</span>
          </div>

          {/* Article list */}
          <div style={{ flex: 1, overflowY: "auto" }}>
            {loading ? (
              Array.from({ length: 8 }).map((_, i) => <SkeletonRow key={i} />)
            ) : filtered.length === 0 ? (
              <div style={{ padding: 24, textAlign: "center", color: "#333", fontSize: 11 }}>
                No articles found
              </div>
            ) : (
              filtered.map((a, i) => (
                <ArticleRow
                  key={i}
                  article={a}
                  onClick={() => setSelectedCountry(a.country === selectedCountry ? null : a.country)}
                />
              ))
            )}
          </div>
        </div>

        {/* Right panel: map */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", position: "relative" }}>
          {/* Map header */}
          <div style={{
            padding: "6px 14px",
            borderBottom: "1px solid #141414",
            display: "flex",
            alignItems: "center",
            gap: 10,
            flexShrink: 0,
          }}>
            <span style={{ fontSize: 9, color: "#444", letterSpacing: "0.1em" }}>WORLD INTELLIGENCE MAP</span>
            <span style={{ fontSize: 9, color: "#222" }}>·</span>
            <span style={{ fontSize: 9, color: "#333" }}>{markers.length} ACTIVE REGIONS</span>
            <span style={{ fontSize: 9, color: "#222", marginLeft: "auto" }}>AUTO-REFRESH 10M</span>
          </div>

          {/* Map container */}
          <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
            <ComposableMap
              projection="geoMercator"
              projectionConfig={{ scale: 120, center: [0, 20] }}
              style={{ width: "100%", height: "100%" }}
            >
              <Geographies geography={GEO_URL}>
                {({ geographies }: { geographies: GeoFeature[] }) =>
                  geographies.map(geo => (
                    <Geography
                      key={geo.rsmKey}
                      geography={geo}
                      style={{
                        default: { fill: "#141414", stroke: "#0d0d0d", strokeWidth: 0.5, outline: "none" },
                        hover:   { fill: "#1e1e1e", outline: "none" },
                        pressed: { fill: "#1a2a3a", outline: "none" },
                      }}
                    />
                  ))
                }
              </Geographies>

              {markers.map((m, i) => (
                <Marker key={i} coordinates={[m.lng, m.lat]}>
                  <circle
                    r={markerRadius(m.count)}
                    fill={categoryColor(m.dominantCategory)}
                    fillOpacity={selectedCountry === m.country ? 1 : 0.75}
                    stroke={selectedCountry === m.country ? "#fff" : "#000"}
                    strokeWidth={selectedCountry === m.country ? 1.5 : 0.5}
                    style={{ cursor: "pointer" }}
                    onClick={() => setSelectedCountry(m.country === selectedCountry ? null : m.country)}
                    onMouseEnter={e => {
                      const rect = (e.target as SVGCircleElement).closest("svg")?.getBoundingClientRect();
                      if (rect) {
                        setTooltip({
                          visible: true,
                          x: e.clientX - rect.left,
                          y: e.clientY - rect.top,
                          country: m.country,
                          count: m.count,
                        });
                      }
                    }}
                    onMouseMove={e => {
                      const rect = (e.target as SVGCircleElement).closest("svg")?.getBoundingClientRect();
                      if (rect) {
                        setTooltip(prev => ({ ...prev, x: e.clientX - rect.left, y: e.clientY - rect.top }));
                      }
                    }}
                    onMouseLeave={() => setTooltip(prev => ({ ...prev, visible: false }))}
                  />
                </Marker>
              ))}
            </ComposableMap>

            {/* Tooltip */}
            {tooltip.visible && (
              <div style={{
                position: "absolute",
                left: tooltip.x + 10,
                top: tooltip.y - 30,
                background: "#111",
                border: "1px solid #2a2a2a",
                borderRadius: 4,
                padding: "4px 8px",
                pointerEvents: "none",
                zIndex: 10,
              }}>
                <div style={{ fontSize: 11, color: "#e5e5e5", fontWeight: 600 }}>{tooltip.country}</div>
                <div style={{ fontSize: 9, color: "#666" }}>{tooltip.count} article{tooltip.count !== 1 ? "s" : ""}</div>
              </div>
            )}
          </div>

          {/* Legend */}
          <div style={{
            padding: "6px 14px",
            borderTop: "1px solid #141414",
            display: "flex",
            alignItems: "center",
            gap: 16,
            flexShrink: 0,
          }}>
            <span style={{ fontSize: 9, color: "#333", letterSpacing: "0.08em" }}>CATEGORY</span>
            {[
              { label: "Conflict",  color: "#ff3b3b" },
              { label: "Economic",  color: "#00d084" },
              { label: "Energy",    color: "#f59e0b" },
              { label: "Monetary",  color: "#3b82f6" },
              { label: "Political", color: "#a855f7" },
              { label: "Corporate", color: "#f59e0b" },
              { label: "General",   color: "#555" },
            ].map(({ label, color }) => (
              <div key={label} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <div style={{ width: 6, height: 6, borderRadius: "50%", background: color }} />
                <span style={{ fontSize: 9, color: "#444" }}>{label.toUpperCase()}</span>
              </div>
            ))}
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <div style={{ width: 4, height: 4, borderRadius: "50%", background: "#555" }} />
                <span style={{ fontSize: 9, color: "#333" }}>1-2</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#555" }} />
                <span style={{ fontSize: 9, color: "#333" }}>3-5</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#555" }} />
                <span style={{ fontSize: 9, color: "#333" }}>5+</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
