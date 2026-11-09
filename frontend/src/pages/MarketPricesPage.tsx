import React, { useState, useEffect, useRef } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { useFarmProfile } from '../context/FarmProfileContext';
import { useAssistant } from '../context/AssistantContext';
import { localizeCropName, localizeLocation } from '../i18n/agriculture';
import { FarmLocationFields } from '../components/FarmLocationFields';
import { getState, isDistrictInState, type GeolocationResult } from '../services/geography';
import { Search, MapPin, ShieldCheck, Volume2, Square, ArrowLeft, Bot, AlertCircle } from 'lucide-react';

interface MandiRecord {
  commodity: string;
  variety?: string | null;
  grade?: string | null;
  market?: string | null;
  district: string;
  state: string;
  min_price_per_kg?: number | null;
  max_price_per_kg?: number | null;
  modal_price_per_kg?: number | null;
  currency: 'INR';
  unit: string;
  data_type: 'illustrative';
  disclaimer: string;
  record_date?: string | null;
  freshness?: 'illustrative';
  source: string;
  source_url?: string | null;
  retrieved_at?: string | null;
  reported_unit: string;
  state_code?: string;
  district_code?: string;
}

interface MarketPriceResponse {
  records: MandiRecord[];
  total_count: number;
  disclaimer: string;
  last_updated: string;
  data_provenance?: string;
  is_live_api?: boolean;
  data_type?: 'illustrative';
  retrieved_at?: string | null;
  source_url?: string | null;
  related_source_url?: string | null;
}

interface MarketPricesPageProps {
  onNavigate?: (tab: string) => void;
}

