import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ThrottlerModule } from '@nestjs/throttler';
import { TerminusModule } from '@nestjs/terminus';

import { AuthModule } from './auth/auth.module';
import { WorkflowModule } from './workflow/workflow.module';
import { TaskModule } from './task/task.module';
import { AgentModule } from './agent/agent.module';
import { ApprovalModule } from './approval/approval.module';
import { AuditModule } from './audit/audit.module';
import { HealthModule } from './health/health.module';
import { MetricsModule } from './metrics/metrics.module';
import { NatsModule } from './nats/nats.module';

@Module({
  imports: [
    // ─── Config ───────────────────────────────────────────────────
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: ['.env.local', '.env'],
    }),

    // ─── Rate Limiting ────────────────────────────────────────────
    ThrottlerModule.forRoot([
      { name: 'short', ttl: 1000, limit: 20 },
      { name: 'medium', ttl: 10000, limit: 100 },
      { name: 'long', ttl: 60000, limit: 1000 },
    ]),

    // ─── Database ─────────────────────────────────────────────────
    TypeOrmModule.forRootAsync({
      imports: [ConfigModule],
      useFactory: (config: ConfigService) => ({
        type: 'postgres',
        url: config.get<string>('DATABASE_URL'),
        entities: [__dirname + '/**/*.entity{.ts,.js}'],
        synchronize: false,
        logging: config.get<string>('NODE_ENV') === 'development',
        ssl: config.get<string>('DB_SSL') === 'true'
          ? { rejectUnauthorized: false }
          : false,
        poolSize: 20,
      }),
      inject: [ConfigService],
    }),

    // ─── Health ───────────────────────────────────────────────────
    TerminusModule,

    // ─── Application Modules ──────────────────────────────────────
    NatsModule,
    AuthModule,
    WorkflowModule,
    TaskModule,
    AgentModule,
    ApprovalModule,
    AuditModule,
    HealthModule,
    MetricsModule,
  ],
})
export class AppModule {}
