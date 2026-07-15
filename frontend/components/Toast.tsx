'use client';

import React, { createContext, useContext, useState, useCallback, useEffect } from "react";

export type ToastType = "news" | "gain" | "loss" | "info" | "warn";

export interface ToastItem {
  id: string;
  type: ToastType;
  title: string;
  body?: string;
  exiting?: boolean;
}

interface ToastCtx {
  push: (t: Omit<ToastItem, "id" | "exiting">) => void;
}

const Ctx = createContext<ToastCtx>({ push: () => {} });

export function useToast() {
  return useContext(Ctx);
}

function ToastEl({ toast, onRemove }: { toast: ToastItem; onRemove: (id: string) => void }) {
  useEffect(() => {
    const t = setTimeout(() => onRemove(toast.id), 5500);
    return () => clearTimeout(t);
  }, [toast.id, onRemove]);

  const colors: Record<ToastType, { border: string; icon: string; label: string }> = {
    news:  { border: "#3b82f6", icon: "◈", label: "#3b82f6" },
    gain:  { border: "#00d084", icon: "▲", label: "#00d084" },
    loss:  { border: "#ff3b3b", icon: "▼", label: "#ff3b3b" },
    info:  { border: "#555",    icon: "●", label: "#888" },
    warn:  { border: "#f59e0b", icon: "◆", label: "#f59e0b" },
  };
  const c = colors[toast.type];

  return (
    <div
      className={toast.exiting ? "toast-exit" : "toast-enter"}
      style={{
        width: 300, background: "#0d0d0d", border: `1px solid ${c.border}33`,
        borderLeft: `3px solid ${c.border}`, borderRadius: 4,
        padding: "10px 12px", marginBottom: 6, cursor: "pointer",
        boxShadow: `0 4px 20px rgba(0,0,0,0.6), 0 0 0 1px #1a1a1a`,
      }}
      onClick={() => onRemove(toast.id)}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
        <span style={{ fontSize: 10, color: c.label }}>{c.icon}</span>
        <span style={{ fontSize: 11, fontWeight: 700, color: "#e5e5e5" }}>{toast.title}</span>
      </div>
      {toast.body && (
        <div style={{ fontSize: 10, color: "#666", lineHeight: 1.4, marginTop: 2 }}>
          {toast.body.slice(0, 120)}{toast.body.length > 120 ? "…" : ""}
        </div>
      )}
    </div>
  );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const push = useCallback((t: Omit<ToastItem, "id" | "exiting">) => {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts(prev => [{ ...t, id }, ...prev].slice(0, 6));
  }, []);

  const remove = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  return (
    <Ctx.Provider value={{ push }}>
      {children}
      <div style={{
        position: "fixed", bottom: 32, right: 16, zIndex: 9999,
        display: "flex", flexDirection: "column-reverse",
        pointerEvents: "none",
      }}>
        {toasts.map(t => (
          <div key={t.id} style={{ pointerEvents: "auto" }}>
            <ToastEl toast={t} onRemove={remove} />
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
