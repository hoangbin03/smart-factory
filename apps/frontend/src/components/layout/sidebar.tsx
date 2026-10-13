'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Activity, Bot, CheckCircle, FileText, FolderGit2, GitBranch, KeyRound, LayoutDashboard, ListTodo, Sparkles, Wrench, Zap } from 'lucide-react';

const navItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/nexus', label: 'Nexus Master', icon: Zap },
  { href: '/projects', label: 'Projects', icon: FolderGit2 },
  { href: '/workflows', label: 'Workflows', icon: GitBranch },
  { href: '/tasks', label: 'Tasks', icon: ListTodo },
  { href: '/agents', label: 'Agent Fleet', icon: Bot },
  { href: '/agents/config', label: 'Agent Config', icon: KeyRound },
  { href: '/tools', label: 'Tool Config', icon: Wrench },
  { href: '/templates', label: 'Templates & Skills', icon: Sparkles },
  { href: '/kbs', label: 'Knowledge Base', icon: FileText },
  { href: '/approvals', label: 'Approvals', icon: CheckCircle },
  { href: '/audit', label: 'Audit Trail', icon: Activity },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-icon"><Zap size={18} /></div>
        <div>
          <div className="brand-title">SmartFactory</div>
          <div className="brand-sub">AI Software Production</div>
        </div>
      </div>
      <nav className="side-nav">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link key={href} href={href} className={active ? 'side-link active' : 'side-link'}>
              <Icon size={16} />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="side-status">
        <div className="row"><span className="live-dot" /><strong>Live API mode</strong></div>
        <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>Backend data only</div>
      </div>
    </aside>
  );
}
