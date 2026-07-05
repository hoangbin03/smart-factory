import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AgentResolverService } from './agent-resolver.service';
import { AgentEntity } from './entities/agent.entity';

@Module({
  imports: [TypeOrmModule.forFeature([AgentEntity])],
  providers: [AgentResolverService],
  exports: [AgentResolverService],
})
export class AgentResolverModule {}
