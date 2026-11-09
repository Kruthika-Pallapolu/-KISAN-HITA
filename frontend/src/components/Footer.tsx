import React from 'react';
import { useLanguage } from '../context/LanguageContext';
import { Sprout, Heart } from 'lucide-react';

interface FooterProps {
  onSelectTab: (tab: string) => void;
}

export const Footer: React.FC<FooterProps> = ({ onSelectTab }) => {
  const { t, languages } = useLanguage();

  return (
    <footer style={{
      background: 'rgba(18, 19, 12, 0.95)',
      borderTop: '1px solid var(--border-card)',
      padding: '4rem 1.5rem 6.5rem', // padding bottom leaves space for persistent assistant pill
      marginTop: '5rem',
      position: 'relative',
      zIndex: 10
    }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: '2.5rem',
          marginBottom: '3rem'
        }}>
          {/* Brand & Purpose */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1rem' }}>
              <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: 'linear-gradient(135deg, #2f3a1c, #8a6a45)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--amber)'
              }}>
                <Sprout size={18} />
              </div>
              <span style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--cream)' }}>
                {t('appName')}
              </span>
            </div>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', lineHeight: 1.6, marginBottom: '1rem' }}>
              {t('tagline')}. {t('footerAttribution')}
            </p>
          </div>

          {/* Quick Navigation */}
          <div>
            <h4 className="mono" style={{ fontSize: '0.78rem', color: 'var(--amber)', textTransform: 'uppercase', marginBottom: '1.2rem', letterSpacing: '0.08em' }}>
              {t('quickNavigation')}
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.88rem' }}>
              <a href="#home" onClick={(e) => { e.preventDefault(); onSelectTab('home'); }} style={{ color: 'var(--cream)', opacity: 0.75 }}>
                {t('navHome')}
              </a>
              <a href="#choose-crop" onClick={(e) => { e.preventDefault(); onSelectTab('choose-crop'); }} style={{ color: 'var(--cream)', opacity: 0.75 }}>
                {t('navChooseCrop')}
              </a>
              <a href="#check-crop" onClick={(e) => { e.preventDefault(); onSelectTab('check-crop'); }} style={{ color: 'var(--cream)', opacity: 0.75 }}>
                {t('navCheckCrop')}
              </a>
              <a href="#market-prices" onClick={(e) => { e.preventDefault(); onSelectTab('market-prices'); }} style={{ color: 'var(--cream)', opacity: 0.75 }}>
                {t('navMarketPrices')}
              </a>
            </div>
          </div>

          {/* Supported Languages */}
          <div>
            <h4 className="mono" style={{ fontSize: '0.78rem', color: 'var(--amber)', textTransform: 'uppercase', marginBottom: '1.2rem', letterSpacing: '0.08em' }}>
              {t('supportedLanguages')}
            </h4>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.45rem' }}>
              {languages.map((l) => (
                <span
                  key={l.code}
                  style={{
                    background: 'rgba(244, 236, 216, 0.06)',
                    border: '1px solid var(--border-card)',
                    padding: '0.3rem 0.6rem',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.76rem',
                    color: 'var(--cream)'
                  }}
                >
                  {l.nativeName} ({l.name})
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Bottom Bar */}
        <div style={{
          borderTop: '1px solid var(--border-card)',
          paddingTop: '1.8rem',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem',
          color: 'var(--text-dim)',
          fontSize: '0.78rem'
        }}>
          <div>{t('copyright')}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
            <span>{t('footerPowered')}</span>
          </div>
        </div>
      </div>
    </footer>
  );
};

