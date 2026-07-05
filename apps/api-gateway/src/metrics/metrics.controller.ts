import { Controller, Get, Res } from '@nestjs/common';
import { Response } from 'express';
import { ApiTags, ApiExcludeEndpoint } from '@nestjs/swagger';
import { register, collectDefaultMetrics } from 'prom-client';

collectDefaultMetrics({ prefix: 'factory_gateway_' });

@ApiTags('metrics')
@Controller('metrics')
export class MetricsController {
  @Get()
  @ApiExcludeEndpoint()
  async getMetrics(@Res() res: Response) {
    res.set('Content-Type', register.contentType);
    res.end(await register.metrics());
  }
}
