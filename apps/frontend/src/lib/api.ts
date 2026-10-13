'use client';

import { getToken } from './auth';
import type { Agent, AgentHealthSummary, Approval, AuditLog, AuthResponse, HealthResponse, PageResult, Task, User, Workflow, WorkflowArtifact } from './types';

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3000').replace(/\/$/, '');

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function toQuery(params: Record<string, string | number | undefined>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') search.set(key, String(value));
  });
  const query = search.toString();
  return query ? '?' + query : '';
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has('Content-Type') && init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const token = getToken();
  if (token) headers.set('Authorization', 'Bearer ' + token);
  const response = await fetch(API_BASE_URL + path, { ...init, headers });
  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    const message = typeof payload === 'string' ? payload : (payload as any).message || 'API request failed';
    throw new ApiError(message, response.status);
  }
  return payload as T;
}

const NEXUS_BASE_URL = (process.env.NEXT_PUBLIC_NEXUS_URL || 'http://localhost:8100').replace(/\/$/, '');
const KBS_BASE_URL = (process.env.NEXT_PUBLIC_KBS_URL || 'http://localhost:8200').replace(/\/$/, '');

async function requestService<T>(baseUrl: string, path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has('Content-Type') && init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const response = await fetch(baseUrl + path, { ...init, headers });
  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    const message = typeof payload === 'string' ? payload : (payload as any).message || 'API request failed';
    throw new ApiError(message, response.status);
  }
  return payload as T;
}

