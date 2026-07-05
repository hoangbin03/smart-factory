'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { KeyRound, LogIn, UserPlus } from 'lucide-react';
import { useState } from 'react';
import { api } from '@/lib/api';
import { clearSession, getSavedUser, saveSession } from '@/lib/auth';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui';

export default function AuthPage() {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('admin@factory.local');
  const [username, setUsername] = useState('admin');
  const [fullName, setFullName] = useState('Factory Admin');
  const [password, setPassword] = useState('Admin@123');
  const [savedUser, setSavedUser] = useState(getSavedUser());

  const profile = useQuery({ queryKey: ['auth', 'me', savedUser?.id], queryFn: api.auth.me, enabled: Boolean(savedUser) });

  const login = useMutation({
    mutationFn: () => mode === 'login' ? api.auth.login({ email, password }) : api.auth.register({ email, username, password, fullName }),
    onSuccess: (res) => {
      saveSession(res.accessToken, res.user);
      setSavedUser(res.user);
      window.dispatchEvent(new Event('factory-auth-change'));
      queryClient.invalidateQueries();
    },
  });

  function logout() {
    clearSession();
    setSavedUser(null);
    window.dispatchEvent(new Event('factory-auth-change'));
    queryClient.clear();
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Authentication</h1>
          <p className="page-subtitle">JWT session for protected API actions.</p>
        </div>
      </div>

      <div className="grid grid-2">
        <section className="panel panel-pad">
          <div className="panel-title"><KeyRound size={16} /> Session</div>
          <div style={{ marginTop: 16 }}>
            {profile.isLoading ? <LoadingState /> : null}
            {profile.error ? <ErrorState error={profile.error} /> : null}
            {profile.data ? (
              <div className="stack">
                <div className="notice success">Signed in as <strong>{profile.data.username}</strong> ({profile.data.role})</div>
                <div className="code">{profile.data.email}</div>
                <button className="btn btn-danger" onClick={logout}>Logout</button>
              </div>
            ) : !profile.isLoading && !profile.error ? <EmptyState title="No active session" /> : null}
          </div>
        </section>

        <section className="panel panel-pad">
          <div className="toolbar">
            <button className={mode === 'login' ? 'btn btn-primary' : 'btn'} onClick={() => setMode('login')}><LogIn size={14} /> Login</button>
            <button className={mode === 'register' ? 'btn btn-primary' : 'btn'} onClick={() => setMode('register')}><UserPlus size={14} /> Register</button>
          </div>
          <div className="form-grid">
            <label className="label">Email<input className="input" value={email} onChange={(e) => setEmail(e.target.value)} /></label>
            {mode === 'register' ? <label className="label">Username<input className="input" value={username} onChange={(e) => setUsername(e.target.value)} /></label> : null}
            {mode === 'register' ? <label className="label">Full name<input className="input" value={fullName} onChange={(e) => setFullName(e.target.value)} /></label> : null}
            <label className="label">Password<input className="input" value={password} onChange={(e) => setPassword(e.target.value)} type="password" /></label>
            {login.error ? <ErrorState error={login.error} /> : null}
            <button className="btn btn-primary" disabled={login.isPending} onClick={() => login.mutate()}>{mode === 'login' ? 'Login' : 'Create account'}</button>
          </div>
        </section>
      </div>
    </div>
  );
}
