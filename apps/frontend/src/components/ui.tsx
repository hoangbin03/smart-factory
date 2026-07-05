'use client';

import type { LucideIcon } from 'lucide-react';

export function StatusBadge({ status }: { status?: string | null }) {
  const normalized = String(status || 'UNKNOWN').toLowerCase();
  return <span className={'badge badge-' + normalized}>{normalized.replace(/_/g, ' ')}</span>;
}

export function StatCard({ label, value, sub, icon: Icon, color = '#818cf8' }: { label: string; value: string | number; sub?: string; icon?: LucideIcon; color?: string }) {
  return (
    <div className="card">
      <div className="spread">
        <div>
          <div className="kpi-label">{label}</div>
          <div className="kpi-value" style={{ color }}>{value}</div>
          {sub ? <div className="kpi-sub">{sub}</div> : null}
        </div>
        {Icon ? <Icon size={28} color={color} /> : null}
      </div>
    </div>
  );
}

export function EmptyState({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="notice">
      <strong>{title}</strong>
      {detail ? <div style={{ marginTop: 4 }}>{detail}</div> : null}
    </div>
  );
}

export function ErrorState({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : 'Request failed';
  return <div className="notice error">{message}</div>;
}

export function LoadingState() {
  return <div className="notice"><span className="live-dot" /> Loading live data</div>;
}

export function formatDate(value?: string | null) {
  if (!value) return '-';
  return new Date(value).toLocaleString('vi-VN', { hour12: false });
}

export function duration(start?: string | null, end?: string | null) {
  if (!start) return '-';
  const stop = end ? new Date(end).getTime() : Date.now();
  const seconds = Math.max(0, Math.floor((stop - new Date(start).getTime()) / 1000));
  if (seconds < 60) return String(seconds) + 's';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return String(minutes) + 'm ' + String(seconds % 60) + 's';
  return String(Math.floor(minutes / 60)) + 'h ' + String(minutes % 60) + 'm';
}

export function stringifyShort(value: unknown, max = 110) {
  const raw = typeof value === 'string' ? value : JSON.stringify(value ?? {});
  return raw.length > max ? raw.slice(0, max) + '...' : raw;
}
