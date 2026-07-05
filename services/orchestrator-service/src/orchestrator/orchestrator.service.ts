import { Injectable, Logger, Inject } from '@nestjs/common';
import { ClientProxy } from '@nestjs/microservices';
import { Cron, CronExpression } from '@nestjs/schedule';
import { v4 as uuidv4 } from 'uuid';
import { WorkflowEngineService } from '../workflow-engine/workflow-engine.service';
import { TaskEngineService } from '../task-engine/task-engine.service';
import { AgentResolverService } from '../agent-resolver/agent-resolver.service';
import { EventSubjects } from '@factory/shared-events';
import { NATS_CLIENT } from '../nats/nats.module';

/**
 * Factory Orchestrator - Central Control
 *
 * Principles:
 * - Only the orchestrator dispatches tasks to agents
 * - Agents never call other agents
 * - All coordination flows through here
 */
@Injectable()
export class OrchestratorService {
  private readonly logger = new Logger(OrchestratorService.name);

  constructor(
    private readonly workflowEngine: WorkflowEngineService,
    private readonly taskEngine: TaskEngineService,
    private readonly agentResolver: AgentResolverService,
    @Inject(NATS_CLIENT) private readonly natsClient: ClientProxy,
  ) {}

  /**
   * Main orchestration loop — runs every 5 seconds
   * Picks up PENDING workflows and queued tasks
   */
  @Cron(CronExpression.EVERY_5_SECONDS)
  async orchestrationLoop(): Promise<void> {
    try {
      await this.processRunningWorkflows();
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

  async advanceWorkflow(workflowId: string): Promise<void> {
    const workflow = await this.workflowEngine.findOne(workflowId);
    await this.taskEngine.ensureDefaultTasksForWorkflow(workflow);

    const nextTask = await this.taskEngine.getNextPendingTask(workflowId);

    if (!nextTask) {
      // No more tasks — check if all completed
      const allComplete = await this.taskEngine.areAllTasksComplete(workflowId);
      if (allComplete) {
        await this.workflowEngine.completeWorkflow(workflowId);
        this.logger.log(`Workflow ${workflowId} completed`);
      }
      return;
    }

    // Resolve agent for the task
    const agent = await this.agentResolver.resolve(nextTask.agentId ?? '', nextTask.goal);

    if (!agent) {
      this.logger.warn(`No agent available for task ${nextTask.id}`);
      return;
    }

    // Queue the task
    await this.taskEngine.queueTask(nextTask.id, agent.agentId);

    // Dispatch to agent runtime via NATS
    this.natsClient.emit(EventSubjects.RUNTIME_AGENT_EXECUTE, {
      eventId: uuidv4(),
      timestamp: new Date().toISOString(),
      source: 'orchestrator',
      workflowId,
      taskId: nextTask.id,
      agentId: agent.agentId,
      goal: nextTask.goal,
      context: nextTask.input,
      constraints: nextTask.constraints,
    });

    this.logger.log(
      `Dispatched task ${nextTask.id} → agent ${agent.agentId} (workflow ${workflowId})`,
    );
  }

  /**
   * Handle task completion reported by agent runtime
   */
  async onTaskCompleted(payload: {
    taskId: string;
    workflowId: string;
    agentId: string;
    success: boolean;
    output: Record<string, unknown>;
    summary: string;
  }): Promise<void> {
    if (payload.success) {
      await this.taskEngine.completeTask(payload.taskId, payload.output);
      this.logger.log(`Task ${payload.taskId} completed successfully`);
    } else {
      await this.taskEngine.failTask(payload.taskId, payload.output);
      this.logger.warn(`Task ${payload.taskId} failed`);
    }

    // Continue workflow
    await this.advanceWorkflow(payload.workflowId);
  }

  async startWorkflow(workflowId: string): Promise<void> {
    const workflow = await this.workflowEngine.startWorkflow(workflowId);
    await this.taskEngine.ensureDefaultTasksForWorkflow(workflow);
    await this.advanceWorkflow(workflowId);
  }
}
