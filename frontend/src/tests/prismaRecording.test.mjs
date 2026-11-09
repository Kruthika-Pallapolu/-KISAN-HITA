import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { PrismaManualRecorder, uploadPrismaRecording } from '../services/prismaRecording.ts';

test('Prisma manual recording uses only an API-documented media type and releases the microphone', async () => {
  const oldRecorder = globalThis.MediaRecorder;
  const oldNavigator = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
  let stoppedTracks = 0;
  class FakeMediaRecorder {
    static isTypeSupported(type) { return type === 'audio/mp4'; }
    state = 'inactive';
    constructor(stream, options) { this.stream = stream; this.mimeType = options.mimeType; }
    start() { this.state = 'recording'; }
    stop() {
      this.state = 'inactive';
      this.ondataavailable?.({ data: new Blob(['audio'], { type: this.mimeType }) });
      this.onstop?.();
    }
  }
  const stream = { getTracks: () => [{ stop() { stoppedTracks += 1; } }] };
  Object.defineProperty(globalThis, 'MediaRecorder', { configurable: true, value: FakeMediaRecorder });
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { mediaDevices: { getUserMedia: async () => stream } } });
  try {
    const recorder = new PrismaManualRecorder();
    await recorder.start();
    await new Promise((resolve) => setTimeout(resolve, 5));
    const result = await recorder.stop();
    assert.equal(result.mimeType, 'audio/mp4');
    assert.equal(result.filename, 'recording.m4a');
    assert.ok(result.durationSeconds > 0);
    assert.equal(stoppedTracks, 1);
  } finally {
    if (oldRecorder === undefined) delete globalThis.MediaRecorder;
    else Object.defineProperty(globalThis, 'MediaRecorder', { configurable: true, value: oldRecorder });
    if (oldNavigator) Object.defineProperty(globalThis, 'navigator', oldNavigator);
    else delete globalThis.navigator;
  }
});

test('Prisma upload sends the correct manual multipart contract and validates transcript', async () => {
  let request;
  const transcript = await uploadPrismaRecording({
    blob: new Blob(['mock audio'], { type: 'audio/mp4' }),
    mimeType: 'audio/mp4', filename: 'recording.m4a', durationSeconds: 1.2,
  }, 'te', async (url, options) => {
    request = { url, options };
    return { ok: true, json: async () => ({ transcript: 'రేపు వర్షం పడుతుందా?' }) };
  });
  assert.equal(request.url, '/api/voice/stt/upload');
  assert.equal(request.options.method, 'POST');
  assert.equal(request.options.credentials, 'same-origin');
  const form = request.options.body;
  assert.equal(form.get('language'), 'te');
  assert.equal(form.get('duration_seconds'), '1.2');
  assert.equal(form.get('file').name, 'recording.m4a');
  assert.equal(transcript, 'రేపు వర్షం పడుతుందా?');
});

test('Prisma client rejects overlong clips before making a request', async () => {
  let calls = 0;
  await assert.rejects(() => uploadPrismaRecording({
    blob: new Blob(['sample']), mimeType: 'audio/mp4', filename: 'clip.m4a', durationSeconds: 30.1,
  }, 'en', async () => { calls += 1; }), /up to 30 seconds/);
  assert.equal(calls, 0);
});

test('Prisma frontend hands only the returned transcript to existing assistant chat without a wake-listener dependency', () => {
  const context = readFileSync(new URL('../context/AssistantContext.tsx', import.meta.url), 'utf8');
  assert.match(context, /uploadPrismaRecording\(recording, language\)/);
  assert.match(context, /sendMessage\(transcript/);
  assert.doesNotMatch(context, /wakeWord|requestWakeMicrophoneYield|returnWakeMicrophone/);
});
