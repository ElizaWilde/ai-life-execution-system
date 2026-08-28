"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAppSettings } from "../../lib/settings";
import WitchHatIcon from "../common/WitchHatIcon";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: "grid" },
  { href: "/today", label: "Today", icon: "calendar" },
  { href: "/weekly-plan", label: "Plans", icon: "list" },
  { href: "/review", label: "Review", icon: "chart" },
  { href: "/settings", label: "Settings", icon: "gear" },
];

function NavIcon({ name }: { name: string }) {
  const shapes: Record<string, React.ReactNode> = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></>,
    list: <><path d="M9 6h12M9 12h12M9 18h12"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/></>,
    chart: <path d="M4 19V9M10 19V5M16 19v-7M22 19H2"/>,
    note: <><path d="M5 3h14v18H5zM8 8h8M8 12h8M8 16h5"/></>,
    gear: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H3v-4h.2a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/></>,
  };
  return <svg aria-hidden="true" fill="none" height="20" viewBox="0 0 24 24" width="20">{shapes[name]}</svg>;
}

export default function Sidebar({ compact = false, onNavigate }: { compact?: boolean; onNavigate?: () => void }) {
  const pathname = usePathname();
  const settings = useAppSettings();
  const initials = settings.name.split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase() || "AL";
  return <aside aria-label="Primary navigation" className={compact ? "sidebar is-compact" : "sidebar"} id="app-sidebar">
    <Link href="/dashboard" className="brand-lockup"><WitchHatIcon className="brand-witch-hat" size={40} /><span><strong>AI Life</strong><small>Execution System</small></span></Link>
    <nav>{navItems.map((item) => <Link aria-label={item.label} key={item.href} href={item.href} onClick={onNavigate} title={compact ? item.label : undefined} className={`nav-link ${pathname === item.href ? "active" : ""}`}><NavIcon name={item.icon} /><span>{item.label}</span></Link>)}</nav>
    <Link aria-label="Open profile settings" className="sidebar-user" href="/settings#profile" onClick={onNavigate}>
      <span
        aria-hidden="true"
        className={`user-avatar ${settings.avatarDataUrl ? "has-image" : ""}`}
        style={settings.avatarDataUrl ? { backgroundImage: `url(${settings.avatarDataUrl})` } : undefined}
      >
        {settings.avatarDataUrl ? "" : initials}
      </span>
      <div><strong>{settings.name}</strong><small>{settings.email}</small></div><b aria-hidden="true">›</b>
    </Link>
  </aside>;
}
