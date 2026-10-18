import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createApi, validateBackendUrl } from '../src/api.ts';
import { createMockApi } from '../src/mock.ts';
import { PcmBuffer } from '../src/pcm.ts';
import { gestureOf } from '../src/gestures.ts';

test('audio and lifecycle events are not interpreted as omitted-zero clicks', () => {
  assert.equal(gestureOf({ audioEvent: { audioPcm: new Uint8Array(4) } }), null);
  assert.equal(gestureOf({ sysEvent: {} }), 'click');
  assert.equal(gestureOf({ textEvent: { eventType: 2 } }), 'down');
  assert.equal(gestureOf({ sysEvent: { eventType: 3 } }), 'exit');
  assert.equal(gestureOf({ sysEvent: { eventType: 4 } }), 'foreground');
  assert.equal(gestureOf({ sysEvent: { eventType: 5 } }), 'background');
  assert.equal(gestureOf({ sysEvent: { eventType: 9 } }), 'end');
  assert.equal(gestureOf({ sysEvent: { eventType: 10 } }), 'end');
});

test('PCM preserves every byte across frame boundaries and flushes only full samples', () => {
  const pcm = new PcmBuffer(8);
  assert.deepEqual(pcm.push(Uint8Array.from([0, 1, 2])), []);
  const chunks = pcm.push(Uint8Array.from([3, 4, 5, 6, 7, 8, 9, 10]));
  assert.deepEqual([...chunks[0]], [0, 1, 2, 3, 4, 5, 6, 7]);
  assert.deepEqual([...pcm.flush()!], [8, 9]);
  assert.equal(pcm.flush(), null);
  pcm.push(new Uint8Array(4));
  pcm.clear();
  assert.equal(pcm.flush(), null);
});

test('backend config accepts origins only and rejects credentials and insecure public hosts', () => {
  assert.equal(validateBackendUrl('https://api.example.com/'), 'https://api.example.com');
  assert.equal(validateBackendUrl('http://localhost:8000'), 'http://localhost:8000');
  for (const url of ['', 'https://a:b@api.example.com', 'https://api.example.com/v1', 'http://api.example.com', 'https://api.example.com/?key=secret']) {
    assert.throws(() => validateBackendUrl(url));
  }
});

test('REST client sends raw PCM and the frozen queue payload', async () => {
  const calls: Array<{ url: string; init: RequestInit }> = [];
  const api = createApi('https://api.example.com', async (url, init) => {
    calls.push({ url: String(url), init: init! });
    return Response.json(String(url).includes('/queue') ? { queued: true, owner_name: 'Priya R.' } : { transcript: '', cards: [] });
  });
  await api.listen('a/b', new Uint8Array([1, 2]));
  await api.queue('card/id', 'a/b');
  assert.equal(calls[0].url, 'https://api.example.com/listen?session_id=a%2Fb');
  assert.equal(calls[0].init.headers && new Headers(calls[0].init.headers).get('Content-Type'), 'application/octet-stream');
  assert.deepEqual([...new Uint8Array(calls[0].init.body as ArrayBuffer)], [1, 2]);
  assert.equal(calls[1].url, 'https://api.example.com/cards/card%2Fid/queue');
  assert.deepEqual(JSON.parse(calls[1].init.body as string), { session_id: 'a/b' });
});

test('REST failures and malformed cards never look like successful responses', async () => {
  const failed = createApi('https://api.example.com', async () => new Response('secret provider detail', { status: 500 }));
  await assert.rejects(failed.start(), /500/);
  const malformed = createApi('https://api.example.com', async () => Response.json({ transcript: '', cards: [{ term: 'missing ids' }] }));
  await assert.rejects(malformed.listenText('session', 'Bluebird'), /Invalid/);
  const send = createApi('https://api.example.com', async () => Response.json({ sent: false }));
  await assert.rejects(send.send('draft'), /Invalid/);
  const discard = createApi('https://api.example.com', async () => Response.json({ discarded: false }));
  await assert.rejects(discard.discard('draft'), /Invalid/);
});

test('requests abort after six seconds instead of accepting late cards', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const api = createApi('https://api.example.com', async (_url, init) => new Promise((_resolve, reject) => {
    init!.signal!.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
  }));
  const result = assert.rejects(api.listen('session', new Uint8Array(2)), /6 seconds/);
  t.mock.timers.tick(6000);
  await result;
});

test('mock mode supports the complete approval flow, mute and three-sighting fade-out', async () => {
  const api = createMockApi();
  const { session_id } = await api.start();
  const first = await api.listenText(session_id, 'Bluebird and FCS');
  assert.equal(first.cards.length, 2);
  await api.queue(first.cards[0].card_id, session_id);
  await api.mute(first.cards[1].term_id);
  assert.equal((await api.listenText(session_id, 'Bluebird and FCS')).cards.length, 1);
  assert.equal((await api.listenText(session_id, 'Bluebird')).cards.length, 1);
  assert.equal((await api.listenText(session_id, 'Bluebird')).cards.length, 0);
  const { drafts } = await api.end(session_id);
  assert.equal(drafts.length, 1);
  assert.equal((await api.digest()).sent.length, 0);
  await api.send(drafts[0].draft_id);
  assert.equal((await api.digest()).sent.length, 1);
  await assert.rejects(api.queue(first.cards[0].card_id, session_id));
});

test('mock draft discard removes it from repeated end and blocks sending', async () => {
  const api = createMockApi();
  const { session_id } = await api.start();
  const { cards } = await api.listenText(session_id, 'Bluebird');
  await api.queue(cards[0].card_id, session_id);
  const draft = (await api.end(session_id)).drafts[0];
  assert.deepEqual(await api.discard(draft.draft_id), { discarded: true });
  assert.deepEqual((await api.end(session_id)).drafts, []);
  await assert.rejects(api.send(draft.draft_id));
});
