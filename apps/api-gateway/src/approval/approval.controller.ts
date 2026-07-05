import { Controller, Get, Post, Patch, Body, Param, UseGuards, Request } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import { IsString, IsOptional } from 'class-validator';
import { ApiProperty } from '@nestjs/swagger';
import { ApprovalService } from './approval.service';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';

class CreateApprovalDto {
  @ApiProperty({ required: false }) @IsOptional() @IsString() workflowId?: string;
  @ApiProperty({ required: false }) @IsOptional() @IsString() taskId?: string;
  @ApiProperty() @IsString() title: string;
  @ApiProperty({ required: false }) @IsOptional() @IsString() description?: string;
}

class DecisionDto {
  @ApiProperty({ required: false }) @IsOptional() @IsString() notes?: string;
}

@ApiTags('approvals')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('v1/approvals')
export class ApprovalController {
  constructor(private readonly approvalService: ApprovalService) {}

  @Post()
  @ApiOperation({ summary: 'Request approval' })
  create(@Body() dto: CreateApprovalDto, @Request() req: { user: { sub: string } }) {
    return this.approvalService.create({ ...dto, requestedBy: req.user.sub });
  }

  @Get('pending')
  @ApiOperation({ summary: 'List pending approvals' })
  findPending() {
    return this.approvalService.findPending();
  }

  @Get(':id')
  @ApiOperation({ summary: 'Get approval by ID' })
  findOne(@Param('id') id: string) {
    return this.approvalService.findOne(id);
  }

  @Patch(':id/approve')
  @ApiOperation({ summary: 'Approve a request' })
  approve(
    @Param('id') id: string,
    @Body() dto: DecisionDto,
    @Request() req: { user: { sub: string } },
  ) {
    return this.approvalService.approve(id, req.user.sub, dto.notes);
  }

  @Patch(':id/reject')
  @ApiOperation({ summary: 'Reject a request' })
  reject(
    @Param('id') id: string,
    @Body() dto: DecisionDto,
    @Request() req: { user: { sub: string } },
  ) {
    return this.approvalService.reject(id, req.user.sub, dto.notes);
  }
}
