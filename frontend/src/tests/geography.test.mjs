import test from 'node:test';
import assert from 'node:assert/strict';
import {
  STATES,
  DISTRICTS,
  getState,
  getDistrictsForState,
  isDistrictInState,
  getStateForDistrict,
  resetDistrictForStateChange,
  detectCurrentLocation,
} from '../services/geography.ts';

test('all 28 states and 8 Union Territories have canonical names and LGD identifiers', () => {
  assert.equal(STATES.length, 36);
  assert.equal(STATES.filter((state) => state.type === 'S').length, 28);
  assert.equal(STATES.filter((state) => state.type === 'U').length, 8);
  for (const state of STATES) {
    assert.ok(state.name.length > 2);
    assert.ok(Number.isInteger(state.lgdCode) && state.lgdCode > 0);
  }
});

test('all 784 districts have a valid state parent and unique LGD code', () => {
  assert.equal(DISTRICTS.length, 784);
  const stateCodes = new Set(STATES.map((state) => state.code));
  const districtCodes = new Set();
  for (const district of DISTRICTS) {
    assert.ok(stateCodes.has(district.stateCode), `${district.name} has valid parent ${district.stateCode}`);
    assert.ok(Number.isInteger(district.lgdCode) && district.lgdCode > 0);
    assert.ok(!districtCodes.has(district.lgdCode), `duplicate district LGD code ${district.lgdCode}`);
    districtCodes.add(district.lgdCode);
  }
});

test('state filtering returns Nellore only for AP and Karnataka districts only for Karnataka', () => {
  const ap = getDistrictsForState('Andhra Pradesh');
  assert.ok(ap.some((district) => district.name === 'Nellore'));
  assert.ok(ap.every((district) => district.stateCode === getState('AP').code));
  assert.ok(!ap.some((district) => district.name === 'Warangal'));

  const ka = getDistrictsForState('Karnataka');
  assert.ok(ka.some((district) => district.name === 'Bengaluru Urban'));
  assert.ok(ka.every((district) => district.stateCode === getState('KA').code));
  assert.ok(!ka.some((district) => district.name === 'Nellore'));
});

test('changing states clears the old district and back again restores the correct choices', () => {
  const toKarnataka = resetDistrictForStateChange('Karnataka');
  assert.deepEqual(toKarnataka, { state: 'Karnataka', district: '' });
  assert.equal(getDistrictsForState(toKarnataka.state).some((item) => item.name === 'Nellore'), false);

  const toAndhra = resetDistrictForStateChange('Andhra Pradesh');
  assert.deepEqual(toAndhra, { state: 'Andhra Pradesh', district: '' });
  assert.ok(getDistrictsForState(toAndhra.state).some((item) => item.name === 'Nellore'));
});

test('district validation and state lookup work with canonical and legacy state identifiers', () => {
  assert.equal(isDistrictInState('Nellore', 'AP'), true);
  assert.equal(isDistrictInState('Nellore', 'Andhra Pradesh'), true);
  assert.equal(isDistrictInState('Nellore', 'Karnataka'), false);
  assert.equal(isDistrictInState('Warangal', 'AP'), false);
  assert.equal(isDistrictInState('Warangal', 'TS'), true);
  assert.equal(getStateForDistrict('Nellore')?.name, 'Andhra Pradesh');
  assert.equal(getStateForDistrict('Warangal')?.name, 'Telangana');
  assert.equal(getStateForDistrict('Coimbatore')?.name, 'Tamil Nadu');
  assert.equal(getStateForDistrict('Palakkad')?.name, 'Kerala');
});

function withBrowserMocks({ position, geoError, address, fetchError } = {}, run) {
  const originalWindow = globalThis.window;
  const originalNavigator = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
  const originalFetch = globalThis.fetch;
  globalThis.window = {
    isSecureContext: true,
    location: { hostname: 'localhost' },
    setTimeout,
    clearTimeout,
  };
  Object.defineProperty(globalThis, 'navigator', {
    configurable: true,
    value: {
      geolocation: {
        getCurrentPosition(success, error) {
          if (geoError) error(geoError);
          else success({ coords: position || { latitude: 14.4, longitude: 80.0 } });
        },
      },
    },
  });
  globalThis.fetch = fetchError
    ? async () => { throw fetchError; }
    : async () => ({ ok: true, json: async () => ({ address }) });
  return Promise.resolve().then(run).finally(() => {
    globalThis.window = originalWindow;
    if (originalNavigator) Object.defineProperty(globalThis, 'navigator', originalNavigator);
    else delete globalThis.navigator;
    globalThis.fetch = originalFetch;
  });
}

test('live location selects an exact Indian state and district and returns coordinates for the weather request', async () => {
  await withBrowserMocks({
    address: { country_code: 'in', state: 'Andhra Pradesh', state_district: 'Nellore District' },
  }, async () => {
    const result = await detectCurrentLocation();
    assert.equal(result.success, true);
    assert.equal(result.state.name, 'Andhra Pradesh');
    assert.equal(result.district.name, 'Nellore');
    assert.deepEqual(result.coordinates, { latitude: 14.4, longitude: 80.0 });
  });
});

test('live location never guesses a district when reverse geocoding is inconclusive', async () => {
  await withBrowserMocks({
    address: { country_code: 'in', state: 'Andhra Pradesh', state_district: 'Unknown Administrative Area' },
  }, async () => {
    const result = await detectCurrentLocation();
    assert.equal(result.success, false);
    assert.equal(result.error, 'geocodingFailed');
    assert.equal(result.district, undefined);
  });
});

