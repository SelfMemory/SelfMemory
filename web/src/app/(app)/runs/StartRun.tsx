"use client";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useApi } from "@/components/Providers";
import type { RunCommand } from "@/lib/api/types";

const HELP: Record<Exclude<RunCommand, "query">, string> = {
  ingest: "Re-read the scope's sources and update its pages.",
  lint: "Check the scope for broken links, gaps and contradictions, and fix what it can.",
};

export function StartRun({ scopes }: { scopes: { key: string; label: string }[] }) {
  const api = useApi();
  const router = useRouter();
  const [command, setCommand] = useState<"ingest" | "lint">("lint");
  const [scope, setScope] = useState(scopes[0]?.key ?? "");
  const [message, setMessage] = useState("");
  const start = useMutation({
    mutationFn: () => api.startRun({ command, scope, message, display_text: `${command === "lint" ? "Lint" : "Ingest"} ${scopes.find((s) => s.key === scope)?.label ?? scope}` }),
    onSuccess: (r) => router.push(`/runs/${r.job_id}`),
  });

  if (!scopes.length) return <p className="muted">You can only read these wikis, so you can’t start runs here.</p>;
  return (
    <form className="stack" onSubmit={(e) => { e.preventDefault(); start.mutate(); }}>
      <div className="seg" role="group" aria-label="Kind of run">
        {(["lint", "ingest"] as const).map((c) => (
          <button type="button" key={c} aria-pressed={command === c} onClick={() => setCommand(c)}>
            {c === "lint" ? "Tidy up" : "Re-ingest"}
          </button>
        ))}
      </div>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>{HELP[command]}</p>
      <label className="field">
        Scope
        <select className="select" value={scope} onChange={(e) => setScope(e.target.value)}>
          {scopes.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
        </select>
      </label>
      <label className="field">
        Instructions <span className="hint">Optional</span>
        <textarea className="textarea" value={message} onChange={(e) => setMessage(e.target.value)} />
      </label>
      {start.error && <p className="error">{start.error.message}</p>}
      <button className="btn" disabled={start.isPending}>{start.isPending ? "Starting…" : "Start run"}</button>
    </form>
  );
}
