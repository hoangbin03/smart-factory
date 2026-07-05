import { Injectable, NotFoundException, Inject } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { FindManyOptions, Repository } from 'typeorm';
import { ClientProxy } from '@nestjs/microservices';
import { v4 as uuidv4 } from 'uuid';
import { TaskEntity } from './entities/task.entity';
import { CreateTaskDto, UpdateTaskDto } from './dto/task.dto';
import { TaskStatus } from '@factory/shared-types';
import { EventSubjects } from '@factory/shared-events';
import { NATS_CLIENT } from '../nats/nats.module';

@Injectable()
export class TaskService {
  constructor(
    @InjectRepository(TaskEntity)
    private readonly taskRepo: Repository<TaskEntity>,
    @Inject(NATS_CLIENT) private readonly natsClient: ClientProxy,
  ) {}

  async create(dto: CreateTaskDto): Promise<TaskEntity> {
    const task = this.taskRepo.create({
      ...dto,
      status: TaskStatus.PENDING,
      input: dto.input ?? {},
      constraints: dto.constraints ?? {},
      order: dto.order ?? 0,
    });
    const saved = await this.taskRepo.save(task);

    this.natsClient.emit(EventSubjects.TASK_CREATED, {
      eventId: uuidv4(),
      timestamp: new Date().toISOString(),
      source: 'api-gateway',
      taskId: saved.id,
      workflowId: saved.workflowId,
      agentId: saved.agentId,
      goal: saved.goal,
      order: saved.order,
    });

    return saved;
  }

  async findByWorkflow(query: {
    workflowId?: string;
    status?: string;
    page?: number | string;
    limit?: number | string;
  }) {
    const parsedPage = Number(query.page);
    const parsedLimit = Number(query.limit);
    const page = Number.isInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1;
    const limit = Number.isInteger(parsedLimit) && parsedLimit > 0
      ? Math.min(parsedLimit, 100)
      : 20;
    const skip = (page - 1) * limit;
    const where: FindManyOptions<TaskEntity>['where'] = {};

    if (query.workflowId) {
      (where as Record<string, unknown>)['workflowId'] = query.workflowId;
    }
    if (query.status) {
      (where as Record<string, unknown>)['status'] = query.status;
    }

    const [data, total] = await this.taskRepo.findAndCount({
      where,
      order: { order: 'ASC' },
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

  async findOne(id: string): Promise<TaskEntity> {
    const task = await this.taskRepo.findOne({ where: { id } });
    if (!task) throw new NotFoundException(`Task ${id} not found`);
    return task;
  }

  async update(id: string, dto: UpdateTaskDto): Promise<TaskEntity> {
    const task = await this.findOne(id);
    Object.assign(task, dto);
    return this.taskRepo.save(task);
  }

  async cancel(id: string): Promise<TaskEntity> {
    const task = await this.findOne(id);
    const prev = task.status;
    task.status = TaskStatus.CANCELLED;
    const saved = await this.taskRepo.save(task);

    this.natsClient.emit(EventSubjects.TASK_CANCELLED, {
      eventId: uuidv4(),
      timestamp: new Date().toISOString(),
      source: 'api-gateway',
      taskId: id,
      workflowId: task.workflowId,
      previousStatus: prev,
      currentStatus: TaskStatus.CANCELLED,
    });

    return saved;
  }

  async remove(id: string): Promise<void> {
    const task = await this.findOne(id);
    await this.taskRepo.remove(task);
  }
}
