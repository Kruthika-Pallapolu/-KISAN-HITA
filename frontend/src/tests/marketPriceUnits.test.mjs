import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');
test('Market Prices renders local illustrative INR/kg references without invented mandi metadata', () => {
  const page = read('../pages/MarketPricesPage.tsx');
  const schema = read('../../../backend/app/models/schemas.py');
  const provider = read('../../../backend/app/services/market_provider.py');
  assert.match(page, /marketIllustrativeLabel/);
  assert.match(page, /marketIllustrativeDisclosure/);
  assert.match(page, /marketDistrictReference/);
  assert.match(page, /marketUnitLabel/);
  assert.match(page, /list="market-commodity-options"/);
  assert.match(page, /\/api\/market-prices\/commodities/);
  assert.doesNotMatch(page, /data\.gov\.in|AGMARKNET|rec\.source_url|marketOfficialRecordLabel|marketRetrievedAt|marketLatestReportDate/);
  assert.match(provider, /LocalIllustrativeMarketProvider/);
  assert.doesNotMatch(provider, /httpx|data\.gov\.in|API_KEY/i);
  assert.match(schema, /data_type: str = "illustrative"/);
  assert.match(schema, /state_code: Optional\[str\]/);
  assert.match(schema, /unit: str = "kg"/);
  assert.match(schema, /currency: str = "INR"/);
});
test('market demo disclosure and result labels have localized entries for all seven languages', () => {
  const translations = read('../i18n/supplementalTranslations.ts');
  for (const key of ['marketIllustrativeLabel', 'marketIllustrativeDisclosure', 'marketDatasetLabel', 'marketDistrictReference', 'marketUnitLabel', 'marketVarietyLabel']) {
    assert.equal((translations.match(new RegExp(`${key}:`, 'g')) || []).length, 7, `${key} must exist in all seven locales`);
  }
  assert.equal((translations.match(/marketSourceBanner:/g) || []).length, 7);
});
