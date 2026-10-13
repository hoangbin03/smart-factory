import { Module } from '@nestjs/common';
import { OrchestratorService } from './orchestrator.service';
import { OrchestratorController } from './orchestrator.controller';
import { WorkflowEngineModule } from '../workflow-engine/workflow-engine.module';
import { TaskEngineModule } from '../task-engine/task-engine.module';
import { AgentResolverModule } from '../agent-resolver/agent-resolver.module';
import { AuditService } from '../audit/audit.service';
import { ApprovalService } from '../approval/approval.service';

@Module({
  imports: [
    WorkflowEngineModule,
    TaskEngineModule,
    AgentResolverModule,
  ],
  controllers: [OrchestratorController],
  providers: [OrchestratorService, AuditService, ApprovalService],
  exports: [OrchestratorService],
})
export class OrchestratorModule {}
