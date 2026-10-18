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
    <section class="intro"><p class="context">HALCYON ROBOTICS <span aria-hidden="true">/</span> YOUR FIRST WEEK</p><h1>A little context.<br><em>A quieter first week.</em></h1><p>Catch the unfamiliar. Find your person. Keep the conversation going.</p><div class="intro-rule" aria-hidden="true"><span>01</span><span>LISTEN</span><span>02</span><span>LEARN</span><span>03</span><span>FOLLOW UP</span></div></section>
    <section aria-labelledby="meeting-title" class="meeting-panel">
      <div class="section-kicker">01 / IN THE MOMENT</div>
      <div class="section-heading"><h2 id="meeting-title">Your meeting</h2><span id="meeting-status" role="status">Ready</span></div>
      <p id="device-status" class="secondary" role="status">Connecting to glasses… Phone controls are ready.</p>
      <div id="error" class="error" role="alert" hidden></div>
      <div class="meeting-controls"><button id="start" class="primary">Start meeting</button><button id="pause" hidden>Pause listening</button><button id="end" disabled>End meeting</button></div>
      <div class="glasses-preview" aria-label="Glasses display preview"><div class="preview-label"><span>G2 DISPLAY PREVIEW</span><span>576 × 288</span></div><div class="display-canvas"><p id="display-status"></p><p id="display-term"></p><p id="display-detail"></p></div></div>
      <div class="card-controls"><button id="queue" disabled>Ask the owner</button><button id="mute" disabled>I know this</button><button id="next" disabled>Next / last card</button></div>
      <p class="hint">On G2: press to ask, swipe down to mute, swipe up for the next card. Hold to end. Double press opens the system exit dialog.</p>
    </section>
    <section class="question-panel" aria-labelledby="queue-title"><div class="section-kicker">02 / AFTER THE MEETING</div><div class="section-heading"><h2 id="queue-title">Questions to take with you</h2><span id="queue-count">0</span></div><ul id="questions" class="entries"></ul></section>
    <section id="draft-section" class="draft-section" aria-labelledby="draft-title" hidden><div class="section-kicker">03 / FOLLOW UP</div><h2 id="draft-title">A conversation starts here.</h2><p class="secondary" id="delivery-note"></p><div id="drafts"></div></section>
    <details id="fallback"><summary>Try a phrase instead</summary><p class="secondary">Use typed input if the room is noisy or your glasses are disconnected.</p><form id="text-form"><label for="phrase">Meeting phrase</label><textarea id="phrase" rows="2" maxlength="2000">Bluebird is slipping because FCS is still on the old golden path.</textarea><button id="listen-text" type="submit" disabled>Find terms</button></form><p id="last-phrase" class="secondary"></p></details>
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
  text('meeting-status', s.phase === 'ending' ? 'Ending…' : s.phase === 'ended' ? 'Meeting ended' : s.listening ? 'Listening' : s.phase === 'active' ? 'Paused' : 'Ready when you are');
  const start = element<HTMLButtonElement>('start');
  start.textContent = s.phase === 'active' ? 'Resume listening' : 'Start meeting';
  start.hidden = s.listening || s.phase === 'ending';
  start.disabled = s.busy;
  element<HTMLButtonElement>('pause').hidden = !s.listening;
  element<HTMLButtonElement>('pause').disabled = s.busy;
  element<HTMLButtonElement>('end').disabled = s.phase !== 'active' || s.busy;
  for (const id of ['queue', 'mute']) element<HTMLButtonElement>(id).disabled = !s.card || s.busy || s.phase !== 'active';
  element<HTMLButtonElement>('next').disabled = s.phase !== 'active' || s.busy;
  element<HTMLButtonElement>('listen-text').disabled = s.phase !== 'active' || s.busy;
  text('error', s.error);
  element('error').hidden = !s.error;
  text('queue-count', String(s.queued.length));
  const questions = element('questions');
  questions.replaceChildren();
  if (!s.queued.length) {
    const li = document.createElement('li');
    li.className = 'empty';
    li.textContent = 'An unfamiliar term is a good place to start. Queue one to ask its owner after the meeting.';
    questions.append(li);
  }
  for (const card of s.queued) {
    const li = document.createElement('li');
    const term = document.createElement('strong'); term.textContent = card.term;
    const owner = document.createElement('span'); owner.textContent = `${card.source === 'llm' ? 'Suggested contact: ' : ''}${card.owner_name} / ${card.owner_team}`;
    li.append(term, owner); questions.append(li);
  }
  element('draft-section').hidden = s.phase !== 'ended';
  text('delivery-note', __MOCK_MODE__ ? 'Demo only. Approving a draft simulates delivery; no email is sent.' : 'Each approval sends one message to the configured demo inbox. Owner addresses are display-only.');
  const drafts = element('drafts'); drafts.replaceChildren();
  if (s.phase === 'ended' && !s.drafts.length) {
    const empty = document.createElement('p'); empty.textContent = 'No questions queued this time. Start another meeting whenever you need a little context.'; drafts.append(empty);
  }
  for (const draft of s.drafts) {
    const article = document.createElement('article'); article.className = 'draft';
    const owner = document.createElement('h3'); owner.textContent = `For ${draft.to_name}`;
    const subject = document.createElement('p'); subject.className = 'subject'; subject.textContent = draft.subject;
    const body = document.createElement('p'); body.className = 'draft-body'; body.textContent = draft.body;
    const button = document.createElement('button'); button.className = 'primary';
    const sent = s.sent.includes(draft.draft_id);
    button.textContent = sent ? (__MOCK_MODE__ ? 'Sent (demo)' : 'Sent') : 'Approve and send';
    button.disabled = sent || s.busy;
    button.onclick = () => { void meeting.send(draft.draft_id); };
    article.append(owner, subject, body, button); drafts.append(article);
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
if (__MOCK_MODE__) element<HTMLDetailsElement>('fallback').open = true;
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
  text('device-status', 'Phone preview. Open in Even Hub or the simulator to connect your glasses.');
  window.addEventListener('flutterInAppWebViewPlatformReady', () => { void connect(); }, { once: true });
}
