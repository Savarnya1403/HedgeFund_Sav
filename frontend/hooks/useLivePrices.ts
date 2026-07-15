'use client';

import { useEffect, useRef, useState, useCallback } from "react";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8001/ws/live";

interface PriceUpdate {
  price: number;
  change: number;
  change_pct: number;
}

export function useLivePrices(symbols: string[]) {
  const [prices, setPrices] = useState<Map<string, PriceUpdate>>(new Map());
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const symbolsKey = symbols.join(",");

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(JSON.stringify({ action: "subscribe", symbols }));
      };

      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data as string);
          if (msg.type === "prices" && msg.data) {
            setPrices(prev => {
              const next = new Map(prev);
              for (const [sym, info] of Object.entries(msg.data as Record<string, PriceUpdate>)) {
                next.set(sym, info);
              }
              return next;
            });
          }
        } catch {}
      };

      ws.onclose = () => {
        wsRef.current = null;
        // Reconnect after 3s
        reconnectRef.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {}
  }, [symbolsKey]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    connect();
    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // prevent reconnect on intentional close
        wsRef.current.close();
      }
    };
  }, [connect]);

  // Re-subscribe when symbols change
  useEffect(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN && symbols.length > 0) {
      wsRef.current.send(JSON.stringify({ action: "subscribe", symbols }));
    }
  }, [symbolsKey]); // eslint-disable-line react-hooks/exhaustive-deps

  return prices;
}
