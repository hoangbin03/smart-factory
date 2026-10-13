import { Injectable, Logger } from '@nestjs/common';
import { InjectDataSource } from '@nestjs/typeorm';
import { DataSource } from 'typeorm';

/**
 * Writes an audit trail of everything the factory does — which agent ran,
 * task lifecycle, reworks, approvals — into the audit_logs table.
 * Non-blocking: audit failures never break orchestration.
 */
@Injectable()
export class AuditService {
  private readonly logger = new Logger(AuditService.name);

  constructor(@InjectDataSource() private readonly dataSource: DataSource) {}

  async record(
    action: 'CREATE' | 'UPDATE' | 'DELETE' | 'EXECUTE' | 'APPROVE' | 'REJECT',
    entityType: string,
    entityId: string | null,
    changes: Record<string, unknown> = {},
    actorType = 'agent',
  ): Promise<void> {
    try {
      await this.dataSource.query(
        `INSERT INTO audit_logs (action, entity_type, entity_id, actor_type, changes, metadata)
         VALUES ($1, $2, $3, $4, $5::jsonb, '{}'::jsonb)`,
        [action, entityType, entityId, actorType, JSON.stringify(changes ?? {})],
      );
    } catch (err) {
      this.logger.warn(`Audit write failed: ${(err as Error).message}`);
    }
  }
}
