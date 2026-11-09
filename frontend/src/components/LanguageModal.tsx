import React from 'react';
import { Check, Globe, X } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';
import type { SupportedLanguage } from '../i18n/translations';

export const LanguageModal: React.FC = () => {
  const { showLanguageModal, setShowLanguageModal, language, setLanguage, languages, t } = useLanguage();
  if (!showLanguageModal) return null;

  const handleSelect = (code: SupportedLanguage) => setLanguage(code);

  return (
    <div className="cinematic-modal-overlay" style={{
      position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(10, 11, 7, 0.85)',
      backdropFilter: 'blur(10px)', display: 'flex', alignItems: 'center',
      justifyContent: 'center', padding: '1.5rem',
    }}>
      <div className="cinematic-modal-surface" style={{
        background: 'var(--char-card)', border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-lg)', maxWidth: '560px', width: '100%', padding: '2rem',
        boxShadow: '0 20px 50px rgba(0, 0, 0, 0.6)', position: 'relative',
      }}>
        <button type="button" onClick={() => setShowLanguageModal(false)} aria-label="Close language selection"
          style={{ position: 'absolute', top: '1.2rem', right: '1.2rem', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
          <X size={20} />
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.6rem' }}>
          <Globe size={24} style={{ color: 'var(--amber)' }} />
          <h2 style={{ fontSize: '1.4rem' }}>{t('firstVisitTitle')}</h2>
        </div>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.92rem', marginBottom: '1.8rem' }}>{t('firstVisitSub')}</p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0.85rem' }}>
          {languages.map((item) => {
            const selected = language === item.code;
            return <button key={item.code} type="button" onClick={() => handleSelect(item.code)}
              aria-pressed={selected}
              style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', padding: '1rem', borderRadius: 'var(--radius-md)', background: selected ? 'rgba(240, 168, 58, 0.16)' : 'var(--char-input)', border: `1.5px solid ${selected ? 'var(--amber)' : 'var(--border-card)'}`, color: 'var(--cream)', cursor: 'pointer', textAlign: 'left', transition: 'all 0.2s', position: 'relative' }}>
              <span style={{ fontSize: '1.2rem', fontWeight: 800, color: selected ? 'var(--amber)' : 'var(--cream)', marginBottom: '0.2rem' }}>{item.nativeName}</span>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{item.name}</span>
              <span className="mono" style={{ fontSize: '0.68rem', color: 'var(--text-dim)', marginTop: '0.4rem' }}>{item.region}</span>
              {selected && <span aria-hidden="true" style={{ position: 'absolute', top: '0.8rem', right: '0.8rem', width: '20px', height: '20px', borderRadius: '50%', background: 'var(--amber)', color: 'var(--char)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Check size={14} strokeWidth={3} /></span>}
            </button>;
          })}
        </div>
        <div style={{ marginTop: '1.8rem', display: 'flex', justifyContent: 'flex-end' }}>
          <button type="button" className="btn btn-primary" style={{ width: '100%', padding: '0.85rem' }} onClick={() => setShowLanguageModal(false)}>{t('continueApp')}</button>
        </div>
      </div>
    </div>
  );
};
