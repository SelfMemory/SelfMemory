import { ScopeFilter } from "@/components/ScopeFilter";
import { guard, serverApi } from "@/lib/api/server";
import type { ScopeKind } from "@/lib/api/types";
import { TimelinePlayer } from "./TimelinePlayer";

export const metadata = { title: "Timeline" };

export default async function TimelinePage({ searchParams }: { searchParams: Promise<{ scope?: string }> }) {
  const { scope } = await searchParams;
  const api = await serverApi();
  const [{ scopes }, { frames }] = await Promise.all([guard(api.tree()), guard(api.timeline(scope, 200))]);
  const kinds: Record<string, ScopeKind> = Object.fromEntries(scopes.map((s) => [s.wiki, s.kind]));

  return (
    <>
      <div className="page-head">
        <div>
          <h1>How the wiki grew</h1>
          <p>Every commit the agent or a person made, replayed in order. New pages in each step are ringed.</p>
        </div>
        <ScopeFilter base="/wiki/timeline" scopes={scopes} current={scope} />
      </div>
      {frames.length === 0 ? (
        <div className="empty">No commits yet. The first ingest will start the history.</div>
      ) : (
        <TimelinePlayer key={scope ?? "all"} frames={frames} kinds={kinds} />
      )}
    </>
  );
}
