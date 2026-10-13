import { Injectable, Logger } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { TaskEntity } from './entities/task.entity';
import { TaskStatus } from '@factory/shared-types';

/** Max times a workflow may loop back to the developer before accepting the result. */
const MAX_REWORK_ROUNDS = 2;

@Injectable()
export class TaskEngineService {
  private readonly logger = new Logger(TaskEngineService.name);
  private readonly defaultPipeline = [
    {
      name: 'Architecture design',
      agentId: 'architect_agent',
      goalPrefix: 'Design architecture and technical approach for',
    },
    {
      name: 'Implementation plan',
      agentId: 'planner_agent',
      goalPrefix: 'Break down implementation tasks for',
    },
    {
      name: 'Development',
      agentId: 'developer_agent',
      goalPrefix: 'Implement the requested project work for',
    },
    {
      name: 'Code review',
      agentId: 'reviewer_agent',
      goalPrefix: 'Review implementation quality and security for',
    },
    {
      name: 'Quality assurance',
      agentId: 'qa_agent',
      goalPrefix: 'Create and run QA validation for',
    },
    {
      name: 'Deployment plan',
      agentId: 'devops_agent',
      goalPrefix: 'Prepare deployment and operations plan for',
    },
  ];

  constructor(
    @InjectRepository(TaskEntity)
    private readonly taskRepo: Repository<TaskEntity>,
  ) {}

  async getNextPendingTask(workflowId: string): Promise<TaskEntity | null> {
    return this.taskRepo.findOne({
      where: { workflowId, status: TaskStatus.PENDING },
      order: { order: 'ASC' },
    });
  }

  async ensureDefaultTasksForWorkflow(workflow: {
    id: string;
    name: string;
    goal: string;
    config?: Record<string, unknown>;
  }): Promise<void> {
    const existingTasks = await this.taskRepo.count({ where: { workflowId: workflow.id } });
    if (existingTasks > 0) return;

    const tasks = this.defaultPipeline.map((step, index) => this.taskRepo.create({
      workflowId: workflow.id,
      name: step.name,
      status: TaskStatus.PENDING,
      agentId: step.agentId,
      goal: `${step.goalPrefix}: ${workflow.goal}`,
      input: {
        workflowName: workflow.name,
        workflowGoal: workflow.goal,
        workflowConfig: workflow.config ?? {},
        pipelineStep: step.name,
      },
      output: {},
      constraints: {},
      order: index,
      retryCount: 0,
      maxRetries: 3,
    }));

    await this.taskRepo.save(tasks);
    this.logger.log(`Created ${tasks.length} default tasks for workflow ${workflow.id}`);
  }

  /** True if a task in this workflow is currently executing (enforces sequential dispatch). */
  async hasRunningTask(workflowId: string): Promise<boolean> {
    const count = await this.taskRepo.count({
      where: { workflowId, status: TaskStatus.RUNNING },
    });
    return count > 0;
  }

  async areAllTasksComplete(workflowId: string): Promise<boolean> {
    const nonCompleted = await this.taskRepo.count({
      where: [
        { workflowId, status: TaskStatus.PENDING },
        { workflowId, status: TaskStatus.QUEUED },
        { workflowId, status: TaskStatus.RUNNING },
      ],
    });
    return nonCompleted === 0;
  }

  async queueTask(taskId: string, agentId: string): Promise<TaskEntity> {
    const task = await this.taskRepo.findOneOrFail({ where: { id: taskId } });
    task.status = TaskStatus.RUNNING;
    task.agentId = agentId;
    task.startedAt = new Date();
    return this.taskRepo.save(task);
  }

  /**
   * Atomically claim a PENDING task (PENDING -> RUNNING). Returns false if another
   * dispatch already claimed it — prevents the 5s cron from double-dispatching.
   */
  async claimTask(taskId: string, agentId: string): Promise<boolean> {
    const result = await this.taskRepo
      .createQueryBuilder()
      .update(TaskEntity)
      .set({ status: TaskStatus.RUNNING, agentId, startedAt: () => 'NOW()' })
      .where('id = :id AND status = :pending', { id: taskId, pending: TaskStatus.PENDING })
      .execute();
    return (result.affected ?? 0) > 0;
  }

