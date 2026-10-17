import type { Api, Card, Draft, ListenResult } from './api.ts';
import { PcmBuffer } from './pcm.ts';

export interface MeetingState {
  phase: 'idle' | 'active' | 'ending' | 'ended';
  listening: boolean;
  busy: boolean;
  card: Card | null;
  queued: Card[];
  drafts: Draft[];
  sent: string[];
  notice: string;
  error: string;
  transcript: string;
}

export class Meeting {
  readonly state: MeetingState = {
    phase: 'idle', listening: false, busy: false, card: null,
    queued: [], drafts: [], sent: [], notice: '', error: '', transcript: '',
  };
  private api: Api;
  private microphone: (enabled: boolean) => Promise<void>;
  private changed: () => void;
  private session = '';
  private pcm = new PcmBuffer();
  private pending: Card[] = [];
  private lastCard: Card | null = null;
  private muted = new Set<string>();
  private timer: ReturnType<typeof setTimeout> | undefined;
  private upload: Promise<void> | null = null;
  private nextChunk: Uint8Array | null = null;
  private generation = 0;
  private disposed = false;
  private visible = true;

  constructor(api: Api, microphone: (enabled: boolean) => Promise<void>, changed: () => void) {
    this.api = api;
    this.microphone = microphone;
    this.changed = changed;
  }
  private emit() { if (!this.disposed) this.changed(); }
  private cancelTimer() { clearTimeout(this.timer); }
  private async action(work: () => Promise<void>) {
    if (this.state.busy || this.disposed) return;
    this.state.busy = true;
    this.state.error = '';
    this.emit();
    try { await work(); }
    catch (error) { this.state.error = error instanceof Error ? error.message : 'Action failed. Please try again.'; }
    finally { this.state.busy = false; this.emit(); }
  }
  async start() {
    await this.action(async () => {
      if (this.state.listening) return;
      if (this.state.phase !== 'active') {
        if (this.state.drafts.some(draft => !this.state.sent.includes(draft.draft_id))) {
          throw new Error('Approve the remaining drafts before starting another meeting.');
        }
        const result = await this.api.start();
        this.session = result.session_id;
        Object.assign(this.state, { phase: 'active', queued: [], drafts: [], sent: [], transcript: '', notice: '', card: null });
        this.pending = [];
        this.lastCard = null;
      }
      this.pcm.clear();
      await this.microphone(true);
      if (this.disposed || !this.visible) { await this.microphone(false); return; }
      this.state.listening = true;
    });
  }
  private async stopCapture() {
    if (this.state.listening) {
      await this.microphone(false);
      this.state.listening = false;
    }
    this.generation++;
    const tail = this.pcm.flush();
    await this.upload;
    if (tail) {
      const result = await this.api.listen(this.session, tail);
      if (this.state.phase === 'active') this.receive(result);
    }
  }
  async pause() {
    await this.action(async () => { await this.stopCapture(); });
  }
  async suspend() {
    this.visible = false;
    try { await this.stopCapture(); }
    catch (error) { this.state.error = error instanceof Error ? error.message : 'Could not pause microphone.'; }
    this.emit();
  }
  foreground() { this.visible = true; this.emit(); }
  async listenText(text: string) {
    if (this.state.phase !== 'active' || !text.trim()) return;
    await this.action(async () => { this.receive(await this.api.listenText(this.session, text.trim())); });
  }
  private receive(result: ListenResult) {
    if (this.state.phase !== 'active' || this.disposed) return;
    this.state.transcript = result.transcript;
    for (const card of result.cards) {
      if (!this.muted.has(card.term_id) && this.state.card?.term_id !== card.term_id &&
          !this.pending.some(c => c.term_id === card.term_id)) this.pending.push(card);
    }
    if (!this.state.card && !this.state.notice) this.showNext(false);
    this.emit();
  }
  private showNext(replay: boolean) {
    this.cancelTimer();
    this.state.notice = '';
    this.state.card = this.pending.shift() ?? (replay ? this.lastCard : null);
    if (this.state.card) {
      this.lastCard = this.state.card;
      this.timer = setTimeout(() => { this.showNext(false); }, 8000);
    }
    this.emit();
  }
  next() {
    if (this.state.busy || this.state.phase !== 'active') return;
    this.showNext(!this.state.card && !this.state.notice);
  }
  async queue() {
    if (this.state.phase !== 'active' || !this.state.card) return;
    await this.action(async () => {
      const card = this.state.card!;
      this.cancelTimer();
      try {
        const result = await this.api.queue(card.card_id, this.session);
        this.state.queued.push(card);
        this.state.card = null;
        this.state.notice = `Queued for ${result.owner_name}`;
        this.timer = setTimeout(() => { this.showNext(false); }, 2000);
      } catch (error) {
        this.timer = setTimeout(() => { this.showNext(false); }, 8000);
        throw error;
      }
    });
  }
  async mute() {
    if (this.state.phase !== 'active' || !this.state.card) return;
    await this.action(async () => {
      const card = this.state.card!;
      this.cancelTimer();
      try { await this.api.mute(card.term_id); }
      catch (error) {
        this.timer = setTimeout(() => { this.showNext(false); }, 8000);
        throw error;
      }
      this.muted.add(card.term_id);
      this.pending = this.pending.filter(c => c.term_id !== card.term_id);
      if (this.lastCard?.term_id === card.term_id) this.lastCard = null;
      this.showNext(false);
    });
  }
  async end() {
    if (this.state.phase !== 'active') return;
    await this.action(async () => {
      this.state.phase = 'ending';
      this.cancelTimer();
      this.emit();
      try {
        await this.stopCapture();
        const result = await this.api.end(this.session);
        this.state.drafts = result.drafts;
        this.state.phase = 'ended';
        this.state.card = null;
        this.state.notice = '';
        this.state.transcript = '';
        this.pending = [];
        this.lastCard = null;
      } catch (error) {
        this.state.phase = 'active';
        if (this.state.card) this.timer = setTimeout(() => { this.showNext(false); }, 8000);
        throw error;
      }
    });
  }
  async send(id: string) {
    if (this.state.phase !== 'ended' || this.state.sent.includes(id) || !this.state.drafts.some(d => d.draft_id === id)) return;
    await this.action(async () => { await this.api.send(id); this.state.sent.push(id); });
  }
  audio(frame: Uint8Array) {
    if (!this.state.listening || this.state.phase !== 'active' || this.disposed) return;
    for (const chunk of this.pcm.push(frame)) this.enqueueAudio(chunk);
  }
  private enqueueAudio(chunk: Uint8Array) {
    // shortcut: keep only the newest waiting chunk under slow network; use realtime STT if this drops speech.
    this.nextChunk = chunk;
    if (this.upload) return;
    const session = this.session;
    const generation = this.generation;
    this.upload = (async () => {
      while (this.nextChunk && !this.disposed) {
        const pcm = this.nextChunk;
        this.nextChunk = null;
        try {
          const result = await this.api.listen(session, pcm);
          if (this.generation === generation && this.state.listening) {
            this.state.error = '';
            this.receive(result);
          }
        } catch (error) {
          if (!this.disposed) {
            this.state.error = error instanceof Error ? error.message : 'Audio upload failed.';
            this.emit();
          }
        }
      }
    })().finally(() => { this.upload = null; });
  }
  dispose() {
    this.disposed = true;
    this.generation++;
    this.cancelTimer();
    this.nextChunk = null;
    this.pcm.clear();
    this.state.listening = false;
    void this.microphone(false).catch(() => {});
  }
}
