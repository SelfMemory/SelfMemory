"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import type { ScopeTree as Scope } from "@/lib/api/types";
import { pageHref } from "@/lib/paths";

/** Scopes (org room, projects with sub-projects, personal) and their pages. */
export function ScopeTree({ scopes }: { scopes: Scope[] }) {
  const current = useSearchParams().get("path") ?? "";
  const byKey = new Map(scopes.map((s) => [s.key, s]));
  const roots = scopes.filter((s) => !s.parent || !byKey.has(s.parent));
  const order = { org: 0, project: 1, user: 2 } as const;
  roots.sort((a, b) => order[a.kind] - order[b.kind] || a.label.localeCompare(b.label));

  const render = (s: Scope) => {
    const open = current.startsWith(s.wiki + "/");
    const groups = groupByDir(s.files, s.wiki);
    return (
      <details key={s.key} open={open || scopes.length <= 3}>
        <summary>
          <span className={`dot ${s.kind}`} aria-hidden />
          {s.label}
          <span className="count">{s.files.length}</span>
        </summary>
        <ul>
          {groups.map(([dir, files]) => (
            <li key={dir || "."}>
              {dir && <div className="dir">{dir}/</div>}
              <ul style={dir ? undefined : { border: 0, margin: 0, padding: 0 }}>
                {files.map((f) => (
                  <li key={f}>
                    <Link href={pageHref(f)} aria-current={f === current ? "page" : undefined} title={f}>
                      {f.split("/").pop()!.replace(/\.md$/, "")}
                    </Link>
                  </li>
                ))}
              </ul>
            </li>
          ))}
          {s.children.map((c) => byKey.get(c)).filter(Boolean).map((c) => <li key={c!.key}>{render(c!)}</li>)}
        </ul>
      </details>
    );
  };

  if (!scopes.length) return <p style={{ padding: "0 10px", color: "var(--rail-muted)" }}>No wikis you can read yet.</p>;
  return <div className="tree">{roots.map(render)}</div>;
}

function groupByDir(files: string[], root: string): [string, string[]][] {
  const m = new Map<string, string[]>();
  for (const f of [...files].sort()) {
    const rel = f.slice(root.length + 1);
    const dir = rel.includes("/") ? rel.slice(0, rel.lastIndexOf("/")) : "";
    m.set(dir, [...(m.get(dir) ?? []), f]);
  }
  return [...m.entries()].sort(([a], [b]) => (a === "" ? -1 : b === "" ? 1 : a.localeCompare(b)));
}