  /** Sum of LLM tokens consumed across all tasks of a workflow (for budget caps). */
  async getWorkflowTokenTotal(workflowId: string): Promise<number> {
    const tasks = await this.taskRepo.find({ where: { workflowId } });
    return tasks.reduce((sum, task) => {
      const tokens = (task.output as any)?.metrics?.tokens?.total_tokens ?? 0;
      return sum + (Number(tokens) || 0);
    }, 0);
  }

  async startTask(taskId: string): Promise<TaskEntity> {
    const task = await this.taskRepo.findOneOrFail({ where: { id: taskId } });
    task.status = TaskStatus.RUNNING;
    task.startedAt = new Date();
    return this.taskRepo.save(task);
  }

  async completeTask(taskId: string, output: Record<string, unknown>): Promise<TaskEntity> {
    const task = await this.taskRepo.findOneOrFail({ where: { id: taskId } });
    task.status = TaskStatus.COMPLETED;
    task.output = output;
    task.completedAt = new Date();
    return this.taskRepo.save(task);
  }

  /**
   * QA/Reviewer → Developer feedback loop.
   * Re-opens the developer task with the reviewer/QA feedback and resets every
   * downstream task so the fix flows through review and QA again.
   * Returns false when the rework budget is exhausted (result is accepted as-is).
   */
  async requestRework(
    workflowId: string,
    requestingAgentId: string,
    feedback: string,
  ): Promise<boolean> {
    const developerTask = await this.taskRepo.findOne({
      where: { workflowId, agentId: 'developer_agent' },
    });
    if (!developerTask) {
      this.logger.warn(`Rework requested but no developer task in workflow ${workflowId}`);
      return false;
    }

    const input = (developerTask.input ?? {}) as Record<string, unknown>;
    const round = Number(input.reworkRound ?? 0);
    if (round >= MAX_REWORK_ROUNDS) {
      this.logger.warn(
        `Workflow ${workflowId}: rework budget exhausted (${round}/${MAX_REWORK_ROUNDS}) — accepting result`,
      );
      return false;
    }

    // Re-open the developer task with feedback
    developerTask.status = TaskStatus.PENDING;
    developerTask.input = {
      ...input,
      reworkRound: round + 1,
      reworkFeedback: feedback,
      reworkRequestedBy: requestingAgentId,
    };
    developerTask.output = {};
    developerTask.startedAt = null as unknown as Date;
    developerTask.completedAt = null as unknown as Date;
    developerTask.retryCount = 0;
    await this.taskRepo.save(developerTask);

    // Reset every downstream task (review, qa, devops, ...) so they re-run on the fix
    const downstream = await this.taskRepo.find({ where: { workflowId } });
    for (const task of downstream) {
      if (task.order > developerTask.order) {
        task.status = TaskStatus.PENDING;
        task.output = {};
        task.startedAt = null as unknown as Date;
        task.completedAt = null as unknown as Date;
        task.retryCount = 0;
        await this.taskRepo.save(task);
      }
    }

    this.logger.warn(
      `Workflow ${workflowId}: ${requestingAgentId} requested rework (round ${round + 1}/${MAX_REWORK_ROUNDS})`,
    );
    return true;
  }

  async failTask(taskId: string, output: Record<string, unknown>): Promise<TaskEntity> {
    const task = await this.taskRepo.findOneOrFail({ where: { id: taskId } });
    task.retryCount++;

    if (task.retryCount < task.maxRetries) {
      task.status = TaskStatus.PENDING; // Retry
      this.logger.warn(`Task ${taskId} retry ${task.retryCount}/${task.maxRetries}`);
    } else {
      task.status = TaskStatus.FAILED;
      task.output = output;
      task.completedAt = new Date();
      this.logger.error(`Task ${taskId} permanently failed after ${task.maxRetries} retries`);
    }

    return this.taskRepo.save(task);
  }
}
