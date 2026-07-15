'use client';

import { useEffect, useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api, fmt, changeClass, changeSign, type UniverseEntry } from "@/lib/api";
import { usePrices } from "@/contexts/PriceContext";

type Category = "nifty50" | "psu" | "nifty100" | "search";

const CAT_SYMBOLS: Record<Exclude<Category, "search">, string[]> = {
  nifty50: [
    "RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","SBIN","BAJFINANCE","BHARTIARTL",
    "NTPC","POWERGRID","ONGC","COALINDIA","TATAMOTORS","HCLTECH","WIPRO","ITC","LT",
    "AXISBANK","TITAN","SUNPHARMA","HINDUNILVR","KOTAKBANK","ASIANPAINT","MARUTI","ULTRACEMCO",
  ],
  psu: [
    "NTPC","ONGC","COALINDIA","POWERGRID","BPCL","BHEL","SAIL","GAIL","IOC","HPCL",
    "NMDC","NALCO","RECLTD","PFC","BEL","BEML","CONCOR","IRCTC","RAILTEL","IRFC",
    "NHPC","SJVN","RVNL","NBCC","HAL","PNB","CANBK","BANKBARODA","OIL","GRSE","HAL",
  ],
  nifty100: [
    "DMART","SIEMENS","HAVELLS","DABUR","MARICO","COLPAL","GODREJCP","BERGEPAINT",
    "BOSCHLTD","MUTHOOTFIN","CHOLAFIN","DLF","ZOMATO","TVSMOTOR","VEDL","SAIL","OFSS",
    "BANKBARODA","GAIL","IOC","HPCL","PFC","RECLTD","NHPC","IRCTC","AMBUJACEM",
    "NAUKRI","ZYDUSLIFE","LUPIN","HAL","ADANIENT","ADANIPORTS",
  ],
};

interface DisplayStock {
  symbol: string;
  price: number;
  change_pct: number;
  change: number;
  volume?: number;
}

function PriceCell({ symbol, price, change_pct, change }: DisplayStock) {
  const prevPriceRef = useRef<number>(price);
  const [flashClass, setFlashClass] = useState("");

  useEffect(() => {
    if (price > 0 && price !== prevPriceRef.current) {
      const dir = price > prevPriceRef.current ? "price-flash-up" : "price-flash-down";
      setFlashClass(dir);
      const t = setTimeout(() => setFlashClass(""), 1000);
      prevPriceRef.current = price;
      return () => clearTimeout(t);
    }
  }, [price]);

  return (
    <div className={flashClass} style={{ textAlign: "right", borderRadius: 2, transition: "color 0.2s" }}>
      <div className="num" style={{ fontSize: 11, fontWeight: 700, color: "#d4d4d4" }}>
        {price > 0 ? `₹${fmt(price)}` : "—"}
      </div>
      <div className={`num ${changeClass(change_pct)}`} style={{ fontSize: 10 }}>
        {changeSign(change_pct)}{fmt(change_pct)}%
      </div>
    </div>
  );
}

