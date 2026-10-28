"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/wiki", label: "Browse" },
  { href: "/wiki/search", label: "Search" },
  { href: "/wiki/graph", label: "Graph" },
  { href: "/wiki/timeline", label: "Timeline" },
  { href: "/chat", label: "Ask" },
  { href: "/upload", label: "Add sources" },
  { href: "/runs", label: "Runs" },
];

export function NavLinks() {
  const path = usePathname();
  const active = (href: string) =>
    href === "/wiki" ? path === "/wiki" || path.startsWith("/wiki/page") : path.startsWith(href);
  return (
    <nav className="nav" aria-label="Sections">
      {LINKS.map((l) => (
        <Link key={l.href} href={l.href} aria-current={active(l.href) ? "page" : undefined}>
          {l.label}
        </Link>
      ))}
    </nav>
  );
}
