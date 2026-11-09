import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createNonSecurityUuid, getOrCreateConversationId } from '../services/nonSecurityIds.ts';

test('prefers crypto.randomUUID when the browser provides it', () => {
  const cryptoApi = {
    randomUUID: () => '123e4567-e89b-42d3-a456-426614174000',
    getRandomValues: () => { throw new Error('must not be called'); },
  };
  assert.equal(createNonSecurityUuid(cryptoApi), '123e4567-e89b-42d3-a456-426614174000');
});

test('generates a UUID v4 from getRandomValues when randomUUID is unavailable', () => {
  const cryptoApi = {
    getRandomValues: (bytes) => {
      bytes.fill(0);
      return bytes;
    },
  };
  const id = createNonSecurityUuid(cryptoApi);
  assert.match(id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
});

test('uses a documented non-security fallback when browser crypto APIs are absent', () => {
  const first = createNonSecurityUuid({});
  const second = createNonSecurityUuid({});
  assert.match(first, /^local-[a-z0-9]+-[a-z0-9]+-[a-z0-9]+$/);
  assert.notEqual(first, second);
});

test('conversation ID is generated once, persisted, and reused on subsequent provider initialization', () => {
  const values = new Map();
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
  let generated = 0;
  const cryptoApi = { randomUUID: () => `00000000-0000-4000-8000-${String(++generated).padStart(12, '0')}` };

  const firstInitialization = getOrCreateConversationId(storage, 'kisan_hita_conversation_id', cryptoApi);
  const secondInitialization = getOrCreateConversationId(storage, 'kisan_hita_conversation_id', cryptoApi);
  assert.equal(firstInitialization, secondInitialization);
  assert.equal(generated, 1);

  const source = readFileSync(new URL('../context/AssistantContext.tsx', import.meta.url), 'utf8');
  assert.match(source, /useState<string>\(\(\) => getConversationId\(isGuest, guestContextId\)\)/);
  assert.match(source, /storageKeys\.conversation/);
  assert.doesNotMatch(source, /crypto\.randomUUID\(/);
});

test('clearing the assistant conversation still creates and saves one replacement ID', () => {
  const source = readFileSync(new URL('../context/AssistantContext.tsx', import.meta.url), 'utf8');
  assert.match(source, /const nextConversationId = `conv_\$\{createNonSecurityUuid\(\)\.replace\(/);
  assert.match(source, /storage\.setItem\(storageKeys\.conversation, nextConversationId\)/);
  assert.match(source, /setConversationId\(nextConversationId\)/);
});
