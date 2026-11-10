import test from 'node:test';
import assert from 'node:assert/strict';
import { easeScrollProgress, getScrollProgress, getVideoTime, shouldSeekFrame, ScrollScrubRuntime } from '../services/scrollScrub.ts';
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
  assert.match(component, /preload="metadata"/);
  assert.match(component, /reducedMotion: \(\) => reducedMotionQuery\.matches/);
  assert.match(component, /prefers-reduced-motion:\s*reduce/);
  assert.match(component, /window\.visualViewport\?\.addEventListener\('resize'/);
  assert.doesNotMatch(component, /video\.play\(/);
  const runtime = readFileSync(new URL('../services/scrollScrub.ts', import.meta.url), 'utf8');
  assert.match(runtime, /loadedmetadata/);
  assert.match(runtime, /loadeddata/);
  assert.match(runtime, /canplay/);
  assert.match(runtime, /pageshow/);
  assert.match(runtime, /popstate/);
  assert.match(runtime, /video\.seeking/);
  assert.match(runtime, /scheduleSeekRetry/);
  assert.match(runtime, /removeEventListener\('scroll'/);
  const css = readFileSync(new URL('../index.css', import.meta.url), 'utf8');
  assert.doesNotMatch(css, /prefers-reduced-motion:\s*reduce\)\s*\{\s*\.scroll-scrub-background__video\s*\{\s*visibility:\s*hidden/);
});

class FakeVideo extends EventTarget {
  duration = 10;
  readyState = 0;
  networkState = 0;
  seeking = false;
  loadCount = 0;
  pauseCount = 0;
  values = [];
  failNextSeek = false;
  _currentTime = 0;
  get currentTime() { return this._currentTime; }
  set currentTime(value) {
    if (this.failNextSeek) {
      this.failNextSeek = false;
      throw new Error('decoder not ready');
    }
    this._currentTime = value;
    this.values.push(value);
  }
  load() { this.loadCount += 1; }
  pause() { this.pauseCount += 1; }
}

const makeRuntime = ({ video = new FakeVideo(), events = new EventTarget(), progress = () => 0, motion = () => false } = {}) => {
  const frames = new Map();
  const timers = [];
  let nextFrame = 1;
  const runtime = new ScrollScrubRuntime({
    video,
    events,
    readProgress: progress,
    mobile: () => false,
    reducedMotion: motion,
    onUnavailable: () => {},
    requestFrame: (callback) => { const id = nextFrame++; frames.set(id, callback); return id; },
    cancelFrame: (id) => frames.delete(id),
    setTimer: (callback) => { const timer = { callback }; timers.push(timer); return timer; },
    clearTimer: (timer) => { const index = timers.indexOf(timer); if (index >= 0) timers.splice(index, 1); },
  });
  const flushFrames = (limit = 100) => {
    let count = 0;
    while (frames.size && count++ < limit) {
      const [id, callback] = frames.entries().next().value;
      frames.delete(id);
      callback(0);
    }
    return count;
  };
  return { runtime, video, events, frames, timers, flushFrames };
};

test('delayed metadata syncs to the latest scroll, including scrolls before video readiness', () => {
  let progress = 0;
  const { runtime, video, events } = makeRuntime({ progress: () => progress });
  runtime.mount();
  assert.equal(video.loadCount, 0);
  progress = 0.65;
  events.dispatchEvent(new Event('scroll'));
  assert.equal(video.loadCount, 1);
  assert.deepEqual(video.values, []);
  video.readyState = 1;
  video.dispatchEvent(new Event('loadedmetadata'));
  assert.equal(video.currentTime, 6.5);
  runtime.destroy();
});

test('already-ready cached video initializes immediately and browser history events resync', () => {
  let progress = 0.25;
  const { runtime, video, events, flushFrames } = makeRuntime({ video: Object.assign(new FakeVideo(), { readyState: 2 }), progress: () => progress });
  runtime.mount();
  assert.equal(video.currentTime, 2.5);
  assert.equal(video.loadCount, 0);
  flushFrames();
  progress = 0.7;
  events.dispatchEvent(new Event('pageshow'));
  flushFrames();
  assert.ok(Math.abs(video.currentTime - 7) < 0.01);
  runtime.destroy();
});

test('repeated mount/unmount cycles release media listeners and animation frames', () => {
  const video = Object.assign(new FakeVideo(), { readyState: 1 });
  const events = new EventTarget();
  for (let i = 0; i < 4; i += 1) {
    const { runtime, frames } = makeRuntime({ video, events });
    runtime.mount();
    assert.equal(video.pauseCount > 0, true);
    const assignedBeforeUnmount = video.values.length;
    runtime.destroy();
    assert.equal(frames.size, 0);
    video.dispatchEvent(new Event('loadeddata'));
    assert.equal(video.values.length, assignedBeforeUnmount);
  }
});

test('scroll scrubbing follows forward and backward movement and reduced motion jumps to target', () => {
  let progress = 0;
  let reduced = false;
  const { runtime, video, events, flushFrames } = makeRuntime({ progress: () => progress, motion: () => reduced });
  runtime.mount();
  video.readyState = 1;
  video.dispatchEvent(new Event('canplay'));
  progress = 0.8;
  events.dispatchEvent(new Event('scroll'));
  flushFrames();
  const forward = video.currentTime;
  progress = 0.2;
  events.dispatchEvent(new Event('scroll'));
  flushFrames();
  assert.ok(video.currentTime < forward);
  reduced = true;
  progress = 0.6;
  events.dispatchEvent(new Event('scroll'));
  flushFrames();
  assert.equal(video.currentTime, 6);
  runtime.destroy();
});

test('transient seek failures retry; actual video load errors use the poster fallback', () => {
  let progress = 0;
  const { runtime, video, events, timers, flushFrames } = makeRuntime({
    video: Object.assign(new FakeVideo(), { readyState: 1 }),
    progress: () => progress,
    motion: () => true,
  });
  runtime.mount();
  video.failNextSeek = true;
  progress = 0.4;
  events.dispatchEvent(new Event('scroll'));
  flushFrames();
  assert.equal(timers.length, 1);
  timers.shift().callback();
  flushFrames();
  assert.equal(video.currentTime, 4);
  runtime.destroy();

  let unavailable = 0;
  const broken = new FakeVideo();
  const brokenRuntime = new ScrollScrubRuntime({
    video: broken,
    events: new EventTarget(),
    readProgress: () => 0,
    mobile: () => false,
    reducedMotion: () => false,
    onUnavailable: () => { unavailable += 1; },
    requestFrame: () => 1,
    cancelFrame: () => {},
  });
  brokenRuntime.mount();
  broken.dispatchEvent(new Event('error'));
  assert.equal(unavailable, 1);
  brokenRuntime.destroy();
});
