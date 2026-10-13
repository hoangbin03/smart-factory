export type PageResult<T> = {
  data: T[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
};

export type Workflow = {
  id: string;
  name: string;
  description?: string | null;
  status: string;
  goal: string;
  config: Record<string, unknown>;
  metadata: Record<string, unknown>;
  createdBy?: string | null;
  startedAt?: string | null;
  completedAt?: string | null;
  createdAt: string;
  updatedAt: string;
};

export type WorkflowArtifact = {
  taskId: string;
  agentId?: string | null;
  artifactType: string;
  name: string;
  content: string;
  metadata: Record<string, unknown>;
};
export type Task = {
  id: string;
  workflowId: string;
  name: string;
  description?: string | null;
  status: string;
  agentId?: string | null;
  goal: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  constraints: Record<string, unknown>;
  order: number;
  retryCount: number;
  maxRetries: number;
  startedAt?: string | null;
  completedAt?: string | null;
  createdAt: string;
  updatedAt: string;
};

export type Agent = {
  id: string;
  agentId: string;
  name: string;
  description?: string | null;
  role: string;
  runtime: string;
  capabilities: string[];
  tools: string[];
  status: string;
  config: Record<string, unknown>;
  version: string;
  lastSeenAt?: string | null;
  createdAt: string;
  updatedAt: string;
};

export type Approval = {
  id: string;
  workflowId?: string | null;
  taskId?: string | null;
  title: string;
  description?: string | null;
  status: string;
  requestedBy?: string | null;
  approvedBy?: string | null;
  decisionAt?: string | null;
  expiresAt?: string | null;
  notes?: string | null;
  metadata: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
};

export type AuditLog = {
  id: string;
  action: string;
  entityType: string;
  entityId?: string | null;
  actorId?: string | null;
  actorType: string;
  changes: Record<string, unknown>;
  metadata: Record<string, unknown>;
  ipAddress?: string | null;
  userAgent?: string | null;
  createdAt: string;
};

export type User = {
  id: string;
  email: string;
  username: string;
  role: string;
  fullName?: string | null;
};

export type AuthResponse = {
  accessToken: string;
  user: User;
};

export type HealthResponse = {
  status: string;
  info?: Record<string, unknown>;
  error?: Record<string, unknown>;
  details?: Record<string, unknown>;
};

export type AgentHealthSummary = {
  total: number;
  byStatus: Record<string, number>;
};
