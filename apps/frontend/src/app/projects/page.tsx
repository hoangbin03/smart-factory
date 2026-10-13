'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { FolderGit2, GitBranch, Network, Plus, Trash2, Upload, FolderPlus } from 'lucide-react';
import { useState } from 'react';
import { api } from '@/lib/api';
import { EmptyState, ErrorState, LoadingState, formatDate } from '@/components/ui';

const IGNORE = ['node_modules', '.git', '__pycache__', '.next', 'dist', 'build', '.venv', 'venv'];
const BINARY_RE = /\.(png|jpe?g|gif|ico|svg|pdf|zip|gz|tar|exe|dll|woff2?|ttf|eot|mp4|mp3|wav|wasm|bin)$/i;

async function readFolder(list: FileList): Promise<{ path: string; content: string }[]> {
  const out: { path: string; content: string }[] = [];
  for (const f of Array.from(list)) {
    const rel = (f as any).webkitRelativePath || f.name;
    const parts = String(rel).split('/');
    if (parts.some((p) => IGNORE.includes(p))) continue;
    const relPath = parts.length > 1 ? parts.slice(1).join('/') : f.name;
    if (!relPath || BINARY_RE.test(relPath) || f.size > 500_000) continue;
    try { out.push({ path: relPath, content: await f.text() }); } catch { /* skip */ }
    if (out.length >= 500) break;
  }
  return out;
}

function CreateModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [mode, setMode] = useState<'empty' | 'git' | 'folder'>('git');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [repoUrl, setRepoUrl] = useState('');
  const [branch, setBranch] = useState('');
  const [token, setToken] = useState('');
  const [files, setFiles] = useState<{ path: string; content: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setError(null); setBusy(true);
    try {
      if (mode === 'git' && !repoUrl.trim()) throw new Error('Nhập Git URL');
      if (mode === 'folder' && !files.length) throw new Error('Chọn thư mục có mã nguồn');
      const project = await api.nexus.projects.create({
        name: name.trim() || (mode === 'git' ? repoUrl.split('/').pop() || 'Imported repo' : 'New project'),
        description,
        source_type: mode,
        repo_url: mode === 'git' ? repoUrl.trim() : '',
        branch: branch.trim(),
        token: token.trim(),
      });
      if (mode === 'folder') await api.nexus.projects.importUpload(project.id, files);
      qc.invalidateQueries({ queryKey: ['projects'] });
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Tạo project thất bại');
    } finally { setBusy(false); }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2 className="page-title">New project</h2>
        <div className="row" style={{ gap: 8, marginBottom: 12 }}>
          <button className={`btn ${mode === 'git' ? 'btn-primary' : ''}`} onClick={() => setMode('git')}><GitBranch size={14} /> Git URL</button>
          <button className={`btn ${mode === 'folder' ? 'btn-primary' : ''}`} onClick={() => setMode('folder')}><Upload size={14} /> Thư mục máy</button>
          <button className={`btn ${mode === 'empty' ? 'btn-primary' : ''}`} onClick={() => setMode('empty')}><FolderPlus size={14} /> Trống</button>
        </div>
        <div className="form-grid">
          <label className="label">Tên<input className="input" value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label className="label">Mô tả<input className="input" value={description} onChange={(e) => setDescription(e.target.value)} /></label>
          {mode === 'git' && <>
            <label className="label">Git URL<input className="input" value={repoUrl} onChange={(e) => setRepoUrl(e.target.value)} placeholder="https://github.com/user/repo.git" /></label>
            <label className="label">Branch (tùy chọn)<input className="input" value={branch} onChange={(e) => setBranch(e.target.value)} /></label>
            <label className="label">Token (private, tùy chọn)<input className="input" type="password" value={token} onChange={(e) => setToken(e.target.value)} /></label>
          </>}
          {mode === 'folder' && <label className="label">Chọn thư mục
            {/* @ts-expect-error webkitdirectory non-standard */}
            <input className="input" type="file" webkitdirectory="" directory="" multiple onChange={async (e) => e.target.files && setFiles(await readFolder(e.target.files))} />
            <span className="muted">{files.length ? `${files.length} file` : 'Chưa chọn'}</span>
          </label>}
          {error ? <div className="muted" style={{ color: '#dc2626' }}>{error}</div> : null}
          <div className="spread">
            <button className="btn" onClick={onClose}>Cancel</button>
            <button className="btn btn-primary" disabled={busy} onClick={submit}>{busy ? 'Đang tạo…' : 'Tạo project'}</button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ProjectsPage() {
  const qc = useQueryClient();
  const [showNew, setShowNew] = useState(false);
  const [genId, setGenId] = useState<string | null>(null);
  const projects = useQuery({ queryKey: ['projects'], queryFn: () => api.nexus.projects.list(), refetchInterval: 8000 });
  const remove = useMutation({ mutationFn: (id: string) => api.nexus.projects.remove(id), onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }) });
  const rows = projects.data?.data || [];

  const generate = async (id: string) => {
    setGenId(id);
    try { await api.nexus.projects.generateKg(id); qc.invalidateQueries({ queryKey: ['projects'] }); }
    catch (e) { alert(e instanceof Error ? e.message : 'Generate failed'); }
    finally { setGenId(null); }
  };

  return (
    <div className="page-wide">
      {showNew ? <CreateModal onClose={() => setShowNew(false)} /> : null}
      <div className="page-header">
        <div><h1 className="page-title">Projects</h1><p className="page-subtitle">{projects.data?.total || 0} project · clone git / upload folder / tạo trống</p></div>
        <button className="btn btn-primary" onClick={() => setShowNew(true)}><Plus size={14} /> New project</button>
      </div>
      <section className="panel">
        {projects.isLoading ? <div className="panel-pad"><LoadingState /></div> : null}
        {projects.error ? <div className="panel-pad"><ErrorState error={projects.error} /></div> : null}
        {!projects.isLoading && !rows.length ? <div className="panel-pad"><EmptyState title="Chưa có project" /></div> : null}
        {rows.length ? <div className="table-wrap"><table className="table">
          <thead><tr><th>Project</th><th>Nguồn</th><th>Knowledge Graph</th><th>Tạo lúc</th><th>Actions</th></tr></thead>
          <tbody>
            {rows.map((p: any) => (
              <tr key={p.id}>
                <td><strong>{p.name}</strong><div className="muted" style={{ fontSize: 12 }}>{p.description}</div><div className="code">{p.id}</div></td>
                <td><span className="row" style={{ gap: 6 }}><FolderGit2 size={13} /> {p.source_type}</span>{p.repo_url ? <div className="muted" style={{ fontSize: 11 }}>{p.repo_url}</div> : null}</td>
                <td>
                  {p.kg_status === 'READY'
                    ? <span className="muted">{p.node_count} nodes · {p.edge_count} edges</span>
                    : <span className="muted">{p.kg_status === 'BUILDING' ? 'đang build…' : p.kg_status === 'FAILED' ? 'lỗi' : 'chưa có'}</span>}
                </td>
                <td>{formatDate(p.created_at)}</td>
                <td><div className="row">
                  <button className="btn" disabled={genId === p.id} onClick={() => generate(p.id)}><Network size={13} /> {genId === p.id ? 'Building…' : 'Generate graph'}</button>
                  <Link className="btn" href={`/projects/${p.id}`}><Network size={13} /> Mở graph</Link>
                  <button className="btn btn-danger" disabled={remove.isPending} onClick={() => confirm('Xóa project?') && remove.mutate(p.id)}><Trash2 size={13} /></button>
                </div></td>
              </tr>
            ))}
          </tbody>
        </table></div> : null}
      </section>
    </div>
  );
}
