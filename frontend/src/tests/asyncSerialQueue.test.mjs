import test from 'node:test';
import assert from 'node:assert/strict';
import { AsyncSerialQueue } from '../services/asyncSerialQueue.ts';

test('assistant submissions stay separate and run once in click order', async () => {
  const queue = new AsyncSerialQueue();
  const requests = [];
  const questions = [
    'Will it rain tomorrow in my district?',
    'Which crop suits black cotton soil?',
    'Check current chilli mandi price',
    'Cotton leaves are turning yellow with spots',
  ];
  await Promise.all(questions.map((question) => queue.enqueue(async () => {
    requests.push(question);
  })));
  assert.deepEqual(requests, questions);
  assert.equal(new Set(requests).size, 4);
});

test('a failed submission does not prevent the next question from being sent', async () => {
  const queue = new AsyncSerialQueue();
  const sent = [];
  const failed = queue.enqueue(async () => { throw new Error('request failed'); });
  const next = queue.enqueue(async () => { sent.push('next'); });
  await assert.rejects(failed, /request failed/);
  await next;
  assert.deepEqual(sent, ['next']);
});
