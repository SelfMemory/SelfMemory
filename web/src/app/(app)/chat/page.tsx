import Link from "next/link";
import { ScopeTag } from "@/components/ScopeTag";
import { guard, serverApi } from "@/lib/api/server";
import { when } from "@/lib/scopes";
import { NewChat } from "./NewChat";

export const metadata = { title: "Ask" };

export default async function ChatsPage({ searchParams }: { searchParams: Promise<{ scope?: string }> }) {
  const { scope } = await searchParams;
  const api = await serverApi();
  const [{ scopes }, { chats }] = await Promise.all([guard(api.tree()), guard(api.chats())]);
  const byKey = new Map(scopes.map((s) => [s.key, s]));
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Ask the wiki</h1>
          <p>The agent answers from the pages you can read, and cites them. Pick one scope to keep answers focused.</p>
        </div>
      </div>
      <div className="split">
        {chats.length === 0 ? (
          <div className="empty">No conversations yet. Start one on the right.</div>
        ) : (
          <ul className="list">
            {chats.map((c) => (
              <li key={c.id}>
                <div className="grow">
                  <Link className="title" href={`/chat/${c.id}`}>{c.title}</Link>
                  <div className="row" style={{ gap: 10, fontSize: 13 }}>
                    <ScopeTag scope={c.scope ? byKey.get(c.scope) : undefined} fallback={c.scope ?? "All scopes"} />
                    <span className="muted">{when(c.updated_at)}</span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
        <aside className="aside">
          <h3>New conversation</h3>
          <NewChat scopes={scopes.map((s) => ({ key: s.key, label: s.label }))} initialScope={scope} />
        </aside>
      </div>
    </>
  );
}
