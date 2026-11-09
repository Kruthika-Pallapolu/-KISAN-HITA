import React from 'react';
import { useLanguage } from '../context/LanguageContext';
import { useAssistant } from '../context/AssistantContext';
import { Bot, Sprout, ShieldAlert, TrendingUp, Mic, ArrowRight, CheckCircle2, Sparkles, Volume2 } from 'lucide-react';

interface HomePageProps {
  onSelectTab: (tab: string) => void;
}

export const HomePage: React.FC<HomePageProps> = ({ onSelectTab }) => {
  const { t, language } = useLanguage();
  const { openAssistant } = useAssistant();

  const handleOpenAssistant = () => {
    openAssistant();
  };

  const featureCards = [
    {
      id: 'choose-crop',
      badge: t('badgeCrop'),
      title: t('cropAdvisorTitle'),
      desc: t('cropAdvisorSub'),
      icon: <Sprout size={26} style={{ color: 'var(--amber)' }} />,
      stat: t('statCrop'),
    },
    {
      id: 'check-crop',
      badge: t('badgeHealth'),
      title: t('cropHealthTitle'),
      desc: t('cropHealthSub'),
      icon: <ShieldAlert size={26} style={{ color: 'var(--amber)' }} />,
      stat: t('statHealth'),
    },
    {
      id: 'market-prices',
      badge: t('badgeMarket'),
      title: t('marketTitle'),
      desc: t('marketSub'),
      icon: <TrendingUp size={26} style={{ color: 'var(--amber)' }} />,
      stat: t('statMarket'),
    },
  ];

  return (
    <div className="home-page">
      {/* Hero Section */}
      <section className="home-hero">
        <div className="home-hero-content">
          {/* Badge */}
          <div style={{ display: 'inline-flex', marginBottom: '0.15rem' }}>
            {language === 'en' ? (
              <span className="mono home-hero-eyebrow">Cinematic AI for Indian farmers</span>
            ) : (
              <span className="badge"><Sparkles size={13} />{t('tagline')}</span>
            )}
          </div>

          {/* Heading */}
          <h1 className="home-hero-title">
            {t('heroHeading')}
          </h1>

          {/* Subtext */}
          {language === 'en' ? (
            <>
              <p className="home-hero-tagline">Empowering Indian farmers with technology that listens.</p>
              <p className="home-hero-copy">Making agricultural knowledge more accessible through the power of voice.</p>
            </>
          ) : <p className="home-hero-copy">{t('heroSub')}</p>}

          {/* CTAs */}
          <div className="home-hero-actions" style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'flex-start',
            gap: '1rem'
          }}>
            {language !== 'en' && (
              <button
                onClick={handleOpenAssistant}
                className="btn btn-primary"
                style={{ padding: '0.85rem 1.8rem', fontSize: '1rem' }}
              >
                <Bot size={19} />
                <span>{t('startConversation')}</span>
              </button>
            )}
            <button
              onClick={() => document.getElementById(language === 'en' ? 'home-purpose' : 'step-by-step-process')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
              className={`btn ${language === 'en' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '0.85rem 1.8rem', fontSize: '1rem' }}
            >
              <span>{language === 'en' ? 'Discover Kisan Hita' : t('exploreFeatures')}</span>
              <ArrowRight size={17} />
            </button>
          </div>
        </div>
        {language === 'en' && <div className="home-scroll-cue" aria-hidden="true"><span>Scroll</span><i /></div>}
      </section>

      {/* Story & Philosophy Section */}
      <section className={`home-story${language === 'en' ? ' home-story-reference' : ''}`} id="step-by-step-process">
        <div className="home-story-content">
          <div style={{ textAlign: language === 'en' ? 'left' : 'center', marginBottom: '2.8rem' }}>
            {language !== 'en' && <span className="mono" style={{ color: 'var(--amber)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{t('stepByStep')}</span>}
            <h2 style={{ fontSize: '2rem', marginTop: '0.5rem', marginBottom: '0.8rem' }}>
              {language === 'en' ? 'Every field has a story. Every farmer deserves answers.' : t('howItWorks')}
            </h2>
            {language === 'en' ? (
              <>
                <p className="home-artifact-copy">Agriculture involves countless questions, decisions and everyday challenges. Accessing useful information should feel simpler and more natural.</p>
                <p className="home-artifact-copy">Kisan Hita aims to bring agricultural knowledge closer to farmers through voice-first interaction.</p>
              </>
            ) : <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem' }}>{t('homeProcessSub')}</p>}
          </div>

          {language !== 'en' && <div className="home-story-grid">
            <div className="card">
              <span className="mono" style={{ color: 'var(--amber)', fontSize: '1.1rem', fontWeight: 800 }}>01</span>
              <h3 style={{ fontSize: '1.2rem', margin: '0.8rem 0 0.5rem' }}>{t('speakNaturally')}</h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', lineHeight: 1.5 }}>
                {t('speakNaturallySub')}
              </p>
            </div>

            <div className="card">
              <span className="mono" style={{ color: 'var(--amber)', fontSize: '1.1rem', fontWeight: 800 }}>02</span>
              <h3 style={{ fontSize: '1.2rem', margin: '0.8rem 0 0.5rem' }}>{t('intentRecognition')}</h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', lineHeight: 1.5 }}>
                {t('intentRecognitionSub')}
              </p>
            </div>

            <div className="card">
              <span className="mono" style={{ color: 'var(--amber)', fontSize: '1.1rem', fontWeight: 800 }}>03</span>
              <h3 style={{ fontSize: '1.2rem', margin: '0.8rem 0 0.5rem' }}>{t('clearGuidance')}</h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', lineHeight: 1.5 }}>
                {t('clearGuidanceSub')}
              </p>
            </div>
          </div>}
        </div>
      </section>

      {language === 'en' && <section className="home-purpose" id="home-purpose" data-background-intro>
        <div className="home-purpose-content">
          <h2>A simpler way to access agricultural knowledge.</h2>
          <p>Kisan Hita is a voice-first AI assistant designed around farmers, making information more accessible through natural conversational interaction.</p>
          <div className="home-purpose-grid">
            <article><span>01</span><h3>Speak Naturally</h3><p>Interact using voice instead of depending entirely on typing.</p></article>
            <article><span>02</span><h3>Access Information</h3><p>Make agricultural information easier to reach through a conversational experience.</p></article>
            <article><span>03</span><h3>Designed Around Farmers</h3><p>An experience shaped around the needs and realities of agricultural communities.</p></article>
          </div>
        </div>
      </section>}

      {/* Farmer Services Grid */}
      <section className="home-services">
        <div className="home-services-content">
          <div style={{ marginBottom: '2.5rem' }}>
            <span className="mono" style={{ color: 'var(--amber)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              {language === 'en' ? 'HOW IT HELPS' : t('agriculturalIntelligence')}
            </span>
            <h2 style={{ fontSize: '2.2rem', marginTop: '0.4rem' }}>
              {language === 'en' ? 'How It Helps' : t('exploreServices')}
            </h2>
          </div>

          <div className="grid-2">
            {featureCards.map((card) => (
              <div
                key={card.id}
                className="card card-highlight home-feature-card"
                onClick={() => onSelectTab(card.id)}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.2rem' }}>
                    <span className="mono" style={{
                      color: 'var(--amber)',
                      background: 'rgba(240, 168, 58, 0.12)',
                      padding: '0.25rem 0.65rem',
                      borderRadius: 'var(--radius-sm)',
                      fontWeight: 700
                    }}>
                      {card.badge}
                    </span>
                    <div style={{
                      width: '44px',
                      height: '44px',
                      borderRadius: '12px',
                      background: 'rgba(240, 168, 58, 0.12)',
                      border: '1px solid var(--border-subtle)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}>
                      {card.icon}
                    </div>
                  </div>

                  <h3 style={{ fontSize: '1.35rem', marginBottom: '0.6rem' }}>
                    {card.title}
                  </h3>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.92rem', lineHeight: 1.6 }}>
                    {card.desc}
                  </p>
                </div>

                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  paddingTop: '1rem',
                  borderTop: '1px solid var(--border-card)'
                }}>
                  <span className="mono" style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                    {card.stat}
                  </span>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.4rem',
                    color: 'var(--amber)',
                    fontSize: '0.88rem',
                    fontWeight: 700
                  }}>
                    <span>{t('explore')}</span>
                    <ArrowRight size={16} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
};

