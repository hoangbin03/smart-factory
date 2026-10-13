'use client';

import { useEffect, useState, useRef } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { Zap, Send, Activity, Bot, GitBranch, Terminal, FolderGit2, Network } from 'lucide-react';
import { api } from '@/lib/api';
import { StatCard } from '@/components/ui';

export default function NexusPage() {
  const [snapshot, setSnapshot] = useState<any>(null);
  const [chatHistory, setChatHistory] = useState<{ role: string; content: string }[]>([
    { role: 'assistant', content: 'Xin chào! Em là Nexus. Anh có thể yêu cầu em: tạo project (clone git), giao việc cho agent, tạo skill, hoặc hỏi về tình hình dự án qua knowledge graph.' },
  ]);
  const [chatInput, setChatInput] = useState('');
  const [sending, setSending] = useState(false);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  const initialSnapshot = useQuery({ queryKey: ['nexus', 'snapshot'], queryFn: api.nexus.snapshot, staleTime: 60000 });
  const projects = useQuery({ queryKey: ['projects', 'nexus'], queryFn: () => api.nexus.projects.list(), retry: false, refetchInterval: 10000 });

  useEffect(() => { if (initialSnapshot.data && !snapshot) setSnapshot(initialSnapshot.data); }, [initialSnapshot.data]);

  // live event stream via monitor WS
  useEffect(() => {
    const w = new WebSocket((process.env.NEXT_PUBLIC_NEXUS_URL || 'ws://localhost:8100').replace('http', 'ws') + '/ws/monitor');
    w.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === 'snapshot') setSnapshot(payload.data);
        else if (payload.type === 'event') api.nexus.snapshot().then(setSnapshot).catch(() => {});
      } catch { /* ignore */ }
    };
    return () => w.close();
  }, []);

  useEffect(() => { chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [chatHistory, sending]);

  const sendChat = async (e: React.FormEvent) => {
    e.preventDefault();
    const message = chatInput.trim();
    if (!message || sending) return;
    const history = chatHistory.filter((m) => m.role !== 'system');
    setChatHistory((prev) => [...prev, { role: 'user', content: message }]);
    setChatInput('');
    setSending(true);
    try {
      const res = await api.nexus.chat({ message, history });
      setChatHistory((prev) => [...prev, { role: 'assistant', content: res.reply }]);
      projects.refetch();
    } catch (err) {
      setChatHistory((prev) => [...prev, { role: 'assistant', content: '⚠️ Lỗi khi gọi Nexus: ' + (err instanceof Error ? err.message : 'unknown') }]);
    } finally {
      setSending(false);
    }
  };

  const projectRows = projects.data?.data || [];
  const kgReady = projectRows.filter((p: any) => p.kg_status === 'READY').length;

  return (
    <div className="page-wide">
      <div className="page-header">
        <div>
          <h1 className="page-title"><Zap size={24} style={{ display: 'inline', color: '#fbbf24', verticalAlign: 'middle', marginRight: 8 }} /> Nexus Intelligence</h1>
          <p className="page-subtitle">Master Agent điều phối & giám sát toàn nhà máy. Giao việc trực tiếp qua chat.</p>
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '2fr 1fr', gap: 24 }}>
        <div className="stack" style={{ gap: 24 }}>
          <div className="grid grid-4">
            <StatCard label="Live Workflows" value={snapshot?.workflows?.active || 0} icon={GitBranch} color="#818cf8" />
            <StatCard label="Active Agents" value={snapshot?.agents?.total || 0} icon={Bot} color="#34d399" />
            <StatCard label="Projects" value={projectRows.length} sub={kgReady + ' with KG'} icon={FolderGit2} color="#22d3ee" />
            <StatCard label="Total Events" value={snapshot?.total_events || 0} icon={Activity} color="#f472b6" />
          </div>

          <section className="panel">
            <div className="panel-head"><div className="panel-title"><FolderGit2 size={16} /> Projects & Knowledge Graph</div><Link href="/projects" className="btn">Mở Projects</Link></div>
            <div className="panel-pad stack" style={{ gap: 8 }}>
              {projectRows.length === 0 ? <div className="muted">Chưa có project. Bảo Nexus: "tạo project từ repo …".</div> : null}
              {projectRows.slice(0, 5).map((p: any) => (
                <div key={p.id} className="card"><div className="spread">
                  <div><strong>{p.name}</strong><div className="muted" style={{ fontSize: 12 }}>{p.source_type} · {p.kg_status === 'READY' ? `${p.node_count} nodes / ${p.edge_count} edges` : 'KG chưa build'}</div></div>
                  <Link href={`/projects/${p.id}`} className="btn"><Network size={13} /> Graph</Link>
                </div></div>
              ))}
            </div>
          </section>

          <section className="panel">
            <div className="panel-head"><div className="panel-title"><Terminal size={16} /> Live Event Stream</div></div>
            <div className="panel-pad" style={{ maxHeight: 320, overflowY: 'auto', background: '#0f172a', fontFamily: 'monospace', fontSize: 13 }}>
              {snapshot?.recent_events?.map((ev: any) => (
                <div key={ev.id} style={{ marginBottom: 8, paddingBottom: 8, borderBottom: '1px solid #1e293b' }}>
                  <span style={{ color: '#64748b' }}>[{new Date(ev.timestamp).toLocaleTimeString()}]</span>{' '}
                  <strong style={{ color: '#e2e8f0' }}>{ev.subject}</strong>{' '}
                  <span style={{ color: '#94a3b8' }}>{ev.data?.agentId ? `(Agent: ${ev.data.agentId})` : ''}{ev.data?.workflowId ? ` (WF: ${String(ev.data.workflowId).slice(0, 8)})` : ''}</span>
                </div>
              ))}
              {!snapshot?.recent_events?.length && <div className="muted">No recent events...</div>}
            </div>
          </section>
        </div>

        {/* Chat with Nexus (REST — supports create project/workflow/skill actions) */}
        <div className="panel flex-col" style={{ height: 'calc(100vh - 120px)' }}>
          <div className="panel-head"><div className="panel-title"><Zap size={16} color="#fbbf24" /> Talk to Nexus</div></div>
          <div className="panel-pad flex-1" style={{ overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 16 }}>
            {chatHistory.map((msg, i) => (
              <div key={i} style={{ alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start', background: msg.role === 'user' ? '#3b82f6' : '#1e293b', padding: '8px 12px', borderRadius: 8, maxWidth: '90%', lineHeight: 1.5, fontSize: 14, whiteSpace: 'pre-wrap' }}>
                {msg.content}
              </div>
            ))}
            {sending ? <div style={{ alignSelf: 'flex-start', background: '#1e293b', padding: '8px 12px', borderRadius: 8, fontSize: 14 }} className="muted">Nexus đang xử lý…</div> : null}
            <div ref={chatBottomRef} />
          </div>
          <div style={{ padding: 16, borderTop: '1px solid var(--border)' }}>
            <form onSubmit={sendChat} style={{ display: 'flex', gap: 8 }}>
              <input className="input" style={{ flex: 1 }} placeholder="VD: tạo project từ github.com/... / giao việc trên dự án X" value={chatInput} onChange={(e) => setChatInput(e.target.value)} />
              <button type="submit" className="btn btn-primary" disabled={!chatInput.trim() || sending}><Send size={16} /></button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
