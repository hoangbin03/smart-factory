'use client';

import Link from 'next/link';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle, Plus, XCircle } from 'lucide-react';
import { useState } from 'react';
import { api, ApiError } from '@/lib/api';
import { EmptyState, ErrorState, LoadingState, StatusBadge, formatDate } from '@/components/ui';

function ApprovalModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const workflows = useQuery({ queryKey: ['workflows', 'approval'], queryFn: () => api.workflows.list({ page: 1, limit: 100 }) });
  const [workflowId, setWorkflowId] = useState('');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const create = useMutation({ mutationFn: () => api.approvals.create({ workflowId: workflowId || undefined, title, description: description || undefined }), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['approvals'] }); onClose(); } });
  return <div className="modal-backdrop" onClick={onClose}><div className="modal" onClick={(e) => e.stopPropagation()}><h2 className="page-title">Request approval</h2><div className="form-grid"><label className="label">Workflow<select className="select" value={workflowId} onChange={(e) => setWorkflowId(e.target.value)}><option value="">No workflow</option>{workflows.data?.data.map((wf) => <option key={wf.id} value={wf.id}>{wf.name}</option>)}</select></label><label className="label">Title<input className="input" value={title} onChange={(e) => setTitle(e.target.value)} /></label><label className="label">Description<textarea className="textarea" value={description} onChange={(e) => setDescription(e.target.value)} /></label>{create.error ? <ErrorState error={create.error} /> : null}<div className="spread"><button className="btn" onClick={onClose}>Cancel</button><button className="btn btn-primary" disabled={!title.trim() || create.isPending} onClick={() => create.mutate()}><Plus size={14} /> Create</button></div></div></div></div>;
}

export default function ApprovalsPage() {
  const queryClient = useQueryClient();
  const [showNew, setShowNew] = useState(false);
  const [notes, setNotes] = useState('');
  const approvals = useQuery({ queryKey: ['approvals', 'pending'], queryFn: api.approvals.pending, retry: false });
  const approve = useMutation({ mutationFn: (id: string) => api.approvals.approve(id, notes), onSuccess: () => { setNotes(''); queryClient.invalidateQueries({ queryKey: ['approvals'] }); } });
  const reject = useMutation({ mutationFn: (id: string) => api.approvals.reject(id, notes), onSuccess: () => { setNotes(''); queryClient.invalidateQueries({ queryKey: ['approvals'] }); } });
  const rows = approvals.data || [];
  const needsLogin = approvals.error instanceof ApiError && approvals.error.status === 401;
  return <div className="page">{showNew ? <ApprovalModal onClose={() => setShowNew(false)} /> : null}<div className="page-header"><div><h1 className="page-title">Approvals</h1><p className="page-subtitle">Protected approval decisions from API Gateway.</p></div><button className="btn btn-primary" onClick={() => setShowNew(true)}><Plus size={14} /> Request approval</button></div>
    {needsLogin ? <div className="notice error" style={{ marginBottom: 16 }}>Login is required for approval endpoints. <Link href="/auth" style={{ textDecoration: 'underline' }}>Open auth</Link></div> : null}
    <label className="label" style={{ marginBottom: 16 }}>Decision notes<input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} /></label>
    {approvals.isLoading ? <LoadingState /> : null}{approvals.error && !needsLogin ? <ErrorState error={approvals.error} /> : null}{!approvals.isLoading && rows.length === 0 && !approvals.error ? <EmptyState title="No pending approvals" /> : null}
    <div className="stack">{rows.map((approval) => <section className="panel panel-pad" key={approval.id}><div className="spread"><div><h2 style={{ fontSize: 15, fontWeight: 760 }}>{approval.title}</h2><p className="muted" style={{ marginTop: 6 }}>{approval.description || '-'}</p></div><StatusBadge status={approval.status} /></div><div className="grid grid-2" style={{ marginTop: 14 }}><div className="code">workflow: {approval.workflowId || '-'}</div><div className="code">task: {approval.taskId || '-'}</div><div className="code">requested: {approval.requestedBy || '-'}</div><div className="code">created: {formatDate(approval.createdAt)}</div></div><div className="row" style={{ justifyContent: 'flex-end', marginTop: 16 }}><button className="btn btn-danger" disabled={reject.isPending} onClick={() => reject.mutate(approval.id)}><XCircle size={13} /> Reject</button><button className="btn btn-primary" disabled={approve.isPending} onClick={() => approve.mutate(approval.id)}><CheckCircle size={13} /> Approve</button></div></section>)}</div>
  </div>;
}
