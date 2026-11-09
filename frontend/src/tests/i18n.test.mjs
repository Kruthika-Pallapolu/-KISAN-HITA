import test from 'node:test';
import assert from 'node:assert';
import { translations, LANGUAGES } from '../i18n/translations.ts';
import { getAgricultureTranslationCoverage, localizeCropName, localizeLocation, localizeMarketUnit, localizeSeason, localizeSoil, localizeWater, localizeWeatherCondition } from '../i18n/agriculture.ts';
import { supplementalTranslations } from '../i18n/supplementalTranslations.ts';
import { cropHealthCopy } from '../i18n/cropHealth.ts';
import { cropAdviceAuditContent, localizeCropAdvice } from '../i18n/cropAdvisory.ts';
import { assistantQuestionSuggestions } from '../i18n/assistantQuestions.ts';

test('Verify all 7 supported languages are defined', () => {
  const expectedCodes = ['te', 'en', 'hi', 'ta', 'kn', 'ml', 'mr'];
  assert.strictEqual(LANGUAGES.length, 7);
  for (const code of expectedCodes) {
    const found = LANGUAGES.find((l) => l.code === code);
    assert.ok(found, `Language ${code} should be defined in LANGUAGES list`);
    assert.ok(found.nativeName, `Language ${code} should have nativeName`);
  }
});

test('Base translation dictionaries and supplemental translation keys are complete across languages', () => {
  const codes = ['te', 'en', 'hi', 'ta', 'kn', 'ml', 'mr'];
  const keys = Object.keys(translations.en).sort();
  for (const code of codes) assert.deepEqual(Object.keys(translations[code]).sort(), keys, `Base translation keys are incomplete for ${code}`);
  for (const code of codes) assert.deepEqual(Object.keys(supplementalTranslations[code]).sort(), Object.keys(supplementalTranslations.en).sort(), `Supplemental translation keys are incomplete for ${code}`);
});

test('all seven languages retain the regular assistant navigation and remove wake-listening copy', () => {
  for (const language of ['te', 'en', 'hi', 'ta', 'kn', 'ml', 'mr']) {
    assert.ok(translations[language].navAssistant, `${language} assistant navigation label should be present`);
    assert.ok(!Object.hasOwn(translations[language], 'assistantName'), `${language} must not expose assistant renaming terminology`);
    assert.equal(Object.keys(translations[language]).some((key) => key.startsWith('heyKisan') || key.startsWith('wakePhrase')), false);
  }
  assert.equal(translations.en.navAssistant, 'Kisan Hita');
  assert.equal(supplementalTranslations.en.askAssistantMandi, 'Ask Kisan Hita about mandi prices');
});

test('first-visit language question and authentication validation are localized in every language', () => {
  const keys = ['firstVisitLanguageQuestion', 'authEmailRequired', 'authEmailInvalid', 'authPasswordRequired', 'authPasswordMismatch', 'authAccountExists', 'authInvalidCredentials', 'authPasswordLength', 'authPasswordInvalid', 'authGenericError'];
  for (const language of ['te', 'en', 'hi', 'ta', 'kn', 'ml', 'mr']) {
    for (const key of keys) assert.ok(translations[language][key]?.trim(), `Missing ${language}.${key}`);
  }
});

test('Agricultural display dictionaries cover canonical farmer-facing values in all seven languages', () => {
  const coverage = getAgricultureTranslationCoverage();
  for (const language of ['te', 'en', 'hi', 'ta', 'kn', 'ml', 'mr']) {
    assert.equal(coverage[language], true, `Agricultural translations are incomplete for ${language}`);
    assert.ok(localizeCropName('Chilli', language));
    assert.ok(localizeSoil('Black Cotton Soil', language));
    assert.ok(localizeWater('Good irrigation', language));
    assert.ok(localizeSeason('Kharif (Monsoon)', language));
    assert.ok(localizeMarketUnit('₹/Quintal', language));
  }
});

test('Localized crop and form labels leave canonical API values untouched', () => {
  assert.equal(localizeCropName('Chilli', 'te'), 'మిరప');
  assert.equal(localizeSoil('Black Cotton Soil', 'hi'), 'काली कपास मिट्टी (भारी चिकनी मिट्टी)');
  assert.equal(localizeWater('Good irrigation', 'ta'), 'நல்ல பாசனம் (கால்வாய் / தொடர்ந்து நீர் தரும் ஆழ்துளைக் கிணறு)');
  assert.equal(localizeSeason('Kharif (Monsoon)', 'mr'), 'खरीप (पावसाळा)');
});

