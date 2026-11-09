import React from 'react';
import { useAssistant } from '../context/AssistantContext';
import { useLanguage } from '../context/LanguageContext';
import { Bot } from 'lucide-react';
import { KISAN_HITA_NAME } from '../services/productIdentity';

export const PersistentAssistantBar: React.FC = () => {
  const { toggleAssistant, isOpen } = useAssistant();
  const { t } = useLanguage();

  // If the full modal is already open, hide the floating bar to prevent visual redundancy
  if (isOpen) return null;

  return (
    <div className="persistent-assistant-widget" style={{
      position: 'fixed',
      bottom: '1.4rem',
      left: '50%',
      transform: 'translateX(-50%)',
      zIndex: 40,
      width: '92%',
      maxWidth: '560px',
      pointerEvents: 'auto'
    }}>
      <div
        onClick={toggleAssistant}
        style={{
          background: 'rgba(28, 30, 20, 0.94)',
          backdropFilter: 'blur(16px)',
          border: '1.5px solid var(--border-subtle)',
          borderRadius: 'var(--radius-full)',
          padding: '0.5rem 0.6rem 0.5rem 1.1rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '0.8rem',
          boxShadow: '0 12px 35px rgba(0, 0, 0, 0.65)',
          cursor: 'pointer',
          transition: 'all 0.25s ease'
        }}
        className="persistent-bar"
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', overflow: 'hidden' }}>
          <div style={{
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #2f3a1c, #8a6a45)',
            border: '1px solid var(--border-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--amber)',
            flexShrink: 0,
            position: 'relative'
          }}>
            <Bot size={18} />
            <span style={{
              position: 'absolute',
              bottom: '1px',
              right: '1px',
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: '#4ade80',
              border: '1.5px solid var(--char)'
            }} />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div style={{
              fontSize: '0.88rem',
              fontWeight: 700,
              color: 'var(--cream)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis'
            }}>
              {KISAN_HITA_NAME}
            </div>
            <div style={{
              fontSize: '0.74rem',
              color: 'var(--text-muted)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis'
            }}>
              {t('assistantPlaceholder')}
            </div>
          </div>
        </div>

        {/* Quick Assistant Action */}
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            toggleAssistant();
          }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            background: 'var(--amber)',
            color: 'var(--char)',
            border: 'none',
            padding: '0.55rem 1.1rem',
            borderRadius: 'var(--radius-full)',
            fontWeight: 800,
            fontSize: '0.82rem',
            cursor: 'pointer',
            flexShrink: 0,
            boxShadow: '0 4px 12px rgba(240, 168, 58, 0.35)'
          }}
        >
          <Bot size={16} />
          <span>{t('navAssistant')}</span>
        </button>
      </div>

      <style>{`
        .persistent-bar:hover {
          border-color: var(--amber);
          transform: translateY(-2px);
          box-shadow: 0 16px 40px rgba(0, 0, 0, 0.75), 0 0 20px rgba(240, 168, 58, 0.2);
        }
      `}</style>
    </div>
  );
};

