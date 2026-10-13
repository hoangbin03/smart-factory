'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Sparkles, Plus, Save, Trash2, Check, LayoutTemplate, Wand2, Tag, Bot, Cpu, Zap,
} from 'lucide-react';
import { api } from '@/lib/api';
import { ErrorState, LoadingState } from '@/components/ui';

type Skill = {
  id: string;
  slug: string;
  name: string;
  description?: string;
  category: string;
  kind: 'skill' | 'template' | string;
  instructions: string;
  tags?: string[];
  is_active?: boolean;
};

type AgentRecord = {
  agent_id: string;
  name: string;
  role: string;
  config?: Record<string, any> | null;
};

type Draft = {
  id: string | null;
  name: string;
  kind: string;
  category: string;
  description: string;
  instructions: string;
  tagsText: string;
};

const EMPTY_DRAFT: Draft = {
  id: null, name: '', kind: 'skill', category: 'general',
  description: '', instructions: '', tagsText: '',
};

function toDraft(s: Skill): Draft {
  return {
    id: s.id, name: s.name, kind: s.kind || 'skill', category: s.category || 'general',
    description: s.description || '', instructions: s.instructions || '',
    tagsText: (s.tags || []).join(', '),
  };
}

function KindBadge({ kind }: { kind: string }) {
  const isTemplate = kind === 'template';
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 10, fontWeight: 800,
      padding: '2px 8px', borderRadius: 999, letterSpacing: 0.4,
      background: isTemplate ? 'rgba(234,179,8,0.14)' : 'rgba(99,102,241,0.14)',
      color: isTemplate ? '#eab308' : '#818cf8',
    }}>
      {isTemplate ? <LayoutTemplate size={11} /> : <Wand2 size={11} />}
      {isTemplate ? 'TEMPLATE' : 'SKILL'}
    </span>
  );
}

