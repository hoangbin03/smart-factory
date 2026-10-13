'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Database, Search, Upload, Trash2, FileText } from 'lucide-react';
import { api } from '@/lib/api';
import { StatCard, LoadingState, ErrorState, formatDate } from '@/components/ui';

export default function KBSPage() {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState('');
  const [queryResult, setQueryResult] = useState<any>(null);
  const [isQuerying, setIsQuerying] = useState(false);
  
  const [uploadText, setUploadText] = useState('');
  const [uploadTitle, setUploadTitle] = useState('');
  
  const docs = useQuery({ queryKey: ['kbs', 'documents'], queryFn: () => api.kbs.list() });

  const uploadMut = useMutation({
    mutationFn: () => api.kbs.uploadText({ text: uploadText, title: uploadTitle || 'Untitled', tags: 'manual' }),
    onSuccess: () => {
      setUploadText('');
      setUploadTitle('');
      queryClient.invalidateQueries({ queryKey: ['kbs', 'documents'] });
      alert('Document added to KBS');
    },
    onError: (e) => alert('Upload failed: ' + e)
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.kbs.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['kbs', 'documents'] })
  });

  const handleQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setIsQuerying(true);
    try {
      const res = await api.kbs.query({ query, with_answer: true, top_k: 5 });
      setQueryResult(res);
    } catch (error) {
      alert('Query failed');
    } finally {
      setIsQuerying(false);
    }
  };

  return (
    <div className="page-wide">
      <div className="page-header">
        <div>
          <h1 className="page-title"><Database size={24} style={{ display: 'inline', color: '#10b981', verticalAlign: 'middle', marginRight: 8 }}/> Knowledge Base System</h1>
          <p className="page-subtitle">RAG Vector Database for Nexus and Agents.</p>
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        
        {/* Left: Query & Results */}
        <div className="stack" style={{ gap: 24 }}>
          <section className="panel">
            <div className="panel-head"><div className="panel-title"><Search size={16}/> Query KBS (RAG)</div></div>
            <div className="panel-pad">
              <form onSubmit={handleQuery} style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                <input 
                  className="input" 
                  style={{ flex: 1 }}
                  placeholder="Ask a question against the knowledge base..." 
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                />
                <button type="submit" className="btn btn-primary" disabled={!query.trim() || isQuerying}>
                  {isQuerying ? 'Searching...' : 'Search'}
                </button>
              </form>

              {queryResult && (
                <div style={{ marginTop: 16 }}>
                  <div style={{ background: '#1e293b', padding: 16, borderRadius: 8, marginBottom: 16 }}>
                    <h3 style={{ margin: '0 0 8px 0', fontSize: 14, color: '#10b981' }}>Nexus AI Answer</h3>
                    <div style={{ fontSize: 14, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                      {queryResult.answer}
                    </div>
                  </div>
                  
                  <h4 style={{ fontSize: 12, textTransform: 'uppercase', color: '#64748b', marginBottom: 8 }}>Sources Retrieved</h4>
                  <div className="stack" style={{ gap: 8 }}>
                    {queryResult.chunks.map((chunk: any, i: number) => (
                      <div key={i} style={{ background: '#0f172a', padding: 12, borderRadius: 6, fontSize: 13 }}>
                        <div style={{ color: '#38bdf8', marginBottom: 4, fontWeight: 500 }}>{chunk.metadata.title} (Score: {chunk.score.toFixed(2)})</div>
                        <div style={{ color: '#94a3b8' }}>{chunk.text.length > 200 ? chunk.text.substring(0, 200) + '...' : chunk.text}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </section>
        </div>

        {/* Right: Upload & Manage */}
        <div className="stack" style={{ gap: 24 }}>
          <section className="panel">
            <div className="panel-head"><div className="panel-title"><Upload size={16}/> Add Knowledge</div></div>
            <div className="panel-pad stack" style={{ gap: 12 }}>
              <div>
                <label className="label">Document Title</label>
                <input className="input" value={uploadTitle} onChange={e => setUploadTitle(e.target.value)} placeholder="e.g. Coding Guidelines 2026"/>
              </div>
              <div>
                <label className="label">Content</label>
                <textarea className="input" style={{ height: 120, resize: 'vertical' }} value={uploadText} onChange={e => setUploadText(e.target.value)} placeholder="Paste text content here..."/>
              </div>
              <button className="btn btn-primary" onClick={() => uploadMut.mutate()} disabled={!uploadText.trim() || uploadMut.isPending}>
                {uploadMut.isPending ? 'Ingesting...' : 'Ingest to ChromaDB'}
              </button>
            </div>
          </section>

          <section className="panel">
            <div className="panel-head">
              <div className="panel-title"><FileText size={16}/> Indexed Documents ({docs.data?.total || 0})</div>
            </div>
            <div className="table-wrap">
              {docs.isLoading && <div className="panel-pad"><LoadingState/></div>}
              {docs.error && <div className="panel-pad"><ErrorState error={docs.error}/></div>}
              <table className="table">
                <thead><tr><th>Title / ID</th><th>Source</th><th>Action</th></tr></thead>
                <tbody>
                  {docs.data?.data?.map((doc: any) => (
                    <tr key={doc.id}>
                      <td><strong>{doc.title || 'Untitled'}</strong><div className="muted" style={{ fontSize: 11 }}>{doc.id}</div></td>
                      <td className="muted">{doc.source}</td>
                      <td>
                        <button className="btn btn-danger btn-sm" onClick={() => deleteMut.mutate(doc.id)}><Trash2 size={14}/></button>
                      </td>
                    </tr>
                  ))}
                  {docs.data?.data?.length === 0 && <tr><td colSpan={3} className="text-center muted">No documents in KBS</td></tr>}
                </tbody>
              </table>
            </div>
          </section>
        </div>

      </div>
    </div>
  );
}