export default function Watchlist({ activeSymbol }: { activeSymbol?: string }) {
  const router = useRouter();
  const [category, setCategory] = useState<Category>("nifty50");
  const [search, setSearch] = useState("");
  const [stocks, setStocks] = useState<DisplayStock[]>([]);
  const [loading, setLoading] = useState(true);
  const [universe, setUniverse] = useState<UniverseEntry[]>([]);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef(false);

  const symbols = category === "search" ? [] : CAT_SYMBOLS[category].slice(0, 30);
  const livePrices = usePrices(symbols);

  // Bootstrap with API, then SSE overlay
  const loadCategory = useCallback(async (cat: Exclude<Category, "search">) => {
    setLoading(true);
    abortRef.current = false;
    const syms = CAT_SYMBOLS[cat].slice(0, 20);
    const results: DisplayStock[] = [];
    // Batch fetch first 8 quickly
    const quickBatch = syms.slice(0, 8);
    for (const sym of quickBatch) {
      if (abortRef.current) break;
      try {
        const d = await api.quote(sym);
        if (d) results.push({ symbol: d.symbol, price: d.price, change_pct: d.change_pct, change: d.change, volume: d.volume });
        setStocks([...results]);
      } catch {}
    }
    setLoading(false);
    // Load rest in background
    for (const sym of syms.slice(8)) {
      if (abortRef.current) break;
      try {
        const d = await api.quote(sym);
        if (d) results.push({ symbol: d.symbol, price: d.price, change_pct: d.change_pct, change: d.change, volume: d.volume });
        setStocks([...results]);
      } catch {}
    }
  }, []);

  useEffect(() => {
    api.universe().then(setUniverse).catch(() => {});
  }, []);

  useEffect(() => {
    abortRef.current = true;
    setStocks([]);
    if (category !== "search") loadCategory(category);
  }, [category, loadCategory]);

  // Merge live prices from SSE
  const displayList: DisplayStock[] = stocks.map(s => {
    const live = livePrices.get(s.symbol);
    if (live && live.price > 0) return { ...s, price: live.price, change_pct: live.change_pct, change: live.change };
    return s;
  });

  const handleSearch = (q: string) => {
    setSearch(q);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!q.trim()) {
      if (category === "search") setCategory("nifty50");
      return;
    }
    setCategory("search");
    const qUp = q.toUpperCase();
    const local = universe.filter(e => e.symbol.includes(qUp) || e.company_name.toUpperCase().includes(qUp)).slice(0, 10);
    setStocks(local.map(e => ({ symbol: e.symbol, price: 0, change_pct: 0, change: 0 })));
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await api.search(q);
        setStocks((res || []).map(r => ({ symbol: r.symbol, price: r.price, change_pct: r.change_pct, change: r.change, volume: r.volume })));
      } catch {}
    }, 350);
  };

  const cats: { key: Category; label: string }[] = [
    { key: "nifty50",  label: "N50"  },
    { key: "psu",      label: "PSU"  },
    { key: "nifty100", label: "N100" },
  ];

  return (
    <div style={{
      width: 195, background: "#050505", borderRight: "1px solid #141414",
      display: "flex", flexDirection: "column", flexShrink: 0, overflow: "hidden", height: "100%",
    }}>
      {/* Tabs */}
      <div style={{ display: "flex", borderBottom: "1px solid #141414" }}>
        {cats.map(c => (
          <button key={c.key} onClick={() => { setSearch(""); setCategory(c.key); }}
            style={{
              flex: 1, padding: "6px 0", background: "none", border: "none", cursor: "pointer",
              fontSize: 9, fontWeight: 700, letterSpacing: "0.06em",
              color: category === c.key ? "#e5e5e5" : "#333",
              borderBottom: category === c.key ? "2px solid #3b82f6" : "2px solid transparent",
            }}
          >{c.label}</button>
        ))}
      </div>

      {/* Search */}
      <div style={{ padding: "6px 8px", borderBottom: "1px solid #141414" }}>
        <input
          value={search}
          onChange={e => handleSearch(e.target.value)}
          placeholder="Symbol or name…"
          style={{
            width: "100%", background: "#0d0d0d", border: "1px solid #1a1a1a",
            borderRadius: 3, padding: "4px 8px", fontSize: 10, color: "#ccc", outline: "none",
            boxSizing: "border-box",
          }}
        />
      </div>

      {/* List */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {loading && displayList.length === 0 ? (
          <div style={{ padding: "8px 6px" }}>
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="skeleton" style={{ height: 34, marginBottom: 3 }} />
            ))}
          </div>
        ) : (
          displayList.map(s => (
            <div key={s.symbol} onClick={() => router.push(`/stock/${s.symbol}`)}
              style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "5px 8px", cursor: "pointer", borderBottom: "1px solid #0d0d0d",
                background: activeSymbol === s.symbol ? "#0f1520" : "transparent",
              }}
              onMouseEnter={e => { if (activeSymbol !== s.symbol) e.currentTarget.style.background = "#0d0d0d"; }}
              onMouseLeave={e => { if (activeSymbol !== s.symbol) e.currentTarget.style.background = "transparent"; }}
            >
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: activeSymbol === s.symbol ? "#3b82f6" : "#c8c8c8" }}>
                  {s.symbol}
                </div>
                {s.volume != null && s.volume > 0 && (
                  <div className="num" style={{ fontSize: 9, color: "#2a2a2a" }}>
                    {(s.volume / 1e6).toFixed(1)}M
                  </div>
                )}
              </div>
              <PriceCell {...s} />
            </div>
          ))
        )}
      </div>

      {/* Footer */}
      <div style={{
        padding: "4px 8px", borderTop: "1px solid #141414",
        fontSize: 9, color: "#222", display: "flex", justifyContent: "space-between",
      }}>
        <span>⌘K search</span>
        <span>{displayList.length} symbols</span>
      </div>
    </div>
  );
}
