import { NestFactory } from '@nestjs/core';
import { ValidationPipe, VersioningType } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { SwaggerModule, DocumentBuilder } from '@nestjs/swagger';
import { NestExpressApplication } from '@nestjs/platform-express';
import helmet from 'helmet';
import compression from 'compression';
import morgan from 'morgan';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create<NestExpressApplication>(AppModule, {
    logger: ['error', 'warn', 'log', 'debug', 'verbose'],
  });

  const configService = app.get(ConfigService);
  const port = configService.get<number>('PORT', 3000);
  const nodeEnv = configService.get<string>('NODE_ENV', 'development');

  // ─── Security ────────────────────────────────────────────────────
  app.use(helmet());
  app.enableCors({
    origin: nodeEnv === 'production'
      ? configService.get<string>('ALLOWED_ORIGINS', '').split(',')
      : true,
    credentials: true,
  });

  // ─── Compression & Logging ────────────────────────────────────────
  app.use(compression());
  app.use(morgan(nodeEnv === 'production' ? 'combined' : 'dev'));

  // ─── API Versioning ───────────────────────────────────────────────
  app.enableVersioning({ type: VersioningType.URI });

  // ─── Global Validation Pipe ───────────────────────────────────────
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
      transformOptions: { enableImplicitConversion: true },
    }),
  );

  // ─── Global Prefix ────────────────────────────────────────────────
  app.setGlobalPrefix('api');

  // ─── Swagger / OpenAPI ────────────────────────────────────────────
  if (nodeEnv !== 'production') {
    const swaggerConfig = new DocumentBuilder()
      .setTitle('Factory Platform API')
      .setDescription('Smart Software Factory - API Gateway')
      .setVersion('1.0')
      .addBearerAuth()
      .addTag('auth', 'Authentication endpoints')
      .addTag('workflows', 'Workflow management')
      .addTag('tasks', 'Task management')
      .addTag('agents', 'Agent registry')
      .addTag('approvals', 'Approval management')
      .addTag('audit', 'Audit logs')
      .addTag('health', 'Health checks')
      .build();

    const document = SwaggerModule.createDocument(app, swaggerConfig);
    SwaggerModule.setup('api/docs', app, document, {
      swaggerOptions: { persistAuthorization: true },
    });
  }

  await app.listen(port, '0.0.0.0');

  console.log(`
  ╔══════════════════════════════════════════════════╗
  ║     🏭  Factory Platform - API Gateway          ║
  ║     Environment : ${nodeEnv.padEnd(28)}║
  ║     Port        : ${String(port).padEnd(28)}║
  ║     Swagger     : http://localhost:${port}/api/docs  ║
  ╚══════════════════════════════════════════════════╝
  `);
}

bootstrap();
