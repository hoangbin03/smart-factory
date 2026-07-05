import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { WorkflowEngineService } from './workflow-engine.service';
import { WorkflowEntity } from './entities/workflow.entity';

@Module({
  imports: [TypeOrmModule.forFeature([WorkflowEntity])],
  providers: [WorkflowEngineService],
  exports: [WorkflowEngineService],
})
export class WorkflowEngineModule {}
