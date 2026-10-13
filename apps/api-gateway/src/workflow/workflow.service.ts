import { Injectable, NotFoundException, Inject } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, FindManyOptions, ILike } from 'typeorm';
import { ClientProxy } from '@nestjs/microservices';
import { v4 as uuidv4 } from 'uuid';
import { WorkflowEntity } from './entities/workflow.entity';
import { TaskEntity } from '../task/entities/task.entity';
import { CreateWorkflowDto, UpdateWorkflowDto } from './dto/workflow.dto';
import { WorkflowStatus } from '@factory/shared-types';
import { EventSubjects } from '@factory/shared-events';
import { NATS_CLIENT } from '../nats/nats.module';

@Injectable()
export class WorkflowService {
  constructor(
    @InjectRepository(WorkflowEntity)
    private readonly workflowRepo: Repository<WorkflowEntity>,
    @InjectRepository(TaskEntity)
    private readonly taskRepo: Repository<TaskEntity>,
    @Inject(NATS_CLIENT) private readonly natsClient: ClientProxy,
  ) {}

  async create(dto: CreateWorkflowDto, userId?: string): Promise<WorkflowEntity> {
    const workflow = this.workflowRepo.create({
      ...dto,
      status: WorkflowStatus.PENDING,
      createdBy: userId,
      config: dto.config ?? {},
      metadata: dto.metadata ?? {},
    });

    const saved = await this.workflowRepo.save(workflow);

    this.natsClient.emit(EventSubjects.WORKFLOW_CREATED, {
      eventId: uuidv4(),
      timestamp: new Date().toISOString(),
      source: 'api-gateway',
      workflowId: saved.id,
      name: saved.name,
      goal: saved.goal,
      createdBy: userId,
    });

    return saved;
  }

  async findAll(query: { page?: number | string; limit?: number | string; status?: string; search?: string }) {
    const parsedPage = Number(query.page);
    const parsedLimit = Number(query.limit);
    const page = Number.isInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1;
    const limit = Number.isInteger(parsedLimit) && parsedLimit > 0
      ? Math.min(parsedLimit, 100)
      : 20;
    const skip = (page - 1) * limit;

    const where: FindManyOptions<WorkflowEntity>['where'] = {};
    if (query.status) {
      (where as Record<string, unknown>)['status'] = query.status;
    }
    if (query.search) {
      (where as Record<string, unknown>)['name'] = ILike(`%${query.search}%`);
    }

    const [data, total] = await this.workflowRepo.findAndCount({
      where,
      order: { createdAt: 'DESC' },
      skip,
      take: limit,
    });

    return {
      data,
      total,
      page,
      limit,
      totalPages: Math.ceil(total / limit),
    };
  }

  async findOne(id: string): Promise<WorkflowEntity> {
    const workflow = await this.workflowRepo.findOne({ where: { id } });
    if (!workflow) throw new NotFoundException(`Workflow ${id} not found`);
    return workflow;
  }

  async update(id: string, dto: UpdateWorkflowDto): Promise<WorkflowEntity> {
    const workflow = await this.findOne(id);
    Object.assign(workflow, dto);
    return this.workflowRepo.save(workflow);
  }

  async start(id: string): Promise<WorkflowEntity> {
    const workflow = await this.findOne(id);
    workflow.status = WorkflowStatus.RUNNING;
    workflow.startedAt = new Date();
    const saved = await this.workflowRepo.save(workflow);

    this.natsClient.emit(EventSubjects.WORKFLOW_STARTED, {
      eventId: uuidv4(),
      timestamp: new Date().toISOString(),
      source: 'api-gateway',
      workflowId: id,
      previousStatus: WorkflowStatus.PENDING,
      currentStatus: WorkflowStatus.RUNNING,
    });

    return saved;
  }

  async cancel(id: string): Promise<WorkflowEntity> {
    const workflow = await this.findOne(id);
    workflow.status = WorkflowStatus.CANCELLED;
    const saved = await this.workflowRepo.save(workflow);

    this.natsClient.emit(EventSubjects.WORKFLOW_CANCELLED, {
      eventId: uuidv4(),
      timestamp: new Date().toISOString(),
      source: 'api-gateway',
      workflowId: id,
      previousStatus: workflow.status,
      currentStatus: WorkflowStatus.CANCELLED,
    });

    return saved;
  }

  async remove(id: string): Promise<void> {
    const workflow = await this.findOne(id);
    await this.workflowRepo.remove(workflow);
  }

  async getArtifacts(workflowId: string) {
    await this.findOne(workflowId);
    const tasks = await this.taskRepo.find({
      where: { workflowId },
      order: { order: 'ASC' },
    });

    return tasks.flatMap((task) => {
      const output = task.output ?? {};
      const artifacts = Array.isArray((output as any).artifacts)
        ? (output as any).artifacts
        : [];

      return artifacts
        .filter((artifact: any) => artifact && typeof artifact.content === 'string')
        .map((artifact: any) => ({
          taskId: task.id,
          agentId: task.agentId,
          artifactType: String(artifact.artifactType ?? artifact.artifact_type ?? 'file'),
          name: String(artifact.name ?? 'artifact.txt'),
          content: String(artifact.content ?? ''),
          metadata: artifact.metadata ?? {},
        }));
    });
  }

  async getPreviewHtml(workflowId: string): Promise<string> {
    const artifacts = await this.getArtifacts(workflowId);
    const findByName = (name: string) => artifacts.find((artifact) => artifact.name.toLowerCase() === name);
    const index = findByName('index.html') ?? artifacts.find((artifact) => artifact.artifactType.includes('html'));
    const styles = artifacts
      .filter((artifact) => artifact.name.toLowerCase().endsWith('.css') || artifact.artifactType.includes('css'))
      .map((artifact) => artifact.content)
      .join('\n\n');
    const scripts = artifacts
      .filter((artifact) => artifact.name.toLowerCase().endsWith('.js') || artifact.artifactType.includes('javascript'))
      .map((artifact) => artifact.content)
      .join('\n\n');

    if (!index) {
      return this.emptyPreviewHtml(workflowId);
    }

    let html = index.content;
    if (styles && !html.includes('<style data-factory-preview>')) {
      html = html.includes('</head>')
        ? html.replace('</head>', `<style data-factory-preview>\n${styles}\n</style></head>`)
        : `<style data-factory-preview>\n${styles}\n</style>${html}`;
    }
    if (scripts && !html.includes('<script data-factory-preview>')) {
      html = html.includes('</body>')
        ? html.replace('</body>', `<script data-factory-preview>\n${scripts}\n</script></body>`)
        : `${html}<script data-factory-preview>\n${scripts}\n</script>`;
    }

    return html;
  }

  private emptyPreviewHtml(workflowId: string): string {
    return `<!doctype html><html><head><meta charset="utf-8"><title>No preview</title><style>body{font-family:system-ui;margin:40px;color:#0f172a}code{background:#f1f5f9;padding:2px 6px;border-radius:4px}</style></head><body><h1>No runnable preview yet</h1><p>Workflow <code>${workflowId}</code> has no <code>index.html</code> artifact yet. Start the workflow and wait for the developer task to complete.</p></body></html>`;
  }

  async getStats() {
    const stats = await this.workflowRepo
      .createQueryBuilder('w')
      .select('w.status', 'status')
      .addSelect('COUNT(*)', 'count')
      .groupBy('w.status')
      .getRawMany();

    return stats.reduce((acc: Record<string, number>, row) => {
      acc[row.status] = parseInt(row.count, 10);
      return acc;
    }, {});
  }
}
