import Link from "next/link";
import { ScopeTag } from "@/components/ScopeTag";
import { guard, serverApi } from "@/lib/api/server";
import { pageHref } from "@/lib/paths";

export const metadata = { title: "Search" };

function highlight(text: string, q: string) {
  const terms = q.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? [];
  if (!terms.length) return text;
  const re = new RegExp(`(${terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
  return text.split(re).map((part, i) => (i % 2 ? <mark key={i}>{part}</mark> : part));
}

export default async function Search({ searchParams }: { searchParams: Promise<{ q?: string; scope?: string }> }) {
  const { q = "", scope = "" } = await searchParams;
  const api = await serverApi();
  const [{ scopes }, found] = await Promise.all([
    guard(api.tree()),
    q.trim() ? guard(api.search(q, scope || undefined)) : Promise.resolve(null),
  ]);
  const byKey = new Map(scopes.map((s) => [s.key, s]));

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Search</h1>
          <p>Matches page titles, descriptions and text across every wiki you can read.</p>
        </div>
      </div>
      <form className="row" style={{ marginBottom: 20 }} role="search">
        <input className="input" name="q" defaultValue={q} placeholder="What are you looking for?" style={{ flex: 1, minWidth: 220 }} autoFocus />
        <select className="select" name="scope" defaultValue={scope} aria-label="Scope">
          <option value="">All scopes</option>
          {scopes.map((s) => (
            <option key={s.key} value={s.key}>{s.label}</option>
          ))}
        </select>
        <button className="btn">Search</button>
      </form>
      {found &&
        (found.results.length === 0 ? (
          <div className="empty">No pages match “{q}”. Try fewer words, or ask the agent instead.</div>
        ) : (
          <ul className="list">
            {found.results.map((r) => (
              <li key={r.path} style={{ display: "block" }}>
                <div className="row" style={{ justifyContent: "space-between", gap: 8 }}>
                  <Link className="title" href={pageHref(r.path)}>{highlight(r.title, q)}</Link>
                  <ScopeTag scope={byKey.get(r.scope)} fallback={r.scope} />
                </div>
                {r.description && <div className="muted">{highlight(r.description, q)}</div>}
                <div style={{ fontFamily: "var(--font-read)", fontSize: 15, marginTop: 4 }}>{highlight(r.snippet, q)}</div>
              </li>
            ))}
          </ul>
        ))}
    </>
  );
}
