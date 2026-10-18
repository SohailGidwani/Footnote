import {
  waitForEvenAppBridge, TextContainerProperty, CreateStartUpPageContainer,
  TextContainerUpgrade, AudioInputSource,
} from '@evenrealities/even_hub_sdk';
import type { EvenAppBridge } from '@evenrealities/even_hub_sdk';
import { createApi } from './api.ts';
import { createMockApi } from './mock.ts';
import { Meeting } from './meeting.ts';
import { gestureOf } from './gestures.ts';
import { containers, screenFor } from './screen.ts';
import './style.css';

document.querySelector<HTMLDivElement>('#app')!.innerHTML = `
  <main class="companion">
    <header class="masthead"><a class="wordmark" href="./">footnote<span aria-hidden="true">*</span></a><span id="mode" class="mode"></span></header>
    <section id="draft-section" class="draft-section" aria-labelledby="draft-title" hidden><h2 id="draft-title">Before you send</h2><p class="draft-intro">A draft is ready. Read it, then choose whether to send.</p><div id="drafts"></div><p class="secondary" id="delivery-note"></p></section>
    <section id="meeting-panel" aria-labelledby="meeting-title" class="meeting-panel">
      <div class="meeting-heading"><div><h1 id="meeting-title">Your meeting</h1><p id="meeting-copy">Start when the conversation starts. The glasses will show terms as they come up.</p></div><span id="meeting-status" role="status">Ready</span></div>
      <div id="error" class="error" role="alert" hidden></div>
      <div class="meeting-controls"><button id="start" class="primary">Start listening</button><button id="pause" hidden>Pause</button></div>
      <p id="device-status" class="device-status" role="status">Connecting to glasses… Phone controls are ready.</p>
      <div class="glasses-preview" aria-label="Glasses display preview"><div class="preview-label"><span>On your glasses</span><span>576 × 288</span></div><div class="display-canvas"><p id="display-status"></p><p id="display-term"></p><p id="display-detail"></p></div></div>
      <div id="card-controls" class="card-controls" hidden><button id="queue" class="primary" disabled>Ask later</button><button id="mute" disabled>I know this</button><button id="next" disabled>Next card</button></div>
      <p class="hint">On G2: press to save a question, swipe down if you know it, swipe up for the next term, or hold to end.</p>
      <button id="end" class="end-meeting" disabled>End meeting</button>
    </section>
    <section class="question-panel" aria-labelledby="queue-title"><div class="section-heading"><h2 id="queue-title">Questions to carry</h2><span id="queue-count">None yet</span></div><ul id="questions" class="entries"></ul></section>
    <details id="fallback"><summary>Try a phrase on your phone</summary><p class="secondary">Use typed input if the room is noisy or your glasses are disconnected.</p><form id="text-form"><label for="phrase">Meeting phrase</label><textarea id="phrase" rows="2" maxlength="2000">Bluebird is slipping because FCS is still on the old golden path.</textarea><button id="listen-text" type="submit" disabled>Find terms</button></form><p id="last-phrase" class="secondary"></p></details>
    <details id="demo-tools" hidden><summary>Simulator gestures</summary><div class="demo-buttons"><button data-gesture="click">Single press</button><button data-gesture="up">Swipe up</button><button data-gesture="down">Swipe down</button><button data-gesture="end">Long press</button><button data-gesture="exit">Double press</button></div><p id="exit-note" role="status"></p></details>
    <footer>Less jargon. More belonging.<span>Footnote / LA Hacks 2026</span></footer>
  </main>`;

function element<T extends HTMLElement>(id: string): T { return document.getElementById(id) as T; }
function text(id: string, value: string) { element(id).textContent = value; }
const api = __MOCK_MODE__ ? createMockApi() : createApi(__BACKEND_URL__);
let bridge: EvenAppBridge | null = null;
let pageReady = false;
let unsubscribe: (() => void) | undefined;
let renderTimer: ReturnType<typeof setTimeout> | undefined;
let rendering = false;
let renderAgain = false;
const lastDisplay = new Map<number, string>();
let disposed = false;

const meeting = new Meeting(api, async enabled => {
  if (__MOCK_MODE__) return;
  if (!pageReady || !bridge) throw new Error('Glasses are not connected. Use a typed phrase, or connect G2 and resume listening.');
  if (!await bridge.audioControl(enabled, AudioInputSource.Glasses)) {
    throw new Error(enabled ? 'Microphone permission denied or G2 disconnected. Use typed input, then retry listening.' : 'Could not stop the microphone. Reconnect G2 and retry.');
  }
}, render);

