import assert from 'node:assert/strict';
import { test } from 'node:test';
import { Meeting } from '../src/meeting.ts';
import { createMockApi } from '../src/mock.ts';
import type { ListenResult } from '../src/api.ts';

function setup() {
  const api = createMockApi();
  const mic: boolean[] = [];
  const meeting = new Meeting(api, async enabled => { mic.push(enabled); }, () => {});
  return { api, meeting, mic };
}

test('phone and gestures share start, queue, mute, end and explicit send state', async () => {
  const { meeting, mic } = setup();
  await meeting.start();
  assert.equal(meeting.state.listening, true);
  await meeting.listenText('Bluebird and FCS');
  assert.equal(meeting.state.card?.term, 'BLUEBIRD');
  await meeting.queue();
  assert.equal(meeting.state.queued.length, 1);
  assert.match(meeting.state.notice, /Queued for Priya/);
  meeting.next();
  assert.equal(meeting.state.card?.term, 'FCS');
  await meeting.mute();
  assert.equal(meeting.state.card, null);
  await meeting.end();
  assert.equal(meeting.state.drafts.length, 1);
  assert.equal(meeting.state.sent.length, 0);
  await meeting.send(meeting.state.drafts[0].draft_id);
  assert.equal(meeting.state.sent.length, 1);
  assert.deepEqual(mic, [true, false]);
  meeting.dispose();
});

test('discard removes an ended draft and permits a new meeting', async () => {
  const { meeting } = setup();
  await meeting.start();
  await meeting.listenText('Bluebird');
  await meeting.queue();
  await meeting.end();
  const draftId = meeting.state.drafts[0].draft_id;
  await meeting.discard(draftId);
  assert.deepEqual(meeting.state.drafts, []);
  await meeting.start();
  assert.equal(meeting.state.phase, 'active');
  meeting.dispose();
});

test('card expiry advances after eight seconds and queue feedback lasts two seconds', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const { meeting } = setup();
  await meeting.start();
  await meeting.listenText('Bluebird and FCS');
  await meeting.queue();
  t.mock.timers.tick(1999);
  assert.match(meeting.state.notice, /Queued/);
  t.mock.timers.tick(1);
  assert.equal(meeting.state.card?.term, 'FCS');
  t.mock.timers.tick(8000);
  assert.equal(meeting.state.card, null);
  await meeting.end();
  meeting.dispose();
});

test('a failed end remains retryable and never loses queued questions', async () => {
  const { api, meeting } = setup();
  await meeting.start();
  await meeting.listenText('Bluebird');
  await meeting.queue();
  const end = api.end;
  api.end = async () => { throw new Error('Offline'); };
  await meeting.end();
  assert.equal(meeting.state.phase, 'active');
  assert.equal(meeting.state.queued.length, 1);
  assert.match(meeting.state.error, /Offline/);
  api.end = end;
  await meeting.end();
  assert.equal(meeting.state.phase, 'ended');
  assert.equal(meeting.state.drafts.length, 1);
  meeting.dispose();
});

test('mic denial leaves typed fallback usable without creating another session', async () => {
  const api = createMockApi();
  let starts = 0;
  const start = api.start;
  api.start = async () => { starts++; return start(); };
  const meeting = new Meeting(api, async enabled => { if (enabled) throw new Error('Microphone denied'); }, () => {});
  await meeting.start();
  assert.equal(meeting.state.phase, 'active');
  assert.equal(meeting.state.listening, false);
  await meeting.listenText('Bluebird');
  assert.equal(meeting.state.card?.term, 'BLUEBIRD');
  await meeting.start();
  assert.equal(starts, 1);
  await meeting.end();
  meeting.dispose();
});

test('duplicate queue actions are blocked while the first is pending', async () => {
  const { api, meeting } = setup();
  await meeting.start();
  await meeting.listenText('Bluebird');
  const queue = api.queue;
  let release!: () => void;
  api.queue = async (...args) => { await new Promise<void>(resolve => { release = resolve; }); return queue(...args); };
  const pending = meeting.queue();
  await meeting.queue();
  release();
  await pending;
  assert.equal(meeting.state.queued.length, 1);
  await meeting.end();
  meeting.dispose();
});

test('ending drains audio, discards late cards, and uploads the final partial chunk', async () => {
  const { api, meeting } = setup();
  let resolveListen!: (value: ListenResult) => void;
  const sizes: number[] = [];
  api.listen = async (_session, pcm) => {
    sizes.push(pcm.length);
    if (sizes.length === 1) return new Promise(resolve => { resolveListen = resolve; });
    return { transcript: '', cards: [] };
  };
  await meeting.start();
  meeting.audio(new Uint8Array(128_100));
  const ending = meeting.end();
  resolveListen({ transcript: 'late', cards: [] });
  await ending;
  assert.deepEqual(sizes, [128_000, 100]);
  assert.equal(meeting.state.phase, 'ended');
  assert.equal(meeting.state.card, null);
  assert.equal(meeting.state.transcript, '');
  meeting.dispose();
});

test('background pauses microphone, foreground does not silently resume recording', async () => {
  const { meeting, mic } = setup();
  await meeting.start();
  await meeting.pause();
  assert.equal(meeting.state.listening, false);
  assert.deepEqual(mic, [true, false]);
  await meeting.end();
  meeting.dispose();
});

test('background stops recording even while a queue request is pending', async () => {
  const { api, meeting, mic } = setup();
  await meeting.start();
  await meeting.listenText('Bluebird');
  const queue = api.queue;
  let release!: () => void;
  api.queue = async (...args) => { await new Promise<void>(resolve => { release = resolve; }); return queue(...args); };
  const pending = meeting.queue();
  await meeting.suspend();
  assert.equal(meeting.state.listening, false);
  assert.deepEqual(mic, [true, false]);
  release(); await pending;
  await meeting.end(); meeting.dispose();
});

test('a mute request cannot expire its card and clear a different card', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const { api, meeting } = setup();
  await meeting.start();
  await meeting.listenText('Bluebird and FCS');
  const mute = api.mute;
  let release!: () => void;
  api.mute = async (...args) => { await new Promise<void>(resolve => { release = resolve; }); return mute(...args); };
  const pending = meeting.mute();
  t.mock.timers.tick(8000);
  assert.equal(meeting.state.card?.term, 'BLUEBIRD');
  release(); await pending;
  assert.equal(meeting.state.card?.term, 'FCS');
  await meeting.end(); meeting.dispose();
});
