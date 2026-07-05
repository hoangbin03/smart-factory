import { Injectable, Logger } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { TaskEntity } from './entities/task.entity';
import { TaskStatus } from '@factory/shared-types';

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