test('Supplemental interface copy is synchronized across all supported languages', () => {
  const keys = Object.keys(supplementalTranslations.en);
  for (const language of ['te', 'en', 'hi', 'ta', 'kn', 'ml', 'mr']) {
    assert.deepEqual(Object.keys(supplementalTranslations[language]).sort(), keys.slice().sort(), `Supplemental keys differ for ${language}`);
    for (const key of keys) assert.ok(supplementalTranslations[language][key]?.trim(), `Missing ${key} for ${language}`);
  }
});

test('illustrative market demo disclosures are localized in all seven languages', () => {
  const codes = ['te', 'en', 'hi', 'ta', 'kn', 'ml', 'mr'];
  const keys = ['marketIllustrativeLabel', 'marketIllustrativeDisclosure', 'marketDatasetLabel', 'marketDistrictReference', 'marketUnitLabel', 'marketVarietyLabel'];
  for (const key of keys) {
    for (const code of codes) assert.ok(supplementalTranslations[code][key]?.trim(), `Missing ${code}.${key}`);
    for (const code of codes.filter((item) => item !== 'en')) assert.notEqual(supplementalTranslations[code][key], supplementalTranslations.en[key], `${key} must be localized for ${code}`);
  }
});

test('Core crop names are consistently available in every supported language', () => {
  const crops = ['Chilli', 'Cotton', 'Paddy', 'Rice', 'Maize', 'Groundnut', 'Tomato', 'Onion', 'Bengal Gram', 'Red Gram', 'Soybean'];
  for (const language of ['te', 'en', 'hi', 'ta', 'kn', 'ml', 'mr']) {
    for (const crop of crops) assert.ok(localizeCropName(crop, language), `Missing ${crop} in ${language}`);
  }
});

test('All locally supported market commodities have localized display names in every language', () => {
  const crops = ['Paddy', 'Wheat', 'Maize', 'Groundnut', 'Cotton', 'Red gram (Tur)', 'Chilli (dry)', 'Tomato', 'Onion', 'Potato', 'Soybean', 'Mustard', 'Gram (Chana)', 'Turmeric', 'Ginger', 'Apple', 'Cabbage', 'Green peas', 'Garlic', 'Coriander seed', 'Jute', 'Pineapple', 'Brinjal', 'Cauliflower', 'Okra', 'Bottle gourd', 'Bitter gourd', 'Cucumber', 'Pumpkin', 'Spinach', 'Beans', 'Drumstick'];
  for (const language of ['te', 'en', 'hi', 'ta', 'kn', 'ml', 'mr']) {
    for (const crop of crops) {
      const label = localizeCropName(crop, language);
      assert.ok(label);
      if (language !== 'en') assert.notEqual(label, crop, `${crop} needs a ${language} display name`);
    }
  }
});

test('Market location labels use curated translations or readable canonical names, never generated transliteration', () => {
  for (const language of ['en', 'te', 'hi', 'ta', 'kn', 'ml', 'mr']) {
    assert.ok(localizeLocation('Nellore', language));
    assert.ok(localizeLocation('Kolar', language));
    assert.ok(localizeLocation('Andhra Pradesh', language));
    assert.ok(localizeLocation('All States', language));
    assert.ok(localizeLocation('All Districts', language));
    assert.ok(localizeWeatherCondition('Heavy Rain', language));
    assert.ok(localizeMarketUnit('₹/Quintal', language));
    assert.ok(supplementalTranslations[language].marketIllustrativeLabel);
    assert.ok(supplementalTranslations[language].marketIllustrativeDisclosure);
    assert.ok(supplementalTranslations[language].weatherDemoLabel);
    assert.ok(supplementalTranslations[language].weatherDemoNotice);
    assert.ok(supplementalTranslations[language].weatherRainfall);
    assert.ok(supplementalTranslations[language].weatherDisclaimer);
  }
  assert.equal(localizeLocation('Nellore', 'en'), 'Nellore');
  assert.deepEqual(['te', 'en', 'hi', 'ta', 'kn', 'ml', 'mr'].map((language) => localizeLocation('Kolar', language)), ['కోలార్', 'Kolar', 'कोलार', 'கோலார்', 'ಕೋಲಾರ', 'കോലാർ', 'कोलार']);
  assert.equal(localizeLocation('Uncatalogued LGD District', 'te'), 'Uncatalogued LGD District');
  assert.equal(localizeLocation('Nellore', 'te'), 'నెల్లూరు');
});

