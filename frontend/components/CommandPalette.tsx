'use client';

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";

const PAGES = [
  { label: "Home Dashboard",     path: "/home",          icon: "⌂", desc: "Comprehensive market outlook — sectors, sentiment, FII, news" },
  { label: "Dashboard",          path: "/dashboard",     icon: "◈", desc: "Market intelligence hub" },
  { label: "Screener",           path: "/screener",      icon: "⚡", desc: "Momentum, breakout, mean reversion" },
  { label: "Global Macro",       path: "/macro",         icon: "◎", desc: "Indices, FX, commodities, yield curve, macro regime" },
  { label: "Institutional Intel",path: "/institutional", icon: "◑", desc: "FII/DII flows, bulk deals, block deals, sector flows" },
  { label: "Quant Models",       path: "/quant",         icon: "⚛", desc: "Markov regime, arbitrage scanner, factor model, patterns" },
  { label: "AI Signals",         path: "/recommend",     icon: "◆", desc: "Buy/sell recommendations with 6-pillar scoring" },
  { label: "Compare Stocks",     path: "/compare",       icon: "↔", desc: "Correlation & normalized chart comparison" },
  { label: "Geopolitical Globe", path: "/globe",         icon: "◉", desc: "World news mapped by geography" },
  { label: "Volume Scanner",     path: "/volume",        icon: "▲", desc: "Volume deviation from historical averages" },
  { label: "Market Patterns",    path: "/patterns",      icon: "⌘", desc: "Historical event analysis & repeating patterns" },
  { label: "Pairs Trading",      path: "/pairs",         icon: "⇌", desc: "Statistical arbitrage signals" },
  { label: "Sectors",            path: "/sectors",       icon: "▦", desc: "Sector heatmap & breadth" },
  { label: "News Feed",          path: "/news",          icon: "◇", desc: "Live market news with sentiment" },
];

const QUICK_SYMBOLS = [
  "RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","SBIN","NTPC","ONGC",
  "BAJFINANCE","BHARTIARTL","POWERGRID","COALINDIA","HAL","TATAMOTORS","WIPRO",
];

export default function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<{ type: "page" | "symbol"; label: string; path: string; desc?: string; icon?: string }[]>([]);
  const [selected, setSelected] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  useEffect(() => {
    if (open) {
      setQuery("");
      setSelected(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  useEffect(() => {
    if (!query) {
      setResults([
        ...PAGES.map(p => ({ type: "page" as const, ...p })),
        ...QUICK_SYMBOLS.slice(0, 5).map(s => ({ type: "symbol" as const, label: s, path: `/stock/${s}`, desc: "NSE", icon: "◐" })),
      ]);
      return;
    }
    const q = query.toUpperCase();
    const pageMatches = PAGES.filter(p => p.label.toUpperCase().includes(q) || p.desc.toUpperCase().includes(q))
      .map(p => ({ type: "page" as const, ...p }));
    const symMatches = QUICK_SYMBOLS.filter(s => s.includes(q))
      .map(s => ({ type: "symbol" as const, label: s, path: `/stock/${s}`, desc: "NSE Equity", icon: "◐" }));
    // Add direct symbol entry
    if (q.length >= 2 && !symMatches.find(s => s.label === q)) {
      symMatches.unshift({ type: "symbol", label: q, path: `/stock/${q}`, desc: "Open stock page", icon: "→" });
    }
    setResults([...pageMatches, ...symMatches].slice(0, 8));
    setSelected(0);
  }, [query]);

  const navigate = useCallback((path: string) => {
    router.push(path);
    onClose();
  }, [router, onClose]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") { onClose(); }
      if (e.key === "ArrowDown") { e.preventDefault(); setSelected(s => Math.min(s + 1, results.length - 1)); }
      if (e.key === "ArrowUp")   { e.preventDefault(); setSelected(s => Math.max(s - 1, 0)); }
      if (e.key === "Enter" && results[selected]) { navigate(results[selected].path); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, results, selected, navigate, onClose]);

  if (!open) return null;

  return (
    <div className="cmd-backdrop" style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", zIndex: 9998,
      display: "flex", alignItems: "flex-start", justifyContent: "center", paddingTop: 80,
    }} onClick={onClose}>
      <div style={{
        width: 560, background: "#0d0d0d", border: "1px solid #2a2a2a",
        borderRadius: 6, overflow: "hidden", boxShadow: "0 24px 64px rgba(0,0,0,0.9)",
      }} onClick={e => e.stopPropagation()}>
        {/* Search input */}
        <div style={{ display: "flex", alignItems: "center", padding: "0 16px", borderBottom: "1px solid #1a1a1a" }}>
          <span style={{ fontSize: 14, color: "#333", marginRight: 10 }}>⌘</span>
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search symbols, screens, pages…"
            style={{
              flex: 1, background: "none", border: "none", outline: "none",
              padding: "14px 0", fontSize: 14, color: "#e5e5e5",
              fontFamily: "var(--font-geist-mono), monospace",
            }}
          />
          <span style={{ fontSize: 10, color: "#333", fontFamily: "monospace" }}>ESC</span>
        </div>

        {/* Results */}
        <div style={{ maxHeight: 360, overflow: "auto" }}>
          {results.length === 0 && (
            <div style={{ padding: "20px 16px", color: "#444", fontSize: 12 }}>No results</div>
          )}
          {results.map((r, i) => (
            <div
              key={r.path + i}
              onClick={() => navigate(r.path)}
              style={{
                display: "flex", alignItems: "center", gap: 12,
                padding: "10px 16px", cursor: "pointer",
                background: i === selected ? "#141414" : "transparent",
                borderBottom: "1px solid #111",
              }}
              onMouseEnter={() => setSelected(i)}
            >
              <span style={{ fontSize: 13, color: r.type === "page" ? "#3b82f6" : "#555", width: 16, textAlign: "center" }}>
                {r.icon}
              </span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: i === selected ? "#fff" : "#d4d4d4", fontFamily: "monospace" }}>
                  {r.label}
                </div>
                {r.desc && <div style={{ fontSize: 10, color: "#444" }}>{r.desc}</div>}
              </div>
              <span style={{ fontSize: 10, color: "#2a2a2a" }}>↵</span>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div style={{ padding: "8px 16px", borderTop: "1px solid #111", display: "flex", gap: 16, color: "#333", fontSize: 10 }}>
          <span>↑↓ navigate</span><span>↵ open</span><span>esc close</span>
        </div>
      </div>
    </div>
  );
}
