import {
  Controller, Get, Post, Put, Delete, Patch,
  Body, Param, Query, UseGuards, Request, Res,
  HttpCode, HttpStatus, Header,
} from '@nestjs/common';
import type { Response } from 'express';
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

  @Get(':id/artifacts')
  @ApiOperation({ summary: 'Get generated workflow artifacts' })
  getArtifacts(@Param('id') id: string) {
    return this.workflowService.getArtifacts(id);
  }

  @Get(':id/download')
  @ApiOperation({ summary: 'Download the produced project as a .zip' })
  async download(@Param('id') id: string, @Res() res: Response) {
    const runtimeUrl = process.env.AGENT_RUNTIME_URL || 'http://agent-runtime-service:8000';
    const upstream = await fetch(`${runtimeUrl}/api/v1/workspace/${id}/download`);
    if (!upstream.ok || !upstream.body) {
      res.status(upstream.status === 404 ? 404 : 502).json({
        message: upstream.status === 404 ? 'No downloadable project for this workflow yet.' : 'Download failed',
      });
      return;
    }
    res.setHeader('Content-Type', 'application/zip');
    res.setHeader('Content-Disposition', `attachment; filename="workflow-${id}.zip"`);
    const buffer = Buffer.from(await upstream.arrayBuffer());
    res.send(buffer);
  }

  @Post(':id/import/git')
  @ApiOperation({ summary: 'Clone a git repo into the workflow workspace' })
  async importGit(@Param('id') id: string, @Body() body: any, @Res() res: Response) {
    const runtimeUrl = process.env.AGENT_RUNTIME_URL || 'http://agent-runtime-service:8000';
    try {
      const upstream = await fetch(`${runtimeUrl}/api/v1/workspace/${id}/import/git`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body ?? {}),
      });
      const data = await upstream.json().catch(() => ({}));
      res.status(upstream.status).json(data);
    } catch (e: any) {
      res.status(502).json({ message: 'Import failed', detail: String(e?.message || e) });
    }
  }

  @Post(':id/import/upload')
  @ApiOperation({ summary: 'Import an uploaded local folder into the workflow workspace' })
  async importUpload(@Param('id') id: string, @Body() body: any, @Res() res: Response) {
    const runtimeUrl = process.env.AGENT_RUNTIME_URL || 'http://agent-runtime-service:8000';
    try {
      const upstream = await fetch(`${runtimeUrl}/api/v1/workspace/${id}/import/upload`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body ?? {}),
      });
      const data = await upstream.json().catch(() => ({}));
      res.status(upstream.status).json(data);
    } catch (e: any) {
      res.status(502).json({ message: 'Import failed', detail: String(e?.message || e) });
    }
  }

  @Post(':id/deploy')
  @ApiOperation({ summary: 'Build & run the produced project as a live preview container' })
  async deploy(@Param('id') id: string, @Res() res: Response) {
    const runtimeUrl = process.env.AGENT_RUNTIME_URL || 'http://agent-runtime-service:8000';
    try {
      const upstream = await fetch(`${runtimeUrl}/api/v1/workspace/${id}/deploy`, { method: 'POST' });
      const body = await upstream.json().catch(() => ({}));
      res.status(upstream.status).json(body);
    } catch (e: any) {
      res.status(502).json({ message: 'Deploy request failed', detail: String(e?.message || e) });
    }
  }

  @Post(':id/undeploy')
  @ApiOperation({ summary: 'Stop the workflow preview container' })
  async undeploy(@Param('id') id: string, @Res() res: Response) {
    const runtimeUrl = process.env.AGENT_RUNTIME_URL || 'http://agent-runtime-service:8000';
    try {
      const upstream = await fetch(`${runtimeUrl}/api/v1/workspace/${id}/undeploy`, { method: 'POST' });
      const body = await upstream.json().catch(() => ({}));
      res.status(upstream.status).json(body);
    } catch (e: any) {
      res.status(502).json({ message: 'Undeploy request failed', detail: String(e?.message || e) });
    }
  }

  @Get(':id/preview')
  @Header('Content-Type', 'text/html; charset=utf-8')
  @Header('Content-Security-Policy', "default-src 'self' 'unsafe-inline' data: blob:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'")
  @ApiOperation({ summary: 'Preview generated static web artifact' })
  preview(@Param('id') id: string) {
    return this.workflowService.getPreviewHtml(id);
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
