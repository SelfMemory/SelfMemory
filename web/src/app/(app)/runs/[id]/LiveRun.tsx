"use client";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useApi } from "@/components/Providers";
import { RunLog } from "@/components/RunLog";
import type { RunStatus } from "@/lib/api/types";
import { useRunStream } from "@/lib/useRunStream";

export function LiveRun({ id, initialStatus }: { id: string; initialStatus: RunStatus }) {
  const api = useApi();
  const router = useRouter();
  const stream = useRunStream(id);
  const status = stream.status ?? initialStatus;
  const live = !stream.done && (status === "queued" || status === "running");
  const cancel = useMutation({ mutationFn: () => api.cancelRun(id) });

  // A finished run may have changed pages: refresh the server-rendered tree.
  useEffect(() => {
    if (stream.done) router.refresh();
  }, [stream.done, router]);

  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <span className={`status ${status}`}>{status}</span>
        {live && (
          <button className="btn danger" onClick={() => cancel.mutate()} disabled={cancel.isPending}>
            {cancel.isPending ? "Cancelling…" : "Cancel run"}
          </button>
        )}
      </div>
      {cancel.error && <p className="error">{cancel.error.message}</p>}
      <RunLog events={stream.events} live={live} />
    </div>
  );
}
