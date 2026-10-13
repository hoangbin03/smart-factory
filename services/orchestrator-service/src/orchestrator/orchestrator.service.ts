import { Injectable, Logger, Inject } from '@nestjs/common';
import { ClientProxy } from '@nestjs/microservices';
import { Cron, CronExpression } from '@nestjs/schedule';
import { v4 as uuidv4 } from 'uuid';
import { WorkflowEngineService } from '../workflow-engine/workflow-engine.service';
import { TaskEngineService } from '../task-engine/task-engine.service';
import { AgentResolverService } from '../agent-resolver/agent-resolver.service';
import { AuditService } from '../audit/audit.service';
import { ApprovalService } from '../approval/approval.service';
import { EventSubjects } from '@factory/shared-events';
import { WorkflowStatus } from '@factory/shared-types';
import { NATS_CLIENT } from '../nats/nats.module';

/**
 * Factory Orchestrator - Central Control
 *
 * Principles:
 * - Only the orchestrator dispatches tasks to agents
 * - Agents never call other agents
 * - All coordination flows through here
 *
 * Adds: human-in-the-loop approval gates, token budget caps, an audit trail,
 * and atomic task claiming to prevent double-dispatch.
 */
@Injectable()
export class OrchestratorService {
  private readonly logger = new Logger(OrchestratorService.name);
  private readonly defaultTokenBudget = Number(process.env.MAX_WORKFLOW_TOKENS ?? 500000);

  constructor(
    private readonly workflowEngine: WorkflowEngineService,
    private readonly taskEngine: TaskEngineService,
    private readonly agentResolver: AgentResolverService,
    private readonly audit: AuditService,
    private readonly approvals: ApprovalService,
    @Inject(NATS_CLIENT) private readonly natsClient: ClientProxy,
  ) {}

  @Cron(CronExpression.EVERY_5_SECONDS)
  async orchestrationLoop(): Promise<void> {
    try {
      await this.processRunningWorkflows();
      await this.processPausedWorkflows();
    } catch (err) {
      this.logger.error('Orchestration loop error', err);
    }
  }

  private async processRunningWorkflows(): Promise<void> {
    const runningWorkflows = await this.workflowEngine.getRunningWorkflows();
    for (const workflow of runningWorkflows) {
      try {
        await this.advanceWorkflow(workflow.id);
      } catch (err) {
        this.logger.error(`Error advancing workflow ${workflow.id}`, err);
      }
    }
  }

  /** Resume or fail workflows that were paused waiting for a human approval gate. */
  private async processPausedWorkflows(): Promise<void> {
    const paused = await this.workflowEngine.getPausedWorkflows();
    for (const workflow of paused) {
      try {
        const nextTask = await this.taskEngine.getNextPendingTask(workflow.id);
        if (!nextTask) continue;
        const approval = await this.approvals.findForTask(workflow.id, nextTask.id);
        if (!approval || approval.status === 'PENDING') continue; // still waiting for a human

        if (approval.status === 'APPROVED') {
          await this.workflowEngine.resumeWorkflow(workflow.id);
          await this.audit.record('APPROVE', 'task', nextTask.id, { task: nextTask.name }, 'user');
          this.logger.log(`Approval granted for ${nextTask.name} — resuming workflow ${workflow.id}`);
          await this.advanceWorkflow(workflow.id);
        } else if (approval.status === 'REJECTED') {
          await this.taskEngine.failTask(nextTask.id, { rejected: true });
          await this.workflowEngine.failWorkflow(workflow.id);
          await this.audit.record('REJECT', 'workflow', workflow.id, { task: nextTask.name }, 'user');
          this.logger.warn(`Approval rejected for ${nextTask.name} — failing workflow ${workflow.id}`);
        }
      } catch (err) {
        this.logger.error(`Error processing paused workflow ${workflow.id}`, err);
      }
    }
  }

