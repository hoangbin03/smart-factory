import { Injectable, Logger } from '@nestjs/common';

/**
 * StateManagerService
 * Manages in-memory orchestration state and coordinates
 * with Redis for distributed state (TODO: Redis integration in Sprint 2)
 */
@Injectable()
export class StateManagerService {
  private readonly logger = new Logger(StateManagerService.name);

  // In-memory state cache for active workflows
  private readonly workflowState = new Map<string, Record<string, unknown>>();
  private readonly taskState = new Map<string, Record<string, unknown>>();

  setWorkflowState(workflowId: string, state: Record<string, unknown>): void {
    this.workflowState.set(workflowId, {
      ...this.workflowState.get(workflowId),
      ...state,
      updatedAt: new Date().toISOString(),
    });
  }

  getWorkflowState(workflowId: string): Record<string, unknown> {
    return this.workflowState.get(workflowId) ?? {};
  }

  setTaskState(taskId: string, state: Record<string, unknown>): void {
    this.taskState.set(taskId, {
      ...this.taskState.get(taskId),
      ...state,
      updatedAt: new Date().toISOString(),
    });
  }

  getTaskState(taskId: string): Record<string, unknown> {
    return this.taskState.get(taskId) ?? {};
  }

  clearWorkflowState(workflowId: string): void {
    this.workflowState.delete(workflowId);
    this.logger.log(`Cleared state for workflow ${workflowId}`);
  }
}
