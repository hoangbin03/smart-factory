'use client';

import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bot, BrainCircuit, Check, Cpu, Edit3, Save, Settings, SlidersHorizontal, Zap } from 'lucide-react';
import { api } from '@/lib/api';
import { ErrorState, LoadingState, StatusBadge } from '@/components/ui';

type AgentRecord = {
  agent_id: string;
  name: string;
  description?: string | null;
  role: string;
  runtime: string;
  capabilities?: string[];
  tools?: string[];
  status: string;
  config?: Record<string, any> | null;
};

type AiConfig = {
  provider: string;
  model: string;
  temperature: number;
  top_p: number;
  max_tokens: number;
  presence_penalty: number;
  frequency_penalty: number;
};

type AgentForm = {
  name: string;
  description: string;
  status: string;
  ai: AiConfig;
};

const defaultAiConfig: AiConfig = {
  provider: 'openrouter',
  model: 'openai/gpt-4o-mini',
  temperature: 0.1,
  top_p: 1,
  max_tokens: 4096,
  presence_penalty: 0,
  frequency_penalty: 0,
};

const modelOptions = [
  'openai/gpt-4o-mini',
  'openai/gpt-4o',
  'anthropic/claude-3.5-sonnet',
  'google/gemini-2.0-flash-001',
  'meta-llama/llama-3.1-70b-instruct',
  'meta/llama-3.1-70b-instruct',
];

function toNumber(value: unknown, fallback: number) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function readAiConfig(agent: AgentRecord | null): AiConfig {
  const raw = (agent?.config?.ai || {}) as Partial<AiConfig>;
  return {
    provider: String(raw.provider || defaultAiConfig.provider),
    model: String(raw.model || defaultAiConfig.model),
    temperature: toNumber(raw.temperature, defaultAiConfig.temperature),
    top_p: toNumber(raw.top_p, defaultAiConfig.top_p),
    max_tokens: toNumber(raw.max_tokens, defaultAiConfig.max_tokens),
    presence_penalty: toNumber(raw.presence_penalty, defaultAiConfig.presence_penalty),
    frequency_penalty: toNumber(raw.frequency_penalty, defaultAiConfig.frequency_penalty),
  };
}

function buildForm(agent: AgentRecord): AgentForm {
  return {
    name: agent.name || '',
    description: agent.description || '',
    status: agent.status || 'HEALTHY',
    ai: readAiConfig(agent),
  };
}

function cleanAiConfig(ai: AiConfig): AiConfig {
  return {
    provider: ai.provider || defaultAiConfig.provider,
    model: ai.model.trim() || defaultAiConfig.model,
    temperature: Math.min(2, Math.max(0, toNumber(ai.temperature, defaultAiConfig.temperature))),
    top_p: Math.min(1, Math.max(0, toNumber(ai.top_p, defaultAiConfig.top_p))),
    max_tokens: Math.min(32768, Math.max(128, Math.round(toNumber(ai.max_tokens, defaultAiConfig.max_tokens)))),
    presence_penalty: Math.min(2, Math.max(-2, toNumber(ai.presence_penalty, defaultAiConfig.presence_penalty))),
    frequency_penalty: Math.min(2, Math.max(-2, toNumber(ai.frequency_penalty, defaultAiConfig.frequency_penalty))),
  };
}