function render() {
  const s = meeting.state;
  const screen = screenFor(s);
  ['display-status', 'display-term', 'display-detail'].forEach((id, index) => text(id, screen[index]));
  text('meeting-title', s.phase === 'ended' ? 'Meeting complete' : s.listening ? 'Listening' : s.phase === 'active' ? 'Listening paused' : 'Your meeting');
  text('meeting-copy', s.phase === 'ended' ? 'Review your drafts above, or start another meeting.' : s.listening ? 'Terms appear on your glasses as the conversation moves.' : s.phase === 'active' ? 'Press resume when you are ready to listen again.' : 'Start when the conversation starts. The glasses will show terms as they come up.');
  text('meeting-status', s.phase === 'ending' ? 'Finishing' : s.phase === 'ended' ? 'Done' : s.listening ? 'Live' : s.phase === 'active' ? 'Paused' : 'Ready');
  const start = element<HTMLButtonElement>('start');
  start.textContent = s.phase === 'active' ? 'Resume listening' : s.phase === 'ended' ? 'Start another meeting' : 'Start listening';
  start.hidden = s.listening || s.phase === 'ending';
  start.disabled = s.busy;
  element<HTMLButtonElement>('pause').hidden = !s.listening;
  element<HTMLButtonElement>('pause').disabled = s.busy;
  element<HTMLButtonElement>('end').disabled = s.phase !== 'active' || s.busy;
  element<HTMLButtonElement>('end').hidden = s.phase !== 'active';
  for (const id of ['queue', 'mute']) element<HTMLButtonElement>(id).disabled = !s.card || s.busy || s.phase !== 'active';
  element<HTMLButtonElement>('next').disabled = s.phase !== 'active' || s.busy;
  element<HTMLButtonElement>('listen-text').disabled = s.phase !== 'active' || s.busy;
  element('card-controls').hidden = !s.card || s.phase !== 'active';
  text('queue', s.card ? `Ask ${s.card.owner_name.split(' ')[0] || 'the owner'} later` : 'Ask later');
  text('error', s.error);
  element('error').hidden = !s.error;
  text('queue-count', s.queued.length ? `${s.queued.length} saved` : 'None yet');
  const questions = element('questions');
  questions.replaceChildren();
  if (!s.queued.length) {
    const li = document.createElement('li');
    li.className = 'empty';
    li.textContent = 'Hear something unfamiliar? Press the glasses to save a question for later.';
    questions.append(li);
  }
  for (const [index, card] of s.queued.entries()) {
    const li = document.createElement('li');
    const number = document.createElement('span'); number.className = 'entry-index'; number.textContent = String(index + 1);
    const copy = document.createElement('div'); copy.className = 'entry-copy';
    const term = document.createElement('strong'); term.textContent = card.term;
    const owner = document.createElement('span'); owner.textContent = `${card.source === 'llm' ? 'Suggested contact: ' : 'Ask '}${card.owner_name} / ${card.owner_team}`;
    copy.append(term, owner); li.append(number, copy); questions.append(li);
  }
  element('draft-section').hidden = s.phase !== 'ended';
  text('delivery-note', __MOCK_MODE__ ? 'Demo only. Approving a draft simulates delivery; no email is sent.' : 'Each approval sends one message to the configured demo inbox. Owner addresses are display-only.');
  const drafts = element('drafts'); drafts.replaceChildren();
  if (s.phase === 'ended' && !s.drafts.length) {
    const empty = document.createElement('p'); empty.textContent = 'No questions queued this time. Start another meeting whenever you need a little context.'; drafts.append(empty);
  }
  for (const draft of s.drafts) {
    const article = document.createElement('article'); article.className = 'draft';
    const recipient = document.createElement('div'); recipient.className = 'draft-field';
    const toLabel = document.createElement('span'); toLabel.textContent = 'To';
    const owner = document.createElement('h3'); owner.textContent = draft.to_name;
    recipient.append(toLabel, owner);
    const subjectField = document.createElement('div'); subjectField.className = 'draft-field';
    const subjectLabel = document.createElement('span'); subjectLabel.textContent = 'Subject';
    const subject = document.createElement('p'); subject.className = 'subject'; subject.textContent = draft.subject;
    subjectField.append(subjectLabel, subject);
    const body = document.createElement('p'); body.className = 'draft-body'; body.textContent = draft.body;
    const button = document.createElement('button'); button.className = 'primary';
    const sent = s.sent.includes(draft.draft_id);
    button.textContent = sent ? (__MOCK_MODE__ ? 'Sent (demo)' : 'Sent') : 'Approve and send';
    button.disabled = sent || s.busy;
    button.onclick = () => { void meeting.send(draft.draft_id); };
    article.append(recipient, subjectField, body, button); drafts.append(article);
  }
  text('last-phrase', s.transcript ? `Last phrase: ${s.transcript}` : '');
  scheduleDisplay();
}

