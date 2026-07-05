import { Injectable, NotFoundException, Inject } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, FindManyOptions, ILike } from 'typeorm';
import { ClientProxy } from '@nestjs/microservices';
import { v4 as uuidv4 } from 'uuid';
import { WorkflowEntity } from './entities/workflow.entity';
import { CreateWorkflowDto, UpdateWorkflowDto } from './dto/workflow.dto';
import { WorkflowStatus } from '@factory/shared-types';
import { EventSubjects } from '@factory/shared-events';
import { NATS_CLIENT } from '../nats/nats.module';

@Injectable()
export class WorkflowService {
  constructor(
    @InjectRepository(WorkflowEntity)
    private readonly workflowRepo: Repository<WorkflowEntity>,
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