export default function AgentConfigPage() {
  const queryClient = useQueryClient();
  const agents = useQuery({ queryKey: ['nexus', 'agents'], queryFn: api.nexus.agents });
  const [selectedAgent, setSelectedAgent] = useState<AgentRecord | null>(null);
  const [formData, setFormData] = useState<AgentForm | null>(null);
  const [saveMessage, setSaveMessage] = useState('');

  const agentList = useMemo(() => {
    const rows = (agents.data?.data || []) as AgentRecord[];
    return [...rows].sort((a, b) => {
      if (a.agent_id === 'nexus_agent') return -1;
      if (b.agent_id === 'nexus_agent') return 1;
      return a.role.localeCompare(b.role) || a.name.localeCompare(b.name);
    });
  }, [agents.data]);

  useEffect(() => {
    if (!selectedAgent && agentList.length) {
      const initial = agentList.find(agent => agent.agent_id === 'nexus_agent') || agentList[0];
      setSelectedAgent(initial);
      setFormData(buildForm(initial));
    }
  }, [agentList, selectedAgent]);

  const updateMut = useMutation({
    mutationFn: (data: { agentId: string; body: any }) => api.nexus.updateAgent(data.agentId, data.body),
    onSuccess: (updated: AgentRecord) => {
      queryClient.invalidateQueries({ queryKey: ['nexus', 'agents'] });
      setSelectedAgent(updated);
      setFormData(buildForm(updated));
      setSaveMessage('Saved');
      window.setTimeout(() => setSaveMessage(''), 1800);
    },
    onError: (error) => setSaveMessage(error instanceof Error ? error.message : 'Save failed'),
  });

  const handleSelect = (agent: AgentRecord) => {
    setSelectedAgent(agent);
    setFormData(buildForm(agent));
    setSaveMessage('');
  };

  const updateAi = (patch: Partial<AiConfig>) => {
    setFormData(current => current ? ({ ...current, ai: { ...current.ai, ...patch } }) : current);
  };

  const handleSave = (event: FormEvent) => {
    event.preventDefault();
    if (!selectedAgent || !formData) return;

    const nextConfig = {
      ...(selectedAgent.config || {}),
      ai: cleanAiConfig(formData.ai),
    };

    updateMut.mutate({
      agentId: selectedAgent.agent_id,
      body: {
        name: formData.name.trim(),
        description: formData.description.trim(),
        status: formData.status,
        config: nextConfig,
      },
    });
  };

  return (
    <div className="page-wide">
      <div className="page-header">
        <div>
          <h1 className="page-title"><Settings size={24} style={{ display: 'inline', color: '#6366f1', verticalAlign: 'middle', marginRight: 8 }}/> Agent Configuration</h1>
          <p className="page-subtitle">Manage runtime identity and AI generation settings.</p>
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '320px minmax(0, 1fr)', gap: 24, alignItems: 'start' }}>
        <div className="panel">
          <div className="panel-head"><div className="panel-title"><Bot size={16}/> Registered Agents</div></div>
          <div className="panel-pad stack">
            {agents.isLoading && <LoadingState />}
            {agents.error && <ErrorState error={agents.error} />}
            {agentList.map((agent) => {
              const active = selectedAgent?.agent_id === agent.agent_id;
              const isNexus = agent.agent_id === 'nexus_agent';
              return (
                <button
                  type="button"
                  key={agent.agent_id}
                  className="card"
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    cursor: 'pointer',
                    border: active ? '1px solid #6366f1' : '1px solid var(--border)',
                    background: active ? 'rgba(99, 102, 241, 0.12)' : undefined,
                  }}
                  onClick={() => handleSelect(agent)}
                >
                  <div className="spread">
                    <div style={{ minWidth: 0 }}>
                      <strong style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        {isNexus ? <Zap size={15} color="#fbbf24" /> : <Cpu size={15} color="#94a3b8" />}
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{agent.name}</span>
                      </strong>
                      <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>{isNexus ? 'Nexus AI Master' : agent.role}</div>
                    </div>
                    <StatusBadge status={agent.status} />
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <div className="panel-title"><Edit3 size={16}/> Configuration Editor</div>
            {saveMessage && <span className="muted" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><Check size={14}/>{saveMessage}</span>}
          </div>
          <div className="panel-pad">
            {!selectedAgent || !formData ? (
              <div className="muted text-center" style={{ padding: 40 }}>Select an agent.</div>
            ) : (
              <form onSubmit={handleSave} className="stack" style={{ gap: 22 }}>
                <div className="grid grid-2">
                  <div>
                    <label className="label">Agent ID</label>
                    <input className="input" value={selectedAgent.agent_id} disabled style={{ opacity: 0.6 }} />
                  </div>
                  <div>
                    <label className="label">Runtime Engine</label>
                    <input className="input" value={selectedAgent.runtime} disabled style={{ opacity: 0.6 }} />
                  </div>
                </div>

                <div className="grid grid-2">
                  <div>
                    <label className="label">Display Name</label>
                    <input className="input" value={formData.name} onChange={event => setFormData({ ...formData, name: event.target.value })} />
                  </div>
                  <div>
                    <label className="label">Status</label>
                    <select className="input" value={formData.status} onChange={event => setFormData({ ...formData, status: event.target.value })}>
                      <option value="HEALTHY">HEALTHY</option>
                      <option value="DEGRADED">DEGRADED</option>
                      <option value="MAINTENANCE">MAINTENANCE</option>
                      <option value="OFFLINE">OFFLINE</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="label">Description / Mission</label>
                  <textarea className="input" style={{ minHeight: 84, resize: 'vertical' }} value={formData.description} onChange={event => setFormData({ ...formData, description: event.target.value })} />
                </div>

                <section className="stack" style={{ gap: 16, borderTop: '1px solid var(--border)', paddingTop: 20 }}>
                  <div className="panel-title" style={{ fontSize: 14 }}><BrainCircuit size={16}/> AI Runtime</div>
                  <div className="grid grid-2">
                    <div>
                      <label className="label">Provider</label>
                      <select className="input" value={formData.ai.provider} onChange={event => updateAi({ provider: event.target.value })}>
                        <option value="openrouter">OpenRouter</option>
                        <option value="nvidia">NVIDIA NIM</option>
                        <option value="auto">Auto</option>
                      </select>
                    </div>
                    <div>
                      <label className="label">Model</label>
                      <input className="input" list="agent-model-options" value={formData.ai.model} onChange={event => updateAi({ model: event.target.value })} />
                      <datalist id="agent-model-options">
                        {modelOptions.map(model => <option value={model} key={model} />)}
                      </datalist>
                    </div>
                  </div>

                  <div className="grid grid-3">
                    <div>
                      <label className="label">Temperature</label>
                      <input type="number" className="input" min={0} max={2} step={0.05} value={formData.ai.temperature} onChange={event => updateAi({ temperature: Number(event.target.value) })} />
                    </div>
                    <div>
                      <label className="label">Top P</label>
                      <input type="number" className="input" min={0} max={1} step={0.05} value={formData.ai.top_p} onChange={event => updateAi({ top_p: Number(event.target.value) })} />
                    </div>
                    <div>
                      <label className="label">Max Tokens</label>
                      <input type="number" className="input" min={128} max={32768} step={128} value={formData.ai.max_tokens} onChange={event => updateAi({ max_tokens: Number(event.target.value) })} />
                    </div>
                  </div>

                  <div className="grid grid-2">
                    <div>
                      <label className="label">Presence Penalty</label>
                      <input type="number" className="input" min={-2} max={2} step={0.1} value={formData.ai.presence_penalty} onChange={event => updateAi({ presence_penalty: Number(event.target.value) })} />
                    </div>
                    <div>
                      <label className="label">Frequency Penalty</label>
                      <input type="number" className="input" min={-2} max={2} step={0.1} value={formData.ai.frequency_penalty} onChange={event => updateAi({ frequency_penalty: Number(event.target.value) })} />
                    </div>
                  </div>
                </section>

                <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: 4 }}>
                  <button type="submit" className="btn btn-primary" disabled={updateMut.isPending}>
                    {updateMut.isPending ? <SlidersHorizontal size={16}/> : <Save size={16}/>} {updateMut.isPending ? 'Saving...' : 'Save Configuration'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}