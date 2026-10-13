'use client';

import { useEffect, useRef } from 'react';

export interface GNode { key: string; label: string; type: string; meta?: any }
export interface GEdge { source: string; target: string; relation: string }

const COLORS: Record<string, string> = {
  folder: '#eab308', file: '#3b82f6', class: '#a855f7', method: '#14b8a6', function: '#22d3ee',
  service: '#f97316', component: '#22c55e', concept: '#ec4899', datamodel: '#ef4444',
  external: '#94a3b8', module: '#06b6d4',
};
const SIZE: Record<string, number> = {
  concept: 9, service: 8, component: 7, datamodel: 7, class: 5, file: 4, folder: 4,
  external: 3, module: 5, method: 2, function: 2.5,
};
const REL_COLOR: Record<string, string> = {
  calls: 'rgba(34,211,238,0.65)', imports: 'rgba(96,165,250,0.5)',
  inherits: 'rgba(168,85,247,0.7)', contains: 'rgba(120,132,150,0.35)',
  depends_on: 'rgba(236,72,153,0.6)', uses: 'rgba(236,72,153,0.5)', relates_to: 'rgba(148,163,184,0.4)',
};

export function Graph3D({ nodes, edges, onSelect }: { nodes: GNode[]; edges: GEdge[]; onSelect?: (n: GNode | null) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const gRef = useRef<any>(null);

  useEffect(() => {
    let disposed = false;
    let cleanupResize: (() => void) | null = null;

    (async () => {
      const mod: any = await import('3d-force-graph');
      const ForceGraph3D = mod.default;
      const SpriteText = (await import('three-spritetext')).default as any;
      if (disposed || !ref.current) return;

      const data = {
        nodes: nodes.map((n) => ({
          id: n.key, name: `${n.label}  ·  ${n.type}`, label: n.label, type: n.type,
          val: SIZE[n.type] || 3, color: COLORS[n.type] || '#94a3b8',
        })),
        links: edges.map((e) => ({ source: e.source, target: e.target, relation: e.relation })),
      };

      const g = ForceGraph3D()(ref.current)
        .backgroundColor('#07070c')
        .graphData(data)
        .nodeLabel('name')
        .nodeColor((n: any) => n.color)
        .nodeVal((n: any) => n.val)
        .nodeOpacity(0.95)
        .nodeResolution(12)
        // persistent text label floating above each node
        .nodeThreeObjectExtend(true)
        .nodeThreeObject((n: any) => {
          const s = new SpriteText(n.label);
          s.color = n.color;
          s.textHeight = Math.max(2.6, (n.val || 3) * 0.9);
          s.fontWeight = '600';
          s.material.depthWrite = false;
          s.position.set(0, (n.val || 3) + 4, 0);
          return s;
        })
        .linkColor((l: any) => REL_COLOR[l.relation] || 'rgba(148,163,184,0.4)')
        .linkWidth((l: any) => (l.relation === 'contains' ? 0.6 : 1.1))
        .linkOpacity(0.85)
        .linkDirectionalParticles((l: any) => (l.relation === 'calls' ? 3 : 0))
        .linkDirectionalParticleWidth(1.6)
        .linkDirectionalParticleSpeed(0.006)
        .width(ref.current.clientWidth)
        .height(680)
        .onNodeClick((n: any) => {
          onSelect?.({ key: n.id, label: n.label, type: n.type });
          const dist = 120;
          const ratio = 1 + dist / Math.hypot(n.x || 1, n.y || 1, n.z || 1);
          g.cameraPosition({ x: (n.x || 0) * ratio, y: (n.y || 0) * ratio, z: (n.z || 0) * ratio }, n, 800);
        })
        .onBackgroundClick(() => onSelect?.(null));

      // gentle initial spread + zoom-to-fit
      g.d3Force('charge')?.strength(-90);
      setTimeout(() => { if (!disposed) g.zoomToFit(600, 40); }, 900);

      const onResize = () => { if (ref.current) g.width(ref.current.clientWidth); };
      window.addEventListener('resize', onResize);
      cleanupResize = () => window.removeEventListener('resize', onResize);
      gRef.current = g;
    })();

    return () => {
      disposed = true;
      cleanupResize?.();
      try { gRef.current?._destructor?.(); } catch { /* noop */ }
      if (ref.current) ref.current.innerHTML = '';
    };
  }, [nodes, edges]);

  if (!nodes.length) {
    return <div style={{ height: 680, display: 'grid', placeItems: 'center', background: '#07070c', color: '#94a3b8', borderRadius: 8 }}>
      Chưa có knowledge graph. Bấm <strong style={{ margin: '0 4px' }}>Generate graph</strong>.
    </div>;
  }
  return <div ref={ref} style={{ width: '100%', height: 680, borderRadius: 8, overflow: 'hidden', background: '#07070c' }} />;
}
