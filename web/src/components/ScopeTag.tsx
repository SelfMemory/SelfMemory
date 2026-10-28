import type { Scope } from "@/lib/api/types";

export function ScopeTag({ scope, fallback }: { scope?: Pick<Scope, "kind" | "label">; fallback?: string | null }) {
  if (!scope) return fallback ? <span className="scope-tag">{fallback}</span> : null;
  return (
    <span className="scope-tag">
      <span className={`dot ${scope.kind}`} aria-hidden />
      {scope.label}
    </span>
  );
}
