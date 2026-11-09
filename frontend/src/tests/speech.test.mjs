import test from 'node:test';
import assert from 'node:assert/strict';
import { splitSpeechText, SpeechService } from '../services/speech.ts';
import { readFileSync } from 'node:fs';

test('long multilingual responses split under the API limit without losing content', () => {
  const text = `తెలుగు వాక్యం ${'రైతు సమాచారం '.repeat(230)}. English sentence ${'farm guidance '.repeat(130)}!`;
  const chunks = splitSpeechText(text, 600);
  assert.ok(chunks.length > 1);
  assert.ok(chunks.every((chunk) => chunk.length <= 600));
  assert.equal(chunks.join(' '), text);
});

test('assistant voice input uses Prisma only; browser SpeechRecognition STT is absent', () => {
  const speech = readFileSync(new URL('../services/speech.ts', import.meta.url), 'utf8');
  const context = readFileSync(new URL('../context/AssistantContext.tsx', import.meta.url), 'utf8');
  const modal = readFileSync(new URL('../components/KisanAssistantModal.tsx', import.meta.url), 'utf8');
  const page = readFileSync(new URL('../pages/AskKisanHitaPage.tsx', import.meta.url), 'utf8');
  assert.doesNotMatch(speech, /SpeechRecognition|webkitSpeechRecognition|VoiceRecognitionService/);
  assert.doesNotMatch(context, /VoiceRecognitionService|startVoiceInput|stopVoiceInput/);
  assert.match(modal, /startPrismaVoiceInput/);
  assert.match(modal, /disabled=\{isProcessing \|\| !prismaEnabled \|\| !voiceConfigLoaded\}/);
  assert.doesNotMatch(modal, /startVoiceInput|stopVoiceInput|SpeechRecognition/);
  assert.doesNotMatch(page, /<Mic|startVoiceInput|stopVoiceInput/);
});

test('backend audio playback starts and ends through the browser Audio element', async () => {
  const oldWindow = globalThis.window;
  const oldAudio = globalThis.Audio;
  const oldFetch = globalThis.fetch;
  const audioInstances = [];
  class FakeAudio {
    constructor(url) { this.url = url; this.playCalls = 0; audioInstances.push(this); }
    play() { this.playCalls += 1; queueMicrotask(() => { this.onplay?.(); this.onended?.(); }); return Promise.resolve(); }
    pause() {}
  }
  globalThis.Audio = FakeAudio;
  globalThis.fetch = async (url) => url.endsWith('/config')
    ? ({ ok: true, json: async () => ({ timbre_enabled: false }) })
    : ({ ok: true, json: async () => ({ audio_base64: 'A'.repeat(80), format: 'audio/wav', language: 'en' }) });
  globalThis.window = { speechSynthesis: { cancel() {}, getVoices: () => [{ lang: 'en-IN' }], speak() {} } };
  try {
    let started = 0;
    let ended = 0;
    let errored = 0;
    await SpeechService.speak('Namaste', 'en', () => started++, () => ended++, () => errored++);
    assert.equal(audioInstances[0].playCalls, 1);
    assert.equal(started, 1);
    assert.equal(ended, 1);
    assert.equal(errored, 0);
  } finally {
    SpeechService.stop();
    globalThis.window = oldWindow;
    globalThis.Audio = oldAudio;
    globalThis.fetch = oldFetch;
  }
});

test('audio playback rejection falls back to browser speech synthesis', async () => {
  const oldWindow = globalThis.window;
  const oldAudio = globalThis.Audio;
  const oldFetch = globalThis.fetch;
  const oldUtterance = globalThis.SpeechSynthesisUtterance;
  let utterance;
  class FakeAudio {
    constructor() { this.onplay = null; this.onended = null; this.onerror = null; }
    play() { return Promise.reject(new Error('autoplay blocked')); }
    pause() {}
  }
  class FakeUtterance {
    constructor(text) { this.text = text; utterance = this; }
  }
  globalThis.Audio = FakeAudio;
  globalThis.SpeechSynthesisUtterance = FakeUtterance;
  globalThis.fetch = async (url) => url.endsWith('/config')
    ? ({ ok: true, json: async () => ({ timbre_enabled: false }) })
    : ({ ok: true, json: async () => ({ audio_base64: 'A'.repeat(80), format: 'audio/wav', language: 'en' }) });
  globalThis.window = { speechSynthesis: { cancel() {}, getVoices: () => [{ lang: 'en-IN' }], speak() {} } };
  const oldWarn = console.warn;
  console.warn = () => {};
  try {
    let started = 0;
    let ended = 0;
    const speech = SpeechService.speak('Namaste', 'en', () => started++, () => ended++);
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(utterance.text, 'Namaste');
    utterance.onstart();
    utterance.onend();
    await speech;
    assert.equal(started, 1);
    assert.equal(ended, 1);
  } finally {
    console.warn = oldWarn;
    SpeechService.stop();
    globalThis.window = oldWindow;
    globalThis.Audio = oldAudio;
    globalThis.fetch = oldFetch;
    globalThis.SpeechSynthesisUtterance = oldUtterance;
  }
});

