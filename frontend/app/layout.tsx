import "../styles/globals.css";
import Link from "next/link";
import type { ReactNode } from "react";

export const metadata = {
  title: "AI Life Execution",
  description: "Weekly planning, daily execution, study timer, and review loop.",
};

const navItems = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/weekly-plan", label: "Weekly Plan" },
  { href: "/today", label: "Today" },
  { href: "/timer", label: "Timer" },
  { href: "/review", label: "Review" },
  { href: "/login", label: "User" },
];

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="app-shell">
          <aside className="sidebar">
            <Link href="/" className="brand">
              AI Life
            </Link>
            <nav>
              {navItems.map((item) => (
                <Link key={item.href} href={item.href} className="nav-link">
                  {item.label}
                </Link>
              ))}
            </nav>
          </aside>
          <main className="main-content">{children}</main>
        </div>
      </body>
    </html>
  );
}
