import React, { useEffect, useState } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { useAuth } from '../context/AuthContext';
import { useFarmProfile } from '../context/FarmProfileContext';
import { SupportedLanguage } from '../i18n/translations';
import { Settings, X, Check } from 'lucide-react';
import { localizeSoil, localizeWater } from '../i18n/agriculture';
import { FarmLocationFields } from './FarmLocationFields';
import { getState, getStateForDistrict } from '../services/geography';

const GUEST_SETTINGS_COPY: Record<SupportedLanguage, { notice: string; end: string }> = {
  en: { notice: 'Guest settings last for this browser session. Guest access expires after 24 hours.', end: 'End guest session' },
  te: { notice: 'అతిథి సెట్టింగ్‌లు ఈ బ్రౌజర్ సెషన్ వరకు ఉంటాయి. అతిథి ప్రవేశం 24 గంటల తర్వాత ముగుస్తుంది.', end: 'అతిథి సెషన్ ముగించండి' },
  hi: { notice: 'अतिथि सेटिंग इस ब्राउज़र सत्र तक रहेंगी। अतिथि प्रवेश 24 घंटे बाद समाप्त होगा।', end: 'अतिथि सत्र समाप्त करें' },
  ta: { notice: 'விருந்தினர் அமைப்புகள் இந்த உலாவி அமர்வு வரை இருக்கும். விருந்தினர் அணுகல் 24 மணிநேரத்தில் முடியும்.', end: 'விருந்தினர் அமர்வை முடிக்கவும்' },
  kn: { notice: 'ಅತಿಥಿ ಸೆಟ್ಟಿಂಗ್‌ಗಳು ಈ ಬ್ರೌಸರ್ ಸೆಷನ್‌ವರೆಗೆ ಇರುತ್ತವೆ. ಅತಿಥಿ ಪ್ರವೇಶ 24 ಗಂಟೆಗಳ ನಂತರ ಮುಗಿಯುತ್ತದೆ.', end: 'ಅತಿಥಿ ಸೆಷನ್ ಅಂತ್ಯಗೊಳಿಸಿ' },
  ml: { notice: 'അതിഥി ക്രമീകരണങ്ങൾ ഈ ബ്രൗസർ സെഷൻ വരെ നിലനിൽക്കും. അതിഥി പ്രവേശനം 24 മണിക്കൂറിന് ശേഷം അവസാനിക്കും.', end: 'അതിഥി സെഷൻ അവസാനിപ്പിക്കുക' },
  mr: { notice: 'अतिथी सेटिंग्ज या ब्राउझर सत्रापुरत्या राहतील. अतिथी प्रवेश २४ तासांनी संपेल.', end: 'अतिथी सत्र समाप्त करा' },
};

