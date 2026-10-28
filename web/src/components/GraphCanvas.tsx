"use client";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { pageHref } from "@/lib/paths";

export interface CanvasNode {
  id: string;
  label: string;
  kind: "org" | "project" | "user";
  weight: number;
  fresh?: boolean;
}

type P = { x: number; y: number; vx: number; vy: number };

const W = 1000;
const H = 640;

/**
 * Small force layout (repulsion + springs + centring), no dependency.
 * Positions persist across prop changes so the timeline can grow in place.
 */
export function GraphCanvas({ nodes, edges, focus }: { nodes: CanvasNode[]; edges: [string, string][]; focus?: string }) {
  const router = useRouter();
  const pos = useRef(new Map<string, P>());
  const [, tick] = useState(0);
  const [hover, setHover] = useState<string | null>(null);

  useEffect(() => {
    const ps = pos.current;
    for (const n of nodes) {
      if (!ps.has(n.id)) {
        const a = Math.random() * Math.PI * 2;
        const r = 40 + Math.random() * 120;
        ps.set(n.id, { x: W / 2 + Math.cos(a) * r, y: H / 2 + Math.sin(a) * r, vx: 0, vy: 0 });
      }
    }
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let alpha = 1;
    let raf = 0;
    const ids = nodes.map((n) => n.id);
    const step = () => {
      for (let i = 0; i < ids.length; i++) {
        const a = ps.get(ids[i])!;
        for (let j = i + 1; j < ids.length; j++) {
          const b = ps.get(ids[j])!;
          const dx = a.x - b.x || 0.01;
          const dy = a.y - b.y || 0.01;
          const d2 = dx * dx + dy * dy;
          const f = (1800 / Math.max(d2, 60)) * alpha;
          a.vx += dx * f * 0.05; a.vy += dy * f * 0.05;
          b.vx -= dx * f * 0.05; b.vy -= dy * f * 0.05;
        }
      }
      for (const [s, t] of edges) {
        const a = ps.get(s), b = ps.get(t);
        if (!a || !b) continue;
        const dx = b.x - a.x, dy = b.y - a.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 1;
        const f = ((d - 70) / d) * 0.04 * alpha;
        a.vx += dx * f; a.vy += dy * f; b.vx -= dx * f; b.vy -= dy * f;
      }
      for (const id of ids) {
        const p = ps.get(id)!;
        p.vx += (W / 2 - p.x) * 0.004 * alpha;
        p.vy += (H / 2 - p.y) * 0.004 * alpha;
        p.vx *= 0.6; p.vy *= 0.6;
        p.x = Math.min(W - 20, Math.max(20, p.x + p.vx));
        p.y = Math.min(H - 20, Math.max(20, p.y + p.vy));
      }
      alpha *= 0.985;
    };
    if (reduce) {
      for (let i = 0; i < 300; i++) step();
      tick((t) => t + 1);
      return;
    }
    const loop = () => {
      step();
      tick((t) => t + 1);
      if (alpha > 0.02) raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [nodes, edges]);

  const linked = new Set<string>();
  const active = hover ?? focus;
  if (active) for (const [s, t] of edges) if (s === active) linked.add(t); else if (t === active) linked.add(s);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Graph of ${nodes.length} pages and ${edges.length} links`}>
      {edges.map(([s, t]) => {
        const a = pos.current.get(s), b = pos.current.get(t);
        if (!a || !b) return null;
        const hot = active && (s === active || t === active);
        return (
          <line key={`${s}>${t}`} className="edge" x1={a.x} y1={a.y} x2={b.x} y2={b.y}
            style={hot ? { stroke: "var(--ink)", strokeWidth: 1.5 } : undefined} />
        );
      })}
      {nodes.map((n) => {
        const p = pos.current.get(n.id);
        if (!p) return null;
        const r = 4 + Math.min(10, Math.sqrt(n.weight) * 2);
        const dim = active && n.id !== active && !linked.has(n.id);
        const showLabel = n.id === active || linked.has(n.id) || n.weight >= 3 || nodes.length < 40;
        return (
          <g key={n.id} className={`node${n.fresh ? " new" : ""}`} transform={`translate(${p.x},${p.y})`}
            opacity={dim ? 0.25 : 1}
            onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover(null)}
            onClick={() => router.push(pageHref(n.id))}>
            <circle r={n.id === focus ? r + 3 : r} fill={`var(--${n.kind})`} />
            {n.id === focus && <circle r={r + 8} fill="none" stroke="var(--mark)" strokeWidth={3} />}
            {showLabel && <text x={r + 4} y={4}>{n.label}</text>}
            <title>{n.id}</title>
          </g>
        );
      })}
    </svg>
  );
}

export function Legend({ extra }: { extra?: React.ReactNode }) {
  return (
    <div className="legend">
      <span><span className="dot org" /> Org room</span>
      <span><span className="dot project" /> Project</span>
      <span><span className="dot user" /> Personal</span>
      {extra}
    </div>
  );
}
