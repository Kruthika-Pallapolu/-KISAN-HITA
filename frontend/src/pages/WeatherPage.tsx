import React, { useState, useEffect, useRef } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { useFarmProfile } from '../context/FarmProfileContext';
import { useAssistant } from '../context/AssistantContext';
import { localizeLocation, localizeWeatherCondition } from '../i18n/agriculture';
import { FarmLocationFields } from '../components/FarmLocationFields';
import { getState, isDistrictInState, type GeolocationResult } from '../services/geography';
import { CloudSun, Droplets, Wind, CloudRain, Shield, AlertTriangle, Volume2, Square, RefreshCw, MapPin, ArrowLeft } from 'lucide-react';

interface WeatherDay {
  day_name: string;
  date: string;
  temp_max: number;
  temp_min: number;
  condition: string;
  precipitation_probability: number;
  icon: string;
}

interface WeatherResponse {
  district: string;
  state: string;
  temperature: number;
  feels_like?: number;
  condition: string;
  humidity: number;
  wind_speed: number;
  rain_probability: number;
  rainfall_mm?: number;
  advisory: string;
  irrigation_advice: string;
  spray_suitability: string;
  produce_protection: string;
  is_official_alert: boolean;
  source: string;
  forecast: WeatherDay[];
}

interface WeatherPageProps {
  onNavigate?: (tab: string) => void;
}