export const SettingsModal: React.FC = () => {
  const { t, language, setLanguage, languages } = useLanguage();
  const { user, isGuest, signOut } = useAuth();
  const { profile, updateProfile, showSettingsModal, setShowSettingsModal } = useFarmProfile();

  const [state, setState] = useState(getState(profile.state)?.name || getStateForDistrict(profile.district)?.name || '');
  const [district, setDistrict] = useState(profile.district);
  const [village, setVillage] = useState(profile.village);
  const [soilType, setSoilType] = useState(profile.soilType);
  const [waterSource, setWaterSource] = useState(profile.waterSource);
  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    if (!showSettingsModal) return;
    setState(getState(profile.state)?.name || getStateForDistrict(profile.district)?.name || '');
    setDistrict(profile.district);
    setVillage(profile.village);
    setSoilType(profile.soilType);
    setWaterSource(profile.waterSource);
  }, [showSettingsModal, profile]);

  if (!showSettingsModal) return null;

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    updateProfile({
      state,
      district,
      village,
      soilType,
      waterSource,
    });
    setSavedSuccess(true);
    setTimeout(() => {
      setSavedSuccess(false);
      setShowSettingsModal(false);
    }, 800);
  };

  return (
    <div className="cinematic-modal-overlay" style={{
      position: 'fixed',
      inset: 0,
      zIndex: 100,
      background: 'rgba(10, 11, 7, 0.85)',
      backdropFilter: 'blur(10px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '1.5rem'
    }}>
      <div className="cinematic-modal-surface" style={{
        background: 'var(--char-card)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-lg)',
        maxWidth: '540px',
        width: '100%',
        padding: '2rem',
        boxShadow: '0 20px 50px rgba(0, 0, 0, 0.6)',
        position: 'relative',
        maxHeight: '90vh',
        overflowY: 'auto'
      }}>
        <button
          onClick={() => setShowSettingsModal(false)}
          style={{
            position: 'absolute',
            top: '1.2rem',
            right: '1.2rem',
            background: 'none',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer'
          }}
        >
          <X size={20} />
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1.5rem' }}>
          <Settings size={22} style={{ color: 'var(--amber)' }} />
          <h2 style={{ fontSize: '1.35rem' }}>{t('settingsTitle')}</h2>
        </div>

        {user && <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '.7rem', marginBottom: '1rem', padding: '.65rem .8rem', border: '1px solid var(--border-card)', borderRadius: '.75rem', color: 'var(--text-muted)', fontSize: '.78rem' }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{user.email}</span>
          <button type="button" onClick={() => void signOut()} style={{ flexShrink: 0, border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-full)', padding: '.35rem .7rem', color: 'var(--cream)', background: 'transparent', cursor: 'pointer' }}>{t('authSignOut')}</button>
        </div>}
        {isGuest && <div role="note" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '.7rem', marginBottom: '1rem', padding: '.65rem .8rem', border: '1px solid var(--border-card)', borderRadius: '.75rem', color: 'var(--text-muted)', fontSize: '.78rem' }}>
          <span>{GUEST_SETTINGS_COPY[language].notice}</span>
          <button type="button" onClick={() => void signOut()} style={{ flexShrink: 0, border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-full)', padding: '.45rem .7rem', color: 'var(--cream)', background: 'transparent', cursor: 'pointer' }}>{GUEST_SETTINGS_COPY[language].end}</button>
        </div>}

        <form onSubmit={handleSave}>
          {/* Language Selection */}
          <div className="input-group">
            <label className="input-label">{t('languageSelect')}</label>
            <select
              className="select-field"
              value={language}
              onChange={(e) => setLanguage(e.target.value as SupportedLanguage)}
            >
              {languages.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.nativeName} ({l.name})
                </option>
              ))}
            </select>
          </div>

          {/* State-first farm location */}
          <div className="input-group">
            <label className="input-label">{t('farmLocation')}</label>
            <FarmLocationFields
              state={state}
              district={district}
              onChange={(nextState, nextDistrict) => { setState(nextState); setDistrict(nextDistrict); }}
            />
          </div>

          {/* Soil Type */}
          <div className="input-group">
            <label className="input-label">{t('soilType')}</label>
            <select
              className="select-field"
              value={soilType}
              onChange={(e) => setSoilType(e.target.value)}
            >
              {['Black Cotton Soil', 'Red Soil', 'Sandy Soil', 'Loamy Soil', 'Clay Soil'].map((soil) => <option key={soil} value={soil}>{localizeSoil(soil, language)}</option>)}
            </select>
          </div>

          {/* Water Source */}
          <div className="input-group">
            <label className="input-label">{t('waterAvailability')}</label>
            <select
              className="select-field"
              value={waterSource}
              onChange={(e) => setWaterSource(e.target.value)}
            >
              {['Good irrigation', 'Limited irrigation', 'Rain-dependent'].map((water) => <option key={water} value={water}>{localizeWater(water, language)}</option>)}
            </select>
          </div>

          <div style={{ marginTop: '1.6rem', display: 'flex', gap: '1rem' }}>
            <button
              type="submit"
              className="btn btn-primary"
              style={{ flex: 1, padding: '0.85rem' }}
            >
              {savedSuccess ? (
                <>
                  <Check size={18} /> {t('saveComplete')}
                </>
              ) : (
                t('savePreferences')
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