  async advanceWorkflow(workflowId: string): Promise<void> {
    const workflow = await this.workflowEngine.findOne(workflowId);
    if (workflow.status !== WorkflowStatus.RUNNING) return;

    await this.taskEngine.ensureDefaultTasksForWorkflow(workflow);

    // ── Strict sequential dispatch ────────────────────────────────
    // Never dispatch the next task while one is still executing — otherwise the
    // 5s cron would start the reviewer/QA before the developer has finished.
    if (await this.taskEngine.hasRunningTask(workflowId)) return;

    // ── Token budget cap ──────────────────────────────────────────
    const cfg = (workflow.config ?? {}) as Record<string, unknown>;
    const budget = Number(cfg.maxTokens ?? this.defaultTokenBudget);
    if (budget > 0) {
      const used = await this.taskEngine.getWorkflowTokenTotal(workflowId);
      if (used >= budget) {
        await this.workflowEngine.failWorkflow(workflowId);
        await this.audit.record('UPDATE', 'workflow', workflowId, { reason: 'token_budget_exceeded', used, budget });
        this.logger.warn(`Workflow ${workflowId} failed — token budget ${used}/${budget}`);
        return;
      }
    }

    const nextTask = await this.taskEngine.getNextPendingTask(workflowId);
    if (!nextTask) {
      const allComplete = await this.taskEngine.areAllTasksComplete(workflowId);
      if (allComplete) {
        await this.workflowEngine.completeWorkflow(workflowId);
        await this.audit.record('UPDATE', 'workflow', workflowId, { status: 'COMPLETED' });
        this.logger.log(`Workflow ${workflowId} completed`);
      }
      return;
    }

    // ── Human-in-the-loop approval gate ───────────────────────────
    const gates = Array.isArray(cfg.approvalGates) ? (cfg.approvalGates as string[]) : [];
    if (gates.includes(nextTask.name)) {
      const approval = await this.approvals.findForTask(workflowId, nextTask.id);
      if (!approval) {
        await this.approvals.createGate(workflowId, nextTask.id, `Approve: ${nextTask.name}`, nextTask.goal);
        await this.workflowEngine.pauseWorkflow(workflowId);
        await this.audit.record('UPDATE', 'task', nextTask.id, { gate: nextTask.name, status: 'awaiting_approval' });
        this.logger.log(`Workflow ${workflowId} paused — awaiting approval for ${nextTask.name}`);
        return;
      }
      if (approval.status === 'PENDING') {
        await this.workflowEngine.pauseWorkflow(workflowId);
        return;
      }
      if (approval.status === 'REJECTED') {
        await this.taskEngine.failTask(nextTask.id, { rejected: true });
        await this.workflowEngine.failWorkflow(workflowId);
        return;
      }
      // APPROVED → fall through and dispatch
    }

    const agent = await this.agentResolver.resolve(nextTask.agentId ?? '', nextTask.goal);
    if (!agent) {
      this.logger.warn(`No agent available for task ${nextTask.id}`);
      return;
    }

    // ── Atomic claim (prevents the cron from double-dispatching) ──
    const claimed = await this.taskEngine.claimTask(nextTask.id, agent.agentId);
    if (!claimed) {
      this.logger.debug(`Task ${nextTask.id} already claimed — skipping`);
      return;
    }

    this.natsClient.emit(EventSubjects.RUNTIME_AGENT_EXECUTE, {
      eventId: uuidv4(),
      timestamp: new Date().toISOString(),
      source: 'orchestrator',
      workflowId,
      // Shared codebase workspace: the project's id when this workflow belongs to
      // a project, else the workflow's own id. Agents operate on this directory.
      workspaceId: workflow.projectId ?? workflowId,
      taskId: nextTask.id,
      agentId: agent.agentId,
      goal: nextTask.goal,
      context: nextTask.input,
      constraints: nextTask.constraints,
    });

    await this.audit.record('EXECUTE', 'task', nextTask.id, { agent: agent.agentId, goal: nextTask.goal });
    this.logger.log(`Dispatched task ${nextTask.id} → agent ${agent.agentId} (workflow ${workflowId})`);
  }

  async onTaskCompleted(payload: {
    taskId: string;
    workflowId: string;
    agentId: string;
    success: boolean;
    output: Record<string, unknown>;
    summary: string;
  }): Promise<void> {
    if (!payload?.taskId || !payload?.workflowId || !payload?.agentId) {
      this.logger.warn(
        `Ignoring malformed agent result: taskId=${payload?.taskId ?? 'null'}, workflowId=${payload?.workflowId ?? 'null'}, agentId=${payload?.agentId ?? 'null'}`,
      );
      return;
    }

    if (payload.success) {
      await this.taskEngine.completeTask(payload.taskId, payload.output);
      const metrics = ((payload.output ?? {}) as Record<string, unknown>).metrics as
        | Record<string, unknown>
        | undefined;
      await this.audit.record('EXECUTE', 'task', payload.taskId, {
        agent: payload.agentId,
        result: 'completed',
        tokens: (metrics?.tokens as any)?.total_tokens ?? 0,
        duration: metrics?.duration_seconds ?? null,
      });
      this.logger.log(`Task ${payload.taskId} completed successfully`);

      if (metrics?.needsRework === true) {
        const feedback = String(metrics.reworkFeedback ?? 'Changes required by review/QA.');
        const reopened = await this.taskEngine.requestRework(payload.workflowId, payload.agentId, feedback);
        if (reopened) {
          await this.audit.record('UPDATE', 'workflow', payload.workflowId, {
            rework_requested_by: payload.agentId,
          });
          this.logger.warn(`Task ${payload.taskId} (${payload.agentId}) triggered developer rework`);
        }
      }
    } else {
      await this.taskEngine.failTask(payload.taskId, payload.output);
      await this.audit.record('EXECUTE', 'task', payload.taskId, { agent: payload.agentId, result: 'failed' });
      this.logger.warn(`Task ${payload.taskId} failed`);
    }

    await this.advanceWorkflow(payload.workflowId);
  }

  async startWorkflow(workflowId: string): Promise<void> {
    const workflow = await this.workflowEngine.startWorkflow(workflowId);
    await this.audit.record('UPDATE', 'workflow', workflowId, { status: 'RUNNING' }, 'user');
    await this.taskEngine.ensureDefaultTasksForWorkflow(workflow);
    await this.advanceWorkflow(workflowId);
  }
}
