import { NestFactory } from '@nestjs/core';
import { ConfigService } from '@nestjs/config';
import { ValidationPipe } from '@nestjs/common';
import { Transport } from '@nestjs/microservices';
import { SwaggerModule, DocumentBuilder } from '@nestjs/swagger';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  const config = app.get(ConfigService);
  const port = config.get<number>('PORT', 4001);

  app.useGlobalPipes(new ValidationPipe({ whitelist: true, transform: true }));
  app.setGlobalPrefix('api');

  app.connectMicroservice({
    transport: Transport.NATS,
    options: {
      servers: [config.get<string>('NATS_URL', 'nats://localhost:4222')],
      queue: 'factory_orchestrator',
    },
  });

  const swaggerConfig = new DocumentBuilder()
    .setTitle('Orchestrator Service')
    .setDescription('Factory Orchestrator - Workflow & Task Engine')
    .setVersion('1.0')
    .build();

  SwaggerModule.setup('api/docs', app, SwaggerModule.createDocument(app, swaggerConfig));

  await app.startAllMicroservices();
  await app.listen(port, '0.0.0.0');
  console.log(`🏭 Orchestrator Service running on port ${port}`);
}

bootstrap();
