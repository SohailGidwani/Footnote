import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { publicConfig, clientDefines, manifestPlugin } from '../config.mjs';
import { containers, screenFor } from '../src/screen.ts';
import { Meeting } from '../src/meeting.ts';
import { createMockApi } from '../src/mock.ts';

test('only public config is exposed and live network whitelist contains exactly the backend origin', () => {
  const root = mkdtempSync(join(tmpdir(), 'footnote-config-'));
  try {
    writeFileSync(join(root, '.env.local'), 'MOCK_MODE=false\nBACKEND_URL=https://api.example.com\nSTEPFUN_API_KEY=should-never-appear\n');
    const config = publicConfig('production', root);
    assert.deepEqual(config, { mock: false, backendUrl: 'https://api.example.com' });
    assert.ok(!JSON.stringify(clientDefines(config)).includes('should-never-appear'));
    const assets: Array<{ fileName: string; source: string }> = [];
    manifestPlugin(config, new URL('../', import.meta.url)).generateBundle.call({ emitFile: asset => assets.push(asset) });
    const manifest = JSON.parse(assets.find(asset => asset.fileName === 'app.json')!.source);
    assert.equal(manifest.min_sdk_version, '0.0.16');
    assert.equal(manifest.min_app_version, '2.2.10');
    assert.deepEqual(manifest.permissions.find(permission => permission.name === 'network').whitelist, ['https://api.example.com']);
    assert.equal(publicConfig('demo', root).mock, true);
    writeFileSync(join(root, '.env.local'), 'MOCK_MODE=false\nBACKEND_URL=https://api.example.com/private\n');
    assert.throws(() => publicConfig('production', root));
  } finally { rmSync(root, { recursive: true, force: true }); }
});

test('the root layout has one event capture and empty cards use single spaces', () => {
  assert.equal(containers.filter(container => container.isEventCapture === 1).length, 1);
  assert.deepEqual(containers.map(container => [container.containerID, container.containerName, container.textColor]), [[1, 'status', 2], [2, 'term', 4], [3, 'detail', 3]]);
  const meeting = new Meeting(createMockApi(), async () => {}, () => {});
  assert.deepEqual(screenFor(meeting.state).slice(1), ['Ready for context', 'Press to start your meeting.']);
  meeting.dispose();
});

test('inferred cards suggest a contact instead of claiming confirmed ownership', () => {
  const meeting = new Meeting(createMockApi(), async () => {}, () => {});
  meeting.state.card = { card_id: 'c', term_id: 't', term: 'NEW PROJECT', line1: 'Meaning inferred from the meeting',
    owner_name: 'Marcus L.', owner_team: 'Platform', source: 'llm', confidence: 0.6 };
  assert.ok(screenFor(meeting.state)[2].includes('Ask: Marcus L. (Platform)'));
  meeting.state.card.source = 'glossary';
  assert.ok(screenFor(meeting.state)[2].includes('Owner: Marcus L. (Platform)'));
  meeting.dispose();
});
