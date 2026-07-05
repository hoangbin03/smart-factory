// ─────────────────────────────────────────
// Core Domain Enums
// ─────────────────────────────────────────

export enum WorkflowStatus {
  PENDING = 'PENDING',
  RUNNING = 'RUNNING',
  PAUSED = 'PAUSED',
  COMPLETED = 'COMPLETED',
  FAILED = 'FAILED',
  CANCELLED = 'CANCELLED',
}

export enum TaskStatus {
  PENDING = 'PENDING',
  QUEUED = 'QUEUED',
  RUNNING = 'RUNNING',
  COMPLETED = 'COMPLETED',
  FAILED = 'FAILED',
  SKIPPED = 'SKIPPED',
  CANCELLED = 'CANCELLED',
}

export enum AgentStatus {
  HEALTHY = 'HEALTHY',
  DEGRADED = 'DEGRADED',
  OFFLINE = 'OFFLINE',
  MAINTENANCE = 'MAINTENANCE',
}

export enum AgentRole {
  ARCHITECT = 'architect',
  PLANNER = 'planner',
  DEVELOPER = 'developer',
  REVIEWER = 'reviewer',
  QA = 'qa',
  DEVOPS = 'devops',
}

export enum ApprovalStatus {
  PENDING = 'PENDING',
  APPROVED = 'APPROVED',
  REJECTED = 'REJECTED',
  ESCALATED = 'ESCALATED',
  EXPIRED = 'EXPIRED',
}

export enum AuditAction {
  CREATE = 'CREATE',
  UPDATE = 'UPDATE',
  DELETE = 'DELETE',
  EXECUTE = 'EXECUTE',
  APPROVE = 'APPROVE',
  REJECT = 'REJECT',
  LOGIN = 'LOGIN',
  LOGOUT = 'LOGOUT',
}

export enum MemoryType {
  EPISODIC = 'episodic',
  SEMANTIC = 'semantic',
  PROCEDURAL = 'procedural',
}

// ─────────────────────────────────────────
// Core Domain Interfaces
// ─────────────────────────────────────────

export interface BaseEntity {
  id: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface Workflow extends BaseEntity {
  name: string;
  description?: string;
  status: WorkflowStatus;
  goal: string;
  config: Record<string, unknown>;
  metadata: Record<string, unknown>;
  createdBy?: string;
  startedAt?: Date;
  completedAt?: Date;
}

export interface Task extends BaseEntity {
  workflowId: string;
  name: string;
  description?: string;
  status: TaskStatus;
  agentId?: string;
  goal: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  constraints: Record<string, unknown>;
  order: number;
  retryCount: number;
  maxRetries: number;
  startedAt?: Date;
  completedAt?: Date;
}

export interface Agent extends BaseEntity {
  agentId: string;
  name: string;
  description?: string;
  role: AgentRole | string;
  runtime: string;
  capabilities: string[];
  tools: string[];
  status: AgentStatus;
  config: Record<string, unknown>;
  version: string;
  lastSeenAt?: Date;
}

export interface Approval extends BaseEntity {
  workflowId?: string;
  taskId?: string;
  title: string;
  description?: string;
  status: ApprovalStatus;
  requestedBy?: string;
  approvedBy?: string;
  decisionAt?: Date;
  expiresAt?: Date;
  notes?: string;
  metadata: Record<string, unknown>;
}

export interface AuditLog {
  id: string;
  action: AuditAction;
  entityType: string;
  entityId?: string;
  actorId?: string;
  actorType: string;
  changes: Record<string, unknown>;
  metadata: Record<string, unknown>;
  ipAddress?: string;
  userAgent?: string;
  createdAt: Date;
}

export interface AgentMemory extends BaseEntity {
  agentId: string;
  workflowId?: string;
  memoryType: MemoryType;
  key: string;
  value: Record<string, unknown>;
  tags: string[];
  expiresAt?: Date;
}

export interface AgentSession {
  id: string;
  agentId: string;
  workflowId?: string;
  taskId?: string;
  sessionData: Record<string, unknown>;
  startedAt: Date;
  endedAt?: Date;
  createdAt: Date;
}

export interface AgentArtifact {
  id: string;
  agentId: string;
  workflowId?: string;
  taskId?: string;
  artifactType: string;
  name: string;
  content?: string;
  metadata: Record<string, unknown>;
  createdAt: Date;
}

// ─────────────────────────────────────────
// Agent Contract Types
// ─────────────────────────────────────────

export interface AgentTaskInput {
  workflowId: string;
  taskId: string;
  goal: string;
  context: Record<string, unknown>;
  constraints: Record<string, unknown>;
}

export interface AgentTaskOutput {
  success: boolean;
  summary: string;
  artifacts: AgentArtifact[];
  metrics: Record<string, number | string>;
  nextAction: string | null;
  error?: string;
}

// ─────────────────────────────────────────
// API Response Types
// ─────────────────────────────────────────

export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
  timestamp: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

export interface PaginationQuery {
  page?: number;
  limit?: number;
  sortBy?: string;
  sortOrder?: 'ASC' | 'DESC';
  search?: string;
}

// ─────────────────────────────────────────
// User Types
// ─────────────────────────────────────────

export interface User extends BaseEntity {
  email: string;
  username: string;
  fullName?: string;
  role: string;
  isActive: boolean;
  lastLoginAt?: Date;
}

export interface JwtPayload {
  sub: string;
  email: string;
  username: string;
  role: string;
  iat?: number;
  exp?: number;
}