export const api = {
  auth: {
    login: (body: { email: string; password: string }) => request<AuthResponse>('/api/auth/login', { method: 'POST', body: JSON.stringify(body) }),
    register: (body: { email: string; username: string; password: string; fullName?: string }) => request<AuthResponse>('/api/auth/register', { method: 'POST', body: JSON.stringify(body) }),
    me: () => request<User>('/api/auth/me'),
  },
  workflows: {
    list: (params: { page?: number; limit?: number; status?: string; search?: string } = {}) => request<PageResult<Workflow>>('/api/v1/workflows' + toQuery(params)),
    stats: () => request<Record<string, number>>('/api/v1/workflows/stats'),
    create: (body: { name: string; description?: string; goal: string; config?: Record<string, unknown>; metadata?: Record<string, unknown> }) => request<Workflow>('/api/v1/workflows', { method: 'POST', body: JSON.stringify(body) }),
    start: (id: string) => request<Workflow>('/api/v1/workflows/' + id + '/start', { method: 'PATCH' }),
    artifacts: (id: string) => request<WorkflowArtifact[]>('/api/v1/workflows/' + id + '/artifacts'),
    preview: (id: string) => request<string>('/api/v1/workflows/' + id + '/preview'),
    download: async (id: string) => {
      const token = getToken();
      const res = await fetch(API_BASE_URL + '/api/v1/workflows/' + id + '/download', {
        headers: token ? { Authorization: 'Bearer ' + token } : undefined,
      });
      if (!res.ok) throw new ApiError('Download failed', res.status);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `workflow-${id}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    },
    importGit: (id: string, body: { repo_url: string; branch?: string; token?: string }) => request<{ ok: boolean; files?: number; output?: string }>('/api/v1/workflows/' + id + '/import/git', { method: 'POST', body: JSON.stringify(body) }),
    importUpload: (id: string, files: { path: string; content: string }[]) => request<{ ok: boolean; files?: number; skipped?: number }>('/api/v1/workflows/' + id + '/import/upload', { method: 'POST', body: JSON.stringify({ files }) }),
    deploy: (id: string) => request<{ ok: boolean; url?: string; port?: number; stack?: string; reachable?: boolean; error?: string }>('/api/v1/workflows/' + id + '/deploy', { method: 'POST' }),
    undeploy: (id: string) => request<{ ok: boolean }>('/api/v1/workflows/' + id + '/undeploy', { method: 'POST' }),
    cancel: (id: string) => request<Workflow>('/api/v1/workflows/' + id + '/cancel', { method: 'PATCH' }),
    remove: (id: string) => request<void>('/api/v1/workflows/' + id, { method: 'DELETE' }),
  },
  tasks: {
    list: (params: { page?: number; limit?: number; workflowId?: string; status?: string } = {}) => request<PageResult<Task>>('/api/v1/tasks' + toQuery(params)),
    create: (body: { workflowId: string; name: string; description?: string; agentId?: string; goal: string; input?: Record<string, unknown>; constraints?: Record<string, unknown>; order?: number }) => request<Task>('/api/v1/tasks', { method: 'POST', body: JSON.stringify(body) }),
    cancel: (id: string) => request<Task>('/api/v1/tasks/' + id + '/cancel', { method: 'PATCH' }),
    remove: (id: string) => request<void>('/api/v1/tasks/' + id, { method: 'DELETE' }),
  },
  agents: {
    list: (params: { page?: number; limit?: number; status?: string; role?: string; search?: string } = {}) => request<PageResult<Agent>>('/api/v1/agents' + toQuery(params)),
    health: () => request<AgentHealthSummary>('/api/v1/agents/health'),
    heartbeat: (agentId: string) => request<Agent>('/api/v1/agents/' + agentId + '/heartbeat', { method: 'PATCH' }),
  },
  approvals: {
    pending: () => request<Approval[]>('/api/v1/approvals/pending'),
    create: (body: { workflowId?: string; taskId?: string; title: string; description?: string }) => request<Approval>('/api/v1/approvals', { method: 'POST', body: JSON.stringify(body) }),
    approve: (id: string, notes?: string) => request<Approval>('/api/v1/approvals/' + id + '/approve', { method: 'PATCH', body: JSON.stringify({ notes }) }),
    reject: (id: string, notes?: string) => request<Approval>('/api/v1/approvals/' + id + '/reject', { method: 'PATCH', body: JSON.stringify({ notes }) }),
  },
  audit: {
    list: (params: { page?: number; limit?: number; entityType?: string; entityId?: string; actorId?: string; action?: string } = {}) => request<PageResult<AuditLog>>('/api/v1/audit' + toQuery(params)),
  },
  health: () => request<HealthResponse>('/api/health'),
  metrics: () => request<string>('/api/metrics'),
  nexus: {
    snapshot: () => requestService<any>(NEXUS_BASE_URL, '/api/v1/monitor/snapshot'),
    agents: () => requestService<any>(NEXUS_BASE_URL, '/api/v1/agents'),
    agentStats: (id: string) => requestService<any>(NEXUS_BASE_URL, `/api/v1/agents/${id}/stats`),
    updateAgent: (id: string, body: any) => requestService<any>(NEXUS_BASE_URL, `/api/v1/agents/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    tools: () => requestService<any>(NEXUS_BASE_URL, '/api/v1/tools'),
    skills: {
      list: () => requestService<any>(NEXUS_BASE_URL, '/api/v1/skills'),
      create: (body: any) => requestService<any>(NEXUS_BASE_URL, '/api/v1/skills', { method: 'POST', body: JSON.stringify(body) }),
      update: (id: string, body: any) => requestService<any>(NEXUS_BASE_URL, `/api/v1/skills/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
      remove: (id: string) => requestService<any>(NEXUS_BASE_URL, `/api/v1/skills/${id}`, { method: 'DELETE' }),
    },
    chat: (body: { message: string, history: any[] }) => requestService<{ reply: string }>(NEXUS_BASE_URL, '/api/v1/chat', { method: 'POST', body: JSON.stringify(body) }),
    projects: {
      list: () => requestService<any>(NEXUS_BASE_URL, '/api/v1/projects/'),
      get: (id: string) => requestService<any>(NEXUS_BASE_URL, `/api/v1/projects/${id}`),
      create: (body: { name: string; description?: string; source_type: string; repo_url?: string; branch?: string; token?: string }) => requestService<any>(NEXUS_BASE_URL, '/api/v1/projects/', { method: 'POST', body: JSON.stringify(body) }),
      remove: (id: string) => requestService<void>(NEXUS_BASE_URL, `/api/v1/projects/${id}`, { method: 'DELETE' }),
      importUpload: (id: string, files: { path: string; content: string }[]) => requestService<any>(NEXUS_BASE_URL, `/api/v1/projects/${id}/import/upload`, { method: 'POST', body: JSON.stringify({ files }) }),
      generateKg: (id: string) => requestService<any>(NEXUS_BASE_URL, `/api/v1/projects/${id}/kg/generate`, { method: 'POST' }),
      getKg: (id: string) => requestService<{ nodes: any[]; edges: any[] }>(NEXUS_BASE_URL, `/api/v1/projects/${id}/kg`),
      queryKg: (id: string, query: string) => requestService<{ answer: string }>(NEXUS_BASE_URL, `/api/v1/projects/${id}/kg/query`, { method: 'POST', body: JSON.stringify({ query }) }),
      listRuns: (id: string) => requestService<{ data: any[] }>(NEXUS_BASE_URL, `/api/v1/projects/${id}/workflows`),
      createRun: (id: string, body: { goal: string; name?: string; agents?: string[] }) => requestService<any>(NEXUS_BASE_URL, `/api/v1/projects/${id}/workflows`, { method: 'POST', body: JSON.stringify(body) }),
      startRun: (id: string, wfId: string) => requestService<any>(NEXUS_BASE_URL, `/api/v1/projects/${id}/workflows/${wfId}/start`, { method: 'POST' }),
    },
  },
  kbs: {
    list: (collection = 'nexus-kb') => requestService<any>(KBS_BASE_URL, `/api/v1/documents?collection=${collection}`),
    query: (body: { query: string; collection?: string; top_k?: number; with_answer?: boolean }) => requestService<any>(KBS_BASE_URL, '/api/v1/query', { method: 'POST', body: JSON.stringify(body) }),
    remove: (id: string, collection = 'nexus-kb') => requestService<void>(KBS_BASE_URL, `/api/v1/documents/${id}?collection=${collection}`, { method: 'DELETE' }),
    uploadText: (body: { text: string; title: string; tags: string }) => {
      const formData = new FormData();
      formData.append('text', body.text);
      formData.append('title', body.title);
      formData.append('tags', body.tags);
      return requestService<any>(KBS_BASE_URL, '/api/v1/documents', { method: 'POST', body: formData });
    }
  }
};