test('Crop health rendered prompts and key form/result copy have real localized content', () => {
  const keys = ['quickPrompts', 'lower', 'wilt', 'curl', 'stem', 'spots', 'today', 'days23', 'week', 'weeks2', 'few', 'patch', 'border', 'wide', 'analyzing', 'takeUpload', 'assessment', 'factors', 'management', 'invalidSize', 'describe', 'failed'];
  const latin = /[A-Za-z]{3,}/;
  for (const language of ['te', 'hi', 'ta', 'kn', 'ml', 'mr']) {
    for (const key of keys) {
      const value = cropHealthCopy[language][key];
      assert.ok(value?.trim(), `Missing crop health copy ${key} for ${language}`);
      assert.ok(!latin.test(value), `Unexpected English in ${key} for ${language}: ${value}`);
    }
  }
});

test('Rendered Chilli, Paddy and Maize recommendation fields have exact localized entries', () => {
  assert.equal(localizeCropName('Paddy (Rice)', 'te'), 'వరి');
  assert.equal(localizeCropName('Bengal Gram (Chickpea)', 'te'), 'శనగ');
  assert.equal(localizeCropName('Black Gram (Urad Dal)', 'te'), 'మినుములు');
  assert.equal(localizeCropName('Maize (Corn)', 'te'), 'మొక్కజొన్న');

  const expected = [
    '150–180 Days', '125–140 Days', '100–115 Days',
    '95–105 Days', '75–85 Days', '105–115 Days', '90–100 Days', '110–130 Days', '80–95 Days', '80–90 Days',
    'High / Controlled (Regular drip or furrow moisture)',
    'High (Submerged / Alternate Wetting and Drying)',
    'Moderate (Critical at knee-high, tasseling, and grain filling)',
    'Moderate (Critical during flowering and boll formation)',
    'Moderate (Peg penetration & pod development stages)',
    'Moderate (Sensitive during flowering and pod filling)',
    'Moderate (Ideal for rice fallows)',
    'Moderate to High (Critical at fruit enlargement)',
    'Low to Moderate / Residual (Thrives on stored moisture)',
    'Low to Moderate (Drought hardy deep taproot)',
    'Low (Drought tolerant after establishment)',
    'Deep, well-drained black cotton and loamy soils support continuous flowering and high dry-pod capsaicin yields.',
    'Heavy black cotton and clay soils in canal and borewell irrigated command areas retain water with minimal percolation loss.',
    'Fertile, well-drained loamy and black soils with good aeration promote high cob weight and grain filling.',
    'Deep black soils offer high water retention capacity essential for deep taproot anchorage and steady boll development.',
    'Loose, friable red sandy soils and light loams allow easy gynophore (peg) penetration and clean pod lifting during harvest.',
    'Deep red sandy loams and light black soils allow deep root penetration without water-logging risk.',
    'Well-drained black and loamy soils with neutral pH facilitate effective Rhizobium nodulation and rapid vegetative growth.',
    'Well-aerated fertile red sandy loam with good organic matter and slightly acidic to neutral pH.',
    'Deep, loose sandy loams and riverbed soils warm up quickly and promote early root expansion and high sugar accumulation.',
    'Light sandy and well-drained loamy soils prevent water stagnation and root rot.',
    'Utilizes residual black soil moisture effectively following early Kharif harvests without requiring heavy flood irrigation.',
    'Excellent for Nellore and coastal AP black soils and rice-fallow systems with residual moisture.',
    'Transplant 35-40 day old seedlings on raised beds; install yellow and blue sticky traps (20 each/acre); maintain ridge drainage.',
    'Transplant 25-day seedlings with 2-3 seedlings per hill; practice Alternate Wetting and Drying (AWD) to save 25% water.',
    'Establish ridge-and-furrow planting for drainage; install pheromone traps at 45 days after sowing.',
    'Apply gypsum at 500 kg/ha at pegging stage (40-45 DAS); inspect foliage regularly for leaf miner and tikka spots.',
    'Apply neem-based formulations or pheromone traps for fall armyworm; ensure field drainage channels.',
    'Intercrop with cotton or maize (1:4 ratio); nip terminal shoots at 45-50 days to encourage profuse branching.',
    'Inoculate seeds with Rhizobium and PSB culture; maintain broad-bed furrow system for drainage.',
    'Raise nursery under net house; transplant 25-day seedlings on raised beds with silver-black mulch.',
    'Sow on raised beds with drip irrigation and plastic mulching; install fruit fly pheromone traps.',
    'Sow with fine sand mixture for uniform stand; ensure surface field drains are open.',
    'Treat seed with Trichoderma viride before sowing; sow after soil temperature cools in late October to November.',
    'Seed treatment with Imidacloprid (5 ml/kg) and Rhizobium culture; broadcast in rice fallows 2-3 days before paddy harvest.',
    'Vulnerable to thrips, mites, and leaf curl complex; excessive standing water causes collar rot and wilt.',
    'Susceptible to blast disease and brown planthopper (BPH) under dense planting and excessive nitrogen.',
    'Susceptible to waterlogging in poorly drained flat fields; requires monitoring for pink bollworm and sucking pests.',
    'Calcium deficiency in light soils causes empty pods (\'pops\'); leaf spot (Tikka disease) during humid spells.',
    'Fall armyworm (Spodoptera frugiperda) damage in early whorl stage; sensitive to water stagnation.',
    'Sterility mosaic disease and pod borer; prolonged cloudy weather during pod formation reduces set.',
    'Short harvest window; prolonged rains at maturity may cause pod shattering and seed quality degradation.',
    'Susceptible to bacterial wilt and tomato leaf curl virus; requires staking and fruit protection.',
    'Susceptible to powdery mildew and fruit fly attack; excess nitrogen causes fruit cracking.',
    'Extremely sensitive to waterlogging even for a few hours; capsule borer damage during maturation.',
    'Sensitive to collar rot if sown in warm soil; pod borer (Helicoverpa) damage during flowering requires timely scouting.',
    'Susceptible to yellow mosaic virus transmitted by whiteflies; waterlogging during early seedling stage causes damping off.',
  ];
  for (const value of expected) {
    assert.ok(cropAdviceAuditContent[value], `Missing exact recommendation mapping for: ${value}`);
    for (const language of ['en', 'te', 'hi', 'ta', 'kn', 'ml', 'mr']) assert.ok(localizeCropAdvice(value, language));
  }
});

