import type { MeetingState } from './meeting.ts';

// Plain-text layers keep one outline and a separate brightness for each line.
// The empty outline layer is behind the text layers.
export const containers = [
  { containerID: 1, containerName: 'status', xPosition: 16, yPosition: 10, width: 544, height: 31, textColor: 2, borderWidth: 0, paddingLength: 0, isEventCapture: 0 },
  { containerID: 2, containerName: 'card-outline', xPosition: 16, yPosition: 48, width: 544, height: 224, textColor: 2, borderWidth: 1, borderColor: 4, paddingLength: 0, isEventCapture: 0 },
  { containerID: 3, containerName: 'term', xPosition: 38, yPosition: 69, width: 500, height: 47, textColor: 4, borderWidth: 0, paddingLength: 0, isEventCapture: 1 },
  { containerID: 4, containerName: 'meaning', xPosition: 38, yPosition: 126, width: 500, height: 52, textColor: 3, borderWidth: 0, paddingLength: 0, isEventCapture: 0 },
  { containerID: 5, containerName: 'owner', xPosition: 38, yPosition: 187, width: 500, height: 34, textColor: 2, borderWidth: 0, paddingLength: 0, isEventCapture: 0 },
  { containerID: 6, containerName: 'hint', xPosition: 38, yPosition: 236, width: 500, height: 25, textColor: 1, borderWidth: 0, paddingLength: 0, isEventCapture: 0 },
];

export function screenFor(state: MeetingState): string[] {
  const outline = '';
  const mode = state.phase === 'ending' ? 'FINISHING' :
    state.phase === 'ended' ? 'DONE' :
    state.listening ? 'LISTENING' :
    state.phase === 'active' ? 'PAUSED' : 'READY';
  const status = `FOOTNOTE / ${mode} / ${state.queued.length} SAVED`;
  if (state.error) return [status, outline, 'Connection issue', 'Check your phone.', '', 'Press to retry'];
  if (state.phase === 'ending') return [status, outline, 'Wrapping up', 'Preparing your questions.', '', 'Review on phone'];
  if (state.phase === 'ended') return [status, outline, 'Meeting complete', 'Your notes are on your phone.', '', ''];
  if (state.notice) return [status, outline, 'Question saved', 'Saved for after the meeting.', '', 'Returning to listening'];
  if (!state.card) return state.phase === 'idle'
    ? [status, outline, 'Ready for context', 'Press to start your meeting.', '', '']
    : state.listening
      ? [status, outline, 'Listening for terms', 'A new word will appear here.', '', 'Press to pause']
      : [status, outline, 'Listening paused', 'Press to resume.', '', 'Hold to end'];
  const card = state.card;
  return [status, outline, card.term, card.line1, `Ask ${card.owner_name}`, 'Press to save question'];
}
