// ─────────────────────────────────────────
// NATS Event Subjects
// ─────────────────────────────────────────

export const EventSubjects = {
  // Workflow Events
  WORKFLOW_CREATED: 'workflow.created',
  WORKFLOW_STARTED: 'workflow.started',
  WORKFLOW_COMPLETED: 'workflow.completed',
  WORKFLOW_FAILED: 'workflow.failed',
  WORKFLOW_CANCELLED: 'workflow.cancelled',
  WORKFLOW_PAUSED: 'workflow.paused',

  // Task Events
  TASK_CREATED: 'task.created',
  TASK_QUEUED: 'task.queued',
  TASK_STARTED: 'task.started',
  TASK_COMPLETED: 'task.completed',
  TASK_FAILED: 'task.failed',
  TASK_CANCELLED: 'task.cancelled',
  TASK_RETRY: 'task.retry',

  // Agent Events
  AGENT_REGISTERED: 'agent.registered',
  AGENT_HEALTH_CHECK: 'agent.health_check',
  AGENT_STATUS_CHANGED: 'agent.status_changed',

  // Approval Events
  APPROVAL_REQUESTED: 'approval.requested',
  APPROVAL_APPROVED: 'approval.approved',
  APPROVAL_REJECTED: 'approval.rejected',
  APPROVAL_EXPIRED: 'approval.expired',

  // Audit Events
  AUDIT_LOG_CREATED: 'audit.log_created',

  // Runtime Events
  RUNTIME_AGENT_EXECUTE: 'runtime.agent.execute',
  RUNTIME_AGENT_RESULT: 'runtime.agent.result',
  RUNTIME_AGENT_ERROR: 'runtime.agent.error',
} as const;

export type EventSubject = (typeof EventSubjects)[keyof typeof EventSubjects];

// ─────────────────────────────────────────
// Event Payload Types
// ─────────────────────────────────────────

export interface BaseEvent {
  eventId: string;
  timestamp: string;
  source: string;
}

export interface WorkflowCreatedEvent extends BaseEvent {
  workflowId: string;
  name: string;
  goal: string;
  createdBy?: string;
}

export interface WorkflowStatusChangedEvent extends BaseEvent {
  workflowId: string;
  previousStatus: string;
  currentStatus: string;
}

export interface TaskCreatedEvent extends BaseEvent {
  taskId: string;
  workflowId: string;
  agentId?: string;
  goal: string;
  order: number;
}

export interface TaskStatusChangedEvent extends BaseEvent {
  taskId: string;
  workflowId: string;
  agentId?: string;
  previousStatus: string;
  currentStatus: string;
}

export interface TaskCompletedEvent extends BaseEvent {
  taskId: string;
  workflowId: string;
  agentId?: string;
  output: Record<string, unknown>;
  success: boolean;
}

export interface AgentExecuteEvent extends BaseEvent {
  taskId: string;
  workflowId: string;
  agentId: string;
  goal: string;
  context: Record<string, unknown>;
  constraints: Record<string, unknown>;
}

export interface AgentResultEvent extends BaseEvent {
  taskId: string;
  workflowId: string;
  agentId: string;
  success: boolean;
  summary: string;
  artifacts: unknown[];
  metrics: Record<string, unknown>;
  error?: string;
}

export interface ApprovalRequestedEvent extends BaseEvent {
  approvalId: string;
  workflowId?: string;
  taskId?: string;
  title: string;
  requestedBy?: string;
}

export interface AuditLogEvent extends BaseEvent {
  action: string;
  entityType: string;
  entityId?: string;
  actorId?: string;
  changes: Record<string, unknown>;
}
