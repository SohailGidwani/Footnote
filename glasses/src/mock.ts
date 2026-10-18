import type { Api, Card, Draft } from './api.ts';

const cards: Card[] = [
  { card_id: 'mock-bluebird', term_id: 'bluebird', term: 'BLUEBIRD', line1: 'v3 navigation stack rewrite', owner_name: 'Priya Raman', owner_team: 'Autonomy', source: 'glossary', confidence: 1 },
  { card_id: 'mock-fcs', term_id: 'fcs', term: 'FCS', line1: 'Fleet Control Service', owner_name: 'Marcus Lindqvist', owner_team: 'Platform', source: 'glossary', confidence: 1 },
];

export function createMockApi(): Api {
  const sessions = new Map<string, { ended: boolean; queue: Card[] }>();
  const seen = new Map<string, number>();
  const muted = new Set<string>();
  const drafts = new Map<string, Draft>();
  const sent = new Set<string>();
  const discarded = new Set<string>();
  function active(id: string) {
    const session = sessions.get(id);
    if (!session || session.ended) throw new Error('Mock meeting is not active.');
    return session;
  }
  async function listenText(id: string, text: string) {
    active(id);
    const matches = cards.filter(card => text.toLowerCase().includes(card.term.toLowerCase()) &&
      !muted.has(card.term_id) && (seen.get(card.term_id) ?? 0) < 3);
    matches.forEach(card => seen.set(card.term_id, (seen.get(card.term_id) ?? 0) + 1));
    return { transcript: text, cards: matches.map(card => ({ ...card })) };
  }
  return {
    async start() {
      const id = `mock-session-${sessions.size + 1}`;
      sessions.set(id, { ended: false, queue: [] });
      return { session_id: id };
    },
    listen: id => listenText(id, 'Bluebird and FCS'),
    listenText,
    async queue(cardId, id) {
      const card = cards.find(c => c.card_id === cardId);
      if (!card) throw new Error('Mock card not found.');
      active(id).queue.push(card);
      return { queued: true, owner_name: card.owner_name };
    },
    async mute(termId) { muted.add(termId); return { muted: true }; },
    async end(id) {
      const session = sessions.get(id);
      if (!session) throw new Error('Mock meeting not found.');
      session.ended = true;
      const owners = [...new Set(session.queue.map(card => card.owner_name))];
      const result = owners.map((owner, index) => {
        const terms = [...new Set(session.queue.filter(c => c.owner_name === owner).map(c => c.term))];
        const draft: Draft = {
          draft_id: `${id}-draft-${index}`, to_name: owner, to_email: 'display-only@halcyon.example',
          subject: `A question about ${terms.join(' and ')}`,
          body: `Hi ${owner.split(' ')[0]},\n\nI'm getting up to speed on ${terms.join(' and ')}. Could you point me to the best place to start, or spare 15 minutes this week?\n\nThanks!`, terms,
        };
        drafts.set(draft.draft_id, draft);
        return draft;
      });
      return { drafts: result.filter(draft => !discarded.has(draft.draft_id)) };
    },
    async send(id) {
      if (!drafts.has(id)) throw new Error('Mock draft not found.');
      if (discarded.has(id)) throw new Error('Mock draft was discarded.');
      sent.add(id);
      return { sent: true };
    },
    async discard(id) {
      if (!drafts.has(id)) throw new Error('Mock draft not found.');
      if (sent.has(id)) throw new Error('Sent mock drafts cannot be discarded.');
      discarded.add(id);
      return { discarded: true };
    },
    async digest() {
      return {
        terms_learned: cards.filter(c => seen.has(c.term_id)).map(c => ({ term: c.term, meaning: c.line1 })),
        people_to_meet: cards.filter(c => seen.has(c.term_id)).map(c => ({ name: c.owner_name, team: c.owner_team })),
        sent: [...sent].map(id => ({ to_name: drafts.get(id)!.to_name, subject: drafts.get(id)!.subject })),
      };
    },
  };
}
