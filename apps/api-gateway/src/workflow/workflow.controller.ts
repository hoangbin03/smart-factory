import {
  Controller, Get, Post, Put, Delete, Patch,
  Body, Param, Query, UseGuards, Request,
  HttpCode, HttpStatus,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth, ApiQuery } from '@nestjs/swagger';
import { WorkflowService } from './workflow.service';
import { CreateWorkflowDto, UpdateWorkflowDto } from './dto/workflow.dto';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';

@ApiTags('workflows')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('v1/workflows')
export class WorkflowController {
  constructor(private readonly workflowService: WorkflowService) {}

  @Post()
  @ApiOperation({ summary: 'Create a new workflow' })
  create(
    @Body() dto: CreateWorkflowDto,
    @Request() req: { user: { sub: string } },
  ) {
    return this.workflowService.create(dto, req.user.sub);
  }

  @Get()
  @ApiOperation({ summary: 'List all workflows with pagination' })
  @ApiQuery({ name: 'page', required: false })
  @ApiQuery({ name: 'limit', required: false })
  @ApiQuery({ name: 'status', required: false })
  @ApiQuery({ name: 'search', required: false })
  findAll(
    @Query('page') page?: number,
    @Query('limit') limit?: number,
    @Query('status') status?: string,
    @Query('search') search?: string,
  ) {
    return this.workflowService.findAll({ page, limit, status, search });
  }

  @Get('stats')
  @ApiOperation({ summary: 'Get workflow statistics by status' })
  getStats() {
    return this.workflowService.getStats();
  }

  @Get(':id')
  @ApiOperation({ summary: 'Get a single workflow by ID' })
  findOne(@Param('id') id: string) {
    return this.workflowService.findOne(id);
  }

  @Put(':id')
  @ApiOperation({ summary: 'Update a workflow' })
  update(@Param('id') id: string, @Body() dto: UpdateWorkflowDto) {
    return this.workflowService.update(id, dto);
  }

  @Patch(':id/start')
  @ApiOperation({ summary: 'Start a pending workflow' })
  start(@Param('id') id: string) {
    return this.workflowService.start(id);
  }

  @Patch(':id/cancel')
  @ApiOperation({ summary: 'Cancel a workflow' })
  cancel(@Param('id') id: string) {
    return this.workflowService.cancel(id);
  }

  @Delete(':id')
  @HttpCode(HttpStatus.NO_CONTENT)
  @ApiOperation({ summary: 'Delete a workflow' })
  remove(@Param('id') id: string) {
    return this.workflowService.remove(id);
  }
}
