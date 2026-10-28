"use client";
import { useEffect, useMemo, useState } from "react";
import { GraphCanvas, Legend, type CanvasNode } from "@/components/GraphCanvas";
import type { ScopeKind, TimelineFrame } from "@/lib/api/types";
import { when } from "@/lib/scopes";

/** Scrub or play through commits; pages added in the shown commit are ringed. */
export function TimelinePlayer({ frames, kinds }: { frames: TimelineFrame[]; kinds: Record<string, ScopeKind> }) {
  // `kinds` maps each scope's wiki dir (e.g. wiki/projects/p) to its kind.
  const [i, setI] = useState(frames.length - 1);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!playing) return;
    if (i >= frames.length - 1) { setPlaying(false); return; }
    const t = setTimeout(() => setI(i + 1), 700);
    return () => clearTimeout(t);
  }, [playing, i, frames.length]);

  const frame = frames[i];
  const prev = useMemo(() => new Set(i > 0 ? frames[i - 1].nodes : []), [frames, i]);
  const nodes: CanvasNode[] = useMemo(() => {
    const deg = new Map<string, number>();
    for (const [, t] of frame.edges) deg.set(t, (deg.get(t) ?? 0) + 1);
    return frame.nodes.map((id) => {
      const scope = Object.keys(kinds).filter((w) => id.startsWith(w + "/")).sort((a, b) => b.length - a.length)[0];
      return {
        id, label: id.split("/").pop()!.replace(/\.md$/, ""),
        kind: kinds[scope] ?? "project", weight: deg.get(id) ?? 0, fresh: i > 0 && !prev.has(id),
      };
    });
  }, [frame, kinds, prev, i]);

  return (
    <>
      <div className="scrub">
        <button className="btn" onClick={() => { if (i >= frames.length - 1) setI(0); setPlaying(!playing); }}>
          {playing ? "Pause" : "Play"}
        </button>
        <input type="range" min={0} max={frames.length - 1} value={i} aria-label="Commit"
          onChange={(e) => { setPlaying(false); setI(Number(e.target.value)); }} />
        <span className="muted" style={{ whiteSpace: "nowrap" }}>{i + 1} of {frames.length}</span>
      </div>
      <div style={{ marginBottom: 12 }}>
        <strong>{frame.message.split("\n")[0]}</strong>{" "}
        <span className="muted">{frame.sha} · {when(frame.date)}</span>
      </div>
      <div className="graph-wrap">
        <GraphCanvas nodes={nodes} edges={frame.edges} />
        <Legend extra={<span>{frame.nodes.length} pages after this commit</span>} />
      </div>
    </>
  );
}
