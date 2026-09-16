'use client';

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { api, fmt, changeClass, changeSign, type IndexData, type MacroTicker } from "@/lib/api";
import { usePriceContext } from "@/contexts/PriceContext";

const MACRO_FORMATS: Record<string, (v: number) => string> = {
  "India VIX": v => v.toFixed(2),
  "USD/INR":   v => "₹" + v.toFixed(2),
  "Crude Oil": v => "$" + v.toFixed(1),
  "Gold":      v => "$" + Math.round(v).toLocaleString(),
  "US 10Y":    v => v.toFixed(3) + "%",
  "S&P 500":   v => v.toLocaleString("en-US", { maximumFractionDigits: 0 }),
};

const NAV_ITEMS = [
  { label: "TERMINAL",   path: "/" },
  { label: "HOME",       path: "/home" },
  { label: "DASH",       path: "/dashboard" },
  { label: "SCREENER",   path: "/screener" },
  { label: "ADV SCR",    path: "/screener/advanced" },
  { label: "OPTIONS",    path: "/options" },
  { label: "STRATEGY",   path: "/strategy" },
  { label: "VOL SURF",   path: "/vol-surface" },
  { label: "ORDER FLOW", path: "/orderflow" },
  { label: "BACKTEST",   path: "/backtest" },
  { label: "OPTIMIZE",   path: "/optimizer" },
  { label: "RISK",       path: "/risk" },
  { label: "RISK SCAN",  path: "/risk-scan" },
  { label: "DEEP FA",    path: "/fundamental" },
  { label: "ALT DATA",   path: "/alternative" },
  { label: "TIMESFM",    path: "/timesfm" },
  { label: "CALENDAR",   path: "/calendar" },
  { label: "MACRO",      path: "/macro" },
  { label: "INSTIT",     path: "/institutional" },
  { label: "QUANT",      path: "/quant" },
  { label: "SIGNALS",    path: "/recommend" },
  { label: "COMPARE",    path: "/compare" },
  { label: "GLOBE",      path: "/globe" },
  { label: "VOLUME",     path: "/volume" },
  { label: "PATTERNS",   path: "/patterns" },
  { label: "PAIRS",      path: "/pairs" },
  { label: "SECTORS",    path: "/sectors" },
  { label: "NEWS",       path: "/news" },
];