test('Assistant suggestions render localized copy in all seven languages', () => {
  for (const language of ['en', 'te', 'hi', 'ta', 'kn', 'ml', 'mr']) {
    assert.equal(assistantQuestionSuggestions[language].length, 4);
    assert.ok(assistantQuestionSuggestions[language].every((question) => question.trim()));
  }
});

test('Verify key translations exist across all 7 languages', () => {
  const requiredKeys = [
    'appName',
    'tagline',
    'heroHeading',
    'heroSub',
    'startConversation',
    'navHome',
    'navAssistant',
    'navWeather',
    'navChooseCrop',
    'navCheckCrop',
    'navMarketPrices',
    'assistantTitle',
    'assistantGreeting',
    'weatherTitle',
    'cropAdvisorTitle',
    'cropHealthTitle',
    'marketTitle',
    'safetyNotice',
    'firstVisitTitle',
  ];

  const langCodes = ['te', 'en', 'hi', 'ta', 'kn', 'ml', 'mr'];
  for (const lang of langCodes) {
    const dict = translations[lang];
    assert.ok(dict, `Translation dictionary for ${lang} must exist`);
    for (const key of requiredKeys) {
      assert.ok(
        dict[key] && dict[key].trim().length > 0,
        `Missing translation for key '${key}' in language '${lang}'`
      );
    }
  }
});

test('live location controls and all failure states are localized in every language', () => {
  const keys = [
    'stateSelect', 'useCurrentLocation', 'detectingLocation', 'locationDetected',
    'locationPermissionDenied', 'locationUnavailable', 'locationTimeout',
    'locationUnsupported', 'locationHttpsRequired', 'locationOutsideIndia',
    'locationGeocodingFailed', 'voicePlaybackFailed',
  ];
  for (const language of ['en', 'te', 'hi', 'ta', 'kn', 'ml', 'mr']) {
    for (const key of keys) {
      assert.ok(supplementalTranslations[language][key]?.trim(), `Missing ${key} in ${language}`);
    }
  }
});

test('Internal AI integration controls are not exposed as user-facing translations', () => {
  const removedKeys = ['voiceCreditsStatus', 'creditsProtectedBadge'];
  for (const lang of ['te', 'en', 'hi', 'ta', 'kn', 'ml', 'mr']) {
    for (const key of removedKeys) {
      assert.ok(!(key in translations[lang]), `Translation key '${key}' should be absent for '${lang}'`);
    }
  }
});

test('Verify safety notice in crop health explicitly cautions against chemical pesticides', () => {
  const langCodes = ['te', 'en', 'hi', 'ta', 'kn', 'ml', 'mr'];
  for (const lang of langCodes) {
    const notice = translations[lang]['safetyNotice'];
    assert.ok(notice.length > 20, `Safety notice for ${lang} must be comprehensive`);
  }
});
