import React, { createContext, useContext, useEffect, useState } from 'react';
import { useLanguage } from './LanguageContext';
import type { SupportedLanguage } from '../i18n/translations';
import { setBrowserSessionMode } from '../services/sessionMode';

export interface AuthUser { id: string; email: string }
interface AuthContextValue {
  user: AuthUser | null;
  isGuest: boolean;
  guestContextId: string | null;
  loading: boolean;
  error: string;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (input: { email: string; password: string; language: SupportedLanguage }) => Promise<void>;
  signOut: () => Promise<void>;
  continueAsGuest: () => Promise<void>;
  clearError: () => void;
}
const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { setLanguage } = useLanguage();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isGuest, setIsGuest] = useState(false);
  const [guestContextId, setGuestContextId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadProfileLanguage = async () => {
    const response = await fetch('/api/settings/profile', { credentials: 'same-origin' });
    if (!response.ok) throw new Error(`Profile request failed (${response.status})`);
    const profile = await response.json();
    if (['te', 'en', 'hi', 'ta', 'kn', 'ml', 'mr'].includes(profile.selected_language)) {
      setLanguage(profile.selected_language as SupportedLanguage);
    }
  };

  useEffect(() => {
    let alive = true;
    fetch('/api/auth/session', { credentials: 'same-origin' })
      .then(async (response) => {
        if (!response.ok) throw new Error('Could not check session status');
        return response.json();
      })
      .then(async (session) => {
        if (!alive) return;
        setBrowserSessionMode(session.mode === 'guest' || session.mode === 'account' ? session.mode : 'none');
        if (session.mode === 'guest') { setIsGuest(true); setGuestContextId(session.context_id || null); return; }
        if (session.mode !== 'account') return;
        const response = await fetch('/api/auth/me', { credentials: 'same-origin' });
        if (!response.ok) throw new Error('Could not check sign-in status');
        const data = await response.json();
        if (!data.authenticated || !data.user) return;
        const previousUser = localStorage.getItem('kisan_hita_last_user');
        if (previousUser !== data.user.id) clearAccountLocalState();
        localStorage.setItem('kisan_hita_last_user', data.user.id);
        await loadProfileLanguage();
        if (alive) setUser(data.user);
      })
      .catch(() => { if (alive) { setUser(null); setIsGuest(false); setBrowserSessionMode('none'); } })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  const clearAccountLocalState = () => {
    for (const key of [
      'kisan_hita_chat_messages', 'kisan_hita_conversation_id',
      'kisan_hita_pending_wf', 'kisan_hita_next_slot', 'kisan_hita_collected_slots',
      'kisan_hita_farm_profile',
    ]) localStorage.removeItem(key);
  };

  const clearGuestLocalState = (contextId: string | null) => {
    if (!contextId) return;
    const prefix = `kisan_hita_guest_${contextId.replace(/[^a-zA-Z0-9_-]/g, '')}_`;
    try {
      for (const key of Object.keys(sessionStorage)) if (key.startsWith(prefix)) sessionStorage.removeItem(key);
      for (const key of Object.keys(localStorage)) if (key.startsWith(prefix)) localStorage.removeItem(key);
    } catch {}
  };

  const authenticate = async (path: string, body: Record<string, unknown>, preserveMigratedHistory = false) => {
    setError('');
    const response = await fetch(path, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
    setIsGuest(false); setGuestContextId(null);
    setBrowserSessionMode('account');
    if (!(preserveMigratedHistory && data.legacy_session_migrated)) clearAccountLocalState();
    await loadProfileLanguage();
    setUser(data.user);
    localStorage.setItem('kisan_hita_last_user', data.user.id);
  };

  const signIn = async (email: string, password: string) => {
    try { await authenticate('/api/auth/login', { email, password }); }
    catch (cause) { const message = cause instanceof Error ? cause.message : 'Sign-in failed'; setError(message); throw cause; }
  };
  const signUp = async (input: { email: string; password: string; language: SupportedLanguage }) => {
    try {
      await authenticate('/api/auth/signup', {
        email: input.email, password: input.password,
        language: input.language,
      }, true);
    } catch (cause) { const message = cause instanceof Error ? cause.message : 'Sign-up failed'; setError(message); throw cause; }
  };
  const signOut = async () => {
    const endedGuestContext = guestContextId;
    try {
      if (isGuest) await fetch('/api/auth/guest/end', { method: 'POST', credentials: 'same-origin' });
      else await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' });
    } finally {
      if (isGuest) clearGuestLocalState(endedGuestContext);
      else { clearAccountLocalState(); localStorage.removeItem('kisan_hita_last_user'); }
      setUser(null); setIsGuest(false); setGuestContextId(null); setBrowserSessionMode('none');
    }
  };

  const continueAsGuest = async () => {
    setError('');
    const response = await fetch('/api/auth/guest', { method: 'POST', credentials: 'same-origin' });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `Guest access failed (${response.status})`);
    if (data.mode === 'account') {
      const accountResponse = await fetch('/api/auth/me', { credentials: 'same-origin' });
      const accountData = await accountResponse.json();
      if (accountData.authenticated && accountData.user) { setUser(accountData.user); setIsGuest(false); setGuestContextId(null); setBrowserSessionMode('account'); return; }
      throw new Error('The current account session could not be restored.');
    }
    setIsGuest(true);
    setGuestContextId(data.context_id || null);
    setBrowserSessionMode('guest');
  };

  return <AuthContext.Provider value={{ user, isGuest, guestContextId, loading, error, signIn, signUp, signOut, continueAsGuest, clearError: () => setError('') }}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside AuthProvider');
  return value;
};
