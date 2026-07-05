'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Search, Square, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { api } from '@/lib/api';
import { EmptyState, ErrorState, LoadingState, StatCard, StatusBadge, duration, formatDate } from '@/components/ui';

function TaskModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const workflows = useQuery({ queryKey: ['workflows', 'for-task'], queryFn: () => api.workflows.list({ page: 1, limit: 100 }) });
  const [workflowId, setWorkflowId] = useState('');
  const [name, setName] = useState('');
  const [goal, setGoal] = useState('');
  const [agentId, setAgentId] = useState('');
  const create = useMutation({ mutationFn: () => api.tasks.create({ workflowId, name, goal, agentId: agentId || undefined }), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['tasks'] }); onClose(); } });
  return <div className="modal-backdrop" onClick={onClose}><div className="modal" onClick={(e) => e.stopPropagation()}><h2 className="page-title">New task</h2><div className="form-grid">
    <label className="label">Workflow<select className="select" value={workflowId} onChange={(e) => setWorkflowId(e.target.value)}><option value="">Select workflow</option>{workflows.data?.data.map((wf) => <option key={wf.id} value={wf.id}>{wf.name}</option>)}</select></label>
    <label className="label">Name<input className="input" value={name} onChange={(e) => setName(e.target.value)} /></label>
    <label className="label">Goal<textarea className="textarea" value={goal} onChange={(e) => setGoal(e.target.value)} /></label>
    <label className="label">Agent id<input className="input" value={agentId} onChange={(e) => setAgentId(e.target.value)} /></label>
    {create.error ? <ErrorState error={create.error} /> : null}
    <div className="spread"><button className="btn" onClick={onClose}>Cancel</button><button className="btn btn-primary" disabled={!workflowId || !name.trim() || !goal.trim() || create.isPending} onClick={() => create.mutate()}><Plus size={14} /> Create</button></div>
  </div></div></div>;
}

export default function TasksPage() {
  const queryClient = useQueryClient();
  const [showNew, setShowNew] = useState(false);
  const [status, setStatus] = useState('');
  const [workflowId, setWorkflowId] = useState('');
  const tasks = useQuery({ queryKey: ['tasks', status, workflowId], queryFn: () => api.tasks.list({ page: 1, limit: 100, status, workflowId }) });
  const workflows = useQuery({ queryKey: ['workflows', 'task-filter'], queryFn: () => api.workflows.list({ page: 1, limit: 100 }) });
  const cancel = useMutation({ mutationFn: api.tasks.cancel, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tasks'] }) });
  const remove = useMutation({ mutationFn: api.tasks.remove, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tasks'] }) });
  const rows = tasks.data?.data || [];
  return <div className="page-wide">{showNew ? <TaskModal onClose={() => setShowNew(false)} /> : null}<div className="page-header"><div><h1 className="page-title">Tasks</h1><p className="page-subtitle">Live task queue from backend.</p></div><button className="btn btn-primary" onClick={() => setShowNew(true)}><Plus size={14} /> New task</button></div>
    <div className="grid grid-4" style={{ marginBottom: 16 }}><StatCard label="Running" value={rows.filter((t) => t.status === 'RUNNING').length} /><StatCard label="Queued" value={rows.filter((t) => t.status === 'QUEUED' || t.status === 'PENDING').length} /><StatCard label="Completed" value={rows.filter((t) => t.status === 'COMPLETED').length} /><StatCard label="Failed" value={rows.filter((t) => t.status === 'FAILED').length} /></div>
    <div className="toolbar"><div style={{ position: 'relative', width: 260 }}><Search size={14} style={{ position: 'absolute', left: 10, top: 11, color: '#64748b' }} /><select className="select" style={{ paddingLeft: 32 }} value={workflowId} onChange={(e) => setWorkflowId(e.target.value)}><option value="">All workflows</option>{workflows.data?.data.map((wf) => <option key={wf.id} value={wf.id}>{wf.name}</option>)}</select></div><select className="select" style={{ width: 170 }} value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All statuses</option><option>PENDING</option><option>QUEUED</option><option>RUNNING</option><option>COMPLETED</option><option>FAILED</option><option>SKIPPED</option><option>CANCELLED</option></select></div>
    <section className="panel">{tasks.isLoading ? <div className="panel-pad"><LoadingState /></div> : null}{tasks.error ? <div className="panel-pad"><ErrorState error={tasks.error} /></div> : null}{!tasks.isLoading && rows.length === 0 ? <div className="panel-pad"><EmptyState title="No tasks returned" /></div> : null}{rows.length ? <div className="table-wrap"><table className="table"><thead><tr><th>Task</th><th>Status</th><th>Agent</th><th>Duration</th><th>Workflow</th><th>Updated</th><th>Actions</th></tr></thead><tbody>{rows.map((task) => <tr key={task.id}><td><strong>{task.name}</strong><div className="muted">{task.goal}</div><div className="code">{task.id}</div></td><td><StatusBadge status={task.status} /></td><td>{task.agentId || '-'}</td><td>{duration(task.startedAt || task.createdAt, task.completedAt)}</td><td className="code">{task.workflowId}</td><td>{formatDate(task.updatedAt)}</td><td><div className="row"><button className="btn" disabled={task.status === 'CANCELLED' || cancel.isPending} onClick={() => cancel.mutate(task.id)}><Square size={13} /> Cancel</button><button className="btn btn-danger" disabled={remove.isPending} onClick={() => remove.mutate(task.id)}><Trash2 size={13} /></button></div></td></tr>)}</tbody></table></div> : null}</section>
  </div>;
}
