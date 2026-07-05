import {
  Entity, PrimaryGeneratedColumn, Column,
  CreateDateColumn, UpdateDateColumn,
} from 'typeorm';
import { TaskStatus } from '@factory/shared-types';

@Entity('tasks')
export class TaskEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'workflow_id', type: 'uuid' })
  workflowId: string;

  @Column()
  name: string;

  @Column({ nullable: true, type: 'text' })
  description?: string;

  @Column({ type: 'enum', enum: TaskStatus, default: TaskStatus.PENDING })
  status: TaskStatus;

  @Column({ name: 'agent_id', nullable: true })
  agentId?: string;

  @Column({ type: 'text' })
  goal: string;

  @Column({ type: 'jsonb', default: '{}' })
  input: Record<string, unknown>;

  @Column({ type: 'jsonb', default: '{}' })
  output: Record<string, unknown>;

  @Column({ type: 'jsonb', default: '{}' })
  constraints: Record<string, unknown>;

  @Column({ name: 'order', default: 0 })
  order: number;

  @Column({ name: 'retry_count', default: 0 })
  retryCount: number;

  @Column({ name: 'max_retries', default: 3 })
  maxRetries: number;

  @Column({ name: 'started_at', nullable: true, type: 'timestamptz' })
  startedAt?: Date;

  @Column({ name: 'completed_at', nullable: true, type: 'timestamptz' })
  completedAt?: Date;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamptz' })
  updatedAt: Date;
}
