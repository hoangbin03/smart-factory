'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, ExternalLink, GitBranch, Plus, Play, Rocket, Search, Square, Trash2, Upload } from 'lucide-react';
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
          <div className="spread">
            <button className="btn" onClick={onClose}>Cancel</button>
            <button className="btn btn-primary" disabled={!name.trim() || !goal.trim() || create.isPending} onClick={() => create.mutate()}><Plus size={14} /> Create</button>
          </div>
        </div>
      </div>
    </div>
  );
}

const IGNORE_SEGMENTS = ['node_modules', '.git', '__pycache__', '.next', 'dist', 'build', '.venv', 'venv'];
const BINARY_RE = /\.(png|jpe?g|gif|ico|svg|pdf|zip|gz|tar|exe|dll|woff2?|ttf|eot|mp4|mp3|wav|wasm|bin)$/i;

async function readFolderFiles(fileList: FileList): Promise<{ path: string; content: string }[]> {
  const out: { path: string; content: string }[] = [];
  for (const f of Array.from(fileList)) {
    const rel = (f as any).webkitRelativePath || f.name;
    const parts = String(rel).split('/');
    if (parts.some((p) => IGNORE_SEGMENTS.includes(p))) continue;
    const relPath = parts.length > 1 ? parts.slice(1).join('/') : f.name; // strip top folder
    if (!relPath || BINARY_RE.test(relPath) || f.size > 500_000) continue;
    try { out.push({ path: relPath, content: await f.text() }); } catch { /* skip */ }
    if (out.length >= 500) break;
  }
  return out;
}

function ImportModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<'git' | 'folder'>('git');
  const [name, setName] = useState('');
  const [goal, setGoal] = useState('');
  const [repoUrl, setRepoUrl] = useState('');
  const [branch, setBranch] = useState('');
  const [token, setToken] = useState('');
  const [files, setFiles] = useState<{ path: string; content: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onPickFolder = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    setFiles(await readFolderFiles(e.target.files));
  };

  const submit = async () => {
    setError(null);
    setBusy(true);
    try {
      if (mode === 'git') {
        if (!repoUrl.trim()) throw new Error('Nhập Git URL');
        await api.workflows.create({
          name: name.trim() || repoUrl.split('/').pop() || 'Imported repo',
          goal: goal.trim() || `Continue and fix the imported project: ${repoUrl}`,
          config: { repoImport: { type: 'git', url: repoUrl.trim(), branch: branch.trim(), token: token.trim() } },
        });
      } else {
        if (!files.length) throw new Error('Chọn một thư mục có file mã nguồn');
        const wf = await api.workflows.create({
          name: name.trim() || 'Imported folder',
          goal: goal.trim() || 'Continue and fix the imported project',
        });
        await api.workflows.importUpload(wf.id, files);
      }
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Import thất bại');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2 className="page-title">Import project</h2>
        <div className="row" style={{ gap: 8, marginBottom: 12 }}>
          <button className={`btn ${mode === 'git' ? 'btn-primary' : ''}`} onClick={() => setMode('git')}><GitBranch size={14} /> Git URL</button>
          <button className={`btn ${mode === 'folder' ? 'btn-primary' : ''}`} onClick={() => setMode('folder')}><Upload size={14} /> Thư mục máy tính</button>
        </div>
        <div className="form-grid">
          <label className="label">Tên (tùy chọn)<input className="input" value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label className="label">Việc cần làm / mục tiêu<textarea className="textarea" value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="VD: Sửa lỗi đăng nhập, thêm chức năng X..." /></label>
          {mode === 'git' ? (
            <>
              <label className="label">Git URL<input className="input" value={repoUrl} onChange={(e) => setRepoUrl(e.target.value)} placeholder="https://github.com/user/repo.git" /></label>
              <label className="label">Branch (tùy chọn)<input className="input" value={branch} onChange={(e) => setBranch(e.target.value)} placeholder="main" /></label>
              <label className="label">Token (repo private, tùy chọn)<input className="input" type="password" value={token} onChange={(e) => setToken(e.target.value)} /></label>
            </>
          ) : (
            <label className="label">Chọn thư mục dự án
              {/* @ts-expect-error webkitdirectory is non-standard */}
              <input className="input" type="file" webkitdirectory="" directory="" multiple onChange={onPickFolder} />
              <span className="muted">{files.length ? `${files.length} file sẽ được import` : 'Chưa chọn (bỏ qua node_modules/.git/ảnh nhị phân)'}</span>
            </label>
          )}
          {error ? <div className="muted" style={{ color: '#dc2626' }}>{error}</div> : null}
          <div className="spread">
            <button className="btn" onClick={onClose}>Cancel</button>
            <button className="btn btn-primary" disabled={busy} onClick={submit}>{busy ? 'Đang import…' : 'Import → tạo workflow'}</button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function WorkflowsPage() {
  const queryClient = useQueryClient();
  const [showNew, setShowNew] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [previewingId, setPreviewingId] = useState<string | null>(null);
  const [deployingId, setDeployingId] = useState<string | null>(null);
  const workflows = useQuery({ queryKey: ['workflows', search, status], queryFn: () => api.workflows.list({ page: 1, limit: 50, search, status }), refetchInterval: 5000 });
  const start = useMutation({ mutationFn: api.workflows.start, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['workflows'] }) });
  const cancel = useMutation({ mutationFn: api.workflows.cancel, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['workflows'] }) });
  const remove = useMutation({ mutationFn: api.workflows.remove, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['workflows'] }) });
  const rows = workflows.data?.data || [];
  const running = rows.filter((row) => row.status === 'RUNNING').length;

  const handleDeploy = async (workflowId: string) => {
    setDeployingId(workflowId);
    try {
      const result = await api.workflows.deploy(workflowId);
      if (result.ok && result.url) {
        window.open(result.url, '_blank');
      } else {
        alert(result.error || 'Deploy failed');
      }
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Deploy failed');
    } finally {
      setDeployingId(null);
    }
  };

  const openPreview = async (workflowId: string) => {
    const previewWindow = window.open('', '_blank');
    setPreviewingId(workflowId);
    try {
      const html = await api.workflows.preview(workflowId);
      const url = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
      if (previewWindow) {
        previewWindow.location.href = url;
      } else {
        window.open(url, '_blank');
      }
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (error) {
      previewWindow?.close();
      alert(error instanceof Error ? error.message : 'Preview failed');
    } finally {
      setPreviewingId(null);
    }
  };

  return (
    <div className="page-wide">
      {showNew ? <WorkflowModal onClose={() => setShowNew(false)} /> : null}
      {showImport ? <ImportModal onClose={() => setShowImport(false)} /> : null}
      <div className="page-header">
        <div><h1 className="page-title">Workflows</h1><p className="page-subtitle">{running} running / {workflows.data?.total || 0} total</p></div>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn" onClick={() => setShowImport(true)}><GitBranch size={14} /> Import project</button>
          <button className="btn btn-primary" onClick={() => setShowNew(true)}><Plus size={14} /> New workflow</button>
        </div>
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
          {rows.map((workflow) => <tr key={workflow.id}><td><strong>{workflow.name}</strong><div className="code">{workflow.id}</div></td><td><StatusBadge status={workflow.status} /></td><td className="muted">{workflow.goal}</td><td>{formatDate(workflow.startedAt)}</td><td>{formatDate(workflow.createdAt)}</td><td><div className="row"><button className="btn" disabled={workflow.status === 'RUNNING' || start.isPending} onClick={() => start.mutate(workflow.id)}><Play size={13} /> Start</button><button className="btn" disabled={previewingId === workflow.id} onClick={() => openPreview(workflow.id)}><ExternalLink size={13} /> Preview</button><button className="btn" onClick={() => api.workflows.download(workflow.id).catch((e) => alert(e instanceof Error ? e.message : 'Download failed'))}><Download size={13} /> Download</button><button className="btn" disabled={deployingId === workflow.id} onClick={() => handleDeploy(workflow.id)}><Rocket size={13} /> {deployingId === workflow.id ? 'Deploying…' : 'Deploy'}</button><button className="btn" disabled={workflow.status === 'CANCELLED' || cancel.isPending} onClick={() => cancel.mutate(workflow.id)}><Square size={13} /> Cancel</button><button className="btn btn-danger" disabled={remove.isPending} onClick={() => remove.mutate(workflow.id)}><Trash2 size={13} /></button></div></td></tr>)}
        </tbody></table></div> : null}
      </section>
    </div>
  );
}
