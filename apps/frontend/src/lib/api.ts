'use client';

import { getToken } from './auth';
import type { Agent, AgentHealthSummary, Approval, AuditLog, AuthResponse, HealthResponse, PageResult, Task, User, Workflow } from './types';

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
  if (!headers.has('Content-Type') && init.body) headers.set('Content-Type', 'application/json');
  const token = getToken();
  if (token) headers.set('Authorization', 'Bearer ' + token);
  const response = await fetch(API_BASE_URL + path, { ...init, headers });
  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    const message = typeof payload === 'string' ? payload : payload.message || 'API request failed';
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
};
