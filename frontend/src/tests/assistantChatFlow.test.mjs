import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { AssistantHttpError, AssistantResponseError, requestAssistantReply } from '../services/assistantChatApi.ts';

test('voice chat uses the real assistant endpoint contract and accepts its actual response shape', async () => {
  let observed;
  const payload = {
    message: 'What is the weather tomorrow?',
    conversation_id: 'conv_voice_test',
    language: 'en',
    farm_context: { district: 'Nellore', state: 'Andhra Pradesh' },
  };
  const result = await requestAssistantReply(payload, async (url, options) => {
    observed = { url, options };
    return new Response(JSON.stringify({
      reply_text: 'I need your district to check a forecast.',
      conversation_id: 'conv_voice_test',
      intent: 'weather',
      routed_feature: 'weather',
    }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  });
  assert.equal(observed.url, '/api/assistant/chat');
  assert.equal(observed.options.method, 'POST');
  assert.equal(observed.options.credentials, 'same-origin');
  assert.deepEqual(JSON.parse(observed.options.body), payload);
  assert.equal(result.reply_text, 'I need your district to check a forecast.');
});

test('HTTP failures and empty or malformed assistant replies become explicit errors', async () => {
  await assert.rejects(
    requestAssistantReply({ message: 'Question', conversation_id: 'c1', language: 'te' }, async () => new Response(JSON.stringify({ detail: 'Sign in required' }), { status: 401 })),
    (error) => error instanceof AssistantHttpError && error.status === 401 && error.detail === 'Sign in required',
  );
  await assert.rejects(
    requestAssistantReply({ message: 'Question', conversation_id: 'c1', language: 'te' }, async () => new Response(JSON.stringify({ reply_text: '  ' }), { status: 200 })),
    AssistantResponseError,
  );
  await assert.rejects(
    requestAssistantReply({ message: 'Question', conversation_id: 'c1', language: 'te' }, async () => new Response('not json', { status: 200 })),
  );
});

test('AssistantContext displays the recognized question and backend reply, speaks it, and shows localized failures', () => {
  const source = readFileSync(new URL('../context/AssistantContext.tsx', import.meta.url), 'utf8');
  assert.match(source, /sender: 'user',[\s\S]*text: trimmed/);
  assert.match(source, /sender: 'assistant',[\s\S]*text: data\.reply_text/);
  assert.match(source, /speakText\(data\.reply_text, options\)/);
  assert.match(source, /options\.onAssistantReply\?\.\(data\.pending_workflow \|\| null, data\.reply_text\)/);
  assert.match(source, /assistantResponseInvalid/);
  assert.match(source, /voiceServerUnavailable/);
});
