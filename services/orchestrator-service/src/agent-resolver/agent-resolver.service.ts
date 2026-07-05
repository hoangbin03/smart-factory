import { Injectable, Logger } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { AgentEntity } from './entities/agent.entity';
import { AgentStatus } from '@factory/shared-types';

@Injectable()
export class AgentResolverService {
  private readonly logger = new Logger(AgentResolverService.name);

  constructor(
    @InjectRepository(AgentEntity)
    private readonly agentRepo: Repository<AgentEntity>,
  ) {}

  /**
   * Resolve best available agent for a task.
   * Priority: explicit agentId → role-based match → any healthy agent
   */
  async resolve(
    preferredAgentId: string,
    goal: string,
  ): Promise<AgentEntity | null> {
    // 1. Try explicit agent
    if (preferredAgentId) {
      const agent = await this.agentRepo.findOne({
        where: { agentId: preferredAgentId, status: AgentStatus.HEALTHY },
      });
      if (agent) return agent;
    }

    // 2. Infer role from goal keywords
    const role = this.inferRole(goal);
    if (role) {
      const agent = await this.agentRepo.findOne({
        where: { role, status: AgentStatus.HEALTHY },
      });
      if (agent) {
        this.logger.log(`Resolved agent ${agent.agentId} for role ${role}`);
        return agent;
      }
    }

    // 3. Fallback: any healthy developer agent
    return this.agentRepo.findOne({
      where: { role: 'developer', status: AgentStatus.HEALTHY },
    });
  }

  private inferRole(goal: string): string | null {
    const lower = goal.toLowerCase();
    if (/(architect|design|schema|database|api design)/.test(lower)) return 'architect';
    if (/(plan|epic|story|sprint|roadmap|breakdown)/.test(lower)) return 'planner';
    if (/(code|build|implement|develop|feature|fix|refactor)/.test(lower)) return 'developer';
    if (/(review|code quality|security|audit code)/.test(lower)) return 'reviewer';
    if (/(test|qa|quality|defect|bug report)/.test(lower)) return 'qa';
    if (/(deploy|docker|kubernetes|ci\/cd|pipeline|infra)/.test(lower)) return 'devops';
    return null;
  }
}
