'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bot, HeartPulse } from 'lucide-react';
import { api } from '@/lib/api';
import { EmptyState, ErrorState, LoadingState, StatCard, StatusBadge, formatDate } from '@/components/ui';

export default function AgentsPage() {
  const queryClient = useQueryClient();
  const agents = useQuery({ queryKey: ['agents'], queryFn: () => api.agents.list({ page: 1, limit: 100 }) });
  const health = useQuery({ queryKey: ['agents', 'health'], queryFn: api.agents.health });
  const heartbeat = useMutation({ mutationFn: api.agents.heartbeat, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['agents'] }) });
  const rows = agents.data?.data || [];
  const byStatus = health.data?.byStatus || {};
  return <div className="page-wide"><div className="page-header"><div><h1 className="page-title">Agent Fleet</h1><p className="page-subtitle">Registered agents from the backend registry.</p></div></div>
    <div className="grid grid-4" style={{ marginBottom: 16 }}><StatCard label="Total" value={health.data?.total || rows.length} icon={Bot} /><StatCard label="Healthy" value={byStatus.HEALTHY || 0} color="#34d399" /><StatCard label="Degraded" value={byStatus.DEGRADED || 0} color="#fbbf24" /><StatCard label="Offline" value={byStatus.OFFLINE || 0} color="#f87171" /></div>
    {agents.isLoading ? <LoadingState /> : null}{agents.error ? <ErrorState error={agents.error} /> : null}{!agents.isLoading && rows.length === 0 ? <EmptyState title="No agents returned" /> : null}
    <div className="grid grid-3">{rows.map((agent) => <section className="card" key={agent.id}><div className="spread"><div><h2 style={{ fontSize: 15, fontWeight: 760 }}>{agent.name}</h2><div className="muted" style={{ fontSize: 12 }}>{agent.role} / {agent.runtime}</div></div><StatusBadge status={agent.status} /></div><p className="muted" style={{ marginTop: 12, minHeight: 38 }}>{agent.description || '-'}</p><div className="row" style={{ flexWrap: 'wrap', marginTop: 12 }}>{agent.capabilities.map((cap) => <span className="badge badge-default" key={cap}>{cap.replace(/_/g, ' ')}</span>)}</div><div className="spread" style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid var(--border)' }}><span className="code">last seen: {formatDate(agent.lastSeenAt)}</span><button className="btn" disabled={heartbeat.isPending} onClick={() => heartbeat.mutate(agent.agentId)}><HeartPulse size={13} /> Heartbeat</button></div></section>)}</div>
  </div>;
}
