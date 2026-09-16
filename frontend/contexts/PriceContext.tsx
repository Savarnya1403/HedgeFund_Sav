'use client';

import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from "react";

const BASE = "/api/backend";

export interface PriceTick {
  price: number;
  change: number;
  change_pct: number;
  volume?: number;
  prev_close?: number;
  symbol: string;
  // Flash direction from prev update
  flash?: "up" | "down" | null;
}

interface PriceContextValue {
  prices: Map<string, PriceTick>;
  lastUpdate: number;
  connected: boolean;
  subscribe: (symbols: string[]) => void;
}

const PriceContext = createContext<PriceContextValue>({
  prices: new Map(),
  lastUpdate: 0,
  connected: false,
  subscribe: () => {},
});

export function PriceProvider({ children }: { children: React.ReactNode }) {
  const [prices, setPrices] = useState<Map<string, PriceTick>>(new Map());
  const [lastUpdate, setLastUpdate] = useState(0);
  const [connected, setConnected] = useState(false);
  const subscribedRef = useRef<Set<string>>(new Set());
  const esRef = useRef<EventSource | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
    }
    const syms = Array.from(subscribedRef.current).join(",");
    const url = `${BASE}/api/stream/prices${syms ? `?symbols=${encodeURIComponent(syms)}` : ""}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => setConnected(true);

    es.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data) as { type: string; data?: Record<string, PriceTick>; ts?: number };
        if (msg.type === "prices" && msg.data) {
          setPrices(prev => {
            const next = new Map(prev);
            for (const [sym, tick] of Object.entries(msg.data!)) {
              const prev_tick = prev.get(sym);
              const flash: "up" | "down" | null =
                prev_tick ? (tick.price > prev_tick.price ? "up" : tick.price < prev_tick.price ? "down" : null) : null;
              next.set(sym, { ...tick, symbol: sym, flash });
            }
            return next;
          });
          setLastUpdate(msg.ts ?? Date.now() / 1000);
        }
      } catch {}
    };

    es.onerror = () => {
      setConnected(false);
      es.close();
      esRef.current = null;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      reconnectTimer.current = setTimeout(connect, 4000);
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      esRef.current?.close();
    };
  }, [connect]);

  const subscribe = useCallback((symbols: string[]) => {
    const added = symbols.filter(s => !subscribedRef.current.has(s));
    if (added.length === 0) return;
    added.forEach(s => subscribedRef.current.add(s));
    // Reconnect with updated symbol list
    connect();
  }, [connect]);

  return (
    <PriceContext.Provider value={{ prices, lastUpdate, connected, subscribe }}>
      {children}
    </PriceContext.Provider>
  );
}

export function usePrice(symbol: string): PriceTick | null {
  const { prices, subscribe } = useContext(PriceContext);
  useEffect(() => {
    if (symbol) subscribe([symbol]);
  }, [symbol, subscribe]);
  return prices.get(symbol) ?? null;
}

export function usePrices(symbols: string[]): Map<string, PriceTick> {
  const { prices, subscribe } = useContext(PriceContext);
  const key = symbols.join(",");
  useEffect(() => {
    if (symbols.length > 0) subscribe(symbols);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, subscribe]);
  return prices;
}

export function usePriceContext() {
  return useContext(PriceContext);
}
