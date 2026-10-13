'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Bot, Check, Cpu, FolderGit2, Terminal, GitBranch, ScanSearch,
  FlaskConical, Search, FileText, ListChecks, Container, Ship,
  Wrench, Save, Zap,
} from 'lucide-react';
import { api } from '@/lib/api';
import { ErrorState, LoadingState } from '@/components/ui';

type ToolDef = {
  tool_id: string;
  name: string;
  category: string;
  status: 'active' | 'builtin' | 'planned' | string;
  description: string;
};

type AgentRecord = {
  agent_id: string;
  name: string;
  role: string;
  status: string;
  tools?: string[];
};

const TOOL_ICONS: Record<string, typeof Wrench> = {
  filesystem_tool: FolderGit2,
  terminal_tool: Terminal,
  git_tool: GitBranch,
  code_analysis_tool: ScanSearch,
  test_runner_tool: FlaskConical,
  search_tool: Search,
  documentation_tool: FileText,
  planning_tool: ListChecks,
  docker_tool: Container,
  kubernetes_tool: Ship,
};

const STATUS_STYLE: Record<string, { bg: string; fg: string; label: string }> = {
  active: { bg: 'rgba(34,197,94,0.14)', fg: '#22c55e', label: 'ACTIVE' },
  builtin: { bg: 'rgba(99,102,241,0.14)', fg: '#818cf8', label: 'BUILT-IN' },
  planned: { bg: 'rgba(148,163,184,0.14)', fg: '#94a3b8', label: 'ROADMAP' },
};

function ToolStatus({ status }: { status: string }) {
  const s = STATUS_STYLE[status] || STATUS_STYLE.planned;
  return (
    <span style={{ background: s.bg, color: s.fg, fontSize: 10, fontWeight: 800, padding: '2px 8px', borderRadius: 999, letterSpacing: 0.4 }}>
      {s.label}
    </span>
  );
}

