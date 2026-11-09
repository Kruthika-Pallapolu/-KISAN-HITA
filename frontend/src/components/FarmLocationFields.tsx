import React, { useMemo, useState } from 'react';
import { MapPin } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';
import { localizeLocation } from '../i18n/agriculture';
import { detectCurrentLocation, getDistrictsForState, resetDistrictForStateChange, STATES, type GeolocationResult } from '../services/geography';

interface FarmLocationFieldsProps {
  state: string;
  district: string;
  onChange: (state: string, district: string) => void;
  includeAll?: boolean;
  layout?: 'stack' | 'inline';
  disabled?: boolean;
  showCurrentLocation?: boolean;
  onCurrentLocation?: (result: GeolocationResult) => void;
}

const GEO_ERROR_KEYS: Record<string, string> = {
  permissionDenied: 'locationPermissionDenied',
  positionUnavailable: 'locationUnavailable',
  timeout: 'locationTimeout',
  unsupported: 'locationUnsupported',
  insecureContext: 'locationHttpsRequired',
  outsideIndia: 'locationOutsideIndia',
  geocodingFailed: 'locationGeocodingFailed',
};

export const FarmLocationFields: React.FC<FarmLocationFieldsProps> = ({
  state,
  district,
  onChange,
  includeAll = false,
  layout = 'stack',
  disabled = false,
  showCurrentLocation = true,
  onCurrentLocation,
}) => {
  const { t, language } = useLanguage();
  const [locating, setLocating] = useState(false);
  const [locationError, setLocationError] = useState('');
  const [locationSuccess, setLocationSuccess] = useState(false);
  const districts = useMemo(() => getDistrictsForState(state), [state]);

  const handleStateChange = (nextState: string) => {
    setLocationError('');
    setLocationSuccess(false);
    const next = resetDistrictForStateChange(nextState, includeAll);
    onChange(next.state, next.district);
  };

  const handleLiveLocation = async () => {
    setLocationError('');
    setLocationSuccess(false);
    setLocating(true);
    const result = await detectCurrentLocation();
    setLocating(false);
    onCurrentLocation?.(result);
    if (!result.success || !result.state || !result.district) {
      setLocationError(t(GEO_ERROR_KEYS[result.error || 'geocodingFailed'] || 'locationFailed'));
      return;
    }
    if (!onCurrentLocation) onChange(result.state.name, result.district.name);
    setLocationSuccess(true);
  };

  const selectStyle: React.CSSProperties = layout === 'inline'
    ? { width: 'auto', minWidth: '220px', padding: '0.55rem 1rem' }
    : {};

  return (
    <div className={`farm-location-fields${layout === 'inline' ? ' farm-location-fields--inline' : ''}`} style={{ display: 'flex', flexDirection: layout === 'inline' ? 'row' : 'column', flexWrap: 'wrap', gap: '0.8rem', alignItems: layout === 'inline' ? 'center' : 'stretch' }}>
      <div className="input-group farm-location-fields__field" style={{ marginBottom: 0, flex: 1, minWidth: '180px' }}>
        <label className="input-label" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <MapPin size={14} aria-hidden="true" />{t('stateSelect')}
        </label>
        <select className="select-field" style={selectStyle} value={state} disabled={disabled} onChange={(event) => handleStateChange(event.target.value)}>
          <option value="">{t('stateSelect')}</option>
          {includeAll && <option value="All">{localizeLocation('All States', language)}</option>}
          {STATES.map((item) => (
            <option key={item.code} value={item.name}>{localizeLocation(item.name, language)}</option>
          ))}
        </select>
      </div>

      <div className="input-group farm-location-fields__field" style={{ marginBottom: 0, flex: 1, minWidth: '180px' }}>
        <label className="input-label">{t('districtSelect')}</label>
        <select
          className="select-field"
          style={selectStyle}
          value={district}
          disabled={disabled || !state || (includeAll && state === 'All')}
          onChange={(event) => {
            setLocationError('');
            setLocationSuccess(false);
            onChange(state, event.target.value);
          }}
        >
          {includeAll && <option value="All">{localizeLocation('All Districts', language)}</option>}
          {includeAll && state !== 'All' && <option value="">{t('districtSelect')}</option>}
          {!includeAll && <option value="">{t('districtSelect')}</option>}
          {districts.map((item) => (
            <option key={item.lgdCode} value={item.name}>{localizeLocation(item.name, language)}</option>
          ))}
        </select>
      </div>

      {showCurrentLocation && <button
        type="button"
        className="btn btn-secondary"
        data-location-action="current"
        style={{ alignSelf: layout === 'inline' ? 'center' : 'flex-start', whiteSpace: 'nowrap', padding: '0.6rem 0.9rem' }}
        onClick={() => void handleLiveLocation()}
        disabled={locating || disabled}
      >
        <MapPin size={15} aria-hidden="true" />
        {locating ? t('detectingLocation') : t('useCurrentLocation')}
      </button>}
      {locationError && <div role="alert" style={{ color: '#f87171', fontSize: '0.78rem', flexBasis: '100%' }}>{locationError}</div>}
      {locationSuccess && <div role="status" style={{ color: 'var(--amber)', fontSize: '0.78rem', flexBasis: '100%' }}>{t('locationDetected')}</div>}
    </div>
  );
};
