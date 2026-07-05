import { Injectable, Logger } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { WorkflowEntity } from './entities/workflow.entity';
import { WorkflowStatus } from '@factory/shared-types';

@Injectable()
export class WorkflowEngineService {
  private readonly logger = new Logger(WorkflowEngineService.name);

  constructor(
    @InjectRepository(WorkflowEntity)
    private readonly workflowRepo: Repository<WorkflowEntity>,
  ) {}

  async getRunningWorkflows(): Promise<WorkflowEntity[]> {
    return this.workflowRepo.find({ where: { status: WorkflowStatus.RUNNING } });
  }

  async findOne(id: string): Promise<WorkflowEntity> {
    return this.workflowRepo.findOneOrFail({ where: { id } });
  }

  async startWorkflow(id: string): Promise<WorkflowEntity> {
    const workflow = await this.findOne(id);
    workflow.status = WorkflowStatus.RUNNING;
    workflow.startedAt = workflow.startedAt ?? new Date();
    return this.workflowRepo.save(workflow);
  }

  async completeWorkflow(id: string): Promise<WorkflowEntity> {
    const workflow = await this.findOne(id);
    workflow.status = WorkflowStatus.COMPLETED;
    workflow.completedAt = new Date();
    return this.workflowRepo.save(workflow);
  }

  async failWorkflow(id: string): Promise<WorkflowEntity> {
    const workflow = await this.findOne(id);
    workflow.status = WorkflowStatus.FAILED;
    return this.workflowRepo.save(workflow);
  }
}
