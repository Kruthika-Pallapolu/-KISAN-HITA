import test from 'node:test';
import assert from 'node:assert/strict';
import { easeScrollProgress, getScrollProgress, getVideoTime, shouldSeekFrame } from '../services/scrollScrub.ts';
import { readFileSync } from 'node:fs';

test('reference scroll progress maps the whole document into a clamped video timeline', () => {
  assert.equal(getScrollProgress(0, 2000, 1000), 0);
  assert.equal(getScrollProgress(500, 2000, 1000), 0.5);
  assert.equal(getScrollProgress(1200, 2000, 1000), 1);
  assert.equal(getScrollProgress(0, 500, 1000), 0);
  assert.equal(getVideoTime(1, 6), 5.95);
});

test('scroll interpolation retains the reference desktop/mobile easing and reduced-motion behavior', () => {
  assert.equal(easeScrollProgress(0, 1, false, false), 0.14);
  assert.equal(easeScrollProgress(0, 1, true, false), 0.22);
  assert.equal(easeScrollProgress(0, 1, true, true), 1);
  assert.equal(shouldSeekFrame(0.1, 0, false), true);
  assert.equal(shouldSeekFrame(0.1, 0, true), true);
  assert.equal(shouldSeekFrame(0.01, 0, false), false);
});

test('integrated background is muted, scroll-scrubbed, and uses both exact local assets', () => {
  const component = readFileSync(new URL('../components/ScrollScrubBackground.tsx', import.meta.url), 'utf8');
  assert.match(component, /kisan-hita-scroll\.mp4/);
  assert.match(component, /kisan-hita-sunset\.png/);
  assert.match(component, /muted/);
  assert.match(component, /video\.currentTime\s*=\s*seconds/);
  assert.match(component, /prefers-reduced-motion:\s*reduce/);
  assert.match(component, /easeScrollProgress\(current, target, mobile, reducedMotion\)/);
  assert.match(component, /if \(video\.seeking\) \{\s*scheduleFrame\(\);/);
  assert.match(component, /video\.pause\(\)/);
  assert.doesNotMatch(component, /video\.play\(/);
  assert.doesNotMatch(component, /reducedMotion\) video\.style\.visibility = 'hidden'/);
  assert.match(component, /removeEventListener\('scroll'/);
  const css = readFileSync(new URL('../index.css', import.meta.url), 'utf8');
  assert.doesNotMatch(css, /prefers-reduced-motion:\s*reduce\)\s*\{\s*\.scroll-scrub-background__video\s*\{\s*visibility:\s*hidden/);
});
