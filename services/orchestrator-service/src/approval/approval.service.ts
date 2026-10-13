import { Injectable, Logger } from '@nestjs/common';
import { InjectDataSource } from '@nestjs/typeorm';
import { DataSource } from 'typeorm';

export interface ApprovalRow {
  id: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'ESCALATED' | 'EXPIRED';
}

/**
 * Human-in-the-loop approval gates. The orchestrator creates a PENDING approval
 * for a gated task and pauses the workflow; a human approves/rejects it (via the
 * gateway approvals API + Approvals UI), and the orchestrator resumes/fails.
 */
@Injectable()
export class ApprovalService {
  private readonly logger = new Logger(ApprovalService.name);

  constructor(@InjectDataSource() private readonly dataSource: DataSource) {}

  async findForTask(workflowId: string, taskId: string): Promise<ApprovalRow | null> {
    const rows = await this.dataSource.query(
      `SELECT id, status FROM approvals WHERE workflow_id = $1 AND task_id = $2
       ORDER BY created_at DESC LIMIT 1`,
      [workflowId, taskId],
    );
    return rows?.[0] ?? null;
  }

  async createGate(workflowId: string, taskId: string, title: string, description: string): Promise<void> {
    await this.dataSource.query(
      `INSERT INTO approvals (workflow_id, task_id, title, description, status)
       VALUES ($1, $2, $3, $4, 'PENDING')`,
      [workflowId, taskId, title, description],
    );
    this.logger.log(`Created approval gate for task ${taskId} in workflow ${workflowId}`);
  }
}
