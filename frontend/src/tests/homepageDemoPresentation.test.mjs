import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');

test('English homepage copy follows the supplied Kisan Hita artifact and keeps feature navigation', () => {
  const page = read('../pages/HomePage.tsx');
  const translations = read('../i18n/translations.ts');
  assert.match(translations, /heroHeading: "KISAN HITA"/);
  for (const exactArtifactCopy of [
    'Cinematic AI for Indian farmers',
    'Empowering Indian farmers with technology that listens.',
    'Making agricultural knowledge more accessible through the power of voice.',
    'Discover Kisan Hita',
    'Every field has a story. Every farmer deserves answers.',
    'A simpler way to access agricultural knowledge.',
  ]) assert.ok(page.includes(exactArtifactCopy), `Missing homepage reference text: ${exactArtifactCopy}`);
  assert.match(page, /onSelectTab\(card\.id\)/);
  assert.match(page, /openAssistant\(\)/);
});

test('navbar no longer renders the boxed app-name brand and preserves assistant/navigation controls', () => {
  const navbar = read('../components/Navbar.tsx');
  assert.doesNotMatch(navbar, /\{t\('appName'\)\}/);
  assert.match(navbar, /toggleAssistant/);
  assert.match(navbar, /navItems\.map/);
});

test('hero heading uses a bounded responsive scale for every localized script', () => {
  const css = read('../index.css');
  const translations = read('../i18n/translations.ts');
  assert.match(css, /\.home-hero-title\s*\{[\s\S]*?font-size:\s*clamp\(2\.7rem,\s*6vw,\s*5\.8rem\)/);
  assert.match(css, /\.home-hero-title\s*\{[\s\S]*?line-height:\s*1\.04/);
  assert.match(css, /\.home-hero-title\s*\{[\s\S]*?max-width:\s*min\(100%,\s*15ch\)/);
  assert.match(css, /\.home-hero-title\s*\{[\s\S]*?text-wrap:\s*balance/);
  for (const language of ['te', 'en', 'hi', 'ta', 'kn', 'ml', 'mr']) {
    assert.match(translations, new RegExp(`${language}:\\s*\\{[\\s\\S]*?heroHeading:`));
  }
});

test('weather uses live API requests while the local illustrative market UI remains separately disclosed', () => {
  const weather = read('../pages/WeatherPage.tsx');
  const market = read('../pages/MarketPricesPage.tsx');
  assert.match(weather, /new URLSearchParams\(\{ district, state, language \}\)/);
  assert.match(weather, /weatherConfigurationMissing/);
  assert.match(weather, /weatherData\.condition_icon_url/);
  assert.match(weather, /weatherData\.wind_direction/);
  assert.match(weather, /weatherData\.visibility_km/);
  assert.doesNotMatch(weather, /weatherDemo(Label|Notice)|DEMO DATA/);
  assert.match(market, /params\.append\('commodity', comm\.trim\(\)\)/);
  assert.match(market, /params\.append\('state', st\)/);
  assert.match(market, /params\.append\('district', dist\)/);
  assert.match(market, /marketIllustrativeDisclosure/);
  assert.match(market, /list=\"market-commodity-options\"/);
  assert.doesNotMatch(market, /data\.gov\.in|AGMARKNET|rec\.source_url/);
});

test('scroll-scrub assets and touch-responsive playback remain enabled with a brighter image treatment', () => {
  const component = read('../components/ScrollScrubBackground.tsx');
  const css = read('../index.css');
  assert.match(component, /kisan-hita-scroll\.mp4/);
  assert.match(component, /easeScrollProgress\(current, target, mobile/);
  assert.match(component, /shouldSeekFrame\(seconds, lastSeek, mobile\)/);
  assert.match(component, /playsInline/);
  assert.match(css, /brightness\(1\.08\) saturate\(1\.08\)/);
  assert.match(css, /max-width: 760px\) and \(orientation: portrait\)/);
});

test('homepage story glass section fits its text without fixed-height whitespace on desktop or mobile', () => {
  const css = read('../index.css');
  const referenceSection = css.match(/\.home-story-reference\s*\{[^}]+\}/)?.[0] || '';
  assert.match(referenceSection, /min-height:\s*0/);
  assert.match(referenceSection, /padding-block:\s*clamp\(1\.75rem, 4vh, 3rem\)/);
  assert.match(css, /\.home-story-reference \.home-story-content > div \{ margin-bottom: 0 !important; \}/);
  assert.match(css, /\.home-story-reference h2 \{ margin-bottom: \.45rem !important; \}/);
  assert.match(css, /\.home-story-reference \.home-artifact-copy:last-child \{ margin-bottom: 0; \}/);
  assert.match(css, /\.home-story-reference \{ min-height: 0; padding-block: 1\.5rem; \}/);
  assert.match(css, /background: linear-gradient\(90deg, rgba\(22, 23, 15, \.88\), rgba\(22, 23, 15, \.68\)\)/);
  assert.match(css, /backdrop-filter: blur\(8px\)/);
});
