'use client';

import { useEffect, useRef } from "react";
import { useToast } from "@/components/Toast";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

interface NewsItem {
  title: string;
  url?: string;
  sentiment?: string;
  tags?: string[];
  source?: string;
}

export default function NewsSSEMonitor() {
  const { push } = useToast();
  const esRef = useRef<EventSource | null>(null);
  const seenRef = useRef<Set<string>>(new Set());
  const isFirstBatch = useRef(true);

  useEffect(() => {
    const connect = () => {
      const es = new EventSource(`${BASE}/api/stream/news`);
      esRef.current = es;

      es.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data) as { type: string; data?: NewsItem | NewsItem[] };
          if (msg.type === "news_batch" && Array.isArray(msg.data)) {
            // On first load — seed seen set, no toasts
            if (isFirstBatch.current) {
              for (const item of msg.data as NewsItem[]) {
                seenRef.current.add(item.url || item.title);
              }
              isFirstBatch.current = false;
            }
          } else if (msg.type === "news_item" && msg.data && !Array.isArray(msg.data)) {
            const item = msg.data as NewsItem;
            const key = item.url || item.title;
            if (!seenRef.current.has(key)) {
              seenRef.current.add(key);
              const type = item.sentiment === "positive" ? "gain"
                         : item.sentiment === "negative" ? "loss"
                         : "news";
              push({
                type,
                title: item.source ? `${item.source} · ${(item.tags?.[0] || "news").toUpperCase()}` : "MARKET NEWS",
                body: item.title,
              });
            }
          }
        } catch {}
      };

      es.onerror = () => {
        es.close();
        esRef.current = null;
        setTimeout(connect, 8000);
      };
    };

    connect();
    return () => esRef.current?.close();
  }, [push]);

  return null;
}
