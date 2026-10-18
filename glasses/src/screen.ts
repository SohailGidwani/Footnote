import type { MeetingState } from './meeting.ts';

export const containers = [
  { containerID: 1, containerName: 'status', xPosition: 16, yPosition: 12, width: 544, height: 40, textColor: 6, isEventCapture: 0 },
  { containerID: 2, containerName: 'term', xPosition: 16, yPosition: 78, width: 544, height: 56, textColor: 15, isEventCapture: 1 },
  { containerID: 3, containerName: 'detail', xPosition: 16, yPosition: 144, width: 544, height: 128, textColor: 11, isEventCapture: 0 },
];

export function screenFor(state: MeetingState): string[] {
  const count = `${state.queued.length} SAVED`;
  const mode = state.phase === 'ending' ? 'FINISHING' :
    state.phase === 'ended' ? 'DONE' :
    state.listening ? 'LISTENING' :
    state.phase === 'active' ? 'PAUSED' : 'READY';
  const status = `FOOTNOTE / ${mode} / ${count}`;
  if (state.error) return [status, 'Connection issue', `${state.error.slice(0, 92)}\nUse phone controls or reconnect G2.`];
  if (state.phase === 'ending') return [status, 'Wrapping up', 'Preparing your follow-up questions...'];
  if (state.phase === 'ended') return [status, 'Meeting complete', `${count}\nReview your follow-ups on your phone.`];
  if (state.notice) return [status, 'Question saved', `${state.notice}\nHold to end meeting`];
  if (!state.card) return state.phase === 'idle'
    ? [status, 'Ready for context', 'Press to start your meeting.']
    : state.listening
      ? [status, 'Listening for terms', 'New words will appear here.\nPress to pause / Hold to end']
      : [status, 'Listening paused', 'Press to resume / Hold to end'];
  const card = state.card;
  return [status, card.term, `${card.line1}\n${card.source === 'llm' ? 'Ask' : 'Owner'}: ${card.owner_name} (${card.owner_team})\nPress: ask / Down: know / Up: next`];
}
