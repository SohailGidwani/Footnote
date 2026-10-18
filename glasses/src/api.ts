export interface Card {
  card_id: string;
  term_id: string;
  term: string;
  line1: string;
  owner_name: string;
  owner_team: string;
  source: 'glossary' | 'llm';
  confidence: number;
}

export interface Draft {
  draft_id: string;
  to_name: string;
  to_email: string;
  subject: string;
  body: string;
  terms: string[];
}

// The frozen contract specifies digest arrays, but leaves entry fields open.
export type DigestEntry = string | Record<string, unknown>;
export interface Digest {
  terms_learned: DigestEntry[];
  people_to_meet: DigestEntry[];
  sent: DigestEntry[];
}
export interface ListenResult { transcript: string; cards: Card[] }
export interface Api {
  start(): Promise<{ session_id: string }>;
  listen(session: string, pcm: Uint8Array): Promise<ListenResult>;
  listenText(session: string, text: string): Promise<ListenResult>;
  queue(card: string, session: string): Promise<{ queued: true; owner_name: string }>;
  mute(term: string): Promise<{ muted: true }>;
  end(session: string): Promise<{ drafts: Draft[] }>;
  send(draft: string): Promise<{ sent: true }>;
  discard(draft: string): Promise<{ discarded: true }>;
  digest(): Promise<Digest>;
}

export function validateBackendUrl(value: string): string {
  let url: URL;
  try { url = new URL(value); } catch { throw new Error('Set BACKEND_URL to the public HTTPS backend origin.'); }
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
  if ((url.protocol !== 'https:' && !(local && url.protocol === 'http:')) ||
      url.username || url.password || url.pathname !== '/' || url.search || url.hash) {
    throw new Error('BACKEND_URL must be an HTTPS origin without credentials, a path, or query.');
  }
  return url.origin;
}

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
function strings(value: Record<string, unknown>, keys: string[]): boolean {
  return keys.every(key => typeof value[key] === 'string' && (value[key] as string).length > 0);
}
function isCard(value: unknown): value is Card {
  return record(value) && strings(value, ['card_id', 'term_id', 'term', 'line1', 'owner_name', 'owner_team']) &&
    (value.term as string).length <= 24 && (value.line1 as string).length <= 44 &&
    (value.owner_name as string).length + (value.owner_team as string).length <= 40 &&
    ['glossary', 'llm'].includes(value.source as string) && typeof value.confidence === 'number' &&
    Number.isFinite(value.confidence) && value.confidence >= 0 && value.confidence <= 1;
}
function isDraft(value: unknown): value is Draft {
  return record(value) && strings(value, ['draft_id', 'to_name', 'to_email', 'subject', 'body']) &&
    Array.isArray(value.terms) && value.terms.every(term => typeof term === 'string');
}
function isListen(value: unknown): value is ListenResult {
  return record(value) && typeof value.transcript === 'string' && Array.isArray(value.cards) &&
    value.cards.length <= 2 && value.cards.every(isCard);
}
function isDigest(value: unknown): value is Digest {
  return record(value) && ['terms_learned', 'people_to_meet', 'sent'].every(key =>
    Array.isArray(value[key]) && value[key].every(item => typeof item === 'string' || record(item)));
}

export function createApi(backendUrl: string, fetcher: typeof fetch = fetch): Api {
  const base = validateBackendUrl(backendUrl);
  async function request<T>(path: string, validate: (data: unknown) => data is T, body?: unknown, raw = false): Promise<T> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 6000);
    try {
      const response = await fetcher(`${base}${path}`, {
        method: body === undefined ? 'GET' : 'POST',
        signal: controller.signal,
        headers: body === undefined ? undefined : { 'Content-Type': raw ? 'application/octet-stream' : 'application/json' },
        body: body === undefined ? undefined : raw ? (body as Uint8Array).slice().buffer : JSON.stringify(body),
      });
      if (!response.ok) throw new Error(`Backend request failed (${response.status}). Check the backend and try again.`);
      const data: unknown = await response.json();
      if (!validate(data)) throw new Error('Invalid backend response. Check the shared API contract.');
      return data;
    } catch (error) {
      if (controller.signal.aborted) throw new Error('Backend did not respond within 6 seconds. Check its status before retrying a send.');
      if (error instanceof TypeError) throw new Error('Cannot reach backend. Check the connection, CORS and app network whitelist.');
      throw error;
    } finally { clearTimeout(timeout); }
  }
  return {
    start: () => request('/session/start', (v): v is { session_id: string } => record(v) && strings(v, ['session_id']), {}),
    listen: (session, pcm) => request(`/listen?session_id=${encodeURIComponent(session)}`, isListen, pcm, true),
    listenText: (session, text) => request('/listen_text', isListen, { session_id: session, text }),
    queue: (card, session) => request(`/cards/${encodeURIComponent(card)}/queue`, (v): v is { queued: true; owner_name: string } => record(v) && v.queued === true && strings(v, ['owner_name']), { session_id: session }),
    mute: term => request(`/terms/${encodeURIComponent(term)}/mute`, (v): v is { muted: true } => record(v) && v.muted === true, {}),
    end: session => request(`/session/${encodeURIComponent(session)}/end`, (v): v is { drafts: Draft[] } => record(v) && Array.isArray(v.drafts) && v.drafts.every(isDraft), {}),
    send: draft => request(`/drafts/${encodeURIComponent(draft)}/send`, (v): v is { sent: true } => record(v) && v.sent === true, {}),
    discard: draft => request(`/drafts/${encodeURIComponent(draft)}/discard`, (v): v is { discarded: true } => record(v) && v.discarded === true, {}),
    digest: () => request('/digest', isDigest),
  };
}
