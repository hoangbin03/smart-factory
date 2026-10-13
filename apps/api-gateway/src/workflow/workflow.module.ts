import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { WorkflowController } from './workflow.controller';
import { WorkflowService } from './workflow.service';
import { WorkflowEntity } from './entities/workflow.entity';
import { TaskEntity } from '../task/entities/task.entity';

@Module({
  imports: [TypeOrmModule.forFeature([WorkflowEntity, TaskEntity])],
  controllers: [WorkflowController],
  providers: [WorkflowService],
  exports: [WorkflowService],
})
export class WorkflowModule {}
