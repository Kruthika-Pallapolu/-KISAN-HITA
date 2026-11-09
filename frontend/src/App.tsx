import React, { useState } from 'react';
import { LanguageProvider } from './context/LanguageContext';
import { FarmProfileProvider } from './context/FarmProfileContext';
import { AssistantProvider } from './context/AssistantContext';
import { Navbar } from './components/Navbar';
import { Footer } from './components/Footer';
import { LanguageModal } from './components/LanguageModal';
import { FirstTimeWelcomeModal } from './components/FirstTimeWelcomeModal';
import { SettingsModal } from './components/SettingsModal';
import { KisanAssistantModal } from './components/KisanAssistantModal';
import { PersistentAssistantBar } from './components/PersistentAssistantBar';
import { HomePage } from './pages/HomePage';
import { ChooseCropPage } from './pages/ChooseCropPage';
import { CheckCropPage } from './pages/CheckCropPage';
import { MarketPricesPage } from './pages/MarketPricesPage';
import { AskKisanHitaPage } from './pages/AskKisanHitaPage';
import { AuthProvider, useAuth } from './context/AuthContext';
import { AuthPage } from './pages/AuthPage';
import { FirstVisitLanguageSelection } from './components/FirstVisitLanguageSelection';
import { ScrollScrubBackground } from './components/ScrollScrubBackground';
import { useLanguage } from './context/LanguageContext';

const AppContent: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<string>('home');

  const handleRouteFeature = (feature: string) => {
    if (feature === 'home' || feature === 'dashboard') setCurrentTab('home');
    else if (feature === 'crop_advisor' || feature === 'choose-crop') setCurrentTab('choose-crop');
    else if (feature === 'crop_health' || feature === 'check-crop') setCurrentTab('check-crop');
    else if (feature === 'market_prices' || feature === 'market-prices') setCurrentTab('market-prices');
    else if (feature === 'ask_kisan') setCurrentTab('ask_kisan');
    else setCurrentTab('home');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="app-shell" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', position: 'relative' }}>
      {/* Reference landscape background, scrubbed by page scroll. */}
      <ScrollScrubBackground />

      {/* Navigation Bar */}
      <Navbar currentTab={currentTab} onSelectTab={handleRouteFeature} />

      {/* Main Page Content */}
      <main style={{ flex: 1, zIndex: 1 }}>
        {currentTab === 'home' && <HomePage onSelectTab={handleRouteFeature} />}
        {currentTab === 'choose-crop' && <ChooseCropPage onNavigate={handleRouteFeature} />}
        {currentTab === 'check-crop' && <CheckCropPage onNavigate={handleRouteFeature} />}
        {currentTab === 'market-prices' && <MarketPricesPage onNavigate={handleRouteFeature} />}
        {currentTab === 'ask_kisan' && <AskKisanHitaPage onRouteFeature={handleRouteFeature} onNavigate={handleRouteFeature} />}
      </main>

      {/* Central Persistent Assistant Floating Bar (Accessible on every page) */}
      <PersistentAssistantBar />

      {/* Central Kisan Assistant Conversational Modal */}
      <KisanAssistantModal onRouteFeature={handleRouteFeature} />

      {/* First-Visit / On-Demand Language Selection Modal */}
      <LanguageModal />

      {/* First-Time Friendly Conversational Welcome Modal */}
      <FirstTimeWelcomeModal />

      {/* Settings & Preferences Modal */}
      <SettingsModal />

      {/* Footer */}
      <Footer onSelectTab={handleRouteFeature} />
    </div>
  );
};

const AuthenticatedApp: React.FC = () => {
  const { user, isGuest, guestContextId, loading, continueAsGuest } = useAuth();
  const { hasChosenLanguage } = useLanguage();
  if (loading) return <div role="status" style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: 'var(--char)', color: 'var(--cream)' }}>Kisan Hita…</div>;
  if (!user && !isGuest) return hasChosenLanguage
    ? <AuthPage onContinueGuest={continueAsGuest} />
    : <FirstVisitLanguageSelection />;
  return <FarmProfileProvider isGuest={isGuest} guestContextId={guestContextId}><AssistantProvider isGuest={isGuest} guestContextId={guestContextId}><AppContent /></AssistantProvider></FarmProfileProvider>;
};

export const App: React.FC = () => {
  return (
    <LanguageProvider>
      <AuthProvider><AuthenticatedApp /></AuthProvider>
    </LanguageProvider>
  );
};

export default App;