export const MarketPricesPage: React.FC<MarketPricesPageProps> = ({ onNavigate }) => {
  const { t, language } = useLanguage();
  const { profile, profileLoaded } = useFarmProfile();
  const { speakText, stopSpeaking, isSpeaking } = useAssistant();

  const [searchCommodity, setSearchCommodity] = useState(profile.selectedCommodity || '');
  const [commodities, setCommodities] = useState<string[]>([]);
  const [selectedState, setSelectedState] = useState(() => getState(profile.state)?.name || 'All');
  const [selectedDistrict, setSelectedDistrict] = useState(() => profile.state && isDistrictInState(profile.district, profile.state) ? profile.district : 'All');
  const [results, setResults] = useState<MarketPriceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeSpeechIdx, setActiveSpeechIdx] = useState<number | null>(null);
  const requestId = useRef(0);
  const activeRequest = useRef<AbortController | null>(null);
  const previousLanguage = useRef(language);

  useEffect(() => {
    let active = true;
    fetch('/api/market-prices/commodities', { credentials: 'same-origin' })
      .then((response) => response.ok ? response.json() : null)
      .then((data) => { if (active && Array.isArray(data?.commodities)) setCommodities(data.commodities); })
      .catch(() => { /* Search remains usable if the catalogue request fails. */ });
    return () => { active = false; };
  }, []);

  const fetchPrices = async (commOverride?: string, stateOverride?: string, distOverride?: string) => {
    const comm = commOverride !== undefined ? commOverride : searchCommodity;
    const st = stateOverride !== undefined ? stateOverride : selectedState;
    const dist = distOverride !== undefined ? distOverride : selectedDistrict;
    const request = ++requestId.current;
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      const params = new URLSearchParams();
      if (comm.trim()) params.append('commodity', comm.trim());
      if (st !== 'All') params.append('state', st);
      if (dist !== 'All') params.append('district', dist);
      params.append('language', language);

      const res = await fetch(`/api/market-prices/search?${params.toString()}`, { signal: controller.signal, credentials: 'same-origin' });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        const code = body?.detail?.code;
        const message = code === 'invalid_input' ? t('marketCommodityRequired')
            : res.status >= 500 ? t('marketServiceUnavailable') : t('marketRequestFailed');
        throw new Error(message);
      }
      const data: MarketPriceResponse = await res.json();
      if (request !== requestId.current) return;
      setResults(data);
    } catch (err: any) {
      if (controller.signal.aborted || request !== requestId.current) return;
      console.error('Market price search error:', err);
      setError(err?.message || t('marketServiceUnavailable'));
    } finally {
      if (request === requestId.current) setLoading(false);
    }
  };

  useEffect(() => {
    if (!profileLoaded) return;
    // Only restore a location when the saved profile contains a valid
    // state-district pair. Never infer a state from a district alone.
    const nextState = getState(profile.state)?.name || 'All';
    const nextDistrict = profile.district && nextState !== 'All' && isDistrictInState(profile.district, nextState) ? profile.district : 'All';
    const nextCommodity = profile.selectedCommodity || '';
    setSelectedState(nextState);
    setSelectedDistrict(nextDistrict);
    setSearchCommodity(nextCommodity);
    if (nextCommodity.trim()) fetchPrices(nextCommodity, nextState, nextDistrict);
    else { setResults(null); setError(null); }
  }, [profileLoaded]);

  useEffect(() => {
    if (previousLanguage.current === language) return;
    previousLanguage.current = language;
    if (profileLoaded) fetchPrices(searchCommodity, selectedState, selectedDistrict);
  }, [language, profileLoaded]);

  useEffect(() => () => {
    requestId.current += 1;
    activeRequest.current?.abort();
  }, []);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchCommodity.trim()) { setError(t('marketCommodityRequired')); return; }
    fetchPrices();
  };

  const handleCurrentLocation = (result: GeolocationResult) => {
    activeRequest.current?.abort();
    requestId.current += 1;
    setLoading(false);
    setResults(null);
    setError(null);
    if (!result.success || !result.state || !result.district) {
      // A failed location lookup must not leave a prior market appearing to
      // represent the current location. Ask the farmer to select manually.
      setSelectedState('All');
      setSelectedDistrict('All');
      return;
    }
    setSelectedState(result.state.name);
    setSelectedDistrict(result.district.name);
    if (searchCommodity.trim()) fetchPrices(searchCommodity, result.state.name, result.district.name);
  };

  const handleSpeakPrice = (rec: MandiRecord, idx: number) => {
    if (activeSpeechIdx === idx && isSpeaking) {
      stopSpeaking();
      setActiveSpeechIdx(null);
    } else {
      setActiveSpeechIdx(idx);
      const price = rec.modal_price_per_kg == null ? 'No modal price was provided.' : `Modal price is ${rec.modal_price_per_kg} rupees per kilogram.`;
      const speech = `${rec.commodity}, ${rec.district}, ${rec.state}: ${price} DEMO DATA, illustrative reference only, not a reported market price.`;
      speakText(speech);
    }
  };

  const formatPricePerKg = (value: number | null | undefined) => value == null
    ? t('marketPriceUnavailable')
    : `₹${value.toLocaleString('en-IN', { maximumFractionDigits: 2 })}/kg`;

  const quickCommodityPills = ['Chilli', 'Cotton', 'Tomato', 'Paddy', 'Groundnut', 'Bengal Gram', 'Onion', 'Soybean'];

  return (
    <div className="module-page market-prices-page" style={{ paddingTop: '5.5rem', paddingBottom: '5rem' }}>
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
                onClick={() => fetchPrices()}
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
            <span className="badge">{t('module4Badge')}</span>
            <span className="mono" style={{ color: 'var(--amber)', fontSize: '0.8rem' }}>{t('marketSourceBanner')}</span>
          </div>
          <h1 style={{ fontSize: 'clamp(1.8rem, 4vw, 2.6rem)', marginBottom: '0.6rem' }}>
            {t('marketTitle')}
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '1rem', maxWidth: '720px' }}>
            {t('marketSub')}
          </p>
        </div>

        <div role="note" className="card" style={{ marginBottom: '1.2rem', padding: '1rem 1.2rem' }}>
          <strong style={{ display: 'block', marginBottom: '.45rem', color: 'var(--amber)' }}>{t('marketIllustrativeLabel')}</strong>
          <p style={{ color: 'var(--text-muted)', fontSize: '.88rem', lineHeight: 1.5, margin: 0 }}>{t('marketIllustrativeDisclosure')}</p>
        </div>

        {/* Search & Filter Bar */}
        <div className="card" style={{ marginBottom: '2.5rem' }}>
          <form onSubmit={handleSearchSubmit}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1.2rem' }}>
              {/* Search input */}
              <div className="input-group" style={{ marginBottom: 0 }}>
                <label className="input-label">{t('searchCommodity')}</label>
                <div style={{ position: 'relative' }}>
                  <Search size={16} style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                  <input
                    type="text"
                    list="market-commodity-options"
                    className="input-field"
                    style={{ paddingLeft: '2.5rem' }}
                    value={searchCommodity}
                    onChange={(e) => {
                      activeRequest.current?.abort();
                      requestId.current += 1;
                      setLoading(false);
                      setResults(null);
                      setError(null);
                      setSearchCommodity(e.target.value);
                    }}
                    placeholder={t('commodityPlaceholder')}
                  />
                  <datalist id="market-commodity-options">
                    {commodities.map((commodity) => <option key={commodity} value={commodity} />)}
                  </datalist>
                </div>
              </div>

              <FarmLocationFields
                state={selectedState}
                district={selectedDistrict}
                includeAll
                layout="inline"
                onCurrentLocation={handleCurrentLocation}
                onChange={(nextState, nextDistrict) => {
                  activeRequest.current?.abort();
                  requestId.current += 1;
                  setLoading(false);
                  setResults(null);
                  setError(null);
                  setSelectedState(nextState);
                  const canonicalDistrict = nextDistrict || (nextState === 'All' ? 'All' : '');
                  setSelectedDistrict(canonicalDistrict);
                  // A newly selected district is a new query. Fetch it
                  // immediately with the selected canonical state/district
                  // instead of leaving the page looking as if the old result
                  // still represents the new location.
                  if (searchCommodity.trim() && canonicalDistrict && canonicalDistrict !== 'All') {
                    fetchPrices(searchCommodity, nextState, canonicalDistrict);
                  }
                }}
              />
            </div>

            {/* Quick Commodity Filter Pills */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
              <span className="mono" style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>{t('popular')}</span>
              {quickCommodityPills.map((comm) => (
                <button
                  key={comm}
                  type="button"
                  onClick={() => {
                    setSearchCommodity(comm);
                    fetchPrices(comm, selectedState, selectedDistrict);
                  }}
                  style={{
                    background: searchCommodity.toLowerCase() === comm.toLowerCase() ? 'var(--amber)' : 'rgba(244, 236, 216, 0.06)',
                    color: searchCommodity.toLowerCase() === comm.toLowerCase() ? 'var(--char)' : 'var(--cream)',
                    border: '1px solid var(--border-card)',
                    padding: '0.25rem 0.65rem',
                    borderRadius: 'var(--radius-full)',
                    fontSize: '0.76rem',
                    cursor: 'pointer',
                    fontWeight: 600
                  }}
                >
                  {localizeCropName(comm, language)}
                </button>
              ))}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.8rem' }}>
              <button
                type="button"
                onClick={() => {
                  activeRequest.current?.abort();
                  requestId.current += 1;
                  setSearchCommodity('');
                  setSelectedState('All');
                  setSelectedDistrict('All');
                  fetchPrices('', 'All', 'All');
                }}
                className="btn btn-secondary"
                style={{ padding: '0.65rem 1.2rem' }}
              >
                {t('marketReset')}
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                style={{ padding: '0.65rem 1.6rem' }}
                disabled={loading}
              >
                <Search size={16} />
                <span>{loading ? t('marketSearching') : t('marketSearch')}</span>
              </button>
            </div>
          </form>
        </div>

        {/* Mandi Price Records Table / Cards */}
        {results && (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.2rem', flexWrap: 'wrap', gap: '0.8rem' }}>
              <div style={{ fontSize: '1.2rem', fontWeight: 800 }}>
                {results.total_count} {t('marketRecordCount')}
              </div>
              <div className="mono" style={{ fontSize: '0.75rem', color: 'var(--amber)' }}>
                {t('marketDatasetLabel')}
              </div>
            </div>

            {results.records.length === 0 ? (
              <div className="card" style={{ padding: '2rem', marginBottom: '2.5rem', border: '1px solid var(--border-subtle)' }}>
                <div style={{ textAlign: 'center', maxWidth: '700px', margin: '0 auto' }}>
                  <ShieldCheck size={40} style={{ color: 'var(--amber)', margin: '0 auto 1rem' }} />
                  <h3 style={{ fontSize: '1.25rem', marginBottom: '0.6rem', color: 'var(--cream)' }}>{t('marketNoResults')}</h3>
                  <p style={{ color: 'var(--text-muted)', lineHeight: 1.6, fontSize: '0.92rem' }}>{results.disclaimer}</p>
                  {onNavigate && <button onClick={() => onNavigate('ask-kisan')} className="btn btn-secondary" style={{ fontSize: '0.9rem', padding: '0.65rem 1.4rem' }}><Bot size={16} /><span>{t('askAssistantMandi')}</span></button>}
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '2.5rem' }}>
                {results.records.map((rec, idx) => (
                  <div
                    key={`${rec.state_code}:${rec.district_code}:${rec.commodity}:${rec.variety || ''}`}
                    className="card card-highlight"
                    style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '1.5rem',
                      padding: '1.4rem 1.6rem'
                    }}
                  >
                    {/* Left: Commodity & Mandi */}
                    <div style={{ minWidth: '240px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.3rem' }}>
                        <span style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--cream)' }}>
                          {localizeCropName(rec.commodity, language)}
                        </span>
                        {rec.variety && <span className="mono" style={{ background: 'rgba(240, 168, 58, 0.15)', color: 'var(--amber)', padding: '0.15rem 0.5rem', borderRadius: 'var(--radius-sm)', fontSize: '0.72rem' }}>{rec.variety}</span>}
                        {rec.grade && <span className="mono" style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>{rec.grade}</span>}
                        <span className="mono" style={{ color: 'var(--amber)', fontSize: '0.68rem', fontWeight: 800 }}>{t('marketIllustrativeLabel')}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-muted)', fontSize: '0.88rem' }}>
                        <MapPin size={14} style={{ color: 'var(--amber)' }} />
                        <span>{t('marketDistrictReference')}: {localizeLocation(rec.district, language)}, {localizeLocation(rec.state, language)}</span>
                      </div>
                      <div style={{ fontSize: '.75rem', color: 'var(--text-muted)', marginTop: '.4rem' }}>{t('marketUnitLabel')}: ₹/kg</div>
                      {rec.variety && <div style={{ fontSize: '.75rem', color: 'var(--text-muted)', marginTop: '.25rem' }}>{t('marketVarietyLabel')}: {rec.variety}</div>}
                    </div>

                    {/* Middle: Prices & Unit */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', flexWrap: 'wrap' }}>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{t('modalPrice')}</div>
                        <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--amber)', lineHeight: 1.1 }}>
                          {formatPricePerKg(rec.modal_price_per_kg)}
                        </div>
                      </div>

                      <div style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '0.2rem',
                        paddingLeft: '1.2rem',
                        borderLeft: '1px solid var(--border-card)',
                        fontSize: '0.8rem'
                      }}>
                        <div style={{ color: 'var(--text-muted)' }}>
                          {t('minPrice')}: <strong style={{ color: 'var(--cream)' }}>{formatPricePerKg(rec.min_price_per_kg)}</strong>
                        </div>
                        <div style={{ color: 'var(--text-muted)' }}>
                          {t('maxPrice')}: <strong style={{ color: 'var(--cream)' }}>{formatPricePerKg(rec.max_price_per_kg)}</strong>
                        </div>
                      </div>

                      {/* Audio Button */}
                      <button
                        onClick={() => handleSpeakPrice(rec, idx)}
                        style={{
                          width: '38px',
                          height: '38px',
                          borderRadius: '50%',
                          background: activeSpeechIdx === idx && isSpeaking ? 'var(--amber)' : 'rgba(240, 168, 58, 0.12)',
                          color: activeSpeechIdx === idx && isSpeaking ? 'var(--char)' : 'var(--amber)',
                          border: 'none',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          cursor: 'pointer',
                          flexShrink: 0
                        }}
                        title={t('listenRecommendationTitle')}
                        aria-label={`${t('marketListenPriceLabel')} ${localizeCropName(rec.commodity, language)}: ${formatPricePerKg(rec.modal_price_per_kg)}`}
                      >
                        {activeSpeechIdx === idx && isSpeaking ? <Square size={16} fill="currentColor" /> : <Volume2 size={18} />}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Disclaimer */}
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
                {results.disclaimer}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

