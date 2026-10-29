import Link from "next/link";
import type { Scope } from "@/lib/api/types";

/** Segmented links that set ?scope= on the current screen. */
export function ScopeFilter({ base, scopes, current }: { base: string; scopes: Scope[]; current?: string }) {
  return (
    <nav className="seg" aria-label="Scope">
      <Link href={base} aria-current={!current ? "page" : undefined}>All</Link>
      {scopes.map((s) => (
        <Link key={s.key} href={`${base}?scope=${encodeURIComponent(s.key)}`} aria-current={current === s.key ? "page" : undefined}>
          {s.label}
        </Link>
      ))}
    </nav>
  );
}
