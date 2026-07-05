import {
  Entity, PrimaryGeneratedColumn, Column,
  CreateDateColumn, UpdateDateColumn,
} from 'typeorm';
import { AgentStatus } from '@factory/shared-types';

@Entity('agents')
export class AgentEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'agent_id', unique: true })
  agentId: string;

  @Column()
  name: string;

  @Column()
  role: string;

  @Column({ default: 'nemo' })
  runtime: string;

  @Column({ type: 'text', array: true, default: '{}' })
  capabilities: string[];

  @Column({ type: 'text', array: true, default: '{}' })
  tools: string[];

  @Column({ type: 'enum', enum: AgentStatus, default: AgentStatus.HEALTHY })
  status: AgentStatus;

  @Column({ type: 'jsonb', default: '{}' })
  config: Record<string, unknown>;

  @Column({ name: 'last_seen_at', nullable: true, type: 'timestamptz' })
  lastSeenAt?: Date;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamptz' })
  updatedAt: Date;
}
