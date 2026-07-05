'use client';

import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { Activity, BarChart2, Bot, Database } from 'lucide-react';
import { api, API_BASE_URL } from '@/lib/api';
import { ErrorState, LoadingState, StatCard, StatusBadge, stringifyShort } from '@/components/ui';

export default function MonitoringPage() {
  const health = useQuery({ queryKey: ['health'], queryFn: api.health });
  const agentHealth = useQuery({ queryKey: ['agents', 'health'], queryFn: api.agents.health });
  const metrics = useQuery({ queryKey: ['metrics'], queryFn: api.metrics });
  const healthStatus = health.data?.status || (health.error ? 'DOWN' : 'CHECKING');
  return <div className="page"><div className="page-header"><div><h1 className="page-title">Monitoring</h1><p className="page-subtitle">Health and metrics from live services.</p></div><Link className="btn btn-primary" href="http://localhost:3001" target="_blank"><BarChart2 size={14} /> Grafana</Link></div><div className="grid grid-3" style={{ marginBottom: 16 }}><StatCard label="API Gateway" value={healthStatus} icon={Activity} color={health.error ? '#f87171' : '#34d399'} /><StatCard label="Agents" value={agentHealth.data?.total || 0} icon={Bot} color="#818cf8" /><StatCard label="Metrics bytes" value={metrics.data?.length || 0} icon={Database} color="#67e8f9" /></div><section className="panel"><div className="panel-head"><div className="panel-title">Service health</div><span className="code">{API_BASE_URL}</span></div><div className="panel-pad stack">{health.isLoading ? <LoadingState /> : null}{health.error ? <ErrorState error={health.error} /> : null}{health.data ? <div className="card"><div className="spread"><strong>API Gateway</strong><StatusBadge status={health.data.status} /></div><pre className="code" style={{ marginTop: 12, whiteSpace: 'pre-wrap' }}>{stringifyShort(health.data, 800)}</pre></div> : null}{agentHealth.error ? <ErrorState error={agentHealth.error} /> : null}{agentHealth.data ? <div className="card"><div className="spread"><strong>Agent health</strong><StatusBadge status="HEALTHY" /></div><pre className="code" style={{ marginTop: 12, whiteSpace: 'pre-wrap' }}>{stringifyShort(agentHealth.data, 800)}</pre></div> : null}{metrics.error ? <ErrorState error={metrics.error} /> : null}{metrics.data ? <div className="card"><strong>Prometheus endpoint</strong><pre className="code" style={{ marginTop: 12, maxHeight: 220, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{metrics.data.slice(0, 3000)}</pre></div> : null}</div></section></div>;
}
