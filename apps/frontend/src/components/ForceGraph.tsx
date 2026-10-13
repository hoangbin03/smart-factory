'use client';

import { useMemo, useRef, useState } from 'react';

export interface GraphNode { key: string; label: string; type: string; meta?: any }
export interface GraphEdge { source: string; target: string; relation: string }

const TYPE_COLORS: Record<string, string> = {
  file: '#2563eb', class: '#7c3aed', function: '#0d9488', service: '#ea580c',
  component: '#16a34a', concept: '#db2777', datamodel: '#dc2626', external: '#64748b', module: '#0891b2',
};
const color = (t: string) => TYPE_COLORS[t] || '#64748b';

const W = 1000, H = 680;

function computeLayout(nodes: GraphNode[], edges: GraphEdge[]) {
  const n = nodes.length;
  if (!n) return [] as { x: number; y: number }[];
  // deterministic ring init (no Math.random → stable layout across renders)
  const pos = nodes.map((_, i) => {
    const a = (i / n) * Math.PI * 2;
    const seed = ((i * 2654435761) % 1000) / 1000;
    const r = 60 + seed * Math.min(W, H) * 0.35;
    return { x: W / 2 + Math.cos(a) * r, y: H / 2 + Math.sin(a) * r, vx: 0, vy: 0 };
  });
  const idx = new Map(nodes.map((nd, i) => [nd.key, i]));
  const links = edges
    .map((e) => [idx.get(e.source), idx.get(e.target)] as [number | undefined, number | undefined])
    .filter(([a, b]) => a !== undefined && b !== undefined) as [number, number][];
  const k = Math.sqrt((W * H) / Math.max(1, n));
  const repulse = k * k;
  const iterations = Math.min(300, Math.max(90, Math.floor(26000 / n)));
  const cx = W / 2, cy = H / 2;
  for (let it = 0; it < iterations; it++) {
    for (let i = 0; i < n; i++) {
      let fx = 0, fy = 0;
      for (let j = 0; j < n; j++) {
        if (i === j) continue;
        let dx = pos[i].x - pos[j].x, dy = pos[i].y - pos[j].y;
        const d2 = dx * dx + dy * dy || 0.01;
        const d = Math.sqrt(d2);
        const f = repulse / d2;
        fx += (dx / d) * f; fy += (dy / d) * f;
      }
      pos[i].vx += fx; pos[i].vy += fy;
    }
    for (const [a, b] of links) {
      let dx = pos[a].x - pos[b].x, dy = pos[a].y - pos[b].y;
      const d = Math.sqrt(dx * dx + dy * dy) || 0.01;
      const f = (d * d) / k;
      const fx = (dx / d) * f, fy = (dy / d) * f;
      pos[a].vx -= fx; pos[a].vy -= fy;
      pos[b].vx += fx; pos[b].vy += fy;
    }
    const cool = 1 - it / iterations;
    for (let i = 0; i < n; i++) {
      pos[i].vx += (cx - pos[i].x) * 0.012;
      pos[i].vy += (cy - pos[i].y) * 0.012;
      let vx = pos[i].vx, vy = pos[i].vy;
      const v = Math.sqrt(vx * vx + vy * vy) || 0.01;
      const maxv = 24 * cool + 1;
      if (v > maxv) { vx = (vx / v) * maxv; vy = (vy / v) * maxv; }
      pos[i].x += vx; pos[i].y += vy;
      pos[i].vx = vx * 0.85; pos[i].vy = vy * 0.85;
    }
  }
  return pos;
}

