import React, { useState, useRef, useEffect } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { useFarmProfile } from '../context/FarmProfileContext';
import { useAssistant } from '../context/AssistantContext';
import { assistantQuestionSuggestions } from '../i18n/assistantQuestions';
import { localizeCropName, localizeLocation, localizeSoil, localizeWater } from '../i18n/agriculture';
import { Bot, Send, Mic, MicOff, Volume2, Square, Trash2, X, ArrowRight, Sparkles } from 'lucide-react';

interface KisanAssistantModalProps {
  onRouteFeature?: (feature: string) => void;
}

export const KisanAssistantModal: React.FC<KisanAssistantModalProps> = ({ onRouteFeature }) => {
  const { t, language } = useLanguage();
  const { profile } = useFarmProfile();
  const {
    isOpen,
    closeAssistant,
    messages,
    sendMessage,
    clearMessages,
    isProcessing,
    isSpeaking,
    currentTranscript,
    voiceError,
    isPrismaRecording,
    startPrismaVoiceInput,
    stopPrismaVoiceInput,
    speakText,
    stopSpeaking,
    suggestedQuestions,
    pendingWorkflow,
    nextSlot,
  } = useAssistant();

  const [inputVal, setInputVal] = useState('');
  const [prismaEnabled, setPrismaEnabled] = useState(false);
  const [voiceConfigLoaded, setVoiceConfigLoaded] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    let active = true;
    setVoiceConfigLoaded(false);
    fetch('/api/voice/config', { credentials: 'same-origin' })
      .then((response) => response.ok ? response.json() : null)
      .then((config) => { if (active) { setPrismaEnabled(config?.prisma_enabled === true); setVoiceConfigLoaded(true); } })
      .catch(() => { if (active) { setPrismaEnabled(false); setVoiceConfigLoaded(true); } });
    return () => { active = false; };
  }, [isOpen]);

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isOpen, isProcessing]);

  // Sync transcript to input field if transcript changes
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

  const handleSuggestionClick = (q: string) => {
    sendMessage(q, onRouteFeature);
  };

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

  return (
    <div className="cinematic-modal-overlay assistant-modal-overlay" style={{
      position: 'fixed',
      inset: 0,
      zIndex: 90,
      background: 'rgba(10, 11, 7, 0.75)',
      backdropFilter: 'blur(8px)',
      display: isOpen ? 'flex' : 'none',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '1rem'
    }}>
      <div className="cinematic-modal-surface assistant-modal-surface" style={{
        background: 'var(--char-card)',
        border: '1.5px solid var(--border-subtle)',
        borderRadius: 'var(--radius-lg)',
        maxWidth: '720px',
        width: '100%',
        height: '82vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 25px 60px rgba(0, 0, 0, 0.7)',
        overflow: 'hidden',
        position: 'relative'
      }}>
        {/* Panel Header */}
        <div className="assistant-modal-header" style={{
          padding: '1rem 1.4rem',
          borderBottom: '1px solid var(--border-card)',
          background: 'rgba(22, 23, 15, 0.95)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{
              width: '38px',
              height: '38px',
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #2f3a1c, #8a6a45)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--amber)',
              border: '1px solid var(--border-subtle)'
            }}>
              <Bot size={20} />
            </div>
            <div>
              <div style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--cream)', lineHeight: 1.2 }}>
                {t('assistantTitle')}
              </div>
              <div className="mono" style={{ fontSize: '0.72rem', color: 'var(--amber)' }}>
                {t('contextGeneral')} • {profile.district}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            {/* Clear conversation button */}
            <button
              onClick={clearMessages}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.35rem',
                background: 'rgba(244, 236, 216, 0.06)',
                border: '1px solid var(--border-card)',
                color: 'var(--text-muted)',
                padding: '0.4rem 0.75rem',
                borderRadius: 'var(--radius-full)',
                fontSize: '0.75rem',
                cursor: 'pointer'
              }}
              title={t('clearConversation')}
            >
              <Trash2 size={13} />
              <span>{t('clearConversation')}</span>
            </button>

            {/* Close panel button */}
            <button
              onClick={closeAssistant}
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                background: 'rgba(244, 236, 216, 0.08)',
                border: 'none',
                color: 'var(--cream)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer'
              }}
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Audio Speaking Wave Bar */}
        {isSpeaking && (
          <div style={{
            background: 'rgba(240, 168, 58, 0.12)',
            borderBottom: '1px solid var(--border-subtle)',
            padding: '0.5rem 1.4rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '3px', height: '16px' }}>
                <span className="wave-bar" />
                <span className="wave-bar" />
                <span className="wave-bar" />
                <span className="wave-bar" />
              </div>
              <span style={{ fontSize: '0.8rem', color: 'var(--amber)', fontWeight: 600 }}>
                {t('voiceSpeaking')}
              </span>
            </div>
            <button
              onClick={() => stopSpeaking(true)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.3rem',
                background: 'rgba(248, 113, 113, 0.2)',
                border: '1px solid rgba(248, 113, 113, 0.4)',
                color: '#f87171',
                padding: '0.25rem 0.6rem',
                borderRadius: 'var(--radius-full)',
                fontSize: '0.75rem',
                cursor: 'pointer',
                fontWeight: 600
              }}
            >
              <Square size={11} fill="currentColor" /> {t('stopAudio')}
            </button>
          </div>
        )}

        {/* Message Thread */}
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
                    width: '30px',
                    height: '30px',
                    borderRadius: '50%',
                    background: 'var(--olive)',
                    border: '1px solid var(--border-subtle)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'var(--amber)',
                    flexShrink: 0,
                    marginTop: '2px'
                  }}>
                    <Bot size={16} />
                  </div>
                )}

                <div style={{
                  maxWidth: '82%',
                  background: isUser ? 'linear-gradient(135deg, rgba(240, 168, 58, 0.2), rgba(138, 106, 69, 0.3))' : 'rgba(22, 23, 15, 0.9)',
                  border: `1px solid ${isUser ? 'var(--border-subtle)' : 'var(--border-card)'}`,
                  borderRadius: 'var(--radius-md)',
                  padding: '0.85rem 1.1rem',
                  color: 'var(--cream)',
                  fontSize: '0.92rem',
                  lineHeight: 1.5,
                  whiteSpace: 'pre-line'
                }}>
                  {msg.text}

                  {/* Metadata link or button if feature was routed */}
                  {msg.feature && msg.feature !== 'assistant' && (
                    <div style={{ marginTop: '0.75rem', paddingTop: '0.6rem', borderTop: '1px solid rgba(244, 236, 216, 0.08)' }}>
                      <button
                        onClick={() => {
                          if (onRouteFeature) onRouteFeature(msg.feature!);
                          closeAssistant();
                        }}
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

                  {/* Footer of bubble: timestamp & listen button */}
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginTop: '0.4rem',
                    gap: '0.8rem'
                  }}>
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
                        title={t('hearAudio')}
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

          {/* Processing indicator */}
          {isProcessing && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <div style={{
                width: '30px',
                height: '30px',
                borderRadius: '50%',
                background: 'var(--olive)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--amber)'
              }}>
                <Bot size={16} />
              </div>
              <div style={{
                background: 'rgba(22, 23, 15, 0.8)',
                border: '1px solid var(--border-card)',
                borderRadius: 'var(--radius-md)',
                padding: '0.6rem 1rem',
                fontSize: '0.85rem',
                color: 'var(--amber)',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem'
              }}>
                <span className="animate-pulse-slow">●</span>
                <span>{t('voiceProcessing')}</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Contextual & Suggested Quick Questions */}
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
            const isCancel = q === t('cancelWorkflow');
            return (
              <button
                key={idx}
                type="button"
                onClick={() => handleSuggestionClick(q)}
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

        {/* Listening Voice Overlay (When Mic Active) */}
        {isPrismaRecording && (
          <div style={{
            padding: '0.8rem 1.4rem',
            background: 'linear-gradient(90deg, rgba(239, 68, 68, 0.15), rgba(240, 168, 58, 0.15))',
            borderTop: '1.5px solid #ef4444',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
              <div style={{
                width: '12px',
                height: '12px',
                borderRadius: '50%',
                background: '#ef4444',
                animation: 'pulse 1s infinite'
              }} />
              <div>
                <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#ef4444' }}>
                  {t('voiceListening')}
                </div>
                {currentTranscript && (
                  <div style={{ fontSize: '0.8rem', color: 'var(--cream)', fontStyle: 'italic' }}>
                    "{currentTranscript}"
                  </div>
                )}
              </div>
            </div>
            <button
              onClick={() => { void stopPrismaVoiceInput(); }}
              style={{
                background: '#ef4444',
                color: 'white',
                border: 'none',
                padding: '0.4rem 0.9rem',
                borderRadius: 'var(--radius-full)',
                fontSize: '0.8rem',
                fontWeight: 700,
                cursor: 'pointer'
              }}
            >
              {t('voicePrismaStop')}
            </button>
          </div>
        )}

        {/* Input Bar */}
        <form
          className="assistant-modal-form"
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
          {voiceConfigLoaded && !prismaEnabled && <span role="status" style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>{t('voicePrismaUnavailable')}</span>}
          {/* The sole voice-input control records clips for Prisma. */}
          <button
            type="button"
            onClick={isPrismaRecording ? () => { void stopPrismaVoiceInput(); } : () => { void startPrismaVoiceInput(); }}
            disabled={isProcessing || !prismaEnabled || !voiceConfigLoaded}
            aria-pressed={isPrismaRecording}
            aria-label={prismaEnabled ? t(isPrismaRecording ? 'voicePrismaStop' : 'voicePrismaRecord') : t('voicePrismaUnavailable')}
            style={{
              width: '44px',
              height: '44px',
              borderRadius: '50%',
              background: isPrismaRecording ? '#ef4444' : 'rgba(240, 168, 58, 0.15)',
              border: `1.5px solid ${isPrismaRecording ? '#ef4444' : 'var(--border-subtle)'}`,
              color: isPrismaRecording ? 'white' : 'var(--amber)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: isProcessing || !prismaEnabled || !voiceConfigLoaded ? 'not-allowed' : 'pointer',
              opacity: isProcessing || !prismaEnabled || !voiceConfigLoaded ? 0.55 : 1,
              flexShrink: 0,
              transition: 'all 0.2s'
            }}
            title={prismaEnabled ? t(isPrismaRecording ? 'voicePrismaStop' : 'voicePrismaRecord') : t('voicePrismaUnavailable')}
          >
            {isPrismaRecording ? <MicOff size={20} /> : <Mic size={20} />}
          </button>

          {/* Text Input */}
          <input
            type="text"
            className="input-field"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            placeholder={t('assistantPlaceholder')}
            style={{ flex: 1, padding: '0.8rem 1rem' }}
          />

          {/* Submit Button */}
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
              flexShrink: 0,
              transition: 'all 0.2s'
            }}
          >
            <Send size={18} />
          </button>
        </form>
        {voiceError && <p role="alert" style={{ margin: '0 1.4rem 1rem', color: '#fca5a5', fontSize: '0.82rem' }}>{voiceError}</p>}
      </div>
    </div>
  );
};

