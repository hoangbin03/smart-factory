import {
  Entity, PrimaryGeneratedColumn, Column,
  CreateDateColumn, UpdateDateColumn,
} from 'typeorm';
import { ApprovalStatus } from '@factory/shared-types';

@Entity('approvals')
export class ApprovalEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'workflow_id', nullable: true, type: 'uuid' })
  workflowId?: string;

  @Column({ name: 'task_id', nullable: true, type: 'uuid' })
  taskId?: string;

  @Column()
  title: string;

  @Column({ nullable: true, type: 'text' })
  description?: string;

  @Column({ type: 'enum', enum: ApprovalStatus, default: ApprovalStatus.PENDING })
  status: ApprovalStatus;

  @Column({ name: 'requested_by', nullable: true, type: 'uuid' })
  requestedBy?: string;

  @Column({ name: 'approved_by', nullable: true, type: 'uuid' })
  approvedBy?: string;

  @Column({ name: 'decision_at', nullable: true, type: 'timestamptz' })
  decisionAt?: Date;

  @Column({ name: 'expires_at', nullable: true, type: 'timestamptz' })
  expiresAt?: Date;

  @Column({ nullable: true, type: 'text' })
  notes?: string;

  @Column({ type: 'jsonb', default: '{}' })
  metadata: Record<string, unknown>;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamptz' })
  updatedAt: Date;
}