test('browser fallback uses a matching selected-language voice and reports unsupported TTS honestly', async () => {
  const oldWindow = globalThis.window;
  const oldAudio = globalThis.Audio;
  const oldFetch = globalThis.fetch;
  const oldUtterance = globalThis.SpeechSynthesisUtterance;
  let spoken = 0;
  let utterance;
  class FakeAudio { play() { queueMicrotask(() => { this.onplay?.(); this.onended?.(); }); return Promise.resolve(); } pause() {} }
  class FakeUtterance { constructor(text) { this.text = text; utterance = this; } }
  globalThis.Audio = FakeAudio;
  globalThis.SpeechSynthesisUtterance = FakeUtterance;
  globalThis.fetch = async (url) => url.endsWith('/config')
    ? ({ ok: true, json: async () => ({ timbre_enabled: false }) })
    : ({ ok: true, json: async () => ({ audio_base64: 'A'.repeat(80), format: 'audio/wav', language: 'hi' }) });
  globalThis.window = { speechSynthesis: {
    cancel() {}, getVoices: () => [{ lang: 'te-IN' }], speak() { spoken += 1; },
  } };
  try {
    let playbackError;
    let ended = 0;
    const supported = SpeechService.speak('నమస్కారం', 'te', undefined, () => ended++, (error) => { playbackError = error; });
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(spoken, 1);
    assert.equal(utterance.lang, 'te-IN');
    assert.equal(utterance.voice.lang, 'te-IN');
    utterance.onend();
    await supported;
    assert.equal(ended, 1);
    assert.equal(playbackError, undefined);

    globalThis.window.speechSynthesis.getVoices = () => [{ lang: 'en-IN' }];
    playbackError = undefined;
    ended = 0;
    const unsupported = SpeechService.speak('నమస్కారం', 'te', undefined, () => ended++, (error) => { playbackError = error; });
    await new Promise((resolve) => setImmediate(resolve));
    await unsupported;
    assert.match(playbackError.message, /No browser speech voice is available for te-IN/);
    assert.equal(ended, 1);
    assert.equal(spoken, 1, 'must not speak the Telugu answer with an English voice');
  } finally {
    SpeechService.stop();
    globalThis.window = oldWindow;
    globalThis.Audio = oldAudio;
    globalThis.fetch = oldFetch;
    globalThis.SpeechSynthesisUtterance = oldUtterance;
  }
});

test('Timbre plays every bounded chunk in order and uses Vasudha for all seven selected languages', async () => {
  const oldWindow = globalThis.window;
  const oldAudio = globalThis.Audio;
  const oldFetch = globalThis.fetch;
  const calls = [];
  const played = [];
  class FakeAudio {
    constructor(url) { this.url = url; }
    play() { played.push(this.url); queueMicrotask(() => { this.onplay?.(); this.onended?.(); }); return Promise.resolve(); }
    pause() {}
  }
  globalThis.Audio = FakeAudio;
  globalThis.window = { speechSynthesis: { cancel() {}, getVoices: () => [{ lang: 'en-IN' }], speak() { assert.fail('must not silently fall back from Timbre'); } } };
  globalThis.fetch = async (url, options) => {
    if (url.endsWith('/config')) return { ok: true, json: async () => ({ timbre_enabled: true }) };
    const payload = JSON.parse(options.body);
    calls.push(payload);
    return { ok: true, json: async () => ({
      audio_base64: 'A'.repeat(80), format: 'audio/wav', language: payload.language,
      provider: 'gnani_live', model: 'timbre-v3.0', voice_name: 'Vasudha',
    }) };
  };
  try {
    const longText = `తెలుగు వాక్యం ${'రైతు సమాచారం '.repeat(210)}. English sentence ${'farm guidance '.repeat(120)}!`;
    let ended = 0;
    await SpeechService.speak(longText, 'te', undefined, () => ended++);
    const normalized = longText.replace(/[*#_~`[\]()]/g, '').replace(/\n+/g, '. ').trim();
    assert.ok(calls.length > 1);
    assert.ok(calls.every((call) => call.text.length <= 1800 && call.language === 'te'));
    assert.equal(calls.map((call) => call.text).join(' '), normalized);
    assert.equal(played.length, calls.length);
    assert.equal(ended, 1);

    calls.length = 0;
    played.length = 0;
    for (const language of ['en', 'te', 'hi', 'ta', 'kn', 'ml', 'mr']) {
      await SpeechService.speak('A short response.', language);
    }
    assert.deepEqual(calls.map((call) => call.language), ['en', 'te', 'hi', 'ta', 'kn', 'ml', 'mr']);
    assert.ok(calls.every((call) => call.text === 'A short response.'));
  } finally {
    SpeechService.stop();
    globalThis.window = oldWindow;
    globalThis.Audio = oldAudio;
    globalThis.fetch = oldFetch;
  }
});

test('Timbre errors are surfaced and do not invoke browser voice fallback', async () => {
  const oldWindow = globalThis.window;
  const oldFetch = globalThis.fetch;
  let browserSpeechCalls = 0;
  globalThis.window = { speechSynthesis: { cancel() {}, getVoices: () => [{ lang: 'te-IN' }], speak() { browserSpeechCalls += 1; } } };
  globalThis.fetch = async (url) => url.endsWith('/config')
    ? ({ ok: true, json: async () => ({ timbre_enabled: true }) })
    : ({ ok: false, status: 503, json: async () => ({ detail: 'provider unavailable' }) });
  try {
    let error;
    let ended = 0;
    await SpeechService.speak('నమస్కారం', 'te', undefined, () => ended++, (value) => { error = value; });
    assert.match(error.message, /HTTP 503/);
    assert.equal(browserSpeechCalls, 0);
    assert.equal(ended, 1);
  } finally {
    SpeechService.stop();
    globalThis.window = oldWindow;
    globalThis.fetch = oldFetch;
  }
});
