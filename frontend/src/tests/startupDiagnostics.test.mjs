import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadConfigFromFile } from 'vite';

test('startup diagnostics are injected before modules in dev and omitted from production HTML', async () => {
  const configPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../vite.config.ts');
  const loaded = await loadConfigFromFile({ command: 'serve', mode: 'development' }, configPath);
  assert.ok(loaded, 'Vite config should load');
  const diagnostics = loaded.config.plugins.find((plugin) => plugin.name === 'kisan-hita-startup-diagnostics');
  assert.ok(diagnostics, 'diagnostic plugin should be registered');
  const transform = diagnostics.transformIndexHtml.handler;
  const html = '<html><head></head><body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body></html>';

  const devHtml = await transform(html, { server: {} });
  assert.ok(devHtml.includes('kh-dev-startup-diagnostics'));
  assert.ok(devHtml.indexOf('</script>') < devHtml.indexOf('<script type="module"'), 'diagnostics script must precede the app module');
  assert.ok(devHtml.includes('Unhandled promise rejection'));
  assert.ok(devHtml.includes('No React mount confirmation after 20 seconds'));
  assert.ok(devHtml.includes('requested-but-no-load-or-error-event'));
  assert.ok(devHtml.includes('moduleResources'));
  assert.ok(devHtml.includes('entry module script observed; request may be in progress'));
  const inlineScript = devHtml.match(/<script>([\s\S]*?)<\/script>/)?.[1];
  assert.ok(inlineScript, 'development diagnostics should be emitted as an early inline script');
  assert.doesNotThrow(() => new Function(inlineScript), 'diagnostic script should parse in browsers');

  const productionHtml = await transform(html, {});
  assert.equal(productionHtml, html, 'diagnostic overlay must not be included in production output');
});
