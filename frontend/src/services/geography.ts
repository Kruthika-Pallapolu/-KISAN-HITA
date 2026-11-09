/**
 * Local Indian administrative directory from the LGD-derived public snapshot.
 * Snapshot: 2026-09-23; retrieved 2026-11-06. Selectors stay available offline.
 */
import adminDirectory from '../data/indiaAdminLgd.json' with { type: 'json' };

export interface StateInfo {
  code: string;
  name: string;
  lgdCode: number;
  type: 'S' | 'U';
}

export interface DistrictInfo {
  id: string;
  name: string;
  stateCode: string;
  lgdCode: number;
  aliases?: string[];
}

export const STATES: StateInfo[] = adminDirectory.states.map((state) => ({
  code: state.code,
  name: state.name,
  lgdCode: state.lgdCode,
  type: state.type as 'S' | 'U',
}));

export const DISTRICTS: DistrictInfo[] = adminDirectory.districts.map((district) => ({
  id: district.id,
  name: district.name,
  stateCode: district.stateCode,
  lgdCode: district.lgdCode,
  aliases: district.aliases,
}));

export function getState(codeOrName: string): StateInfo | undefined {
  const norm = normalizePlaceName(codeOrName);
  const legacyCodes: Record<string, string> = { ap: 'Andhra Pradesh', ts: 'Telangana', ka: 'Karnataka', tn: 'Tamil Nadu', kl: 'Kerala', mh: 'Maharashtra', gj: 'Gujarat', mp: 'Madhya Pradesh', hr: 'Haryana', pb: 'Punjab' };
  const name = normalizePlaceName(legacyCodes[norm] || norm);
  return STATES.find((state) => normalizePlaceName(state.code) === norm || normalizePlaceName(state.name) === name);
}

export function getDistrictsForState(stateCodeOrName: string): DistrictInfo[] {
  if (!stateCodeOrName || stateCodeOrName === 'All' || stateCodeOrName === 'All States') return [];
  const state = getState(stateCodeOrName);
  return state ? DISTRICTS.filter((district) => district.stateCode === state.code) : [];
}

export function resetDistrictForStateChange(nextState: string, includeAll = false): { state: string; district: string } {
  return { state: nextState, district: includeAll && nextState === 'All' ? 'All' : '' };
}

export function isDistrictInState(districtName: string, stateCodeOrName: string): boolean {
  const state = getState(stateCodeOrName);
  if (!state) return false;
  const norm = normalizePlaceName(districtName);
  return DISTRICTS.some((district) => district.stateCode === state.code
    && (normalizePlaceName(district.id) === norm || normalizePlaceName(district.name) === norm
      || district.aliases?.some((alias) => normalizePlaceName(alias) === norm)));
}

export function getStateForDistrict(districtName: string): StateInfo | undefined {
  const norm = normalizePlaceName(districtName);
  const district = DISTRICTS.find((item) => normalizePlaceName(item.id) === norm || normalizePlaceName(item.name) === norm
    || item.aliases?.some((alias) => normalizePlaceName(alias) === norm));
  return district ? STATES.find((state) => state.code === district.stateCode) : undefined;
}