export function ForceGraph({ nodes, edges, onSelect }: { nodes: GraphNode[]; edges: GraphEdge[]; onSelect?: (n: GraphNode | null) => void }) {
  const layout = useMemo(() => computeLayout(nodes, edges), [nodes, edges]);
  const idx = useMemo(() => new Map(nodes.map((n, i) => [n.key, i])), [nodes]);
  const [selected, setSelected] = useState<string | null>(null);
  const [view, setView] = useState({ x: 0, y: 0, s: 1 });
  const drag = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);

  const neighbors = useMemo(() => {
    if (!selected) return new Set<string>();
    const s = new Set<string>([selected]);
    edges.forEach((e) => {
      if (e.source === selected) s.add(e.target);
      if (e.target === selected) s.add(e.source);
    });
    return s;
  }, [selected, edges]);

  const types = useMemo(() => Array.from(new Set(nodes.map((n) => n.type))), [nodes]);

  if (!nodes.length) return <div className="muted" style={{ padding: 40, textAlign: 'center' }}>Chưa có knowledge graph. Bấm <strong>Generate graph</strong>.</div>;

  const pick = (key: string) => {
    const next = selected === key ? null : key;
    setSelected(next);
    onSelect?.(next ? nodes[idx.get(next)!] : null);
  };

  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
    setView((v) => ({ ...v, s: Math.min(4, Math.max(0.3, v.s * factor)) }));
  };
  const onDown = (e: React.MouseEvent) => { drag.current = { x: e.clientX, y: e.clientY, ox: view.x, oy: view.y }; };
  const onMove = (e: React.MouseEvent) => {
    if (!drag.current) return;
    setView((v) => ({ ...v, x: drag.current!.ox + (e.clientX - drag.current!.x), y: drag.current!.oy + (e.clientY - drag.current!.y) }));
  };
  const onUp = () => { drag.current = null; };

  return (
    <div style={{ position: 'relative' }}>
      <div style={{ position: 'absolute', top: 8, left: 8, zIndex: 2, display: 'flex', gap: 10, flexWrap: 'wrap', background: 'rgba(255,255,255,0.85)', padding: '6px 10px', borderRadius: 8, fontSize: 11 }}>
        {types.map((t) => (
          <span key={t} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 10, height: 10, borderRadius: 999, background: color(t), display: 'inline-block' }} />{t}
          </span>
        ))}
      </div>
      <button className="btn" style={{ position: 'absolute', top: 8, right: 8, zIndex: 2 }} onClick={() => setView({ x: 0, y: 0, s: 1 })}>Reset view</button>
      <svg
        viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 680, background: '#f8fafc', borderRadius: 8, cursor: drag.current ? 'grabbing' : 'grab', touchAction: 'none' }}
        onWheel={onWheel} onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp} onMouseLeave={onUp}
      >
        <g transform={`translate(${view.x},${view.y}) scale(${view.s})`}>
          {edges.map((e, i) => {
            const a = layout[idx.get(e.source) ?? -1];
            const b = layout[idx.get(e.target) ?? -1];
            if (!a || !b) return null;
            const active = selected && (e.source === selected || e.target === selected);
            return (
              <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                stroke={active ? '#0f172a' : '#cbd5e1'} strokeWidth={active ? 2 : 1}
                opacity={selected && !active ? 0.15 : 0.7} />
            );
          })}
          {nodes.map((n, i) => {
            const p = layout[i];
            if (!p) return null;
            const dim = selected && !neighbors.has(n.key);
            const r = n.type === 'file' ? 8 : n.type === 'class' ? 7 : n.type === 'function' ? 5 : 10;
            return (
              <g key={n.key} transform={`translate(${p.x},${p.y})`} opacity={dim ? 0.2 : 1} style={{ cursor: 'pointer' }} onClick={() => pick(n.key)}>
                <circle r={r} fill={color(n.type)} stroke={selected === n.key ? '#0f172a' : '#fff'} strokeWidth={selected === n.key ? 3 : 1.5} />
                {(n.type !== 'function' || selected === n.key || view.s > 1.6) && (
                  <text x={r + 3} y={4} fontSize={11} fill="#0f172a">{n.label.length > 26 ? n.label.slice(0, 26) + '…' : n.label}</text>
                )}
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}