function scheduleDisplay() {
  if (!pageReady || disposed) return;
  renderAgain = true;
  if (rendering || renderTimer) return;
  renderTimer = setTimeout(() => { renderTimer = undefined; void updateDisplay(); }, 120);
}
async function updateDisplay() {
  if (!bridge || !pageReady || disposed) return;
  rendering = true; renderAgain = false;
  const screen = screenFor(meeting.state);
  try {
    for (const [index, container] of containers.entries()) {
      if (lastDisplay.get(container.containerID) === screen[index]) continue;
      if (!await bridge.textContainerUpgrade(new TextContainerUpgrade({ containerID: container.containerID, containerName: container.containerName, content: screen[index] }))) {
        throw new Error('Glasses display update failed. Check the G2 connection.');
      }
      lastDisplay.set(container.containerID, screen[index]);
    }
  } catch (error) { text('device-status', error instanceof Error ? error.message : 'Glasses display unavailable.'); }
  finally { rendering = false; if (renderAgain) scheduleDisplay(); }
}

async function gesture(kind: ReturnType<typeof gestureOf>) {
  if (kind === 'exit') {
    if (bridge) await bridge.shutDownPageContainer(1);
    else text('exit-note', 'On G2 this opens the system exit dialog. Connect the simulator or glasses to test it.');
  } else if (kind === 'closed') { cleanup(); }
  else if (kind === 'background') { if (!__MOCK_MODE__) await meeting.suspend(); }
  else if (kind === 'foreground') {
    meeting.foreground();
    lastDisplay.clear(); scheduleDisplay();
    text('device-status', 'Glasses connected. Resume listening when you are ready.');
  } else if (kind === 'end') await meeting.end();
  else if (kind === 'down') await meeting.mute();
  else if (kind === 'up') meeting.next();
  else if (kind === 'click') {
    if (meeting.state.notice || meeting.state.busy) return;
    if (meeting.state.card) await meeting.queue();
    else if (meeting.state.listening) await meeting.pause();
    else await startListening();
  }
}

async function startListening() {
  await meeting.start();
  if (__MOCK_MODE__ && meeting.state.listening) await meeting.listenText('Bluebird and FCS');
}
element('start').onclick = () => { void startListening(); };
element('pause').onclick = () => { void meeting.pause(); };
element('end').onclick = () => { void meeting.end(); };
element('queue').onclick = () => { void meeting.queue(); };
element('mute').onclick = () => { void meeting.mute(); };
element('next').onclick = () => meeting.next();
element('text-form').onsubmit = event => { event.preventDefault(); void meeting.listenText(element<HTMLTextAreaElement>('phrase').value); };
document.querySelectorAll<HTMLButtonElement>('[data-gesture]').forEach(button => {
  button.onclick = () => { void gesture(button.dataset.gesture as ReturnType<typeof gestureOf>); };
});
text('mode', __MOCK_MODE__ ? 'Demo / no audio or email' : 'Live backend');
element('demo-tools').hidden = !__MOCK_MODE__;
render();

async function connect() {
  try {
    bridge = await waitForEvenAppBridge();
    if (disposed) return;
    const screen = screenFor(meeting.state);
    const created = await bridge.createStartUpPageContainer(new CreateStartUpPageContainer({
      containerTotalNum: 3,
      textObject: containers.map((container, index) => new TextContainerProperty({ ...container, borderWidth: 0, paddingLength: 0, content: screen[index] })),
    }));
    if (created !== 0) throw new Error(`Glasses startup failed (${created}). Reopen Footnote after connecting G2.`);
    pageReady = true;
    text('device-status', __MOCK_MODE__ ? 'Display connected. Demo mode does not record audio.' : 'G2 connected. Audio stays off until you start a meeting.');
    unsubscribe = bridge.onEvenHubEvent(event => {
      if (!__MOCK_MODE__ && event.audioEvent?.audioPcm) meeting.audio(event.audioEvent.audioPcm);
      void gesture(gestureOf(event)).catch(error => text('device-status', String(error)));
    });
    scheduleDisplay();
  } catch (error) { text('device-status', error instanceof Error ? error.message : 'Open in Even Hub or the simulator to connect G2.'); }
}
function cleanup() {
  if (disposed) return;
  disposed = true;
  clearTimeout(renderTimer);
  meeting.dispose();
  unsubscribe?.();
}
document.addEventListener('visibilitychange', () => {
  if (__MOCK_MODE__) return;
  if (document.hidden) void meeting.suspend();
  else { meeting.foreground(); lastDisplay.clear(); scheduleDisplay(); }
});
window.addEventListener('pagehide', event => { if (event.persisted) void meeting.suspend(); else cleanup(); });
const host = window as Window & { flutter_inappwebview?: { callHandler?: unknown } };
if (host.flutter_inappwebview?.callHandler) void connect();
else {
  text('device-status', __MOCK_MODE__ ? 'Demo preview; audio and email stay off.' : 'Open in Even Hub to connect G2.');
  window.addEventListener('flutterInAppWebViewPlatformReady', () => { void connect(); }, { once: true });
}