export const WeatherPage: React.FC<WeatherPageProps> = ({ onNavigate }) => {
  const { t, language } = useLanguage();
  const { profile, profileLoaded, updateProfile } = useFarmProfile();
  const { speakText, stopSpeaking, isSpeaking } = useAssistant();

  const [selectedState, setSelectedState] = useState('');
  const [selectedDistrict, setSelectedDistrict] = useState('');
  const [locationInitialized, setLocationInitialized] = useState(false);
  const [gpsCoordinates, setGpsCoordinates] = useState<{ latitude: number; longitude: number } | null>(null);
  const [weatherData, setWeatherData] = useState<WeatherResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);
  const activeRequest = useRef<AbortController | null>(null);
  const languageLocale: Record<string, string> = { en: 'en-IN', te: 'te-IN', hi: 'hi-IN', ta: 'ta-IN', kn: 'kn-IN', ml: 'ml-IN', mr: 'mr-IN' };
  const fetchWeather = async (district: string, state: string, coordinates?: { latitude: number; longitude: number } | null) => {
    if (!coordinates && (!state || !district || !isDistrictInState(district, state))) return;
    const request = ++requestId.current;
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setWeatherData(null);
    setLoading(true);
    setError(null);
    try {
      const res = coordinates
        ? await fetch('/api/weather/current/coordinates', {
            method: 'POST', signal: controller.signal, credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ latitude: coordinates.latitude, longitude: coordinates.longitude, language }),
          })
        : await fetch(`/api/weather/current?${new URLSearchParams({ district, state, language }).toString()}`, {
            signal: controller.signal, credentials: 'same-origin',
          });
      if (!res.ok) {
        let code = '';
        try {
          const payload = await res.clone().json();
          code = typeof payload?.detail === 'object' ? payload.detail.code || '' : '';
        } catch { /* Keep status-based fallback for older API responses. */ }
        const message = code === 'weather_coverage_unavailable'
          ? t('weatherCoverageUnavailable')
          : code === 'weather_geocoding_unavailable'
            ? t('weatherGeocodingUnavailable')
            : res.status === 503 || res.status >= 500
              ? t('weatherUnavailable')
              : res.status === 422
                ? t('weatherInvalidCombination')
                : t('weatherRequestFailed');
        throw new Error(message);
      }
      const data: WeatherResponse = await res.json();
      if (request !== requestId.current) return;
      setWeatherData(data);
    } catch (err: any) {
      if (controller.signal.aborted || request !== requestId.current) return;
      console.error('Weather fetch error:', err);
      setError(err instanceof Error ? err.message : t('weatherRequestFailed'));
    } finally {
      if (request === requestId.current) setLoading(false);
    }
  };

  useEffect(() => {
    if (!profileLoaded || !locationInitialized) return;
    if (gpsCoordinates) fetchWeather(selectedDistrict, selectedState, gpsCoordinates);
    else if (selectedDistrict && selectedState && isDistrictInState(selectedDistrict, selectedState)) fetchWeather(selectedDistrict, selectedState);
    else {
      activeRequest.current?.abort();
      requestId.current += 1;
      setWeatherData(null);
      setError(null);
      setLoading(false);
    }
  }, [profileLoaded, locationInitialized, selectedDistrict, selectedState, gpsCoordinates, language]);

  useEffect(() => () => {
    requestId.current += 1;
    activeRequest.current?.abort();
  }, []);

  useEffect(() => {
    if (!profileLoaded) return;
    const savedState = getState(profile.state)?.name || '';
    const savedDistrict = savedState && isDistrictInState(profile.district, savedState) ? profile.district : '';
    setSelectedState(savedState);
    setSelectedDistrict(savedDistrict);
    setLocationInitialized(true);
  }, [profileLoaded, profile.state, profile.district]);

  const handleLocationChange = (state: string, district: string) => {
    setWeatherData(null);
    setError(null);
    setGpsCoordinates(null);
    setSelectedState(state);
    setSelectedDistrict(district);
    updateProfile({ state, district });
  };

  const handleCurrentLocation = (result: GeolocationResult) => {
    if (!result.success || !result.state || !result.district || !result.coordinates) return;
    setWeatherData(null);
    setError(null);
    setSelectedState(result.state.name);
    setSelectedDistrict(result.district.name);
    setGpsCoordinates(result.coordinates);
    // GPS coordinates and GPS-derived location are intentionally not saved to
    // the account profile or guest session storage.
  };

  const handleHearAudio = () => {
    if (!weatherData) return;
    if (isSpeaking) {
      stopSpeaking();
    } else {
      const speech = `${weatherData.district}: ${weatherData.temperature} degrees, ${weatherData.condition}. Rain probability is ${weatherData.rain_probability} percent. ${weatherData.irrigation_advice} Spray suitability is ${weatherData.spray_suitability}.`;
      speakText(speech);
    }
  };

  return (
    <div className="module-page weather-page" style={{ paddingTop: '5.5rem', paddingBottom: '5rem' }}>
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

        {/* Header Title & Badge */}
        <div style={{ marginBottom: '2rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.6rem' }}>
            <span className="badge">{t('module1Badge')}</span>
            {weatherData && <span className="mono" style={{ color: 'var(--amber)', fontSize: '0.8rem' }}>{weatherData.source.includes('DEMO DATA') ? t('weatherDemoLabel') : t('weatherSourceLabel')}</span>}
          </div>
          <h1 style={{ fontSize: 'clamp(1.8rem, 4vw, 2.6rem)', marginBottom: '0.6rem' }}>
            {t('weatherTitle')}
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '1rem', maxWidth: '720px' }}>
            {t('weatherSub')}
          </p>
        </div>

        {/* District Selector & Audio Control Toolbar */}
        <div className="weather-location-toolbar" style={{
          background: 'var(--char-card)',
          border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)',
          padding: '1.2rem 1.6rem',
          marginBottom: '2rem',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1.2rem'
        }}>
          <div className="weather-location-controls" style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--amber)', fontWeight: 700 }}>
              <MapPin size={18} />
              <span>{t('districtSelect')}:</span>
            </div>
            <FarmLocationFields
              state={selectedState}
              district={selectedDistrict}
              layout="inline"
              onChange={handleLocationChange}
              onCurrentLocation={handleCurrentLocation}
              disabled={!profileLoaded || !locationInitialized}
            />
          </div>

          <div className="weather-location-actions" style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
            {/* Audio Button */}
            <button
              onClick={handleHearAudio}
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
                  <span>{t('hearAudio')}</span>
                </>
              )}
            </button>

            {/* Refresh */}
            <button
              onClick={() => selectedDistrict && fetchWeather(selectedDistrict, selectedState, gpsCoordinates)}
              className="btn btn-secondary"
              style={{ padding: '0.55rem 0.9rem' }}
              title={t('weatherRefresh')}
              disabled={!selectedDistrict || loading}
            >
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>
        </div>

        {/* Loading State */}
        {!profileLoaded && (
          <div role="status" className="card" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
            {t('weatherProfileLoading')}
          </div>
        )}

        {loading && !weatherData && profileLoaded && (
          <div style={{ textAlign: 'center', padding: '4rem 0' }}>
            <div className="mono" style={{ color: 'var(--amber)', fontSize: '1.1rem' }}>
              {t('weatherLoading')} {localizeLocation(selectedDistrict, language)}…
            </div>
          </div>
        )}

        {locationInitialized && !selectedDistrict && !loading && !weatherData && (
          <div role="status" className="card" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
            {t('weatherSelectLocation')}
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="weather-error-banner" style={{
            background: 'rgba(239, 68, 68, 0.12)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: 'var(--radius-md)',
            padding: '1.2rem',
            color: '#f87171',
            marginBottom: '2rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.8rem'
          }}>
            <AlertTriangle size={20} />
            <div style={{ flex: 1 }}>{error}</div>
            {selectedDistrict && <button type="button" className="btn btn-secondary" onClick={() => fetchWeather(selectedDistrict, selectedState)} disabled={loading}>{t('retry')}</button>}
          </div>
        )}

        {weatherData && (
          <>
            {/* Main Current Weather Card */}
            <div className="card card-highlight" style={{ marginBottom: '2rem', padding: '2rem' }}>
              <div className="weather-current-summary" style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '1.5rem', marginBottom: '1.5rem' }}>
                <div>
                  <div className="mono" style={{ color: 'var(--amber)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.3rem' }}>
                    {localizeLocation(weatherData.district, language)} {t('districtSelect')} • {localizeLocation(weatherData.state, language)}
                  </div>
                  <div className="weather-current-reading" style={{ display: 'flex', alignItems: 'baseline', gap: '0.8rem' }}>
                    <span style={{ fontSize: 'clamp(3rem, 7vw, 4.5rem)', fontWeight: 800, color: 'var(--cream)', lineHeight: 1 }}>
                      {Math.round(weatherData.temperature)}°C
                    </span>
                    <span style={{ fontSize: '1.35rem', color: 'var(--amber)', fontWeight: 600 }}>
                      {localizeWeatherCondition(weatherData.condition, language)}
                    </span>
                  </div>
                  {weatherData.feels_like && (
                    <div className="mono" style={{ color: 'var(--text-dim)', marginTop: '0.3rem' }}>
                      {t('feelsLike')} {Math.round(weatherData.feels_like)}°C
                    </div>
                  )}
                </div>

                {/* Advisory Pill */}
                <div style={{
                  maxWidth: '440px',
                  background: 'rgba(22, 23, 15, 0.75)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  padding: '1rem 1.2rem'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--amber)', fontWeight: 700, fontSize: '0.85rem', marginBottom: '0.3rem' }}>
                    <Shield size={16} />
                    <span>{t('weatherAdvisory')}</span>
                  </div>
                  <p style={{ fontSize: '0.88rem', color: 'var(--cream)', lineHeight: 1.5 }}>
                    {weatherData.advisory}
                  </p>
                </div>
              </div>

              {/* 4 Metric Cards */}
              <div className="grid-4">
                <div style={{ background: 'var(--char-input)', padding: '1.2rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-card)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)', fontSize: '0.82rem', marginBottom: '0.4rem' }}>
                    <Droplets size={16} style={{ color: '#38bdf8' }} />
                    <span>{t('humidity')}</span>
                  </div>
                  <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--cream)' }}>
                    {weatherData.humidity}%
                  </div>
                </div>

                <div style={{ background: 'var(--char-input)', padding: '1.2rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-card)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)', fontSize: '0.82rem', marginBottom: '0.4rem' }}>
                    <Wind size={16} style={{ color: '#a3e635' }} />
                    <span>{t('windSpeed')}</span>
                  </div>
                  <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--cream)' }}>
                    {weatherData.wind_speed} <span style={{ fontSize: '0.9rem', fontWeight: 500 }}>km/h</span>
                  </div>
                </div>

                <div style={{ background: 'var(--char-input)', padding: '1.2rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-card)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)', fontSize: '0.82rem', marginBottom: '0.4rem' }}>
                    <CloudRain size={16} style={{ color: '#60a5fa' }} />
                    <span>{t('rainProbability')}</span>
                  </div>
                  <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--cream)' }}>
                    {weatherData.rain_probability}%
                  </div>
                </div>

                <div style={{ background: 'var(--char-input)', padding: '1.2rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-card)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)', fontSize: '0.82rem', marginBottom: '0.4rem' }}>
                    <Droplets size={16} style={{ color: '#38bdf8' }} />
                    <span>{t('weatherRainfall')}</span>
                  </div>
                  <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--cream)' }}>
                    {weatherData.rainfall_mm ?? 0} <span style={{ fontSize: '0.9rem', fontWeight: 500 }}>mm</span>
                  </div>
                </div>

                <div style={{ background: 'var(--char-input)', padding: '1.2rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-card)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)', fontSize: '0.82rem', marginBottom: '0.4rem' }}>
                    <Shield size={16} style={{ color: 'var(--amber)' }} />
                    <span>{t('spraySuitability')}</span>
                  </div>
                  <div style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--amber)', lineHeight: 1.3 }}>
                    {weatherData.spray_suitability}
                  </div>
                </div>
              </div>

              {/* Specific Field Guidance Banners */}
              <div className="weather-guidance-grid" style={{ marginTop: '1.5rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1rem' }}>
                <div style={{ background: 'rgba(47, 58, 28, 0.4)', border: '1px solid rgba(163, 230, 53, 0.2)', padding: '1rem', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#a3e635', marginBottom: '0.3rem' }}>
                    💧 {t('irrigationAdvice')}
                  </div>
                  <p style={{ fontSize: '0.86rem', color: 'var(--cream)', lineHeight: 1.5 }}>
                    {weatherData.irrigation_advice}
                  </p>
                </div>

                <div style={{ background: 'rgba(138, 106, 69, 0.3)', border: '1px solid rgba(240, 168, 58, 0.25)', padding: '1rem', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--amber)', marginBottom: '0.3rem' }}>
                    🌾 {t('produceProtection')}
                  </div>
                  <p style={{ fontSize: '0.86rem', color: 'var(--cream)', lineHeight: 1.5 }}>
                    {weatherData.produce_protection}
                  </p>
                </div>
              </div>
            </div>

            {/* 7-Day Agricultural Forecast */}
            <div className="card" style={{ marginBottom: '2rem' }}>
              <h3 style={{ fontSize: '1.3rem', marginBottom: '1.4rem' }}>
                {t('forecast7Days')}
              </h3>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                gap: '0.9rem'
              }}>
                {weatherData.forecast.map((day, idx) => (
                  <div
                    key={idx}
                    style={{
                      background: idx === 0 ? 'rgba(240, 168, 58, 0.12)' : 'var(--char-input)',
                      border: `1px solid ${idx === 0 ? 'var(--border-subtle)' : 'var(--border-card)'}`,
                      borderRadius: 'var(--radius-md)',
                      padding: '1rem 0.8rem',
                      textAlign: 'center'
                    }}
                  >
                    <div style={{ fontSize: '0.95rem', fontWeight: 700, color: idx === 0 ? 'var(--amber)' : 'var(--cream)' }}>
                      {new Intl.DateTimeFormat(languageLocale[language], { weekday: 'long' }).format(new Date(`${day.date}T12:00:00`))}
                    </div>
                    <div className="mono" style={{ fontSize: '0.68rem', color: 'var(--text-dim)', marginBottom: '0.6rem' }}>
                      {day.date.substring(5)}
                    </div>
                    <div style={{ fontSize: '1.15rem', fontWeight: 800, margin: '0.4rem 0' }}>
                      {Math.round(day.temp_max)}° <span style={{ fontSize: '0.85rem', color: 'var(--text-dim)', fontWeight: 500 }}>/ {Math.round(day.temp_min)}°</span>
                    </div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
                      {localizeWeatherCondition(day.condition, language)}
                    </div>
                    <div className="mono" style={{ fontSize: '0.72rem', color: '#60a5fa' }}>
                      {day.precipitation_probability}% {t('weatherRain')}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Source & Transparency Disclaimer */}
            <div style={{ textAlign: 'center', color: 'var(--text-dim)', fontSize: '0.78rem', maxWidth: '720px', margin: '0 auto' }}>
              {weatherData.source.includes('DEMO DATA') && <p style={{ color: 'var(--amber)', fontWeight: 700 }}>{t('weatherDemoNotice')}</p>}
              <p>
                {t('weatherSource')}: {weatherData.source}. {t('weatherDisclaimer')}
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

