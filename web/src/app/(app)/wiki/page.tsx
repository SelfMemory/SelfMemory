import Link from "next/link";
import { ScopeTag } from "@/components/ScopeTag";
import { guard, serverApi } from "@/lib/api/server";
import { pageHref } from "@/lib/paths";
import { kindLabel, when } from "@/lib/scopes";

export const metadata = { title: "Browse" };

export default async function WikiHome() {
  const api = await serverApi();
  const [{ scopes }, { frames }] = await Promise.all([guard(api.tree()), guard(api.timeline(undefined, 40))]);
  const byKey = new Map(scopes.map((s) => [s.key, s]));
  const recent = [...frames].reverse().slice(0, 12);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Your wikis</h1>
          <p>Every page here was written by the agent from sources you added. Pick a scope on the left, or start below.</p>
        </div>
        <div className="row">
          <Link className="btn ghost" href="/upload">Add sources</Link>
          <Link className="btn" href="/chat">Ask a question</Link>
        </div>
      </div>

      <div className="split">
        <ul className="list">
          {scopes.map((s) => {
            const index = s.files.find((f) => f === `${s.wiki}/index.md`) ?? s.files[0];
            return (
              <li key={s.key}>
                <span className={`dot ${s.kind}`} aria-hidden />
                <div className="grow">
                  <div className="title">
                    {index ? <Link href={pageHref(index)}>{s.label}</Link> : s.label}
                  </div>
                  <div className="muted" style={{ fontSize: 13 }}>
                    {kindLabel[s.kind]} · {s.files.length} page{s.files.length === 1 ? "" : "s"}
                    {s.writable ? "" : " · read only"}
                  </div>
                </div>
                <Link href={`/wiki/graph?scope=${encodeURIComponent(s.key)}`}>Graph</Link>
              </li>
            );
          })}
        </ul>

        <section className="aside">
          <h3>Recent changes</h3>
          {recent.length === 0 ? (
            <p className="muted">Nothing yet. Add sources and the agent will write the first pages.</p>
          ) : (
            <ol className="history">
              {recent.map((f) => (
                <li key={`${f.scope}:${f.id}`}>
                  <div>{f.message.split("\n")[0]}</div>
                  <div className="row" style={{ gap: 8 }}>
                    <ScopeTag scope={byKey.get(f.scope)} fallback={f.scope} />
                    <span className="sha">{f.sha}</span>
                    <span className="muted">{when(f.date)}</span>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </>
  );
}
