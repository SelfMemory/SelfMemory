import Link from "next/link";
import { notFound } from "next/navigation";
import { ApiError } from "@/lib/api/client";
import { guard, serverApi } from "@/lib/api/server";
import { when } from "@/lib/scopes";
import { LiveRun } from "./LiveRun";

export const metadata = { title: "Run" };

export default async function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const api = await serverApi();
  const run = await guard(api.run(id)).catch((e) => {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  });
  return (
    <>
      <div className="crumbs"><Link href="/runs">Runs</Link></div>
      <div className="page-head">
        <div>
          <h1>{run.display_text || run.command}</h1>
          <p>
            {run.command}{run.scope ? ` in ${run.scope}` : ""} · started {when(run.created_at as string)}
          </p>
        </div>
      </div>
      <LiveRun id={id} initialStatus={run.status} />
    </>
  );
}
