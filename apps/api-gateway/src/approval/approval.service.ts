import { Injectable, NotFoundException, BadRequestException, Inject } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { ClientProxy } from '@nestjs/microservices';
import { v4 as uuidv4 } from 'uuid';
import { ApprovalEntity } from './entities/approval.entity';
import { ApprovalStatus } from '@factory/shared-types';
import { EventSubjects } from '@factory/shared-events';
import { NATS_CLIENT } from '../nats/nats.module';

@Injectable()
export class ApprovalService {
  constructor(
    @InjectRepository(ApprovalEntity)
    private readonly approvalRepo: Repository<ApprovalEntity>,
    @Inject(NATS_CLIENT) private readonly natsClient: ClientProxy,
  ) {}

  async create(dto: {
    workflowId?: string;
    taskId?: string;
    title: string;
    description?: string;
    requestedBy?: string;
    expiresAt?: Date;
    metadata?: Record<string, unknown>;
  }): Promise<ApprovalEntity> {
    const approval = this.approvalRepo.create({
      ...dto,
      status: ApprovalStatus.PENDING,
      metadata: dto.metadata ?? {},
    });
    const saved = await this.approvalRepo.save(approval);

    this.natsClient.emit(EventSubjects.APPROVAL_REQUESTED, {
      eventId: uuidv4(),
      timestamp: new Date().toISOString(),
      source: 'api-gateway',
      approvalId: saved.id,
      workflowId: saved.workflowId,
      taskId: saved.taskId,
      title: saved.title,
      requestedBy: saved.requestedBy,
    });

    return saved;
  }

  async findPending(): Promise<ApprovalEntity[]> {
    return this.approvalRepo.find({
      where: { status: ApprovalStatus.PENDING },
      order: { createdAt: 'DESC' },
    });
  }

  async findOne(id: string): Promise<ApprovalEntity> {
    const approval = await this.approvalRepo.findOne({ where: { id } });
    if (!approval) throw new NotFoundException(`Approval ${id} not found`);
    return approval;
  }

  async approve(id: string, userId: string, notes?: string): Promise<ApprovalEntity> {
    const approval = await this.findOne(id);
    if (approval.status !== ApprovalStatus.PENDING) {
      throw new BadRequestException(`Approval is already ${approval.status}`);
    }

    approval.status = ApprovalStatus.APPROVED;
    approval.approvedBy = userId;
    approval.decisionAt = new Date();
    approval.notes = notes;
    const saved = await this.approvalRepo.save(approval);

    this.natsClient.emit(EventSubjects.APPROVAL_APPROVED, {
      eventId: uuidv4(),
      timestamp: new Date().toISOString(),
      source: 'api-gateway',
      approvalId: id,
      workflowId: approval.workflowId,
      taskId: approval.taskId,
    });

    return saved;
  }

  async reject(id: string, userId: string, notes?: string): Promise<ApprovalEntity> {
    const approval = await this.findOne(id);
    if (approval.status !== ApprovalStatus.PENDING) {
      throw new BadRequestException(`Approval is already ${approval.status}`);
    }

    approval.status = ApprovalStatus.REJECTED;
    approval.approvedBy = userId;
    approval.decisionAt = new Date();
    approval.notes = notes;
    const saved = await this.approvalRepo.save(approval);

    this.natsClient.emit(EventSubjects.APPROVAL_REJECTED, {
      eventId: uuidv4(),
      timestamp: new Date().toISOString(),
      source: 'api-gateway',
      approvalId: id,
      workflowId: approval.workflowId,
      taskId: approval.taskId,
    });

    return saved;
  }
}