export default function ToolConfigPage() {
  const queryClient = useQueryClient();
  const toolsQuery = useQuery({ queryKey: ['nexus', 'tools'], queryFn: api.nexus.tools });
  const agentsQuery = useQuery({ queryKey: ['nexus', 'agents'], queryFn: api.nexus.agents });

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedTools, setSelectedTools] = useState<string[]>([]);
  const [saveMessage, setSaveMessage] = useState('');

  const catalog = useMemo<ToolDef[]>(() => (toolsQuery.data?.data || []) as ToolDef[], [toolsQuery.data]);
  const agents = useMemo<AgentRecord[]>(() => {
    const rows = (agentsQuery.data?.data || []) as AgentRecord[];
    return [...rows].sort((a, b) => {
      if (a.agent_id === 'nexus_agent') return -1;
      if (b.agent_id === 'nexus_agent') return 1;
      return a.role.localeCompare(b.role) || a.name.localeCompare(b.name);
    });
  }, [agentsQuery.data]);

  const selectedAgent = useMemo(() => agents.find(a => a.agent_id === selectedId) || null, [agents, selectedId]);

  useEffect(() => {
    if (!selectedId && agents.length) {
      const first = agents.find(a => a.agent_id === 'developer_agent') || agents[0];
      setSelectedId(first.agent_id);
      setSelectedTools(first.tools || []);
    }
  }, [agents, selectedId]);

  const selectAgent = (agent: AgentRecord) => {
    setSelectedId(agent.agent_id);
    setSelectedTools(agent.tools || []);
    setSaveMessage('');
  };

  const toggleTool = (toolId: string) => {
    setSelectedTools(current =>
      current.includes(toolId) ? current.filter(t => t !== toolId) : [...current, toolId],
    );
  };

  const dirty = useMemo(() => {
    const a = [...(selectedAgent?.tools || [])].sort().join(',');
    const b = [...selectedTools].sort().join(',');
    return a !== b;
  }, [selectedAgent, selectedTools]);

  const saveMut = useMutation({
    mutationFn: () => api.nexus.updateAgent(selectedId!, { tools: selectedTools }),
    onSuccess: (updated: AgentRecord) => {
      queryClient.invalidateQueries({ queryKey: ['nexus', 'agents'] });
      setSelectedTools(updated.tools || selectedTools);
      setSaveMessage('Saved');
      window.setTimeout(() => setSaveMessage(''), 1800);
    },
    onError: (error) => setSaveMessage(error instanceof Error ? error.message : 'Save failed'),
  });

  // how many agents use each tool — quick coverage read
  const usage = useMemo(() => {
    const map: Record<string, number> = {};
    agents.forEach(a => (a.tools || []).forEach(t => { map[t] = (map[t] || 0) + 1; }));
    return map;
  }, [agents]);

  const activeCount = catalog.filter(t => t.status === 'active').length;

  return (
    <div className="page-wide">
      <div className="page-header">
        <div>
          <h1 className="page-title">
            <Wrench size={24} style={{ display: 'inline', color: '#6366f1', verticalAlign: 'middle', marginRight: 8 }} />
            Tool Configuration
          </h1>
          <p className="page-subtitle">
            Assign the real tool layer to each agent. {activeCount} active tools run on the workflow workspace.
          </p>
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '300px minmax(0, 1fr)', gap: 24, alignItems: 'start' }}>
        {/* Agent picker */}
        <div className="panel">
          <div className="panel-head"><div className="panel-title"><Bot size={16} /> Agents</div></div>
          <div className="panel-pad stack">
            {agentsQuery.isLoading && <LoadingState />}
            {agentsQuery.error && <ErrorState error={agentsQuery.error} />}
            {agents.map(agent => {
              const active = selectedId === agent.agent_id;
              const isNexus = agent.agent_id === 'nexus_agent';
              return (
                <button
                  type="button"
                  key={agent.agent_id}
                  className="card"
                  style={{
                    width: '100%', textAlign: 'left', cursor: 'pointer',
                    border: active ? '1px solid #6366f1' : '1px solid var(--border)',
                    background: active ? 'rgba(99,102,241,0.12)' : undefined,
                  }}
                  onClick={() => selectAgent(agent)}
                >
                  <div className="spread">
                    <div style={{ minWidth: 0 }}>
                      <strong style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        {isNexus ? <Zap size={15} color="#fbbf24" /> : <Cpu size={15} color="#94a3b8" />}
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{agent.name}</span>
                      </strong>
                      <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>{agent.role}</div>
                    </div>
                    <span className="muted" style={{ fontSize: 12 }}>{(agent.tools || []).length} tools</span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Tool assignment */}
        <div className="panel">
          <div className="panel-head">
            <div className="panel-title">
              <Wrench size={16} /> {selectedAgent ? `Tools for ${selectedAgent.name}` : 'Tools'}
            </div>
            <div style={{ display: 'inline-flex', gap: 12, alignItems: 'center' }}>
              {saveMessage && (
                <span className="muted" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <Check size={14} />{saveMessage}
                </span>
              )}
              <button
                type="button"
                className="btn btn-primary"
                disabled={!dirty || saveMut.isPending || !selectedAgent}
                onClick={() => saveMut.mutate()}
              >
                <Save size={16} /> {saveMut.isPending ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
          <div className="panel-pad">
            {toolsQuery.isLoading && <LoadingState />}
            {toolsQuery.error && <ErrorState error={toolsQuery.error} />}
            {!toolsQuery.isLoading && (
              <div className="stack" style={{ gap: 10 }}>
                {catalog.map(tool => {
                  const Icon = TOOL_ICONS[tool.tool_id] || Wrench;
                  const enabled = selectedTools.includes(tool.tool_id);
                  return (
                    <label
                      key={tool.tool_id}
                      className="card"
                      style={{
                        display: 'flex', gap: 14, alignItems: 'flex-start', cursor: 'pointer',
                        border: enabled ? '1px solid #6366f1' : '1px solid var(--border)',
                        background: enabled ? 'rgba(99,102,241,0.08)' : undefined,
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={enabled}
                        onChange={() => toggleTool(tool.tool_id)}
                        style={{ marginTop: 4, width: 16, height: 16, accentColor: '#6366f1' }}
                      />
                      <div style={{
                        width: 34, height: 34, borderRadius: 8, flexShrink: 0,
                        display: 'grid', placeItems: 'center',
                        background: 'rgba(99,102,241,0.10)', color: '#818cf8',
                      }}>
                        <Icon size={18} />
                      </div>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div className="spread" style={{ gap: 8 }}>
                          <strong style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}>
                            {tool.name}
                            <code style={{ fontSize: 11, color: 'var(--muted)' }}>{tool.tool_id}</code>
                          </strong>
                          <div style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}>
                            <span className="muted" style={{ fontSize: 11 }}>{usage[tool.tool_id] || 0} agents</span>
                            <ToolStatus status={tool.status} />
                          </div>
                        </div>
                        <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>{tool.description}</div>
                        <div className="muted" style={{ fontSize: 11, marginTop: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                          {tool.category}
                        </div>
                      </div>
                    </label>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