test('live location handles permission denial and geocoder failures without coordinate leakage', async () => {
  await withBrowserMocks({
    geoError: { code: 1 },
  }, async () => {
    const result = await detectCurrentLocation();
    assert.equal(result.success, false);
    assert.equal(result.error, 'permissionDenied');
    assert.equal(JSON.stringify(result).includes('latitude'), false);
  });
  await withBrowserMocks({
    address: { country_code: 'us', state: 'California', state_district: 'Los Angeles County' },
  }, async () => {
    const result = await detectCurrentLocation();
    assert.equal(result.success, false);
    assert.equal(result.error, 'outsideIndia');
  });
});

import { localizeLocation } from '../i18n/agriculture.ts';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const supportedLocationLanguages = ['te', 'en', 'hi', 'ta', 'kn', 'ml', 'mr'];

test('all 36 states and 784 districts have readable offline labels in all seven languages', () => {
  const rows = [...STATES, ...DISTRICTS];
  assert.equal(rows.length, 820);
  for (const language of supportedLocationLanguages) {
    for (const row of rows) {
      const label = localizeLocation(row.name, language);
      assert.ok(label.trim(), `${language} label missing for ${row.name}`);
      if (language === 'en') assert.equal(label, row.name);
    }
  }
  // Uncatalogued proper names deliberately remain canonical English; they
  // are more readable than generated, often malformed transliteration.
  assert.equal(localizeLocation('Uncatalogued LGD District', 'te'), 'Uncatalogued LGD District');
});

test('language changes affect only location labels, not canonical state/district values sent to APIs', () => {
  const district = DISTRICTS.find((item) => item.name === 'Nellore');
  const state = STATES.find((item) => item.name === 'Andhra Pradesh');
  assert.ok(district && state);
  const requestBefore = { state: state.name, district: district.name };
  const teluguLabels = { state: localizeLocation(state.name, 'te'), district: localizeLocation(district.name, 'te') };
  const hindiLabels = { state: localizeLocation(state.name, 'hi'), district: localizeLocation(district.name, 'hi') };
  assert.notDeepEqual(teluguLabels, hindiLabels);
  assert.deepEqual(requestBefore, { state: 'Andhra Pradesh', district: 'Nellore' });
  assert.equal(isDistrictInState(requestBefore.district, requestBefore.state), true);
});

test('Weather, Market Prices and shared location selectors use the same display helper', () => {
  const here = dirname(fileURLToPath(import.meta.url));
  const root = resolve(here, '..');
  for (const file of ['pages/WeatherPage.tsx', 'pages/MarketPricesPage.tsx', 'components/FarmLocationFields.tsx']) {
    const source = readFileSync(resolve(root, file), 'utf8');
    assert.match(source, /localizeLocation/, `${file} must use shared location localization`);
  }
  const selector = readFileSync(resolve(root, 'components/FarmLocationFields.tsx'), 'utf8');
  assert.match(selector, /value=\{item\.name\}/, 'selector values stay canonical English names');
});

test('Market Prices restores only a valid saved state-district pair and does not infer a Kolar selection', () => {
  const here = dirname(fileURLToPath(import.meta.url));
  const page = readFileSync(resolve(here, '../pages/MarketPricesPage.tsx'), 'utf8');
  assert.match(page, /getState\(profile\.state\)\?\.name \|\| 'All'/);
  assert.match(page, /profile\.district && nextState !== 'All' && isDistrictInState\(profile\.district, nextState\)/);
  assert.doesNotMatch(page, /getStateForDistrict\(profile\.district\)/);
  assert.equal(isDistrictInState('Kolar', 'Andhra Pradesh'), false);
  assert.equal(isDistrictInState('Kolar', 'Karnataka'), true);
});

test('market district change clears old selection and an unresolved current location never changes the selected pair', () => {
  const fields = readFileSync(new URL('../components/FarmLocationFields.tsx', import.meta.url), 'utf8');
  const page = readFileSync(new URL('../pages/MarketPricesPage.tsx', import.meta.url), 'utf8');
  assert.match(fields, /resetDistrictForStateChange\(nextState, includeAll\)/);
  assert.match(fields, /if \(!result\.success \|\| !result\.state \|\| !result\.district\) \{[\s\S]*?setLocationError[\s\S]*?return;/);
  assert.match(fields, /if \(!onCurrentLocation\) onChange\(result\.state\.name, result\.district\.name\)/);
  assert.match(page, /const canonicalDistrict = nextDistrict \|\| \(nextState === 'All' \? 'All' : ''\)/);
  assert.match(page, /if \(searchCommodity\.trim\(\) && canonicalDistrict && canonicalDistrict !== 'All'\)/);
  assert.match(page, /if \(!result\.success \|\| !result\.state \|\| !result\.district\) \{[\s\S]*?setSelectedState\('All'\);[\s\S]*?setSelectedDistrict\('All'\)/);
  assert.match(fields, /onCurrentLocation\?\.\(result\);\s*if \(!result\.success/);
});

test('Market Prices localizes labels on language changes and submits canonical location identifiers', () => {
  const page = readFileSync(new URL('../pages/MarketPricesPage.tsx', import.meta.url), 'utf8');
  const fields = readFileSync(new URL('../components/FarmLocationFields.tsx', import.meta.url), 'utf8');
  assert.match(page, /previousLanguage\.current === language/);
  assert.match(page, /fetchPrices\(searchCommodity, selectedState, selectedDistrict\)/);
  assert.match(page, /localizeLocation\(rec\.district, language\)/);
  assert.match(page, /localizeLocation\(rec\.state, language\)/);
  assert.match(fields, /localizeLocation\(item\.name, language\)/);
  assert.match(fields, /value=\{item\.name\}/);
});
