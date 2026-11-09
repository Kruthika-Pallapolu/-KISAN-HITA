import React from 'react';
import { Check, Globe } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';
import { translations } from '../i18n/translations';

export const FirstVisitLanguageSelection: React.FC = () => {
  const { language, setLanguage, languages, hasChosenLanguage } = useLanguage();

  return (
    <main className="auth-shell first-visit-shell" style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: '1rem', background: 'transparent' }}>
      <section className="auth-card language-choice-card" aria-labelledby="first-visit-language-question" style={{ width: 'min(100%, 620px)', padding: 'clamp(1.1rem, 4vw, 2rem)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', background: 'var(--char-card)' }}>
        <Globe size={28} color="var(--amber)" aria-hidden="true" />
        <div id="first-visit-language-question" style={{ display: 'grid', gap: '.15rem', margin: '.7rem 0 1.2rem' }}>
          {languages.map((item) => (
            <h1 key={item.code} lang={item.code} style={{ margin: 0, fontSize: item.code === 'en' ? '1.15rem' : '.95rem', color: 'var(--cream)' }}>
              {translations[item.code].firstVisitLanguageQuestion}
            </h1>
          ))}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 155px), 1fr))', gap: '.7rem' }}>
          {languages.map((item) => {
            const selected = hasChosenLanguage && item.code === language;
            return (
              <button
                key={item.code}
                type="button"
                lang={item.code}
                aria-label={`${item.nativeName} (${item.name})`}
                aria-pressed={selected}
                onClick={() => setLanguage(item.code)}
                style={{ minHeight: '4.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '.5rem', padding: '.85rem', borderRadius: 'var(--radius-md)', border: `1px solid ${selected ? 'var(--amber)' : 'var(--border-card)'}`, background: selected ? 'rgba(240, 168, 58, .14)' : 'var(--char-input)', color: 'var(--cream)', cursor: 'pointer', textAlign: 'left' }}
              >
                <span><strong style={{ display: 'block', fontSize: '1.05rem' }}>{item.nativeName}</strong><small style={{ color: 'var(--text-muted)' }}>{item.name}</small></span>
                {selected && <Check size={18} color="var(--amber)" aria-hidden="true" />}
              </button>
            );
          })}
        </div>
      </section>
    </main>
  );
};
