import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');

test('hands-free wake assistant UI, permission flow and recognition service are removed', () => {
  const app = read('../App.tsx');
  const assistant = read('../components/KisanAssistantModal.tsx');
  const auth = read('../pages/AuthPage.tsx');
  const settings = read('../components/SettingsModal.tsx');
  const languageModal = read('../components/LanguageModal.tsx');
  const translations = read('../i18n/translations.ts');
  assert.doesNotMatch(app, /HeyKisanVoiceMode|heyKisanEnabled|hands-free-voice-widget/);
  assert.doesNotMatch(assistant, /heyKisanEnabled/);
  assert.doesNotMatch(auth, /wakePhrase|hands-free|hands‑free|microphone access/);
  assert.doesNotMatch(settings, /wakePhrase|wake phrase/i);
  assert.doesNotMatch(languageModal, /wakePhrase|VoiceRecognitionService|Microphone|microphone/);
  assert.doesNotMatch(translations, /heyKisan|wakePhrase/);
  assert.equal(existsSync(new URL('../components/HeyKisanVoiceMode.tsx', import.meta.url)), false);
  assert.equal(existsSync(new URL('../services/wakeWord.ts', import.meta.url)), false);
});

test('text assistant remains and the sole microphone control is Prisma input', () => {
  const assistant = read('../components/KisanAssistantModal.tsx');
  const context = read('../context/AssistantContext.tsx');
  const askPage = read('../pages/AskKisanHitaPage.tsx');
  assert.match(assistant, /handleSubmit/);
  assert.match(assistant, /startPrismaVoiceInput/);
  assert.match(context, /PrismaManualRecorder/);
  assert.match(context, /uploadPrismaRecording\(recording, language\)/);
  assert.doesNotMatch(context, /VoiceRecognitionService|startVoiceInput|stopVoiceInput/);
  assert.doesNotMatch(askPage, /<Mic|startVoiceInput|stopVoiceInput/);
});
