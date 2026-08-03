"use client";

import { useEffect, useState } from "react";
import Sidebar from "./Sidebar";

const NARROW_SCREEN_QUERY = "(max-width: 900px)";

function SidebarToggleIcon({ open }: { open: boolean }) {
  return (
    <svg aria-hidden="true" fill="none" height="18" viewBox="0 0 24 24" width="18">
      <rect height="18" rx="3" width="18" x="3" y="3" />
      <path d="M9 3v18M13 8l4 4-4 4" className={open ? "sidebar-toggle-chevron open" : "sidebar-toggle-chevron"} />
    </svg>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isNarrowScreen, setIsNarrowScreen] = useState(false);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const mediaQuery = window.matchMedia(NARROW_SCREEN_QUERY);
    const syncToScreenWidth = (event: MediaQueryList | MediaQueryListEvent) => {
      setIsNarrowScreen(event.matches);
      setSidebarOpen(!event.matches);
    };

    syncToScreenWidth(mediaQuery);
    setIsReady(true);
    mediaQuery.addEventListener("change", syncToScreenWidth);
    return () => mediaQuery.removeEventListener("change", syncToScreenWidth);
  }, []);

  const toggleLabel = sidebarOpen ? "Collapse sidebar" : "Expand sidebar";

  return (
    <div
      className={`app-shell ${isReady ? "sidebar-ready" : ""} ${sidebarOpen ? "sidebar-is-open" : "sidebar-is-closed"}`}
    >
      <button
        aria-controls="app-sidebar"
        aria-expanded={sidebarOpen}
        aria-label={toggleLabel}
        className="sidebar-toggle"
        data-tooltip={toggleLabel}
        onClick={() => setSidebarOpen((open) => !open)}
        type="button"
      >
        <SidebarToggleIcon open={sidebarOpen} />
      </button>
      <Sidebar compact={!sidebarOpen} onNavigate={isNarrowScreen ? () => setSidebarOpen(false) : undefined} />
      {isNarrowScreen && sidebarOpen ? (
        <button aria-label="Close sidebar" className="sidebar-backdrop" onClick={() => setSidebarOpen(false)} type="button" />
      ) : null}
      <main className="main-content">{children}</main>
    </div>
  );
}
