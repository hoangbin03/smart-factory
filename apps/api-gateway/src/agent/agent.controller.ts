import { Controller, Get, Param, Query, Patch, UseGuards } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import { AgentService } from './agent.service';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';

@ApiTags('agents')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('v1/agents')
export class AgentController {
  constructor(private readonly agentService: AgentService) {}

  @Get()
  @ApiOperation({ summary: 'List all registered agents' })
  findAll(
    @Query('status') status?: string,
    @Query('role') role?: string,
    @Query('search') search?: string,
    @Query('page') page?: number,
    @Query('limit') limit?: number,
  ) {
    return this.agentService.findAll({ status, role, search, page, limit });
  }

  @Get('health')
  @ApiOperation({ summary: 'Get agent health summary' })
  getHealthSummary() {
    return this.agentService.getHealthSummary();
  }

  @Get(':id')
  @ApiOperation({ summary: 'Get agent by ID' })
  findOne(@Param('id') id: string) {
    return this.agentService.findOne(id);
  }

  @Patch(':agentId/heartbeat')
  @ApiOperation({ summary: 'Report agent heartbeat' })
  heartbeat(@Param('agentId') agentId: string) {
    return this.agentService.heartbeat(agentId);
  }
}
