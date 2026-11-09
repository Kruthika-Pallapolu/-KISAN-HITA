import React, { useState } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { useFarmProfile } from '../context/FarmProfileContext';
import { KISAN_HITA_NAME } from '../services/productIdentity';
import { useAssistant } from '../context/AssistantContext';
import { Bot, CloudSun, Sprout, ShieldAlert, TrendingUp, Settings, Globe, Menu, X } from 'lucide-react';

interface NavbarProps {
  currentTab: string;
  onSelectTab: (tab: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ currentTab, onSelectTab }) => {
  const { t, language, setShowLanguageModal, languages } = useLanguage();
  const { profile, setShowSettingsModal } = useFarmProfile();
  const { toggleAssistant, isOpen } = useAssistant();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const currentLangObj = languages.find((l) => l.code === language);

  const navItems = [
    { id: 'home', label: t('navHome'), icon: null },
    { id: 'weather', label: t('navWeather'), icon: <CloudSun size={17} /> },
    { id: 'choose-crop', label: t('navChooseCrop'), icon: <Sprout size={17} /> },
    { id: 'check-crop', label: t('navCheckCrop'), icon: <ShieldAlert size={17} /> },
    { id: 'market-prices', label: t('navMarketPrices'), icon: <TrendingUp size={17} /> },
  ];

  const handleNavClick = (id: string) => {
    onSelectTab(id);
    setMobileMenuOpen(false);
  };

  return (
    <header style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      zIndex: 50,
      background: 'rgba(22, 23, 15, 0.92)',
      backdropFilter: 'blur(12px)',
      borderBottom: '1px solid var(--border-card)',
      padding: '0.8rem 1.5rem'
    }} className="navbar-header">
      <div style={{
        maxWidth: '1240px',
        margin: '0 auto',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '1rem'
      }} className="navbar-inner">
        {/* Central Kisan Assistant Pill (Heart of the app) */}
        <button
          onClick={toggleAssistant}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.6rem',
            padding: '0.5rem 1.1rem',
            background: isOpen ? 'linear-gradient(135deg, rgba(240, 168, 58, 0.25), rgba(47, 58, 28, 0.4))' : 'rgba(47, 58, 28, 0.5)',
            border: `1.5px solid ${isOpen ? 'var(--amber)' : 'rgba(240, 168, 58, 0.3)'}`,
            borderRadius: 'var(--radius-full)',
            color: 'var(--cream)',
            cursor: 'pointer',
            fontWeight: 700,
            fontSize: '0.88rem',
            boxShadow: isOpen ? '0 0 16px rgba(240, 168, 58, 0.35)' : 'none',
            transition: 'all 0.25s ease'
          }}
          title={t('openAssistant')}
          className="assistant-pill"
        >
          <span style={{
            width: '9px',
            height: '9px',
            borderRadius: '50%',
            background: '#4ade80',
            boxShadow: '0 0 8px #4ade80'
          }} />
          <Bot size={18} style={{ color: 'var(--amber)' }} />
          <span>{KISAN_HITA_NAME}</span>
          <span className="assistant-ai-label" style={{
            background: 'rgba(240, 168, 58, 0.15)',
            color: 'var(--amber)',
            padding: '0.15rem 0.5rem',
            borderRadius: 'var(--radius-full)',
            fontSize: '0.7rem'
          }}>
            AI
          </span>
        </button>

        {/* Desktop Navigation Links */}
        <nav style={{ display: 'none', alignItems: 'center', gap: '1.2rem' }} className="desktop-nav">
          {navItems.map((item) => {
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => handleNavClick(item.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  background: 'none',
                  border: 'none',
                  color: isActive ? 'var(--amber)' : 'var(--cream)',
                  opacity: isActive ? 1 : 0.75,
                  fontWeight: isActive ? 700 : 500,
                  fontSize: '0.88rem',
                  cursor: 'pointer',
                  padding: '0.4rem 0.6rem',
                  position: 'relative',
                  transition: 'opacity 0.2s',
                  fontFamily: 'inherit'
                }}
              >
                {item.icon}
                <span>{item.label}</span>
                {isActive && (
                  <span style={{
                    position: 'absolute',
                    bottom: '-6px',
                    left: '10%',
                    right: '10%',
                    height: '2px',
                    background: 'var(--amber)',
                    borderRadius: '2px'
                  }} />
                )}
              </button>
            );
          })}
        </nav>

        {/* Actions (Language & Settings) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }} className="navbar-actions">
          {/* Language Selector Pill */}
          <button
            onClick={() => setShowLanguageModal(true)}
            className="language-pill"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.45rem',
              background: 'rgba(244, 236, 216, 0.08)',
              border: '1px solid var(--border-card)',
              color: 'var(--cream)',
              padding: '0.45rem 0.85rem',
              borderRadius: 'var(--radius-full)',
              cursor: 'pointer',
              fontSize: '0.82rem',
              fontWeight: 600,
              fontFamily: 'inherit'
            }}
            title={t('switchLanguage')}
          >
            <Globe size={15} style={{ color: 'var(--amber)' }} />
            <span>{currentLangObj?.nativeName || 'English'}</span>
          </button>

          {/* Settings Button */}
          <button
            onClick={() => setShowSettingsModal(true)}
            className="settings-button"
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '50%',
              background: 'rgba(244, 236, 216, 0.08)',
              border: '1px solid var(--border-card)',
              color: 'var(--cream)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer'
            }}
            title={t('navSettings')}
          >
            <Settings size={18} />
          </button>

          {/* Mobile Menu Toggle */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'none',
              border: 'none',
              color: 'var(--cream)',
              cursor: 'pointer',
              padding: '0.4rem'
            }}
            className="mobile-toggle"
          >
            {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </div>

      {/* Mobile Menu Dropdown */}
      {mobileMenuOpen && (
        <div style={{
          marginTop: '1rem',
          padding: '1rem 0',
          borderTop: '1px solid var(--border-card)',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.75rem'
        }}>
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => handleNavClick(item.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.8rem',
                background: currentTab === item.id ? 'rgba(240, 168, 58, 0.15)' : 'none',
                border: 'none',
                color: currentTab === item.id ? 'var(--amber)' : 'var(--cream)',
                padding: '0.7rem 1rem',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.95rem',
                fontWeight: currentTab === item.id ? 700 : 500,
                textAlign: 'left',
                width: '100%',
                cursor: 'pointer'
              }}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}
        </div>
      )}

      <style>{`
        @media (min-width: 900px) {
          .desktop-nav { display: flex !important; }
          .mobile-toggle { display: none !important; }
        }
      `}</style>
    </header>
  );
};

