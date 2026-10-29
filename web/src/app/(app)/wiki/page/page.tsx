import Link from "next/link";
import { Markdown } from "@/components/Markdown";
import { ScopeTag } from "@/components/ScopeTag";
import { ApiError } from "@/lib/api/client";
import { guard, serverApi } from "@/lib/api/server";
import type { FileRead, TimelineFrame } from "@/lib/api/types";
import { scopeOf, when } from "@/lib/scopes";

export const metadata = { title: "Page" };

export default async function WikiPage({ searchParams }: { searchParams: Promise<{ path?: string }> }) {
  const { path = "" } = await searchParams;
  const api = await serverApi();
  const { scopes } = await guard(api.tree());
  const scope = scopeOf(scopes, path);

  let file: FileRead | null = null;
  let error: string | null = null;
  try {
    file = await guard(api.file(path));
  } catch (e) {
    error = e instanceof ApiError ? (e.status === 404 ? "This page does not exist (yet)." : e.message) : String(e);
  }
  const frames: TimelineFrame[] = scope ? (await guard(api.timeline(scope.key, 200))).frames : [];
  // The backend has no per-file log yet; show the scope's commits and mark
  // the one where this page first appeared.
  const born = frames.find((f) => f.nodes.includes(path))?.id;
  const history = [...frames].reverse().slice(0, 30);
  const crumbs = scope ? path.slice(scope.wiki.length + 1).split("/") : path.split("/");

  return (
    <>
      <div className="crumbs">
        <ScopeTag scope={scope} /> {crumbs.length > 1 && <> / {crumbs.slice(0, -1).join(" / ")}</>}
      </div>
      <div className="split">
        <article className="sheet">
          {error && <p className="error">{error}</p>}
          {file?.binary && <p className="muted">Binary file, {file.size} bytes.</p>}
          {file?.content !== undefined && <Markdown source={file.content} path={path} />}
        </article>
        <aside className="aside">
          <div className="row" style={{ marginBottom: 16 }}>
            {scope && (
              <Link className="btn ghost" href={`/wiki/graph?scope=${encodeURIComponent(scope.key)}&focus=${encodeURIComponent(path)}`}>
                Show in graph
              </Link>
            )}
            <Link className="btn ghost" href={`/chat?scope=${encodeURIComponent(scope?.key ?? "")}`}>Ask about this</Link>
          </div>
          <h3>Scope history</h3>
          {history.length === 0 ? (
            <p className="muted">No commits yet.</p>
          ) : (
            <ol className="history">
              {history.map((f) => (
                <li key={f.id} className={f.id === born ? "here" : undefined}>
                  <div>{f.message.split("\n")[0]}</div>
                  <div>
                    <span className="sha">{f.sha}</span> <span className="muted">{when(f.date)}</span>
                    {f.id === born && <strong> · page added</strong>}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </aside>
      </div>
    </>
  );
}
