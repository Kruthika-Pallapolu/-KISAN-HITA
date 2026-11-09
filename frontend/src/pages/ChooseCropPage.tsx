import React, { useState, useEffect, useRef } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { useFarmProfile } from '../context/FarmProfileContext';
import { useAssistant } from '../context/AssistantContext';
import { localizeSeason, localizeSoil, localizeWater, localizeCropName } from '../i18n/agriculture';
import { localizeCropAdvice } from '../i18n/cropAdvisory';
import { FarmLocationFields } from '../components/FarmLocationFields';
import { getState, getStateForDistrict, isDistrictInState } from '../services/geography';
import { Sprout, Clock, Droplets, BookOpen, AlertCircle, Volume2, Square, ArrowRight, ShieldCheck, ArrowLeft, ExternalLink, PhoneCall, Bot } from 'lucide-react';

interface CropRecommendation {
  crop_name: string;
  variety: string;
  duration_days: string;
  water_requirement: string;
  soil_suitability: string;
  limitations: string;
  next_steps: string;
  citation: string;
}

interface CropAdvisorResponse {
  recommendations: CropRecommendation[];
  total_found: number;
  soil_type: string;
  growing_season: string;
  water_availability: string;
  disclaimer: string;
}

interface ChooseCropPageProps {
  onNavigate?: (tab: string) => void;
}

