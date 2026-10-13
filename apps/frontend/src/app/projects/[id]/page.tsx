'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft, Network, Play, Plus, Send } from 'lucide-react';
import { useState } from 'react';
import { api } from '@/lib/api';
import { Graph3D, type GNode } from '@/components/Graph3D';
import { ErrorState, LoadingState, StatusBadge, formatDate } from '@/components/ui';

const TYPE_COLORS: Record<string, string> = {
  folder: '#eab308', file: '#3b82f6', class: '#a855f7', method: '#14b8a6', function: '#22d3ee',
  service: '#f97316', component: '#22c55e', concept: '#ec4899', datamodel: '#ef4444', external: '#94a3b8', module: '#06b6d4',
};

export default function ProjectGraphPage() {
  const params = useParams();
  const id = String(params.id);
  const qc = useQueryClient();
  const project = useQuery({ queryKey: ['project', id], queryFn: () => api.nexus.projects.get(id) });
  const kg = useQuery({ queryKey: ['kg', id], queryFn: () => api.nexus.projects.getKg(id) });
  const [selected, setSelected] = useState<GNode | null>(null);
  const [query, setQuery] = useState('');
  const [answer, setAnswer] = useState('');
  const [gen, setGen] = useState(false);
  const [runGoal, setRunGoal] = useState('');

  const runs = useQuery({ queryKey: ['runs', id], queryFn: () => api.nexus.projects.listRuns(id), refetchInterval: 5000 });
  const createRun = useMutation({
    mutationFn: () => api.nexus.projects.createRun(id, { goal: runGoal.trim() }),
    onSuccess: () => { setRunGoal(''); qc.invalidateQueries({ queryKey: ['runs', id] }); },
  });
  const startRun = useMutation({
    mutationFn: (wfId: string) => api.nexus.projects.startRun(id, wfId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['runs', id] }),
  });

  const ask = useMutation({
    mutationFn: () => api.nexus.projects.queryKg(id, query),
    onSuccess: (r) => setAnswer(r.answer),
  });

  const regenerate = async () => {
    setGen(true);
    try { await api.nexus.projects.generateKg(id); await qc.invalidateQueries({ queryKey: ['kg', id] }); qc.invalidateQueries({ queryKey: ['project', id] }); }
    catch (e) { alert(e instanceof Error ? e.message : 'Generate failed'); }
    finally { setGen(false); }
  };

  const nodes = kg.data?.nodes || [];
  const edges = kg.data?.edges || [];
  const neighbors = selected ? edges.filter((e) => e.source === selected.key || e.target === selected.key) : [];

  return (
    <div className="page-wide">
      <div className="page-header">
        <div>
          <Link href="/projects" className="row muted" style={{ gap: 6, fontSize: 13, marginBottom: 4 }}><ArrowLeft size={14} /> Projects</Link>
          <h1 className="page-title">{project.data?.name || 'Project'}</h1>
          <p className="page-subtitle">{nodes.length} nodes · {edges.length} edges · KG {project.data?.kg_status || '—'}</p>
        </div>
        <button className="btn btn-primary" disabled={gen} onClick={regenerate}><Network size={14} /> {gen ? 'Building…' : 'Regenerate graph'}</button>
      </div>

      {kg.isLoading ? <div className="panel panel-pad"><LoadingState /></div> : null}
      {kg.error ? <div className="panel panel-pad"><ErrorState error={kg.error} /></div> : null}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 16, alignItems: 'start' }}>
        <section className="panel" style={{ overflow: 'hidden' }}>
          <Graph3D nodes={nodes} edges={edges} onSelect={setSelected} />
          <div className="row" style={{ gap: 12, flexWrap: 'wrap', padding: '10px 12px', fontSize: 11 }}>
            {(Array.from(new Set(nodes.map((n: any) => String(n.type)))) as string[]).map((t) => (
              <span key={t} className="row" style={{ gap: 4 }}>
                <span style={{ width: 10, height: 10, borderRadius: 999, background: TYPE_COLORS[t] || '#94a3b8', display: 'inline-block' }} />{t}
              </span>
            ))}
            <span className="muted">· kéo để xoay · lăn chuột zoom · click node</span>
          </div>
        </section>

        <div style={{ display: 'grid', gap: 16 }}>
          <section className="panel panel-pad">
            <h3 className="page-title" style={{ fontSize: 15 }}>Node detail</h3>
            {selected ? (
              <div style={{ marginTop: 8 }}>
                <div><strong>{selected.label}</strong></div>
                <div className="muted" style={{ fontSize: 12 }}>type: {selected.type}</div>
                <div className="code" style={{ marginTop: 4, wordBreak: 'break-all' }}>{selected.key}</div>
                <h4 style={{ margin: '12px 0 6px', fontSize: 13 }}>Liên hệ ({neighbors.length})</h4>
                <div style={{ display: 'grid', gap: 4, maxHeight: 220, overflow: 'auto' }}>
                  {neighbors.map((e, i) => (
                    <div key={i} className="muted" style={{ fontSize: 12 }}>
                      {e.source === selected.key ? `→ ${e.relation} → ${e.target}` : `← ${e.relation} ← ${e.source}`}
                    </div>
                  ))}
                </div>
              </div>
            ) : <p className="muted" style={{ marginTop: 8, fontSize: 13 }}>Bấm vào một node để xem chi tiết + quan hệ.</p>}
          </section>

          <section className="panel panel-pad">
            <h3 className="page-title" style={{ fontSize: 15 }}>Hỏi về dự án (qua KG)</h3>
            <div className="row" style={{ gap: 6, marginTop: 8 }}>
              <input className="input" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="VD: OrderService phụ thuộc gì?" onKeyDown={(e) => e.key === 'Enter' && query.trim() && ask.mutate()} />
              <button className="btn btn-primary" disabled={!query.trim() || ask.isPending} onClick={() => ask.mutate()}><Send size={14} /></button>
            </div>
            {ask.isPending ? <p className="muted" style={{ marginTop: 8, fontSize: 13 }}>Đang phân tích…</p> : null}
            {answer ? <div style={{ marginTop: 10, whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.5 }}>{answer}</div> : null}
          </section>
        </div>
      </div>

      <section className="panel panel-pad" style={{ marginTop: 16 }}>
        <div className="spread" style={{ marginBottom: 10 }}>
          <h3 className="page-title" style={{ fontSize: 16 }}>Runs (workflow trên project này)</h3>
        </div>
        <div className="row" style={{ gap: 8, marginBottom: 12 }}>
          <input className="input" value={runGoal} onChange={(e) => setRunGoal(e.target.value)} placeholder="Giao việc trên codebase này… VD: thêm method discount vào OrderService"
            onKeyDown={(e) => e.key === 'Enter' && runGoal.trim() && createRun.mutate()} />
          <button className="btn btn-primary" disabled={!runGoal.trim() || createRun.isPending} onClick={() => createRun.mutate()}><Plus size={14} /> Tạo run</button>
        </div>
        <p className="muted" style={{ fontSize: 12, marginBottom: 10 }}>Mỗi run chạy developer → reviewer → qa trên workspace dùng chung của project. Sau khi code đổi, bấm <strong>Regenerate graph</strong> để cập nhật KG.</p>
        {(runs.data?.data || []).length ? (
          <div className="table-wrap"><table className="table">
            <thead><tr><th>Run</th><th>Status</th><th>Tasks</th><th>Tạo lúc</th><th></th></tr></thead>
            <tbody>
              {(runs.data?.data || []).map((r: any) => (
                <tr key={r.id}>
                  <td><strong>{r.name}</strong><div className="muted" style={{ fontSize: 12 }}>{r.goal}</div></td>
                  <td><StatusBadge status={r.status} /></td>
                  <td className="muted">{r.tasks_done}/{r.task_count}</td>
                  <td>{formatDate(r.created_at)}</td>
                  <td>{r.status === 'PENDING' ? <button className="btn" disabled={startRun.isPending} onClick={() => startRun.mutate(r.id)}><Play size={13} /> Start</button> : null}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        ) : <p className="muted" style={{ fontSize: 13 }}>Chưa có run nào.</p>}
      </section>
    </div>
  );
}