export default function IndexBar() {
  const router = useRouter();
  const { connected, lastUpdate } = usePriceContext();
  const [indices, setIndices] = useState<IndexData[]>([]);
  const [macro, setMacro] = useState<MacroTicker[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [time, setTime] = useState("");
  const [activePath, setActivePath] = useState("/");
  const navRef = useRef<HTMLDivElement>(null);

  const scrollNav = (dir: "left" | "right") => {
    if (navRef.current) {
      navRef.current.scrollBy({ left: dir === "right" ? 160 : -160, behavior: "smooth" });
    }
  };

  useEffect(() => {
    setActivePath(window.location.pathname);
  }, []);

  useEffect(() => {
    const load = () => {
      api.indices().then(setIndices).catch(() => {});
      api.macro().then(r => setMacro(r.data || [])).catch(() => {});
      api.marketStatus().then(s => setIsOpen(s.is_open)).catch(() => {});
    };
    load();
    const tick = setInterval(() => {
      const now = new Date();
      const ist = new Date(now.getTime() + 5.5 * 3600000);
      setTime(ist.toISOString().slice(11, 19));
    }, 1000);
    const refresh = setInterval(load, 120000);
    return () => { clearInterval(tick); clearInterval(refresh); };
  }, []);

  const macroTickers = macro.filter(m => !["Nifty 50", "Bank Nifty"].includes(m.label));

  return (
    <div style={{
      background: "#050505",
      borderBottom: "1px solid #141414",
      display: "flex", alignItems: "center",
      height: 36, flexShrink: 0, overflow: "hidden",
      userSelect: "none",
    }}>
      {/* Logo */}
      <div style={{
        display: "flex", alignItems: "center", gap: 0,
        padding: "0 12px", borderRight: "1px solid #141414", height: "100%", flexShrink: 0,
      }}>
        <span style={{ fontSize: 12, fontWeight: 800, color: "#fff", letterSpacing: "-0.02em", fontFamily: "monospace" }}>IH</span>
        <span style={{ fontSize: 9, color: "#333", marginLeft: 4, letterSpacing: "0.12em" }}>TERMINAL</span>
      </div>

      {/* Cmd+K */}
      <button
        onClick={() => {
          const event = new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true });
          window.dispatchEvent(event);
        }}
        style={{
          display: "flex", alignItems: "center", gap: 6,
          padding: "0 10px", height: "100%", background: "none", border: "none",
          borderRight: "1px solid #141414", cursor: "pointer", flexShrink: 0,
        }}
        title="Command palette (⌘K)"
      >
        <span style={{ fontSize: 10, color: "#333" }}>⌘K</span>
        <span style={{ fontSize: 10, color: "#2a2a2a" }}>Search</span>
      </button>

      {/* Nav — horizontally scrollable */}
      <div style={{ display: "flex", alignItems: "center", flexShrink: 0, maxWidth: "55vw", borderRight: "1px solid #141414", height: "100%" }}>
        {/* Left arrow */}
        <button
          onClick={() => scrollNav("left")}
          style={{ padding: "0 5px", height: "100%", background: "none", border: "none", cursor: "pointer", color: "#333", fontSize: 10, flexShrink: 0 }}
          onMouseEnter={e => (e.currentTarget.style.color = "#888")}
          onMouseLeave={e => (e.currentTarget.style.color = "#333")}
          title="Scroll left"
        >◂</button>

        {/* Scrollable nav track */}
        <style>{`
          .ih-nav-scroll::-webkit-scrollbar { display: none; }
        `}</style>
        <div
          ref={navRef}
          className="ih-nav-scroll"
          style={{
            display: "flex", height: "100%", overflowX: "auto", overflowY: "hidden",
            scrollbarWidth: "none",
          }}
        >
          <div style={{ display: "flex", height: "100%" }}>
            {NAV_ITEMS.map(n => {
              const active = activePath === n.path;
              return (
                <button key={n.path} onClick={() => { setActivePath(n.path); router.push(n.path); }}
                  style={{
                    padding: "0 9px", height: "100%", background: "none", border: "none", cursor: "pointer",
                    fontSize: 9, fontWeight: 700, letterSpacing: "0.07em", whiteSpace: "nowrap", flexShrink: 0,
                    color: active ? "#e5e5e5" : "#333",
                    borderBottom: active ? "2px solid #3b82f6" : "2px solid transparent",
                  }}
                  onMouseEnter={e => { if (!active) e.currentTarget.style.color = "#777"; }}
                  onMouseLeave={e => { if (!active) e.currentTarget.style.color = "#333"; }}
                >{n.label}</button>
              );
            })}
          </div>
        </div>

        {/* Right arrow */}
        <button
          onClick={() => scrollNav("right")}
          style={{ padding: "0 5px", height: "100%", background: "none", border: "none", cursor: "pointer", color: "#333", fontSize: 10, flexShrink: 0 }}
          onMouseEnter={e => (e.currentTarget.style.color = "#888")}
          onMouseLeave={e => (e.currentTarget.style.color = "#333")}
          title="Scroll right"
        >▸</button>
      </div>

      {/* Indices ticker — scrollable */}
      <div style={{ flex: 1, display: "flex", alignItems: "center", overflow: "hidden", height: "100%" }}>
        <div style={{ display: "flex", alignItems: "center", height: "100%", overflowX: "auto", overflowY: "hidden" }}>
          {indices.map(idx => (
            <div key={idx.name} style={{
              display: "flex", alignItems: "center", gap: 5,
              padding: "0 10px", borderRight: "1px solid #141414",
              height: "100%", flexShrink: 0,
            }}>
              <span style={{ fontSize: 9, color: "#333", letterSpacing: "0.05em" }}>{idx.name.replace("NIFTY ", "NF ")}</span>
              <span className="num" style={{ fontSize: 11, fontWeight: 700, color: "#ccc" }}>{fmt(idx.value, 0)}</span>
              <span className={`num ${changeClass(idx.change_pct)}`} style={{ fontSize: 9 }}>
                {changeSign(idx.change_pct)}{fmt(idx.change_pct)}%
              </span>
            </div>
          ))}

          {/* Separator */}
          {macroTickers.length > 0 && (
            <div style={{ width: 1, height: 16, background: "#1e1e1e", margin: "0 4px", flexShrink: 0 }} />
          )}

          {macroTickers.map(m => {
            const fmtFn = MACRO_FORMATS[m.label];
            const val = fmtFn ? fmtFn(m.price) : m.price.toFixed(2);
            return (
              <div key={m.label} style={{
                display: "flex", alignItems: "center", gap: 5,
                padding: "0 8px", borderRight: "1px solid #141414",
                height: "100%", flexShrink: 0,
              }}>
                <span style={{ fontSize: 9, color: "#2a2a2a" }}>{m.label}</span>
                <span className="num" style={{ fontSize: 10, color: "#888" }}>{m.price > 0 ? val : "—"}</span>
                {m.price > 0 && (
                  <span className={`num ${changeClass(m.change_pct)}`} style={{ fontSize: 9 }}>
                    {changeSign(m.change_pct)}{Math.abs(m.change_pct).toFixed(1)}%
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Right: status + clock */}
      <div style={{
        display: "flex", alignItems: "center", gap: 10,
        padding: "0 12px", borderLeft: "1px solid #141414", flexShrink: 0, height: "100%",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <div className={`live-dot${isOpen ? "" : " closed"}`} />
          <span style={{ fontSize: 9, color: "#2a2a2a" }}>{isOpen ? "LIVE" : "CLOSED"}</span>
        </div>
        {connected && (
          <div style={{ display: "flex", alignItems: "center", gap: 3 }}>
            <div style={{ width: 4, height: 4, borderRadius: "50%", background: "#3b82f6" }} />
            <span style={{ fontSize: 8, color: "#2a2a2a" }}>SSE</span>
          </div>
        )}
        <span className="num" style={{ fontSize: 9, color: "#222" }}>{time} IST</span>
      </div>
    </div>
  );
}
