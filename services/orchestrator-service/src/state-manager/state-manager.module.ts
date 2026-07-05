import { Module } from '@nestjs/common';
import { StateManagerService } from './state-manager.service';

@Module({
  providers: [StateManagerService],
  exports: [StateManagerService],
})
export class StateManagerModule {}
