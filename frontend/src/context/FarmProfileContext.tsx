import React, { createContext, useContext, useEffect, useRef, useState } from 'react';
import { ensureBrowserSession } from '../services/session';

export interface FarmProfile {
  state: string;
  district: string;
  village: string;
  soilType: string;
  waterSource: string;
  selectedCommodity?: string;
  selectedCropHealthName?: string;
  selectedSymptoms?: string;
}

interface FarmProfileContextType {
  profile: FarmProfile;
  profileLoaded: boolean;
  updateProfile: (updates: Partial<FarmProfile>) => void;
  showSettingsModal: boolean;
  setShowSettingsModal: (show: boolean) => void;
}

const emptyProfile: FarmProfile = {
  state: '',
  district: '',
  village: '',
  soilType: '',
  waterSource: '',
};

const LEGACY_FABRICATED_DEFAULTS = {
  state: 'Telangana',
  district: 'Warangal',
  village: 'Dharmasagar',
  soilType: 'Black Cotton Soil',
  waterSource: 'Good irrigation',
};

const FarmProfileContext = createContext<FarmProfileContextType | undefined>(undefined);

function normalizeProfile(value: any): FarmProfile {
  const stored = value || {};
  const profile = { ...emptyProfile, ...stored } as FarmProfile;
  // Remove the old hard-coded sample farm if it was persisted by an earlier app version.
  const isOldSample = profile.state === LEGACY_FABRICATED_DEFAULTS.state
    && profile.district === LEGACY_FABRICATED_DEFAULTS.district
    && profile.village === LEGACY_FABRICATED_DEFAULTS.village;
  if (isOldSample) {
    profile.state = '';
    profile.district = '';
    profile.village = '';
    profile.soilType = '';
    profile.waterSource = '';
  }
  return profile;
}

export const FarmProfileProvider: React.FC<{ children: React.ReactNode; isGuest?: boolean; guestContextId?: string | null }> = ({ children, isGuest = false, guestContextId = null }) => {
  const profileRevision = useRef(0);
  const guestProfileKey = `kisan_hita_guest_${(guestContextId || 'new').replace(/[^a-zA-Z0-9_-]/g, '')}_farm_profile`;
  const [profileLoaded, setProfileLoaded] = useState(false);
  const [profile, setProfileState] = useState<FarmProfile>(() => {
    if (isGuest) {
      try {
        const saved = localStorage.getItem(guestProfileKey);
        return normalizeProfile(saved ? JSON.parse(saved) : null);
      } catch { return emptyProfile; }
    }
    try {
      const saved = localStorage.getItem('kisan_hita_farm_profile');
      return normalizeProfile(saved ? JSON.parse(saved) : null);
    } catch {
      return emptyProfile;
    }
  });
  const [showSettingsModal, setShowSettingsModal] = useState<boolean>(false);

  useEffect(() => {
    if (isGuest) { setProfileLoaded(true); return; }
    let active = true;
    ensureBrowserSession()
      .then(() => fetch('/api/settings/profile', { credentials: 'same-origin' }))
      .then((res) => {
        if (!res.ok) throw new Error(`Profile request failed: ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (!active || profileRevision.current > 0) return;
        const serverProfile = normalizeProfile({
          state: data.state || '',
          district: data.district || '',
          village: data.village || '',
          soilType: data.soil_type || '',
          waterSource: data.water_source || '',
        });
        setProfileState(serverProfile);
        localStorage.setItem('kisan_hita_farm_profile', JSON.stringify(serverProfile));
      })
      .catch(() => {
        // Keep local-only settings if the backend is temporarily unavailable.
      })
      .finally(() => {
        if (active) setProfileLoaded(true);
      });
    return () => { active = false; };
  }, [isGuest, guestContextId]);

  const updateProfile = (updates: Partial<FarmProfile>) => {
    profileRevision.current += 1;
    setProfileState((prev) => {
      const next = normalizeProfile({ ...prev, ...updates });
      if (isGuest) {
        localStorage.setItem(guestProfileKey, JSON.stringify(next));
      } else {
        localStorage.setItem('kisan_hita_farm_profile', JSON.stringify(next));
        ensureBrowserSession().then(() => fetch('/api/settings/profile', {
          method: 'POST', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            state: next.state || null, district: next.district || null, village: next.village,
            soil_type: next.soilType || null, water_source: next.waterSource || null,
          }),
        })).catch(() => {});
      }
      return next;
    });
  };

  return (
    <FarmProfileContext.Provider value={{ profile, profileLoaded, updateProfile, showSettingsModal, setShowSettingsModal }}>
      {children}
    </FarmProfileContext.Provider>
  );
};

export const useFarmProfile = () => {
  const ctx = useContext(FarmProfileContext);
  if (!ctx) throw new Error('useFarmProfile must be used within FarmProfileProvider');
  return ctx;
};
