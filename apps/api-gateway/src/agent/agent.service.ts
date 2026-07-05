import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { AgentEntity } from './entities/agent.entity';
import { AgentStatus } from '@factory/shared-types';

@Injectable()
export class AgentService {
  constructor(
    @InjectRepository(AgentEntity)
    private readonly agentRepo: Repository<AgentEntity>,
  ) {}

  async findAll(query: {
    status?: string;
    role?: string;
    search?: string;
    page?: number | string;
    limit?: number | string;
  }) {
    const parsedPage = Number(query.page);
    const parsedLimit = Number(query.limit);
    const page = Number.isInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1;
    const limit = Number.isInteger(parsedLimit) && parsedLimit > 0
      ? Math.min(parsedLimit, 100)
      : 20;
    const skip = (page - 1) * limit;
    const qb = this.agentRepo.createQueryBuilder('a');
    if (query.status) qb.andWhere('a.status = :status', { status: query.status });
    if (query.role) qb.andWhere('a.role = :role', { role: query.role });
    if (query.search) qb.andWhere('a.name ILIKE :search', { search: `%${query.search}%` });

    const [data, total] = await qb
      .orderBy('a.name', 'ASC')
      .skip(skip)
      .take(limit)
      .getManyAndCount();

    return {
      data,
      total,
      page,
      limit,
      totalPages: Math.ceil(total / limit),
    };
  }

  async findOne(id: string): Promise<AgentEntity> {
    const agent = await this.agentRepo.findOne({ where: { id } });
    if (!agent) throw new NotFoundException(`Agent ${id} not found`);
    return agent;
  }

  async findByAgentId(agentId: string): Promise<AgentEntity> {
    const agent = await this.agentRepo.findOne({ where: { agentId } });
    if (!agent) throw new NotFoundException(`Agent ${agentId} not found`);
    return agent;
  }

  async heartbeat(agentId: string): Promise<AgentEntity> {
    const agent = await this.findByAgentId(agentId);
    agent.lastSeenAt = new Date();
    agent.status = AgentStatus.HEALTHY;
    return this.agentRepo.save(agent);
  }

  async updateStatus(agentId: string, status: AgentStatus): Promise<AgentEntity> {
    const agent = await this.findByAgentId(agentId);
    agent.status = status;
    return this.agentRepo.save(agent);
  }

  async getHealthSummary() {
    const stats = await this.agentRepo
      .createQueryBuilder('a')
      .select('a.status', 'status')
      .addSelect('COUNT(*)', 'count')
      .groupBy('a.status')
      .getRawMany();

    return {
      total: stats.reduce((s: number, r) => s + parseInt(r.count, 10), 0),
      byStatus: stats.reduce((acc: Record<string, number>, r) => {
        acc[r.status] = parseInt(r.count, 10);
        return acc;
      }, {}),
    };
  }
}
