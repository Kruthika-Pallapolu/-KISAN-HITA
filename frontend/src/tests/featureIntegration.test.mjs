import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');

test('Choose Crop submits only explicit selections and guards against stale results', () => {
  const page = source('../pages/ChooseCropPage.tsx');
  assert.match(page, /fetch\('\/api\/crop-advisor\/recommend'/);
  assert.match(page, /signal: controller\.signal/);
  assert.match(page, /request !== requestId\.current/);
  assert.match(page, /key=\{`\$\{rec\.crop_name\}:\$\{rec\.variety\}`\}/);
  assert.match(page, /t\('cropNoResults'\)/);
  assert.doesNotMatch(page, /useEffect\(\(\) => \{\s*fetchRecommendations\(\)/);
});

test('Market search sends selected filters and labels local illustrative records honestly', () => {
  const page = source('../pages/MarketPricesPage.tsx');
  assert.match(page, /params\.append\('commodity', comm\.trim\(\)\)/);
  assert.match(page, /params\.append\('state', st\)/);
  assert.match(page, /params\.append\('district', dist\)/);
  assert.match(page, /signal: controller\.signal/);
  assert.match(page, /marketIllustrativeLabel/);
  assert.match(page, /marketIllustrativeDisclosure/);
  assert.match(page, /marketDatasetLabel/);
  assert.match(page, /list="market-commodity-options"/);
  assert.match(page, /fetchPrices\(searchCommodity, nextState, canonicalDistrict\)/);
  assert.match(page, /results\.disclaimer/);
  assert.doesNotMatch(page, /DEMO reference data, not a live price/);
});

test('assistant UI renders the corrected backend reply text without replacing it with diagnostic metadata', () => {
  const context = source('../context/AssistantContext.tsx');
  const modal = source('../components/KisanAssistantModal.tsx');
  const page = source('../pages/AskKisanHitaPage.tsx');
  assert.match(context, /text: data\.reply_text/);
  assert.match(modal, /msg\.text/);
  assert.match(page, /msg\.text/);
});




test('Assistant input renders one Prisma microphone and never falls back to browser recognition', () => {
  const modal = source('../components/KisanAssistantModal.tsx');
  const context = source('../context/AssistantContext.tsx');
  const micControl = modal.match(/\{\/\* The sole voice-input control records clips for Prisma\. \*\/[\s\S]*?\{\/\* Text Input \*\/\}/)?.[0] || '';
  assert.equal([...micControl.matchAll(/<button/g)].length, 1);
  assert.match(micControl, /prismaEnabled\s*\?/);
  assert.match(micControl, /startPrismaVoiceInput/);
  assert.match(micControl, /disabled=\{isProcessing \|\| !prismaEnabled \|\| !voiceConfigLoaded\}/);
  assert.doesNotMatch(micControl, /\{prismaEnabled &&/);
  assert.match(context, /startPrismaVoiceInput/);
  assert.doesNotMatch(context, /VoiceRecognitionService|startVoiceInput|stopVoiceInput|wakeWord/);
});

test('Market provider is local and the page clearly marks synthetic data', () => {
  const page = source('../pages/MarketPricesPage.tsx');
  const provider = source('../../../backend/app/services/market_provider.py');
  assert.match(provider, /LocalIllustrativeMarketProvider/);
  assert.doesNotMatch(provider, /httpx|data\.gov\.in|DATA_GOV_IN_API_KEY/);
  assert.match(page, /marketIllustrativeDisclosure/);
  assert.match(page, /marketIllustrativeLabel/);
  assert.match(page, /setError\(err\?\.message \|\| t\('marketServiceUnavailable'\)\)/);
  assert.doesNotMatch(page, /marketOfficialDataUnavailable|AGMARKNET|data\.gov\.in/);
});

test('initial answers and Listen again use the same full-response Timbre-aware speech service', () => {
  const context = source('../context/AssistantContext.tsx');
  const modal = source('../components/KisanAssistantModal.tsx');
  const speech = source('../services/speech.ts');
  assert.match(context, /speakText\(data\.reply_text, options\)/);
  assert.match(modal, /onClick=\{\(\) => speakText\(msg\.text\)\}/);
  assert.match(speech, /splitSpeechText\(cleanText\)/);
  assert.match(speech, /timbreEnabled && \(data\.provider !== 'gnani_live'.*data\.voice_name !== 'Vasudha'/);
  assert.match(speech, /if \(timbreEnabled\) \{[\s\S]*?onError\?\.\(error\)/);
});
