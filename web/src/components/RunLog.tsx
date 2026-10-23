"use client";
import { useEffect, useRef } from "react";
import type { RunEvent } from "@/lib/api/types";

function line(ev: RunEvent): { k: string; body: React.ReactNode } | null {
  switch (ev.kind) {
    case "job": return { k: "run", body: `${ev.command} · ${ev.status}${ev.scope ? ` · ${ev.scope}` : ""}` };
    case "start": return { k: "start", body: "sandbox started" };
    case "attempt": return { k: "retry", body: `attempt ${String(ev.attempt)}` };
    case "session": return null;
    case "text": return { k: "says", body: String(ev.text) };
    case "tool": return { k: "tool", body: <><span className="t">{String(ev.tool)}</span> {String(ev.title ?? "")} <span style={{ opacity: 0.6 }}>{String(ev.status ?? "")}</span></> };
    case "usage": return { k: "usage", body: `${JSON.stringify(ev.tokens)}${ev.cost ? ` · $${Number(ev.cost).toFixed(4)}` : ""}` };
    case "commit": return { k: "commit", body: `${String(ev.sha ?? "").slice(0, 7)} ${String(ev.message ?? "")}`.trim() };
    case "error": return { k: "error", body: String(ev.message) };
    case "notice": return { k: "note", body: String(ev.message) };
    case "done": return { k: "done", body: `${ev.status}${ev.code != null ? ` (exit ${ev.code})` : ""}` };
    default: return { k: ev.kind, body: JSON.stringify(ev) };
  }
}

/** Terminal-style transcript of a run's events, pinned to the bottom while live. */
export function RunLog({ events, live }: { events: RunEvent[]; live: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (el && el.scrollHeight - el.scrollTop - el.clientHeight < 120) el.scrollTop = el.scrollHeight;
  }, [events.length]);
  return (
    <div className="log" ref={ref} role="log" aria-live="polite">
      {events.map((ev, i) => {
        const l = line(ev);
        if (!l) return null;
        return (
          <div key={i} className={`ev ${ev.kind}`}>
            <span className="k">{l.k}</span>
            {l.body}
          </div>
        );
      })}
      {live && <span className="cursor" aria-label="running" />}
    </div>
  );
}
