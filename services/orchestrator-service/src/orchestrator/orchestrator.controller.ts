import { Controller, Post, Body, Param, Get } from '@nestjs/common';
import { MessagePattern, Payload } from '@nestjs/microservices';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { OrchestratorService } from './orchestrator.service';
import { EventSubjects } from '@factory/shared-events';

@ApiTags('orchestrator')
@Controller('orchestrator')
export class OrchestratorController {
  constructor(private readonly orchestratorService: OrchestratorService) {}

  @Post('workflows/:id/start')
  @ApiOperation({ summary: 'Trigger workflow execution' })
  async startWorkflow(@Param('id') id: string) {
    await this.orchestratorService.startWorkflow(id);
    return { success: true, message: `Workflow ${id} started` };
  }

  @Post('workflows/:id/advance')
  @ApiOperation({ summary: 'Manually advance workflow to next task' })
  async advanceWorkflow(@Param('id') id: string) {
    await this.orchestratorService.advanceWorkflow(id);
    return { success: true, message: `Workflow ${id} advanced` };
  }

  // ─── NATS Event Handlers ───────────────────────────────────────────
  @MessagePattern(EventSubjects.WORKFLOW_STARTED)
  async handleWorkflowStarted(@Payload() payload: { workflowId: string }) {
    await this.orchestratorService.startWorkflow(payload.workflowId);
  }

  @MessagePattern(EventSubjects.RUNTIME_AGENT_RESULT)
  async handleAgentResult(
    @Payload()
    payload: {
      taskId: string;
      workflowId: string;
      agentId: string;
      success: boolean;
      output: Record<string, unknown>;
      summary: string;
    },
  ) {
    await this.orchestratorService.onTaskCompleted(payload);
  }
}
