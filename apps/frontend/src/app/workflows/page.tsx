'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Play, Search, Square, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { api } from '@/lib/api';
import { EmptyState, ErrorState, LoadingState, StatusBadge, formatDate } from '@/components/ui';

function WorkflowModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [goal, setGoal] = useState('');
  const [description, setDescription] = useState('');
  const create = useMutation({
    mutationFn: () => api.workflows.create({ name, goal, description: description || undefined }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['workflows'] }); onClose(); },
  });
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2 className="page-title">New workflow</h2>
        <div className="form-grid">
          <label className="label">Name<input className="input" value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label className="label">Goal<textarea className="textarea" value={goal} onChange={(e) => setGoal(e.target.value)} /></label>
          <label className="label">Description<textarea className="textarea" value={description} onChange={(e) => setDescription(e.target.value)} /></label>
          {create.error ? <ErrorState error={create.error} /> : null}
          <div className="spread"><button className="btn" onClick={onClose}>Cancel</button><button className="btn btn-primary" disabled={!name.trim() || !goal.trim() || create.isPending} onClick={() => create.mutate()}><Plus size={14} /> Create</button></div>
        </div>
      </div>
    </div>
  );
}

export default function WorkflowsPage() {
  const queryClient = useQueryClient();
  const [showNew, setShowNew] = useState(false);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const workflows = useQuery({ queryKey: ['workflows', search, status], queryFn: () => api.workflows.list({ page: 1, limit: 50, search, status }) });
  const start = useMutation({ mutationFn: api.workflows.start, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['workflows'] }) });
  const cancel = useMutation({ mutationFn: api.workflows.cancel, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['workflows'] }) });
  const remove = useMutation({ mutationFn: api.workflows.remove, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['workflows'] }) });
  const rows = workflows.data?.data || [];
  const running = rows.filter((row) => row.status === 'RUNNING').length;

  return (
    <div className="page-wide">
      {showNew ? <WorkflowModal onClose={() => setShowNew(false)} /> : null}
      <div className="page-header">
        <div><h1 className="page-title">Workflows</h1><p className="page-subtitle">{running} running / {workflows.data?.total || 0} total</p></div>
        <button className="btn btn-primary" onClick={() => setShowNew(true)}><Plus size={14} /> New workflow</button>
      </div>
      <div className="toolbar">
        <div style={{ position: 'relative', width: 300 }}><Search size={14} style={{ position: 'absolute', left: 10, top: 11, color: '#64748b' }} /><input className="input" style={{ paddingLeft: 32 }} value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search workflows" /></div>
        <select className="select" style={{ width: 180 }} value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All statuses</option><option>PENDING</option><option>RUNNING</option><option>PAUSED</option><option>COMPLETED</option><option>FAILED</option><option>CANCELLED</option></select>
      </div>
      <section className="panel">
        {workflows.isLoading ? <div className="panel-pad"><LoadingState /></div> : null}
        {workflows.error ? <div className="panel-pad"><ErrorState error={workflows.error} /></div> : null}
        {!workflows.isLoading && rows.length === 0 ? <div className="panel-pad"><EmptyState title="No workflows returned" /></div> : null}
        {rows.length ? <div className="table-wrap"><table className="table"><thead><tr><th>Workflow</th><th>Status</th><th>Goal</th><th>Started</th><th>Created</th><th>Actions</th></tr></thead><tbody>
          {rows.map((workflow) => <tr key={workflow.id}><td><strong>{workflow.name}</strong><div className="code">{workflow.id}</div></td><td><StatusBadge status={workflow.status} /></td><td className="muted">{workflow.goal}</td><td>{formatDate(workflow.startedAt)}</td><td>{formatDate(workflow.createdAt)}</td><td><div className="row"><button className="btn" disabled={workflow.status === 'RUNNING' || start.isPending} onClick={() => start.mutate(workflow.id)}><Play size={13} /> Start</button><button className="btn" disabled={workflow.status === 'CANCELLED' || cancel.isPending} onClick={() => cancel.mutate(workflow.id)}><Square size={13} /> Cancel</button><button className="btn btn-danger" disabled={remove.isPending} onClick={() => remove.mutate(workflow.id)}><Trash2 size={13} /></button></div></td></tr>)}
        </tbody></table></div> : null}
      </section>
    </div>
  );
}
