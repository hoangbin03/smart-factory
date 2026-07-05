'use client';

import { useQuery } from '@tanstack/react-query';
import { Search } from 'lucide-react';
import { useState } from 'react';
import { api } from '@/lib/api';
import { EmptyState, ErrorState, LoadingState, StatusBadge, formatDate, stringifyShort } from '@/components/ui';

export default function AuditPage() {
  const [entityType, setEntityType] = useState('');
  const [action, setAction] = useState('');
  const logs = useQuery({ queryKey: ['audit', entityType, action], queryFn: () => api.audit.list({ page: 1, limit: 100, entityType, action }) });
  const rows = logs.data?.data || [];
  return <div className="page-wide"><div className="page-header"><div><h1 className="page-title">Audit Trail</h1><p className="page-subtitle">Persisted audit log records from the backend.</p></div></div><div className="toolbar"><div style={{ position: 'relative', width: 260 }}><Search size={14} style={{ position: 'absolute', left: 10, top: 11, color: '#64748b' }} /><input className="input" style={{ paddingLeft: 32 }} placeholder="Entity type" value={entityType} onChange={(e) => setEntityType(e.target.value)} /></div><select className="select" style={{ width: 170 }} value={action} onChange={(e) => setAction(e.target.value)}><option value="">All actions</option><option>CREATE</option><option>UPDATE</option><option>DELETE</option><option>EXECUTE</option><option>APPROVE</option><option>REJECT</option><option>LOGIN</option><option>LOGOUT</option></select></div><section className="panel"><div className="panel-head"><div className="panel-title"><span className="live-dot" /> Event records</div><span className="muted">{logs.data?.total || 0} total</span></div>{logs.isLoading ? <div className="panel-pad"><LoadingState /></div> : null}{logs.error ? <div className="panel-pad"><ErrorState error={logs.error} /></div> : null}{!logs.isLoading && rows.length === 0 ? <div className="panel-pad"><EmptyState title="No audit records returned" /></div> : null}{rows.length ? <div className="table-wrap"><table className="table"><thead><tr><th>Time</th><th>Action</th><th>Entity</th><th>Actor</th><th>Changes</th><th>Metadata</th></tr></thead><tbody>{rows.map((log) => <tr key={log.id}><td>{formatDate(log.createdAt)}<div className="code">{log.id}</div></td><td><StatusBadge status={log.action} /></td><td><strong>{log.entityType}</strong><div className="code">{log.entityId || '-'}</div></td><td>{log.actorType}<div className="code">{log.actorId || '-'}</div></td><td className="code">{stringifyShort(log.changes)}</td><td className="code">{stringifyShort(log.metadata)}</td></tr>)}</tbody></table></div> : null}</section></div>;
}
