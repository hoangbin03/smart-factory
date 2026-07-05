'use client';

import Link from 'next/link';
import { RefreshCw, Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { clearSession, getSavedUser } from '@/lib/auth';
import type { User } from '@/lib/types';

export function TopBar() {
  const [time, setTime] = useState('');
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    setUser(getSavedUser());
    setTime(new Date().toLocaleTimeString('vi-VN', { hour12: false }));
    const id = window.setInterval(() => setTime(new Date().toLocaleTimeString('vi-VN', { hour12: false })), 1000);
    const sync = () => setUser(getSavedUser());
    window.addEventListener('storage', sync);
    window.addEventListener('factory-auth-change', sync);
    return () => {
      window.clearInterval(id);
      window.removeEventListener('storage', sync);
      window.removeEventListener('factory-auth-change', sync);
    };
  }, []);

  function logout() {
    clearSession();
    setUser(null);
    window.dispatchEvent(new Event('factory-auth-change'));
  }

  return (
    <header className="topbar">
      <div className="top-search">
        <Search size={14} />
        <input placeholder="Search views" />
      </div>
      <div className="top-actions">
        <div className="clock">{time}</div>
        <button className="icon-btn" title="Refresh" onClick={() => window.location.reload()}><RefreshCw size={16} /></button>
        {user ? (
          <button className="btn" onClick={logout}>{user.username}</button>
        ) : (
          <Link className="btn btn-primary" href="/auth">Login</Link>
        )}
      </div>
    </header>
  );
}
