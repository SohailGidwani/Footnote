import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { CreateStartUpPageContainer, TextContainerProperty, validateEvenHubPageContainer } from '@evenrealities/even_hub_sdk';
import type { MeetingState } from '../src/meeting.ts';
import { containers, screenFor } from '../src/screen.ts';

const base: MeetingState = {
  phase: 'idle', listening: false, busy: false, card: null, queued: [], drafts: [],
  sent: [], notice: '', error: '', transcript: '',
};

test('G2 layout stays within 576 by 288', () => {
  assert.equal(containers.length, 6);
  assert.equal(containers.filter(container => container.borderWidth > 0).length, 1);
  for (const container of containers) {
    assert.ok(container.xPosition >= 0 && container.xPosition + container.width <= 576);
    assert.ok(container.yPosition >= 0 && container.yPosition + container.height <= 288);
    assert.ok(container.textColor >= 0 && container.textColor <= 4);
  }
});

test('the installed Even SDK accepts the G2 startup page', () => {
  const screen = screenFor(base);
  const page = new CreateStartUpPageContainer({
    containerTotalNum: containers.length,
    textObject: containers.map((container, index) => new TextContainerProperty({
      ...container, content: screen[index],
    })),
  });
  const result = validateEvenHubPageContainer(page);
  assert.equal(result.valid, true, JSON.stringify(result));
});

test('G2 renders listening, term, queued, empty, and error states', () => {
  assert.match(screenFor({ ...base, phase: 'active', listening: true })[2], /Listening for terms/);
  assert.match(screenFor({ ...base, phase: 'active', listening: true, card: {
    card_id: 'c1', term_id: 't1', term: 'Bluebird', line1: 'v3 navigation stack rewrite',
    owner_name: 'Priya Raman', owner_team: 'Autonomy', source: 'glossary', confidence: 1,
  } })[4], /Ask Priya Raman/);
  assert.match(screenFor({ ...base, phase: 'active', notice: 'Queued for Priya Raman' })[2], /Question saved/);
  assert.match(screenFor(base)[2], /Ready for context/);
  assert.match(screenFor({ ...base, phase: 'active', error: 'Cannot reach backend' })[2], /Connection issue/);
});
