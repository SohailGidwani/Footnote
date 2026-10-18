import type { MeetingState } from './meeting.ts';

export const containers = [
  { containerID: 1, containerName: 'status', xPosition: 0, yPosition: 0, width: 576, height: 40, textColor: 2, isEventCapture: 0 },
  { containerID: 2, containerName: 'term', xPosition: 0, yPosition: 72, width: 576, height: 56, textColor: 4, isEventCapture: 1 },
  { containerID: 3, containerName: 'detail', xPosition: 0, yPosition: 132, width: 576, height: 120, textColor: 3, isEventCapture: 0 },
];

export function screenFor(state: MeetingState): string[] {
  const count = `${state.queued.length} queued`;
  const status = state.error ? `Connection error | ${count}` :
    state.phase === 'ending' ? 'Ending meeting...' :
    state.phase === 'ended' ? `Meeting ended | ${count}` :
    state.listening ? `Listening | ${count}` :
    state.phase === 'active' ? `Paused | ${count}` : 'Footnote | Press to start';
  if (state.notice) return [status, state.notice, ' '];
  if (!state.card) return [status, ' ', ' '];
  const card = state.card;
  return [status, card.term, `${card.line1}\n${card.source === 'llm' ? 'Ask' : 'Owner'}: ${card.owner_name} (${card.owner_team})\npress: ask | swipe down: known`];
}
