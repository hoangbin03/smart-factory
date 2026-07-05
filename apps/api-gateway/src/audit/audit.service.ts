import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { AuditLogEntity } from './entities/audit-log.entity';
import { AuditAction } from '@factory/shared-types';

@Injectable()
export class AuditService {
  constructor(
    @InjectRepository(AuditLogEntity)
    private readonly auditRepo: Repository<AuditLogEntity>,
  ) {}

  async log(data: {
    action: AuditAction;
    entityType: string;
    entityId?: string;
    actorId?: string;
    actorType?: string;
    changes?: Record<string, unknown>;
    metadata?: Record<string, unknown>;
    ipAddress?: string;
    userAgent?: string;
  }): Promise<AuditLogEntity> {
    const log = this.auditRepo.create({
      action: data.action,
      entityType: data.entityType,
      entityId: data.entityId,
      actorId: data.actorId,
      actorType: data.actorType ?? 'user',
      changes: data.changes ?? {},
      metadata: data.metadata ?? {},
      ipAddress: data.ipAddress,
      userAgent: data.userAgent,
    });
    return this.auditRepo.save(log);
  }

  async findAll(query: {
    entityType?: string;
    entityId?: string;
    actorId?: string;
    action?: string;
    page?: number | string;
    limit?: number | string;
  }) {
    const parsedPage = Number(query.page);
    const parsedLimit = Number(query.limit);
    const page = Number.isInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1;
    const limit = Number.isInteger(parsedLimit) && parsedLimit > 0
      ? Math.min(parsedLimit, 200)
      : 50;
    const skip = (page - 1) * limit;

    const qb = this.auditRepo.createQueryBuilder('al')
      .orderBy('al.created_at', 'DESC')
      .skip(skip)
      .take(limit);

    if (query.entityType) qb.andWhere('al.entity_type = :et', { et: query.entityType });
    if (query.entityId) qb.andWhere('al.entity_id = :ei', { ei: query.entityId });
    if (query.actorId) qb.andWhere('al.actor_id = :ai', { ai: query.actorId });
    if (query.action) qb.andWhere('al.action = :action', { action: query.action });

    const [data, total] = await qb.getManyAndCount();
    return { data, total, page, limit, totalPages: Math.ceil(total / limit) };
  }
}
