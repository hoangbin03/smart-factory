import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ScheduleModule } from '@nestjs/schedule';
import { ClientsModule, Transport } from '@nestjs/microservices';

import { OrchestratorModule } from './orchestrator/orchestrator.module';
import { WorkflowEngineModule } from './workflow-engine/workflow-engine.module';
import { TaskEngineModule } from './task-engine/task-engine.module';
import { StateManagerModule } from './state-manager/state-manager.module';
import { AgentResolverModule } from './agent-resolver/agent-resolver.module';
import { NatsModule } from './nats/nats.module';
import { HealthController } from './health.controller';

@Module({
  controllers: [HealthController],
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    ScheduleModule.forRoot(),

    TypeOrmModule.forRootAsync({
      imports: [ConfigModule],
      useFactory: (config: ConfigService) => ({
        type: 'postgres',
        url: config.get<string>('DATABASE_URL'),
        entities: [__dirname + '/**/*.entity{.ts,.js}'],
        synchronize: false,
        logging: config.get<string>('NODE_ENV') === 'development',
      }),
      inject: [ConfigService],
    }),

    NatsModule,

    OrchestratorModule,
    WorkflowEngineModule,
    TaskEngineModule,
    StateManagerModule,
    AgentResolverModule,
  ],
})
export class AppModule {}
