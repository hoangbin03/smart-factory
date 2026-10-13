'use client';

import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { AlertCircle, Bot, CheckCircle, FolderGit2, GitBranch, ListTodo, Network, Play, TrendingUp } from 'lucide-react';
import { api } from '@/lib/api';
import { EmptyState, ErrorState, LoadingState, StatCard, StatusBadge, formatDate } from '@/components/ui';

export default function DashboardPage() {
  const workflows = useQuery({ queryKey: ['workflows', 'recent'], queryFn: () => api.workflows.list({ page: 1, limit: 6 }) });
  const workflowStats = useQuery({ queryKey: ['workflows', 'stats'], queryFn: api.workflows.stats });
  const tasks = useQuery({ queryKey: ['tasks', 'dashboard'], queryFn: () => api.tasks.list({ page: 1, limit: 100 }) });
  const agents = useQuery({ queryKey: ['agents', 'dashboard'], queryFn: () => api.agents.list({ page: 1, limit: 20 }) });
  const agentHealth = useQuery({ queryKey: ['agents', 'health'], queryFn: api.agents.health });
  const approvals = useQuery({ queryKey: ['approvals', 'pending'], queryFn: api.approvals.pending, retry: false });
  const projects = useQuery({ queryKey: ['projects', 'dashboard'], queryFn: () => api.nexus.projects.list(), retry: false });

  const stats = workflowStats.data || {};
  const taskRows = tasks.data?.data || [];
  const agentRows = agents.data?.data || [];
  const projectRows = projects.data?.data || [];
  const kgReady = projectRows.filter((p: any) => p.kg_status === 'READY').length;
  const pendingApprovals = approvals.data?.length || 0;
  const completed = Number(stats.COMPLETED || 0);
  const failed = Number(stats.FAILED || 0);
  const successRate = completed + failed > 0 ? Math.round((completed / (completed + failed)) * 100) : 0;

  return (
    <div className="page-wide">
      <div className="page-header">
        <div>
          <h1 className="page-title">Factory Dashboard</h1>
          <p className="page-subtitle">Live overview from API Gateway.</p>
        </div>
        <Link href="/workflows" className="btn btn-primary"><Play size={14} /> New workflow</Link>
      </div>

      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <StatCard label="Running workflows" value={stats.RUNNING || 0} sub={(workflows.data?.total || 0) + ' total'} icon={GitBranch} color="#818cf8" />
        <StatCard label="Pending tasks" value={taskRows.filter((t) => t.status === 'PENDING' || t.status === 'QUEUED').length} sub={taskRows.filter((t) => t.status === 'COMPLETED').length + ' completed'} icon={ListTodo} color="#67e8f9" />
        <StatCard label="Agents" value={agentHealth.data?.total || agentRows.length} sub="registered" icon={Bot} color="#34d399" />
        <StatCard label="Pending approvals" value={pendingApprovals} sub={approvals.error ? 'login required' : 'awaiting decision'} icon={AlertCircle} color="#fbbf24" />
      </div>
      <div className="grid grid-3" style={{ marginBottom: 20 }}>
        <StatCard label="Completed workflows" value={completed} icon={CheckCircle} color="#10b981" />
        <StatCard label="Success rate" value={successRate + '%'} sub="completed vs failed" icon={TrendingUp} color="#f59e0b" />
        <StatCard label="Projects" value={projectRows.length} sub={kgReady + ' with knowledge graph'} icon={FolderGit2} color="#22d3ee" />
      </div>

      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1fr) 360px' }}>
        <section className="panel">
          <div className="panel-head"><div className="panel-title"><GitBranch size={16} /> Recent workflows</div><Link href="/workflows" className="btn">View all</Link></div>
          <div className="table-wrap">
            {workflows.isLoading ? <div className="panel-pad"><LoadingState /></div> : null}
            {workflows.error ? <div className="panel-pad"><ErrorState error={workflows.error} /></div> : null}
            {!workflows.isLoading && workflows.data?.data.length === 0 ? <div className="panel-pad"><EmptyState title="No workflows yet" /></div> : null}
            {workflows.data?.data.length ? (
              <table className="table"><thead><tr><th>Name</th><th>Status</th><th>Goal</th><th>Created</th></tr></thead><tbody>
                {workflows.data.data.map((workflow) => <tr key={workflow.id}><td><strong>{workflow.name}</strong><div className="code">{workflow.id}</div></td><td><StatusBadge status={workflow.status} /></td><td className="muted">{workflow.goal}</td><td>{formatDate(workflow.createdAt)}</td></tr>)}
              </tbody></table>
            ) : null}
          </div>
        </section>

        <section className="panel">
          <div className="panel-head"><div className="panel-title"><Bot size={16} /> Agent fleet</div></div>
          <div className="panel-pad stack">
            {agents.isLoading ? <LoadingState /> : null}
            {agents.error ? <ErrorState error={agents.error} /> : null}
            {agentRows.length === 0 && !agents.isLoading ? <EmptyState title="No agents registered" /> : null}
            {agentRows.map((agent) => <div key={agent.id} className="card"><div className="spread"><div><strong>{agent.name}</strong><div className="muted" style={{ fontSize: 12 }}>{agent.role} / {agent.runtime}</div></div><StatusBadge status={agent.status} /></div></div>)}
          </div>
        </section>
      </div>

      <section className="panel" style={{ marginTop: 20 }}>
        <div className="panel-head"><div className="panel-title"><FolderGit2 size={16} /> Projects & Knowledge Graphs</div><Link href="/projects" className="btn">View all</Link></div>
        <div className="table-wrap">
          {projects.isLoading ? <div className="panel-pad"><LoadingState /></div> : null}
          {!projects.isLoading && projectRows.length === 0 ? <div className="panel-pad"><EmptyState title="Chưa có project" /></div> : null}
          {projectRows.length ? (
            <table className="table"><thead><tr><th>Project</th><th>Nguồn</th><th>Knowledge Graph</th><th>Tạo lúc</th><th></th></tr></thead><tbody>
              {projectRows.slice(0, 6).map((p: any) => (
                <tr key={p.id}>
                  <td><strong>{p.name}</strong><div className="muted" style={{ fontSize: 12 }}>{p.description}</div></td>
                  <td className="muted">{p.source_type}</td>
                  <td>{p.kg_status === 'READY' ? <span className="muted">{p.node_count} nodes · {p.edge_count} edges</span> : <span className="muted">{p.kg_status === 'NONE' ? 'chưa build' : p.kg_status.toLowerCase()}</span>}</td>
                  <td>{formatDate(p.created_at)}</td>
                  <td><Link href={`/projects/${p.id}`} className="btn"><Network size={13} /> Graph</Link></td>
                </tr>
              ))}
            </tbody></table>
          ) : null}
        </div>
      </section>
    </div>
  );
}