export const ChooseCropPage: React.FC<ChooseCropPageProps> = ({ onNavigate }) => {
  const { t, language } = useLanguage();
  const { profile, updateProfile } = useFarmProfile();
  const { speakText, stopSpeaking, isSpeaking } = useAssistant();

  const [soilType, setSoilType] = useState(profile.soilType || 'Black Cotton Soil');
  const [waterAvailability, setWaterAvailability] = useState(profile.waterSource || 'Good irrigation');
  const [growingSeason, setGrowingSeason] = useState('Kharif (Monsoon)');
  const [state, setState] = useState(getState(profile.state)?.name || getStateForDistrict(profile.district)?.name || '');
  const [district, setDistrict] = useState(profile.district || '');

  const [results, setResults] = useState<CropAdvisorResponse | null>(null);
  const [resultCriteria, setResultCriteria] = useState('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [activeSpeechIdx, setActiveSpeechIdx] = useState<number | null>(null);
  const requestId = useRef(0);
  const activeRequest = useRef<AbortController | null>(null);
  const criteriaKey = JSON.stringify({ soilType, waterAvailability, growingSeason, state, district });

  const fetchRecommendations = async () => {
    const submittedCriteria = JSON.stringify({ soilType, waterAvailability, growingSeason, state, district });
    const request = ++requestId.current;
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/crop-advisor/recommend', {
        method: 'POST',
        signal: controller.signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          soil_type: soilType,
          water_availability: waterAvailability,
          growing_season: growingSeason,
          district,
          state,
          language,
        }),
      });
      if (!res.ok) throw new Error(res.status >= 500 ? t('cropServiceUnavailable') : t('cropRequestFailed'));
      const data: CropAdvisorResponse = await res.json();
      if (request !== requestId.current) return;
      setResults(data);
      setResultCriteria(submittedCriteria);
    } catch (err: any) {
      if (controller.signal.aborted || request !== requestId.current) return;
      console.error('Crop recommendation error:', err);
      setError(err?.message || t('cropServiceUnavailable'));
    } finally {
      if (request === requestId.current) setLoading(false);
    }
  };

  useEffect(() => () => {
    requestId.current += 1;
    activeRequest.current?.abort();
  }, []);

  useEffect(() => {
    activeRequest.current?.abort();
    requestId.current += 1;
    setLoading(false);
    setResults(null);
    setError(null);
    if (profile.soilType && profile.soilType !== soilType) {
      setSoilType(profile.soilType);
    }
    if (profile.waterSource && profile.waterSource !== waterAvailability) {
      setWaterAvailability(profile.waterSource);
    }
    if (profile.state || profile.district) {
      const nextState = getState(profile.state)?.name || getStateForDistrict(profile.district)?.name || '';
      setState(nextState);
      setDistrict(profile.district && isDistrictInState(profile.district, nextState) ? profile.district : '');
    }
  }, [profile.soilType, profile.waterSource, profile.state, profile.district]);

  const handleLocationChange = (nextState: string, nextDistrict: string) => {
    activeRequest.current?.abort();
    requestId.current += 1;
    setLoading(false);
    setResults(null);
    setError(null);
    setState(nextState);
    setDistrict(nextDistrict);
    updateProfile({ state: nextState, district: nextDistrict });
  };

  const updateInput = (update: () => void) => {
    activeRequest.current?.abort();
    requestId.current += 1;
    setLoading(false);
    setResults(null);
    setError(null);
    update();
  };

  const handleSpeakCard = (rec: CropRecommendation, idx: number) => {
    if (activeSpeechIdx === idx && isSpeaking) {
      stopSpeaking();
      setActiveSpeechIdx(null);
    } else {
      setActiveSpeechIdx(idx);
      const speech = `${localizeCropName(rec.crop_name, language)}, ${rec.variety}. ${localizeCropAdvice(rec.duration_days, language)}. ${localizeCropAdvice(rec.water_requirement, language)}. ${localizeCropAdvice(rec.soil_suitability, language)} ${localizeCropAdvice(rec.limitations, language)}. ${localizeCropAdvice(rec.next_steps, language)}.`;
      speakText(speech);
    }
  };

  return (
    <div className="module-page crop-advisor-page" style={{ paddingTop: '5.5rem', paddingBottom: '5rem' }}>
      <div className="container">
        {/* Navigation Breadcrumb */}
        {onNavigate && (
          <div style={{ marginBottom: '1.2rem' }}>
            <button
              onClick={() => onNavigate('home')}
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

        {/* Error Alert Banner */}
        {error && (
          <div className="card" style={{ marginBottom: '2rem', border: '1px solid rgba(248, 113, 113, 0.3)', background: 'rgba(248, 113, 113, 0.08)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
                <AlertCircle size={22} style={{ color: '#f87171' }} />
                <span style={{ color: '#f87171', fontSize: '0.92rem' }}>{error}</span>
              </div>
              <button
                onClick={fetchRecommendations}
                className="btn btn-secondary"
                style={{ fontSize: '0.85rem', padding: '0.4rem 1rem' }}
              >
                {t('retry')}
              </button>
            </div>
          </div>
        )}

        {/* Header */}
        <div style={{ marginBottom: '2rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.6rem' }}>
            <span className="badge">{t('module2Badge')}</span>
            <span className="mono" style={{ color: 'var(--amber)', fontSize: '0.8rem' }}>{t('cropSuitabilityLabel')}</span>
          </div>
          <h1 style={{ fontSize: 'clamp(1.8rem, 4vw, 2.6rem)', marginBottom: '0.6rem' }}>
            {t('cropAdvisorTitle')}
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '1rem', maxWidth: '720px' }}>
            {t('cropAdvisorSub')}
          </p>
        </div>

        {/* Input Parameters Form */}
        <div className="card" style={{ marginBottom: '2.5rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.2rem' }}>
            <div className="input-group">
              <label className="input-label">{t('soilType')}</label>
              <select className="select-field" value={soilType} onChange={(e) => updateInput(() => setSoilType(e.target.value))}>
                {['Black Cotton Soil', 'Red Soil', 'Sandy Soil', 'Loamy Soil', 'Clay Soil', 'Other', "I don't know"].map((soil) => <option key={soil} value={soil}>{localizeSoil(soil, language)}</option>)}
              </select>
            </div>

            <div className="input-group">
              <label className="input-label">{t('waterAvailability')}</label>
              <select className="select-field" value={waterAvailability} onChange={(e) => updateInput(() => setWaterAvailability(e.target.value))}>
                {['Good irrigation', 'Limited irrigation', 'Rain-dependent'].map((water) => <option key={water} value={water}>{localizeWater(water, language)}</option>)}
              </select>
            </div>

            <div className="input-group">
              <label className="input-label">{t('growingSeason')}</label>
              <select className="select-field" value={growingSeason} onChange={(e) => updateInput(() => setGrowingSeason(e.target.value))}>
                {['Kharif (Monsoon)', 'Rabi (Winter)', 'Zaid (Summer)'].map((season) => <option key={season} value={season}>{localizeSeason(season, language)}</option>)}
              </select>
            </div>

            <div className="input-group">
              <FarmLocationFields state={state} district={district} onChange={handleLocationChange} />
            </div>
          </div>

          <div style={{ marginTop: '0.8rem', display: 'flex', justifyContent: 'flex-end' }}>
            <button
              onClick={fetchRecommendations}
              className="btn btn-primary"
              style={{ padding: '0.75rem 1.8rem' }}
              disabled={loading}
            >
              <Sprout size={18} />
              <span>{loading ? t('evaluating') : t('getSuitableCrops')}</span>
            </button>
          </div>
        </div>

        {/* Results Section */}
        {results && resultCriteria === criteriaKey && (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '0.8rem' }}>
              <h2 style={{ fontSize: '1.45rem' }}>
                {t('recommendedCrops')}
              </h2>
              <div className="mono" style={{ fontSize: '0.75rem', color: 'var(--amber)' }}>
                {t('soilType')}: {localizeSoil(results.soil_type, language)} • {t('growingSeason')}: {localizeSeason(results.growing_season, language)}
              </div>
            </div>

            {/* Empty State when no research-backed recommendations match */}
            {results.recommendations.length === 0 ? (
              <div className="card" style={{ padding: '2.5rem 2rem', marginBottom: '2.5rem', border: '1px solid var(--border-subtle)', background: 'rgba(28, 30, 20, 0.55)' }}>
                <div style={{ textAlign: 'center', maxWidth: '700px', margin: '0 auto 2rem' }}>
                  <ShieldCheck size={44} style={{ color: 'var(--amber)', margin: '0 auto 1rem' }} />
                  <h3 style={{ fontSize: '1.35rem', marginBottom: '0.6rem', color: 'var(--cream)' }}>
                    {t('cropNoResults')}
                  </h3>
                  <p style={{ color: 'var(--text-muted)', lineHeight: 1.6, fontSize: '0.92rem' }}>
                    {t('cropDemoDisclaimer')}
                  </p>
                </div>

                {/* Practical Guidance for Farmers */}
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                  gap: '1.2rem',
                  marginBottom: '2rem'
                }}>
                  <div style={{
                    background: 'var(--char-input)',
                    border: '1px solid var(--border-card)',
                    borderRadius: 'var(--radius-md)',
                    padding: '1.2rem'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', color: 'var(--amber)', fontWeight: 700, fontSize: '0.9rem' }}>
                      <Sprout size={16} />
                      <span>{t('cropKvkTitle')}</span>
                    </div>
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', lineHeight: 1.5 }}>
                      {t('cropKvkDescription')}
                    </p>
                  </div>

                  <div style={{
                    background: 'var(--char-input)',
                    border: '1px solid var(--border-card)',
                    borderRadius: 'var(--radius-md)',
                    padding: '1.2rem'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', color: '#a3e635', fontWeight: 700, fontSize: '0.9rem' }}>
                      <PhoneCall size={16} />
                      <span>{t('cropCallCentre')}</span>
                    </div>
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', lineHeight: 1.5 }}>
                      {t('cropCallCentreDescription')}
                    </p>
                  </div>

                  <div style={{
                    background: 'var(--char-input)',
                    border: '1px solid var(--border-card)',
                    borderRadius: 'var(--radius-md)',
                    padding: '1.2rem'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', color: '#38bdf8', fontWeight: 700, fontSize: '0.9rem' }}>
                      <ExternalLink size={16} />
                      <span>{t('cropSoilHealthPortal')}</span>
                    </div>
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', lineHeight: 1.5, marginBottom: '0.6rem' }}>
                      {t('cropSoilHealthDescription')}
                    </p>
                    <a
                      href="https://soilhealth.dac.gov.in"
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: '#38bdf8', fontSize: '0.82rem', display: 'inline-flex', alignItems: 'center', gap: '0.3rem', textDecoration: 'underline' }}
                    >
                      soilhealth.dac.gov.in <ExternalLink size={12} />
                    </a>
                  </div>
                </div>

                {onNavigate && (
                  <div style={{ display: 'flex', justifyContent: 'center' }}>
                    <button
                      onClick={() => onNavigate('ask-kisan')}
                      className="btn btn-secondary"
                      style={{ fontSize: '0.9rem', padding: '0.65rem 1.4rem' }}
                    >
                      <Bot size={16} />
                      <span>{t('cropAskAssistant')}</span>
                    </button>
                  </div>
                )}
              </div>
            ) : (
              /* Exactly Max 3 Recommendations Cards */
              <div className="grid-3" style={{ marginBottom: '2.5rem' }}>
                {results.recommendations.map((rec, idx) => (
                <div
                  key={`${rec.crop_name}:${rec.variety}`}
                  className="card card-highlight"
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    gap: '1.2rem',
                    borderTop: '3px solid var(--amber)'
                  }}
                >
                  <div>
                    {/* Header */}
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.8rem', marginBottom: '0.8rem' }}>
                      <div>
                        <h3 style={{ fontSize: '1.35rem', color: 'var(--cream)', marginBottom: '0.2rem' }}>
                          {localizeCropName(rec.crop_name, language)}
                        </h3>
                        <div className="mono" style={{ color: 'var(--amber)', fontSize: '0.78rem' }}>
                          {rec.variety}
                        </div>
                      </div>
                      <button
                        onClick={() => handleSpeakCard(rec, idx)}
                        style={{
                          width: '34px',
                          height: '34px',
                          borderRadius: '50%',
                          background: activeSpeechIdx === idx && isSpeaking ? 'var(--amber)' : 'rgba(240, 168, 58, 0.15)',
                          color: activeSpeechIdx === idx && isSpeaking ? 'var(--char)' : 'var(--amber)',
                          border: 'none',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          cursor: 'pointer',
                          flexShrink: 0
                        }}
                        title={t('listenRecommendationTitle')}
                      >
                        {activeSpeechIdx === idx && isSpeaking ? <Square size={14} fill="currentColor" /> : <Volume2 size={16} />}
                      </button>
                    </div>

                    {/* Quick Specs */}
                    <div style={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.45rem',
                      background: 'var(--char-input)',
                      padding: '0.85rem',
                      borderRadius: 'var(--radius-sm)',
                      marginBottom: '1rem',
                      fontSize: '0.82rem'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--cream)' }}>
                        <Clock size={14} style={{ color: 'var(--amber)' }} />
                        <span><strong>{t('duration')}:</strong> {localizeCropAdvice(rec.duration_days, language)}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--cream)' }}>
                        <Droplets size={14} style={{ color: '#38bdf8' }} />
                        <span><strong>{t('waterReq')}:</strong> {localizeCropAdvice(rec.water_requirement, language)}</span>
                      </div>
                    </div>

                    {/* Soil Suitability Rationale */}
                    <div style={{ marginBottom: '0.85rem' }}>
                      <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                        {t('soilRationale')}
                      </div>
                      <p style={{ fontSize: '0.85rem', color: 'var(--cream)', lineHeight: 1.5 }}>
                        {localizeCropAdvice(rec.soil_suitability, language)}
                      </p>
                    </div>

                    {/* Limitations & Risks */}
                    <div style={{ marginBottom: '0.85rem', background: 'rgba(248, 113, 113, 0.08)', padding: '0.75rem', borderRadius: 'var(--radius-sm)', border: '1px solid rgba(248, 113, 113, 0.2)' }}>
                      <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#f87171', display: 'flex', alignItems: 'center', gap: '0.3rem', marginBottom: '0.2rem' }}>
                        <AlertCircle size={13} />
                        <span>{t('limitations')}</span>
                      </div>
                      <p style={{ fontSize: '0.82rem', color: 'var(--cream)', lineHeight: 1.4 }}>
                        {localizeCropAdvice(rec.limitations, language)}
                      </p>
                    </div>

                    {/* Practical Next Steps */}
                    <div>
                      <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#a3e635', marginBottom: '0.2rem' }}>
                        {t('nextSteps')}
                      </div>
                      <p style={{ fontSize: '0.84rem', color: 'var(--cream)', lineHeight: 1.4 }}>
                        {localizeCropAdvice(rec.next_steps, language)}
                      </p>
                    </div>
                  </div>

                  {/* Official Citation Footer */}
                  <div style={{
                    paddingTop: '0.8rem',
                    borderTop: '1px solid var(--border-card)',
                    fontSize: '0.72rem',
                    color: 'var(--text-dim)',
                    lineHeight: 1.4
                  }}>
                    <BookOpen size={12} style={{ display: 'inline', marginRight: '4px', verticalAlign: 'middle', color: 'var(--amber)' }} />
                    <span>{t('demoAttributionPrefix')} {rec.citation.split(': ').slice(1).join(': ')}</span>
                  </div>
                </div>
              ))}
            </div>
            )}

            {/* Disclaimer on No Fabricated Yields */}
            <div style={{
              background: 'rgba(28, 30, 20, 0.6)',
              border: '1px solid var(--border-card)',
              borderRadius: 'var(--radius-md)',
              padding: '1.2rem',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '0.8rem',
              color: 'var(--text-muted)',
              fontSize: '0.82rem',
              lineHeight: 1.5
            }}>
              <ShieldCheck size={20} style={{ color: 'var(--amber)', flexShrink: 0, marginTop: '2px' }} />
              <div>
                {t('cropDemoDisclaimer')}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

