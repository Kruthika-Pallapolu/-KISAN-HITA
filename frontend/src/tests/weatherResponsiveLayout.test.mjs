import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');

test('weather location selectors stack and stay inside the toolbar at narrow phone widths', () => {
  const component = read('../components/FarmLocationFields.tsx');
  const weather = read('../pages/WeatherPage.tsx');
  const css = read('../index.css');
  assert.match(component, /farm-location-fields--inline/);
  assert.match(weather, /className="weather-location-toolbar"/);
  assert.match(css, /@media \(max-width: 760px\)/);
  assert.match(css, /\.weather-page \.farm-location-fields--inline\s*\{[^}]*flex-direction: column !important/);
  assert.match(css, /\.weather-page \.farm-location-fields--inline \.farm-location-fields__field\s*\{[^}]*width: 100%[^}]*min-width: 0 !important/);
  assert.match(css, /\.weather-page \.farm-location-fields--inline \.select-field\s*\{[^}]*width: 100% !important[^}]*min-width: 0 !important/);
  assert.match(css, /\.weather-page \.weather-location-toolbar\s*\{[^}]*align-items: stretch/);
  // 320px and 375px phone widths use the mobile breakpoint; 1024px retains
  // the component's inline row layout because that rule is scoped to mobile.
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*?\.weather-page \.farm-location-fields--inline/);
  assert.match(component, /flexDirection: layout === 'inline' \? 'row' : 'column'/);
});

test('other weather toolbar and content controls wrap on mobile without fixed-width spill', () => {
  const css = read('../index.css');
  const weather = read('../pages/WeatherPage.tsx');
  assert.match(css, /\.weather-page \.weather-location-actions\s*\{[^}]*flex-wrap: wrap/);
  assert.match(css, /\.weather-page \.weather-error-banner\s*\{\s*flex-wrap: wrap/);
  assert.match(css, /\.weather-page \.weather-guidance-grid\s*\{\s*grid-template-columns: minmax\(0, 1fr\)/);
  assert.match(weather, /weather-current-reading/);
  assert.match(weather, /weather-guidance-grid/);
  assert.match(weather, /gridTemplateColumns: 'repeat\(auto-fit, minmax\(130px, 1fr\)\)'/);
});