export default function TemplatesPage() {
  const queryClient = useQueryClient();
  const skillsQuery = useQuery({ queryKey: ['nexus', 'skills'], queryFn: api.nexus.skills.list });
  const agentsQuery = useQuery({ queryKey: ['nexus', 'agents'], queryFn: api.nexus.agents });

  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [message, setMessage] = useState('');

  const skills = useMemo<Skill[]>(() => (skillsQuery.data?.data || []) as Skill[], [skillsQuery.data]);
  const agents = useMemo<AgentRecord[]>(() => (agentsQuery.data?.data || []) as AgentRecord[], [agentsQuery.data]);
  const selectedSkill = useMemo(() => skills.find(s => s.id === draft.id) || null, [skills, draft.id]);

  useEffect(() => {
    if (draft.id === null && draft.name === '' && skills.length) {
      setDraft(toDraft(skills[0]));
    }
  }, [skills, draft.id, draft.name]);

  const flash = (m: string) => { setMessage(m); window.setTimeout(() => setMessage(''), 1800); };

  const saveMut = useMutation({
    mutationFn: () => {
      const body = {
        name: draft.name.trim(),
        kind: draft.kind,
        category: draft.category.trim() || 'general',
        description: draft.description.trim(),
        instructions: draft.instructions.trim(),
        tags: draft.tagsText.split(',').map(t => t.trim()).filter(Boolean),
      };
      return draft.id ? api.nexus.skills.update(draft.id, body) : api.nexus.skills.create(body);
    },
    onSuccess: (saved: Skill) => {
      queryClient.invalidateQueries({ queryKey: ['nexus', 'skills'] });
      setDraft(toDraft(saved));
      flash('Saved');
    },
    onError: (e) => flash(e instanceof Error ? e.message : 'Save failed'),
  });

  const deleteMut = useMutation({
    mutationFn: () => api.nexus.skills.remove(draft.id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['nexus', 'skills'] });
      setDraft(EMPTY_DRAFT);
      flash('Deleted');
    },
    onError: (e) => flash(e instanceof Error ? e.message : 'Delete failed'),
  });

  // assign / unassign the selected skill to an agent (stored on agent.config.skills)
  const assignMut = useMutation({
    mutationFn: async ({ agent, enable }: { agent: AgentRecord; enable: boolean }) => {
      const slug = selectedSkill!.slug;
      const current: string[] = Array.isArray(agent.config?.skills) ? agent.config!.skills : [];
      const next = enable ? Array.from(new Set([...current, slug])) : current.filter(s => s !== slug);
      return api.nexus.updateAgent(agent.agent_id, { config: { ...(agent.config || {}), skills: next } });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['nexus', 'agents'] });
      flash('Assignment updated');
    },
    onError: (e) => flash(e instanceof Error ? e.message : 'Update failed'),
  });

  const isDirty = useMemo(() => {
    if (!selectedSkill) return draft.name.trim().length > 0 || draft.instructions.trim().length > 0;
    const d = toDraft(selectedSkill);
    return JSON.stringify(d) !== JSON.stringify(draft);
  }, [selectedSkill, draft]);

  return (
    <div className="page-wide">
      <div className="page-header">
        <div>
          <h1 className="page-title">
            <Sparkles size={24} style={{ display: 'inline', color: '#6366f1', verticalAlign: 'middle', marginRight: 8 }} />
            Templates & Skills
          </h1>
          <p className="page-subtitle">
            Create reusable skills and templates, then equip agents with them. Assigned skills are injected into the agent&apos;s prompts at runtime.
          </p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setDraft(EMPTY_DRAFT)}>
          <Plus size={16} /> New
        </button>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '300px minmax(0, 1fr)', gap: 24, alignItems: 'start' }}>
        {/* Library */}
        <div className="panel">
          <div className="panel-head"><div className="panel-title"><Sparkles size={16} /> Library</div></div>
          <div className="panel-pad stack">
            {skillsQuery.isLoading && <LoadingState />}
            {skillsQuery.error && <ErrorState error={skillsQuery.error} />}
            {skills.map(s => {
              const active = draft.id === s.id;
              return (
                <button
                  key={s.id}
                  type="button"
                  className="card"
                  style={{
                    width: '100%', textAlign: 'left', cursor: 'pointer',
                    border: active ? '1px solid #6366f1' : '1px solid var(--border)',
                    background: active ? 'rgba(99,102,241,0.12)' : undefined,
                  }}
                  onClick={() => setDraft(toDraft(s))}
                >
                  <div className="spread" style={{ gap: 8 }}>
                    <strong style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.name}</strong>
                    <KindBadge kind={s.kind} />
                  </div>
                  <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>{s.category}</div>
                </button>
              );
            })}
            {!skillsQuery.isLoading && skills.length === 0 && (
              <div className="muted text-center" style={{ padding: 20 }}>No skills yet. Create one.</div>
            )}
          </div>
        </div>

        {/* Editor + assignment */}
        <div className="stack" style={{ gap: 24 }}>
          <div className="panel">
            <div className="panel-head">
              <div className="panel-title">{draft.id ? 'Edit' : 'New'} {draft.kind === 'template' ? 'Template' : 'Skill'}</div>
              <div style={{ display: 'inline-flex', gap: 12, alignItems: 'center' }}>
                {message && <span className="muted" style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><Check size={14} />{message}</span>}
                {draft.id && (
                  <button type="button" className="btn" style={{ color: '#ef4444' }} onClick={() => deleteMut.mutate()} disabled={deleteMut.isPending}>
                    <Trash2 size={16} /> Delete
                  </button>
                )}
                <button type="button" className="btn btn-primary" onClick={() => saveMut.mutate()} disabled={!isDirty || saveMut.isPending || !draft.name.trim() || !draft.instructions.trim()}>
                  <Save size={16} /> {saveMut.isPending ? 'Saving...' : 'Save'}
                </button>
              </div>
            </div>
            <div className="panel-pad">
              <div className="stack" style={{ gap: 16 }}>
                <div className="grid grid-3">
                  <div style={{ gridColumn: 'span 1' }}>
                    <label className="label">Kind</label>
                    <select className="input" value={draft.kind} onChange={e => setDraft({ ...draft, kind: e.target.value })}>
                      <option value="skill">Skill</option>
                      <option value="template">Template</option>
                    </select>
                  </div>
                  <div style={{ gridColumn: 'span 2' }}>
                    <label className="label">Name</label>
                    <input className="input" value={draft.name} onChange={e => setDraft({ ...draft, name: e.target.value })} placeholder="e.g. Clean Code Standards" />
                  </div>
                </div>
                <div className="grid grid-2">
                  <div>
                    <label className="label">Category</label>
                    <input className="input" value={draft.category} onChange={e => setDraft({ ...draft, category: e.target.value })} placeholder="engineering / security / frontend" />
                  </div>
                  <div>
                    <label className="label"><Tag size={12} style={{ display: 'inline', verticalAlign: 'middle' }} /> Tags (comma separated)</label>
                    <input className="input" value={draft.tagsText} onChange={e => setDraft({ ...draft, tagsText: e.target.value })} placeholder="quality, security" />
                  </div>
                </div>
                <div>
                  <label className="label">Description</label>
                  <input className="input" value={draft.description} onChange={e => setDraft({ ...draft, description: e.target.value })} placeholder="Short summary shown in the library" />
                </div>
                <div>
                  <label className="label">Instructions (injected into the agent prompt)</label>
                  <textarea
                    className="input"
                    style={{ minHeight: 160, resize: 'vertical', fontFamily: 'ui-monospace, monospace', fontSize: 13 }}
                    value={draft.instructions}
                    onChange={e => setDraft({ ...draft, instructions: e.target.value })}
                    placeholder="Write the concrete guidance the agent must follow when this skill is equipped..."
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Assignment */}
          {selectedSkill && (
            <div className="panel">
              <div className="panel-head"><div className="panel-title"><Bot size={16} /> Equip agents with “{selectedSkill.name}”</div></div>
              <div className="panel-pad">
                {agentsQuery.isLoading && <LoadingState />}
                <div className="grid grid-2" style={{ gap: 10 }}>
                  {agents.map(agent => {
                    const assigned = Array.isArray(agent.config?.skills) && agent.config!.skills.includes(selectedSkill.slug);
                    const isNexus = agent.agent_id === 'nexus_agent';
                    return (
                      <label key={agent.agent_id} className="card" style={{
                        display: 'flex', gap: 12, alignItems: 'center', cursor: 'pointer',
                        border: assigned ? '1px solid #6366f1' : '1px solid var(--border)',
                        background: assigned ? 'rgba(99,102,241,0.08)' : undefined,
                      }}>
                        <input
                          type="checkbox"
                          checked={!!assigned}
                          onChange={e => assignMut.mutate({ agent, enable: e.target.checked })}
                          style={{ width: 16, height: 16, accentColor: '#6366f1' }}
                        />
                        {isNexus ? <Zap size={15} color="#fbbf24" /> : <Cpu size={15} color="#94a3b8" />}
                        <div style={{ minWidth: 0 }}>
                          <strong style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis' }}>{agent.name}</strong>
                          <span className="muted" style={{ fontSize: 12 }}>{agent.role}</span>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
