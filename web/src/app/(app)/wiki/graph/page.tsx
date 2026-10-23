import { GraphCanvas, Legend, type CanvasNode } from "@/components/GraphCanvas";
import { ScopeFilter } from "@/components/ScopeFilter";
import { guard, serverApi } from "@/lib/api/server";

export const metadata = { title: "Graph" };

export default async function GraphPage({ searchParams }: { searchParams: Promise<{ scope?: string; focus?: string }> }) {
  const { scope, focus } = await searchParams;
  const api = await serverApi();
  const [{ scopes }, graph] = await Promise.all([guard(api.tree()), guard(api.graph(scope))]);
  const kind = new Map(scopes.map((s) => [s.key, s.kind]));
  const nodes: CanvasNode[] = graph.nodes.map((n) => ({
    id: n.id, label: n.label, kind: kind.get(n.scope) ?? "project", weight: n.links,
  }));
  const orphans = graph.nodes.filter((n) => n.orphan).length;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>How pages connect</h1>
          <p>Each dot is a page; lines are links between them. Bigger dots are linked to more often. Click one to read it.</p>
        </div>
        <ScopeFilter base="/wiki/graph" scopes={scopes} current={scope} />
      </div>
      {nodes.length === 0 ? (
        <div className="empty">No pages in this scope yet.</div>
      ) : (
        <div className="graph-wrap">
          <GraphCanvas nodes={nodes} edges={graph.edges.map((e) => [e.from, e.to])} focus={focus} />
          <Legend
            extra={
              <>
                <span>{nodes.length} pages, {graph.edges.length} links</span>
                {orphans > 0 && <span>{orphans} unlinked</span>}
                {graph.broken > 0 && <span className="error">{graph.broken} broken links</span>}
              </>
            }
          />
        </div>
      )}
    </>
  );
}
