'use client';

import { useEffect, useState } from "react";
import { PriceProvider } from "@/contexts/PriceContext";
import { ToastProvider } from "@/components/Toast";
import CommandPalette from "@/components/CommandPalette";
import NewsSSEMonitor from "@/components/NewsSSEMonitor";

export default function RootClientShell({ children }: { children: React.ReactNode }) {
  const [cmdOpen, setCmdOpen] = useState(false);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCmdOpen(o => !o);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <PriceProvider>
      <ToastProvider>
        <NewsSSEMonitor />
        {children}
        <CommandPalette open={cmdOpen} onClose={() => setCmdOpen(false)} />
      </ToastProvider>
    </PriceProvider>
  );
}
