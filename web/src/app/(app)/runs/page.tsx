import Link from "next/link";
import { ScopeTag } from "@/components/ScopeTag";
import { guard, serverApi } from "@/lib/api/server";
import { when } from "@/lib/scopes";
import { StartRun } from "./StartRun";

export const metadata = { title: "Runs" };

export default async function RunsPage() {
  const api = await serverApi();
  const [{ scopes }, { jobs }] = await Promise.all([guard(api.tree()), guard(api.runs())]);
  const byKey = new Map(scopes.map((s) => [s.key, s]));

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Runs</h1>
          <p>Each run starts a fresh sandbox, lets the agent work on the wikis you can read, then shuts it down.</p>
        </div>
      </div>
      <div className="split">
        {jobs.length === 0 ? (
          <div className="empty">No runs yet. Start one, or add sources to trigger an ingest.</div>
        ) : (
          <ul className="list">
            {jobs.map((j) => (
              <li key={j.id}>
                <span className={`status ${j.status}`}>{j.status}</span>
                <div className="grow">
                  <Link className="title" href={`/runs/${j.id}`}>{j.display_text || j.command}</Link>
                  <div className="row" style={{ gap: 10, fontSize: 13 }}>
                    <span className="muted">{j.command}</span>
                    <ScopeTag scope={j.scope ? byKey.get(j.scope) : undefined} fallback={j.scope} />
                    <span className="muted">{when(j.created_at as string)}</span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
        <aside className="aside">
          <h3>Start a run</h3>
          <StartRun scopes={scopes.filter((s) => s.writable).map((s) => ({ key: s.key, label: s.label }))} />
        </aside>
      </div>
    </>
  );
}
