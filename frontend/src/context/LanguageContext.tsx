import React, { createContext, useContext, useState, useEffect } from 'react';
import { SupportedLanguage, translations, LANGUAGES, LanguageInfo } from '../i18n/translations';
import { supplementalTranslations } from '../i18n/supplementalTranslations';
import { readLanguagePreference, saveLanguagePreference } from '../services/languagePreference';
import { getBrowserSessionMode } from '../services/sessionMode';

interface LanguageContextType {
  language: SupportedLanguage;
  setLanguage: (lang: SupportedLanguage) => void;
  setLanguageLocally: (lang: SupportedLanguage) => void;
  t: (key: string) => string;
  languages: LanguageInfo[];
  hasChosenLanguage: boolean;
  showLanguageModal: boolean;
  setShowLanguageModal: (show: boolean) => void;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export const LanguageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [language, setLanguageState] = useState<SupportedLanguage>(() => readLanguagePreference() || 'en');
  const [hasChosenLanguage, setHasChosenLanguage] = useState(() => Boolean(readLanguagePreference()));

  const [showLanguageModal, setShowLanguageModal] = useState<boolean>(() => {
    // Language is selected during account setup; existing users use their
    // server-saved preference and should not be prompted on every new browser.
    return false;
  });

  const setLanguage = (lang: SupportedLanguage) => {
    setLanguageState(lang);
    setHasChosenLanguage(true);
    saveLanguagePreference(lang);
    if (getBrowserSessionMode() === 'account') {
      void fetch('/api/settings/profile', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ selected_language: lang }),
      }).catch(() => {});
    }
  };

  const setLanguageLocally = (lang: SupportedLanguage) => {
    setLanguageState(lang);
    setHasChosenLanguage(true);
    saveLanguagePreference(lang);
  };

  const t = (key: string): string => {
    const langDict = translations[language] || translations['en'];
    if (langDict[key] || supplementalTranslations[language]?.[key]) return langDict[key] || supplementalTranslations[language][key];
    if (language !== 'en' && translations['en'][key]) {
      if ((import.meta as ImportMeta & { env: { DEV: boolean } }).env.DEV) console.warn(`[i18n] Missing '${key}' for '${language}'; showing English fallback.`);
      return translations['en'][key];
    }
    if ((import.meta as ImportMeta & { env: { DEV: boolean } }).env.DEV) console.warn(`[i18n] Missing translation key '${key}' for '${language}'.`);
    return key;
  };

  return (
    <LanguageContext.Provider
      value={{
        language,
        setLanguage,
        setLanguageLocally,
        t,
        languages: LANGUAGES,
        hasChosenLanguage,
        showLanguageModal,
        setShowLanguageModal
      }}
    >
      {children}
    </LanguageContext.Provider>
  );
};

export const useLanguage = () => {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error('useLanguage must be used within LanguageProvider');
  return ctx;
};

