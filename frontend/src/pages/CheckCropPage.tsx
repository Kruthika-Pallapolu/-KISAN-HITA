import React, { useState, useEffect, useRef } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { useFarmProfile } from '../context/FarmProfileContext';
import { useAssistant } from '../context/AssistantContext';
import { ShieldAlert, Camera, Upload, Trash2, RefreshCw, CheckCircle2, AlertTriangle, PhoneCall, Volume2, Square, Info, Sparkles, ArrowLeft } from 'lucide-react';
import { localizeCropName } from '../i18n/agriculture';
import { cropHealthText as cht } from '../i18n/cropHealth';

interface CropHealthResult {
  crop_name: string;
  reported_symptoms: string;
  cautious_assessment: string;
  potential_factors: string[];
  cultural_management_steps: string[];
  safety_notice: string;
  extension_contact: string;
  has_image: boolean;
  diagnostic_disclaimer: string;
  ai_observations?: string;
}

interface CheckCropPageProps {
  onNavigate?: (tab: string) => void;
}

export const CheckCropPage: React.FC<CheckCropPageProps> = ({ onNavigate }) => {
  const { t, language } = useLanguage();
  const { profile } = useFarmProfile();
  const { speakText, stopSpeaking, isSpeaking } = useAssistant();

  const [cropName, setCropName] = useState(profile.selectedCropHealthName || 'Cotton');
  const [symptoms, setSymptoms] = useState(profile.selectedSymptoms || '');
  const [onsetDays, setOnsetDays] = useState('2-3 days ago');
  const [affectedSpread, setAffectedSpread] = useState('Few scattered plants');
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<CropHealthResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const lastDiagnosis = useRef<{ crop_name: string; symptoms: string; onset_days: string; affected_spread: string; image_base64: string | null } | null>(null);
  const lastLanguage = useRef(language);

  useEffect(() => {
    if (profile.selectedCropHealthName && profile.selectedCropHealthName !== cropName) {
      setCropName(profile.selectedCropHealthName);
    }
    if (profile.selectedSymptoms && profile.selectedSymptoms !== symptoms) {
      setSymptoms(profile.selectedSymptoms);
    }
  }, [profile.selectedCropHealthName, profile.selectedSymptoms]);

  // Refresh an existing report in the newly selected language, keeping the same
  // canonical crop and farmer-entered observations.
  useEffect(() => {
    if (lastLanguage.current === language) return;
    lastLanguage.current = language;
    const previous = lastDiagnosis.current;
    if (!previous) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch('/api/crop-health/diagnose', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          // Rebuild the language-aware textual report without resending an
          // image or triggering a second paid/remote vision analysis.
          body: JSON.stringify({ ...previous, image_base64: null, language }),
        });
        if (!res.ok) return;
        const localized: CropHealthResult = await res.json();
        if (!cancelled) setReport({ ...localized, has_image: Boolean(previous.image_base64), ai_observations: undefined });
      } catch { /* Keep the last valid assessment if refresh is unavailable. */ }
    })();
    return () => { cancelled = true; };
  }, [language]);

  const quickSymptoms = ['lower', 'wilt', 'curl', 'stem', 'spots'];

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate size (< 10MB)
    if (file.size > 10 * 1024 * 1024) {
      alert(cht('invalidSize', language));
      return;
    }

    const reader = new FileReader();
    reader.onloadend = () => {
      setImagePreview(reader.result as string);
    };
    reader.readAsDataURL(file);
  };

  const handleRemoveImage = () => {
    setImagePreview(null);
  };

  const handleDiagnose = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!symptoms.trim()) {
      alert(cht('describe', language));
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const request = {
        crop_name: cropName,
        symptoms,
        onset_days: onsetDays,
        affected_spread: affectedSpread,
        image_base64: imagePreview,
      };
      lastDiagnosis.current = request;
      const res = await fetch('/api/crop-health/diagnose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...request,
          language,
        }),
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        const detailMsg = Array.isArray(errJson?.detail)
          ? errJson.detail.map((d: any) => d.msg).join(', ')
          : (errJson?.detail || `Server returned HTTP ${res.status}`);
        throw new Error(detailMsg);
      }
      const data: CropHealthResult = await res.json();
      setReport(data);
    } catch (err: any) {
      console.error('Crop health evaluation error:', err);
      setError(err instanceof TypeError ? cht('failed', language) : (err?.message || cht('failed', language)));
    } finally {
      setLoading(false);
    }
  };

  const handleSpeakReport = () => {
    if (!report) return;
    if (isSpeaking) {
      stopSpeaking();
    } else {
      const text = `${localizeCropName(report.crop_name, language)}. ${report.cautious_assessment}. ${report.safety_notice} ${report.extension_contact}`;
      speakText(text);
    }
  };

  return (
    <div className="module-page crop-health-page" style={{ paddingTop: '5.5rem', paddingBottom: '5rem' }}>
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

        {/* Header */}
        <div style={{ marginBottom: '2rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.6rem' }}>
            <span className="badge">{t('module3Badge')}</span>
            <span className="mono" style={{ color: 'var(--amber)', fontSize: '0.8rem' }}>{cht('assessment', language)}</span>
          </div>
          <h1 style={{ fontSize: 'clamp(1.8rem, 4vw, 2.6rem)', marginBottom: '0.6rem' }}>
            {t('cropHealthTitle')}
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '1rem', maxWidth: '720px' }}>
            {t('cropHealthSub')}
          </p>
        </div>

        {/* Error Alert Banner */}
        {error && (
          <div className="card" style={{ marginBottom: '1.5rem', border: '1px solid rgba(248, 113, 113, 0.4)', background: 'rgba(248, 113, 113, 0.1)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
              <AlertTriangle size={20} style={{ color: '#f87171', flexShrink: 0 }} />
              <span style={{ color: '#f87171', fontSize: '0.92rem' }}>{error}</span>
            </div>
          </div>
        )}

        {/* Diagnostic Form */}
        <div className="grid-2" style={{ marginBottom: '2.5rem' }}>
          {/* Left Form: Crop & Symptoms */}
          <div className="card">
            <form onSubmit={handleDiagnose}>
              <div className="input-group">
                <label className="input-label">{t('selectCrop')}</label>
                <select className="select-field" value={cropName} onChange={(e) => setCropName(e.target.value)}>
                  {['Cotton', 'Chilli', 'Tomato', 'Paddy', 'Groundnut', 'Bengal Gram', 'Maize', 'Soybean', 'Onion', 'Red Gram'].map((crop) => <option key={crop} value={crop}>{localizeCropName(crop, language)}</option>)}
                </select>
              </div>

              {/* Quick Symptom Prompts */}
              <div style={{ marginBottom: '1rem' }}>
                <label className="input-label" style={{ marginBottom: '0.5rem', display: 'block' }}>
                  {cht('quickPrompts', language)}
                </label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.45rem' }}>
                  {quickSymptoms.map((qs, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => setSymptoms(cht(qs, language))}
                      style={{
                        background: symptoms === qs ? 'rgba(240, 168, 58, 0.2)' : 'var(--char-input)',
                        border: `1px solid ${symptoms === qs ? 'var(--amber)' : 'var(--border-card)'}`,
                        color: symptoms === qs ? 'var(--amber)' : 'var(--text-muted)',
                        padding: '0.35rem 0.7rem',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '0.78rem',
                        cursor: 'pointer',
                        textAlign: 'left'
                      }}
                    >
                      {cht(qs, language)}
                    </button>
                  ))}
                </div>
              </div>

              {/* Symptoms Description Field */}
              <div className="input-group">
                <label className="input-label">{t('describeSymptoms')}</label>
                <textarea
                  className="textarea-field"
                  rows={3}
                  value={symptoms}
                  onChange={(e) => setSymptoms(e.target.value)}
                  placeholder={t('symptomPlaceholder')}
                  required
                />
              </div>

              {/* Onset and Spread */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="input-group">
                  <label className="input-label">{t('onsetDays')}</label>
                  <select className="select-field" value={onsetDays} onChange={(e) => setOnsetDays(e.target.value)}>
                    <option value="Notice today">{cht('today', language)}</option>
                    <option value="2-3 days ago">{cht('days23', language)}</option>
                    <option value="1 week ago">{cht('week', language)}</option>
                    <option value="More than 2 weeks">{cht('weeks2', language)}</option>
                  </select>
                </div>

                <div className="input-group">
                  <label className="input-label">{t('spreadArea')}</label>
                  <select className="select-field" value={affectedSpread} onChange={(e) => setAffectedSpread(e.target.value)}>
                    <option value="Few scattered plants">{cht('few', language)}</option>
                    <option value="One specific patch / low spot">{cht('patch', language)}</option>
                    <option value="Entire field border">{cht('border', language)}</option>
                    <option value="Widespread across entire plot">{cht('wide', language)}</option>
                  </select>
                </div>
              </div>

              <div style={{ marginTop: '0.5rem' }}>
                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{ width: '100%', padding: '0.85rem' }}
                  disabled={loading}
                >
                  <ShieldAlert size={18} />
                  <span>{loading ? cht('analyzing', language) : t('diagnoseHealth')}</span>
                </button>
              </div>
            </form>
          </div>

          {/* Right: Photo Upload & Camera Area */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                <Camera size={20} style={{ color: 'var(--amber)' }} />
                <h3 style={{ fontSize: '1.2rem' }}>{t('uploadPhoto')}</h3>
              </div>

              {imagePreview ? (
                <div style={{ position: 'relative', borderRadius: 'var(--radius-md)', overflow: 'hidden', border: '1px solid var(--border-subtle)', background: 'var(--char-input)' }}>
                  <img
                    src={imagePreview}
                      alt={cht('attached', language)}
                    style={{ width: '100%', maxHeight: '260px', objectFit: 'cover', display: 'block' }}
                  />
                  <div style={{
                    position: 'absolute',
                    top: '0.6rem',
                    right: '0.6rem',
                    display: 'flex',
                    gap: '0.5rem'
                  }}>
                    <button
                      onClick={handleRemoveImage}
                      style={{
                        background: 'rgba(239, 68, 68, 0.85)',
                        border: 'none',
                        color: 'white',
                        padding: '0.4rem',
                        borderRadius: '50%',
                        cursor: 'pointer'
                      }}
                      title={cht('remove', language)}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                  <div style={{ padding: '0.6rem 0.8rem', background: 'rgba(22, 23, 15, 0.9)', fontSize: '0.78rem', color: '#4ade80', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <CheckCircle2 size={14} />
                    <span>{cht('attached', language)}</span>
                  </div>
                </div>
              ) : (
                <label style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.8rem',
                  padding: '2.5rem 1.5rem',
                  border: '2px dashed var(--border-card)',
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--char-input)',
                  cursor: 'pointer',
                  textAlign: 'center',
                  transition: 'border-color 0.2s'
                }}>
                  <div style={{
                    width: '52px',
                    height: '52px',
                    borderRadius: '50%',
                    background: 'rgba(240, 168, 58, 0.12)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'var(--amber)'
                  }}>
                    <Upload size={24} />
                  </div>
                  <div>
                    <div style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--cream)', marginBottom: '0.2rem' }}>
                      {cht('takeUpload', language)}
                    </div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                      {cht('fileTypes', language)}
                    </div>
                  </div>
                  <input
                    type="file"
                    accept="image/*"
                    capture="environment"
                    onChange={handleImageUpload}
                    style={{ display: 'none' }}
                  />
                </label>
              )}
            </div>

            {/* Safety Caution Banner */}
            <div style={{
              marginTop: '1.2rem',
              background: 'rgba(240, 168, 58, 0.08)',
              border: '1px solid rgba(240, 168, 58, 0.25)',
              borderRadius: 'var(--radius-md)',
              padding: '0.9rem',
              display: 'flex',
              gap: '0.6rem',
              alignItems: 'flex-start'
            }}>
              <Info size={18} style={{ color: 'var(--amber)', flexShrink: 0, marginTop: '2px' }} />
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
                {t('safetyNotice')}
              </p>
            </div>
          </div>
        </div>

        {/* Diagnosis / Appraisal Report */}
        {report && (
          <div className="card card-highlight" style={{ marginBottom: '2rem', padding: '2rem', borderTop: '3px solid var(--amber)' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', marginBottom: '1.5rem' }}>
              <div>
                <span className="mono" style={{ color: 'var(--amber)', fontSize: '0.8rem', textTransform: 'uppercase' }}>
                  {cht('assessment', language)}
                </span>
                <h2 style={{ fontSize: '1.6rem', marginTop: '0.2rem' }}>
                  {localizeCropName(report.crop_name, language)} • {cht('visibleStress', language)}
                </h2>
              </div>

              <button
                onClick={handleSpeakReport}
                className={`btn ${isSpeaking ? 'btn-outline' : 'btn-primary'}`}
                style={{ padding: '0.55rem 1.2rem' }}
              >
                {isSpeaking ? (
                  <>
                    <Square size={16} fill="currentColor" />
                    <span>{t('stopAudio')}</span>
                  </>
                ) : (
                  <>
                    <Volume2 size={16} />
                    <span>{cht('listenReport', language)}</span>
                  </>
                )}
              </button>
            </div>

            {/* Assessment Text */}
            <div style={{ background: 'var(--char-input)', padding: '1.2rem', borderRadius: 'var(--radius-md)', marginBottom: '1.5rem', border: '1px solid var(--border-card)' }}>
              <p style={{ fontSize: '0.94rem', color: 'var(--cream)', lineHeight: 1.6 }}>
                {report.cautious_assessment}
              </p>
            </div>

            {/* AI Vision Observations (if generated by Gemini) */}
            {report.ai_observations && (
              <div style={{
                background: 'rgba(240, 168, 58, 0.08)',
                border: '1px solid rgba(240, 168, 58, 0.3)',
                padding: '1.2rem',
                borderRadius: 'var(--radius-md)',
                marginBottom: '1.5rem'
              }}>
                <h4 style={{ fontSize: '0.92rem', color: 'var(--amber)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Sparkles size={16} />
                  <span>{cht('vision', language)}</span>
                </h4>
                <p style={{ fontSize: '0.9rem', color: 'var(--cream)', lineHeight: 1.6, whiteSpace: 'pre-line' }}>
                  {report.ai_observations}
                </p>
              </div>
            )}

            {/* Potential Factors & Non-chemical Cultural Management */}
            <div className="grid-2" style={{ marginBottom: '1.5rem' }}>
              <div style={{ background: 'rgba(22, 23, 15, 0.7)', padding: '1.2rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-card)' }}>
                <h4 style={{ fontSize: '0.92rem', color: 'var(--amber)', marginBottom: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <AlertTriangle size={16} />
                  <span>{cht('factors', language)}</span>
                </h4>
                <ul style={{ paddingLeft: '1.2rem', fontSize: '0.88rem', color: 'var(--cream)', lineHeight: 1.6 }}>
                  {report.potential_factors.map((f, i) => (
                    <li key={i} style={{ marginBottom: '0.4rem' }}>{f}</li>
                  ))}
                </ul>
              </div>

              <div style={{ background: 'rgba(47, 58, 28, 0.4)', padding: '1.2rem', borderRadius: 'var(--radius-md)', border: '1px solid rgba(163, 230, 53, 0.25)' }}>
                <h4 style={{ fontSize: '0.92rem', color: '#a3e635', marginBottom: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <CheckCircle2 size={16} />
                  <span>{cht('management', language)}</span>
                </h4>
                <ul style={{ paddingLeft: '1.2rem', fontSize: '0.88rem', color: 'var(--cream)', lineHeight: 1.6 }}>
                  {report.cultural_management_steps.map((m, i) => (
                    <li key={i} style={{ marginBottom: '0.4rem' }}>{m}</li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Expert Extension Support Hotline */}
            <div style={{
              background: 'linear-gradient(135deg, rgba(240, 168, 58, 0.15), rgba(47, 58, 28, 0.3))',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              padding: '1.2rem',
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '1rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
                <div style={{
                  width: '40px',
                  height: '40px',
                  borderRadius: '50%',
                  background: 'var(--amber)',
                  color: 'var(--char)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <PhoneCall size={20} />
                </div>
                <div>
                  <div style={{ fontSize: '0.9rem', fontWeight: 800, color: 'var(--cream)' }}>
                    {cht('contact', language)}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    {report.extension_contact}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