function normalizePlaceName(value: string): string {
  return (value || '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/&/g, ' and ')
    .replace(/\b(district|dist\.?|state|union territory)\b/g, ' ')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
    .replace(/\s+/g, ' ');
}

const STATE_ALIASES: Record<string, string> = {
  'nct of delhi': 'Delhi',
  'national capital territory of delhi': 'Delhi',
  'orissa': 'Odisha',
  'pondicherry': 'Puducherry',
  'uttaranchal': 'Uttarakhand',
  'jammu and kashmir': 'Jammu And Kashmir',
  'andaman and nicobar islands': 'Andaman And Nicobar Islands',
  'dadra and nagar haveli': 'Dadra And Nagar Haveli And Daman And Diu',
  'daman and diu': 'Dadra And Nagar Haveli And Daman And Diu',
};

function matchState(rawName: string): StateInfo | undefined {
  const raw = normalizePlaceName(rawName);
  const canonical = STATE_ALIASES[raw] || rawName;
  const norm = normalizePlaceName(canonical);
  return STATES.find((state) => normalizePlaceName(state.name) === norm);
}

function matchDistrict(rawName: string, state: StateInfo): DistrictInfo | undefined {
  const raw = normalizePlaceName(rawName);
  if (!raw) return undefined;
  const candidates = DISTRICTS.filter((district) => district.stateCode === state.code);
  const exact = candidates.filter((district) => normalizePlaceName(district.name) === raw
    || district.aliases?.some((alias) => normalizePlaceName(alias) === raw));
  if (exact.length === 1) return exact[0];

  // Geocoders sometimes append administrative labels. Only accept a unique
  // full-name containment match within the already matched state.
  const contained = candidates.filter((district) => {
    const canonical = normalizePlaceName(district.name);
    return raw.startsWith(canonical + ' ') || raw.endsWith(' ' + canonical);
  });
  return contained.length === 1 ? contained[0] : undefined;
}

export interface GeolocationResult {
  success: boolean;
  state?: StateInfo;
  district?: DistrictInfo;
  coordinates?: { latitude: number; longitude: number };
  error?: 'unsupported' | 'insecureContext' | 'permissionDenied' | 'positionUnavailable'
    | 'timeout' | 'outsideIndia' | 'geocodingFailed';
  source: 'nominatim' | 'failed';
}

/**
 * Requests coordinates only after a user action, reverse-geocodes through
 * Nominatim, and returns canonical names with in-memory coordinates for an
 * exact weather request. Callers must not persist the coordinates.
 * If the geocoder cannot resolve an exact district, nothing is guessed.
 */
export async function detectCurrentLocation(): Promise<GeolocationResult> {
  if (typeof window === 'undefined' || !navigator.geolocation) {
    return { success: false, error: 'unsupported', source: 'failed' };
  }
  const host = window.location.hostname;
  if (!window.isSecureContext && host !== 'localhost' && host !== '127.0.0.1') {
    return { success: false, error: 'insecureContext', source: 'failed' };
  }

  let position: GeolocationPosition;
  try {
    position = await new Promise<GeolocationPosition>((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: false,
        timeout: 12000,
        maximumAge: 60000,
      });
    });
  } catch (error) {
    const code = (error as GeolocationPositionError)?.code;
    const reason = code === 1 ? 'permissionDenied' : code === 2 ? 'positionUnavailable' : 'timeout';
    return { success: false, error: reason, source: 'failed' };
  }

  const { latitude, longitude } = position.coords;
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 8000);
  try {
    const url = new URL('https://nominatim.openstreetmap.org/reverse');
    url.search = new URLSearchParams({
      format: 'jsonv2',
      lat: String(latitude),
      lon: String(longitude),
      zoom: '10',
      addressdetails: '1',
      'accept-language': 'en',
    }).toString();
    const response = await fetch(url.toString(), {
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    });
    if (!response.ok) return { success: false, error: 'geocodingFailed', source: 'failed' };
    const result = await response.json();
    const countryCode = result?.address?.country_code?.toLowerCase();
    if (countryCode && countryCode !== 'in') {
      return { success: false, error: 'outsideIndia', source: 'failed' };
    }
    const address = result.address || {};
    if (!countryCode) return { success: false, error: 'geocodingFailed', source: 'failed' };
    const state = matchState(address.state || '');
    if (!state) return { success: false, error: 'geocodingFailed', source: 'failed' };
    const districtName = address.state_district || address.district || address.county || '';
    const district = matchDistrict(districtName, state);
    if (!district) return { success: false, error: 'geocodingFailed', source: 'failed' };
    return { success: true, state, district, coordinates: { latitude, longitude }, source: 'nominatim' };
  } catch {
    return { success: false, error: 'geocodingFailed', source: 'failed' };
  } finally {
    window.clearTimeout(timer);
  }
}
