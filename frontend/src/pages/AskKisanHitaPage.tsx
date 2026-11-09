import React, { useState, useRef, useEffect } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { useFarmProfile } from '../context/FarmProfileContext';
import { useAssistant } from '../context/AssistantContext';
import { Bot, Send, Volume2, Square, Sparkles, Trash2, ArrowRight, ArrowLeft } from 'lucide-react';
import { assistantQuestionSuggestions } from '../i18n/assistantQuestions';
import { localizeCropName, localizeLocation, localizeSoil, localizeWater } from '../i18n/agriculture';
import { KISAN_HITA_NAME } from '../services/productIdentity';

interface AskKisanHitaPageProps {
  onRouteFeature?: (feature: string) => void;
  onNavigate?: (tab: string) => void;
}

export const AskKisanHitaPage: React.FC<AskKisanHitaPageProps> = ({ onRouteFeature, onNavigate }) => {
  const { t, language } = useLanguage();
  const { profile } = useFarmProfile();
  const {
    messages,
    sendMessage,
    clearMessages,
    isProcessing,
    isSpeaking,
    currentTranscript,
    voiceError,
    speakText,
    stopSpeaking,
    suggestedQuestions,
    pendingWorkflow,
    nextSlot,
  } = useAssistant();

  const [inputVal, setInputVal] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const getContextualChips = () => {
    if (pendingWorkflow === 'market_prices' && nextSlot === 'commodity') {
      return ['Chilli', 'Cotton', 'Tomato', 'Paddy'].map((crop) => localizeCropName(crop, language)).concat(t('cancelWorkflow'));
    }
    if (pendingWorkflow === 'market_prices' && nextSlot === 'district') {
      return ['Warangal', 'Khammam', 'Guntur', 'Karimnagar'].map((place) => localizeLocation(place, language)).concat(t('cancelWorkflow'));
    }
    if (pendingWorkflow === 'crop_advisor' && nextSlot === 'soil_type') {
      return ['Black Cotton Soil', 'Red Soil', 'Loamy Soil'].map((soil) => localizeSoil(soil, language)).concat(t('cancelWorkflow'));
    }
    if (pendingWorkflow === 'crop_advisor' && nextSlot === 'water_source') {
      return ['Good irrigation', 'Limited irrigation', 'Rain-dependent'].map((water) => localizeWater(water, language)).concat(t('cancelWorkflow'));
    }
    if (pendingWorkflow === 'crop_health' && nextSlot === 'crop_name') {
      return ['Cotton', 'Chilli', 'Paddy', 'Tomato'].map((crop) => localizeCropName(crop, language)).concat(t('cancelWorkflow'));
    }
    return assistantQuestionSuggestions[language] || suggestedQuestions;
  };

  const activeChips = getContextualChips();

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isProcessing]);

  useEffect(() => {
    if (currentTranscript) {
      setInputVal(currentTranscript);
    }
  }, [currentTranscript]);

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!inputVal.trim() || isProcessing) return;
    sendMessage(inputVal, onRouteFeature);
    setInputVal('');
  };

  return (
    <div className="module-page assistant-page" style={{ paddingTop: '5.5rem', paddingBottom: '5rem' }}>
      <div className="container" style={{ maxWidth: '840px' }}>
        {/* Navigation Breadcrumb */}
        {(onNavigate || onRouteFeature) && (
          <div style={{ marginBottom: '1.2rem' }}>
            <button
              onClick={() => (onNavigate ? onNavigate('home') : onRouteFeature?.('home'))}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.45rem',
                background: 'rgba(244, 236, 216, 0.05)',
                border: '1px solid var(--border-card)',
                color: 'var(--amber)',
                padding: '0.35rem 0.85rem',
                borderRadius: 'var(--radius-full)',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.2s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(240, 168, 58, 0.15)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(244, 236, 216, 0.05)';
              }}
            >
              <ArrowLeft size={14} />
              <span>{t('navHome')}</span>
            </button>
          </div>
        )}

        {/* Header */}
        <div style={{ marginBottom: '1.5rem', textAlign: 'center' }}>
          <div style={{ display: 'inline-flex', marginBottom: '0.6rem' }}>
            <span className="badge">{t('assistantPageBadge')}</span>
          </div>
          <h1 style={{ fontSize: 'clamp(1.8rem, 4vw, 2.4rem)', marginBottom: '0.4rem' }}>
            Ask {KISAN_HITA_NAME}
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem' }}>
            {t('assistantPageSub')}
          </p>
        </div>

        {/* Chat Window Container */}
        <div className="card" style={{ padding: 0, overflow: 'hidden', height: '68vh', display: 'flex', flexDirection: 'column' }}>
          {/* Top Bar */}
          <div style={{
            padding: '0.85rem 1.4rem',
            borderBottom: '1px solid var(--border-card)',
            background: 'rgba(22, 23, 15, 0.85)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #2f3a1c, #8a6a45)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--amber)'
              }}>
                <Bot size={18} />
              </div>
              <span style={{ fontSize: '0.9rem', fontWeight: 700 }}>
                {KISAN_HITA_NAME}{profile.district ? ` • ${profile.district}` : ''}
              </span>
            </div>

            <button
              onClick={clearMessages}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.35rem',
                background: 'none',
                border: 'none',
                color: 'var(--text-muted)',
                fontSize: '0.78rem',
                cursor: 'pointer'
              }}
            >
              <Trash2 size={14} />
              <span>{t('clearConversation')}</span>
            </button>
          </div>

          {/* Messages Log */}
          <div style={{
            flex: 1,
            overflowY: 'auto',
            padding: '1.4rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '1rem'
          }}>
            {messages.map((msg) => {
              const isUser = msg.sender === 'user';
              return (
                <div
                  key={msg.id}
                  style={{
                    display: 'flex',
                    justifyContent: isUser ? 'flex-end' : 'flex-start',
                    alignItems: 'flex-start',
                    gap: '0.6rem'
                  }}
                >
                  {!isUser && (
                    <div style={{
                      width: '28px',
                      height: '28px',
                      borderRadius: '50%',
                      background: 'var(--olive)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'var(--amber)',
                      flexShrink: 0
                    }}>
                      <Bot size={15} />
                    </div>
                  )}

                  <div style={{
                    maxWidth: '82%',
                    background: isUser ? 'linear-gradient(135deg, rgba(240, 168, 58, 0.2), rgba(138, 106, 69, 0.3))' : 'rgba(22, 23, 15, 0.85)',
                    border: `1px solid ${isUser ? 'var(--border-subtle)' : 'var(--border-card)'}`,
                    borderRadius: 'var(--radius-md)',
                    padding: '0.85rem 1.1rem',
                    color: 'var(--cream)',
                    fontSize: '0.92rem',
                    lineHeight: 1.5,
                    whiteSpace: 'pre-line'
                  }}>
                    {msg.text}

                    {msg.feature && msg.feature !== 'assistant' && (
                      <div style={{ marginTop: '0.75rem', paddingTop: '0.6rem', borderTop: '1px solid rgba(244, 236, 216, 0.08)' }}>
                        <button
                          onClick={() => onRouteFeature && onRouteFeature(msg.feature!)}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.4rem',
                            background: 'rgba(240, 168, 58, 0.15)',
                            border: '1px solid var(--border-subtle)',
                            color: 'var(--amber)',
                            padding: '0.35rem 0.75rem',
                            borderRadius: 'var(--radius-full)',
                            fontSize: '0.78rem',
                            fontWeight: 700,
                            cursor: 'pointer'
                          }}
                        >
                          <span>{t('openFeature').replace('{feature}', msg.feature.replace('_', ' ').toUpperCase())}</span>
                          <ArrowRight size={13} />
                        </button>
                      </div>
                    )}

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '0.4rem' }}>
                      <span className="mono" style={{ fontSize: '0.65rem', color: 'var(--text-dim)' }}>
                        {msg.timestamp}
                      </span>
                      {!isUser && (
                        <button
                          onClick={() => speakText(msg.text)}
                          style={{
                            background: 'none',
                            border: 'none',
                            color: 'var(--amber)',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.25rem',
                            fontSize: '0.7rem'
                          }}
                        >
                          <Volume2 size={13} />
                          <span>{t('hearAudio')}</span>
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}

            {isProcessing && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <div style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: '50%',
                  background: 'var(--olive)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--amber)'
                }}>
                  <Bot size={15} />
                </div>
                <div style={{
                  background: 'rgba(22, 23, 15, 0.8)',
                  border: '1px solid var(--border-card)',
                  borderRadius: 'var(--radius-md)',
                  padding: '0.6rem 1rem',
                  fontSize: '0.85rem',
                  color: 'var(--amber)'
                }}>
                  ● {t('voiceProcessing')}
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Contextual & Quick Prompts */}
          <div style={{
            padding: '0.6rem 1.4rem',
            background: pendingWorkflow ? 'rgba(240, 168, 58, 0.08)' : 'rgba(22, 23, 15, 0.5)',
            borderTop: '1px solid rgba(244, 236, 216, 0.06)',
            display: 'flex',
            gap: '0.5rem',
            alignItems: 'center',
            overflowX: 'auto',
            whiteSpace: 'nowrap'
          }}>
            <Sparkles size={14} style={{ color: 'var(--amber)', flexShrink: 0 }} />
            {pendingWorkflow && (
              <span className="mono" style={{ fontSize: '0.72rem', color: 'var(--amber)', fontWeight: 700, marginRight: '0.2rem' }}>
                {pendingWorkflow.replace('_', ' ').toUpperCase()}:
              </span>
            )}
            {activeChips.map((q, idx) => {
              const isCancel = q === 'Cancel' || q === 'రద్దు';
              return (
                <button
                  key={idx}
                  type="button"
                  onClick={() => sendMessage(q, onRouteFeature)}
                  style={{
                    background: isCancel ? 'rgba(239, 68, 68, 0.15)' : 'rgba(244, 236, 216, 0.06)',
                    border: `1px solid ${isCancel ? 'rgba(239, 68, 68, 0.35)' : 'var(--border-card)'}`,
                    color: isCancel ? '#f87171' : 'var(--cream)',
                    padding: '0.35rem 0.75rem',
                    borderRadius: 'var(--radius-full)',
                    fontSize: '0.78rem',
                    cursor: 'pointer',
                    flexShrink: 0,
                    fontWeight: isCancel ? 700 : 500
                  }}
                >
                  {q}
                </button>
              );
            })}
          </div>

          {/* Input Bar */}
          <form
            onSubmit={handleSubmit}
            style={{
              padding: '1rem 1.4rem',
              background: 'rgba(22, 23, 15, 0.98)',
              borderTop: '1px solid var(--border-card)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem'
            }}
          >
            <input
              type="text"
              className="input-field"
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              placeholder={t('assistantPlaceholder')}
              style={{ flex: 1, padding: '0.8rem 1rem' }}
            />

            <button
              type="submit"
              disabled={!inputVal.trim() || isProcessing}
              style={{
                width: '44px',
                height: '44px',
                borderRadius: '50%',
                background: inputVal.trim() && !isProcessing ? 'var(--amber)' : 'rgba(244, 236, 216, 0.1)',
                border: 'none',
                color: inputVal.trim() && !isProcessing ? 'var(--char)' : 'var(--text-dim)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: inputVal.trim() && !isProcessing ? 'pointer' : 'not-allowed',
                flexShrink: 0
              }}
            >
              <Send size={18} />
            </button>
          </form>
          {voiceError && <p role="alert" style={{ margin: '0 1.4rem 1rem', color: '#fca5a5', fontSize: '0.82rem' }}>{voiceError}</p>}
        </div>
      </div>
    </div>
  );
};

