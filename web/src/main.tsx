import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { createApi } from '../../glasses/src/api.ts';
import type { Digest, DigestEntry } from '../../glasses/src/api.ts';
import { createMockApi } from '../../glasses/src/mock.ts';
import './style.css';

const api = __MOCK_MODE__ ? createMockApi() : createApi(__BACKEND_URL__);
const demoReady = __MOCK_MODE__ ? (async () => {
  const { session_id } = await api.start();
  const { cards } = await api.listenText(session_id, 'Bluebird and FCS');
  await api.queue(cards[0].card_id, session_id);
  const { drafts } = await api.end(session_id);
  await api.send(drafts[0].draft_id);
})() : Promise.resolve();

function field(entry: DigestEntry, keys: string[]): string {
  if (typeof entry === 'string') return entry;
  for (const key of keys) if (typeof entry[key] === 'string') return entry[key];
  return '';
}

function count(value: number, one: string, many: string): string {
  return `${value} ${value === 1 ? one : many}`;
}

function DigestList({ title, entries, kind, empty }: { title: string; entries: DigestEntry[]; kind: 'terms' | 'people' | 'sent'; empty: string }) {
  const names = kind === 'terms' ? ['term', 'name'] : kind === 'people' ? ['name', 'owner_name', 'to_name'] : ['subject', 'to_name', 'owner_name'];
  const details = kind === 'terms' ? ['meaning', 'line1', 'definition'] : kind === 'people' ? ['team', 'owner_team'] : ['to_name', 'body'];
  return <section className={`digest-section ${kind}`} aria-label={title}>
    <div className="section-heading"><h2>{title}</h2><span>{entries.length}</span></div>
    <ul className="entries">{entries.length ? entries.map((entry, index) => {
      const name = field(entry, names);
      const detail = typeof entry === 'string' ? '' : field(entry, details);
      return <li key={index}>{kind === 'terms' && <span className="digest-index">{String(index + 1).padStart(2, '0')}</span>}<div className="digest-copy"><strong>{name || 'Details available in your meeting'}</strong>{detail && <span>{detail}</span>}</div></li>;
    }) : <li className="empty">{empty}</li>}</ul>
  </section>;
}

function App() {
  const [digest, setDigest] = useState<Digest | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let current = true;
    setLoading(true); setError('');
    void demoReady.then(() => api.digest()).then(data => { if (current) setDigest(data); })
      .catch(reason => { if (current) setError(reason instanceof Error ? reason.message : 'Could not load your digest.'); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [revision]);
  const firstTerm = digest?.terms_learned[0];
  return <main className="digest">
    <header className="masthead"><a className="wordmark" href="./">footnote<span aria-hidden="true">*</span></a><div className="header-actions"><span className="mode">{__MOCK_MODE__ ? 'Sample digest' : 'Your digest'}</span><button disabled={loading} onClick={() => setRevision(value => value + 1)}>{loading ? 'Refreshing…' : 'Refresh'}</button></div></header>
    <div className="digest-intro"><div><span className="eyebrow">After the room</span><h1>{digest?.terms_learned.length ? `${digest.terms_learned.length} things to remember.` : 'What stayed with you.'}</h1><p>Terms, people, and the questions you sent.</p></div>{digest && <div className="digest-meta"><span>{count(digest.terms_learned.length, 'word', 'words')}</span><span>{count(digest.people_to_meet.length, 'person', 'people')}</span><span>{count(digest.sent.length, 'message', 'messages')} sent</span></div>}</div>
    {loading && !digest && <p className="secondary" role="status">Gathering your meeting notes…</p>}
    {error && <div className="error" role="alert">{error} Use Refresh to try again.</div>}
    {digest && <div aria-busy={loading}>
      {firstTerm && <div className="memory-strip"><span>From the meeting</span><strong>{field(firstTerm, ['term', 'name'])}</strong><p>{field(firstTerm, ['meaning', 'line1', 'definition'])}</p></div>}
      <div className="digest-ledger">
        <DigestList title="Words caught" entries={digest.terms_learned} kind="terms" empty="Words you meet during a session will appear here." />
        <DigestList title="People to meet" entries={digest.people_to_meet} kind="people" empty="When a word has an owner, you can find them here." />
      </div>
      <DigestList title="Conversation started" entries={digest.sent} kind="sent" empty="No messages sent. Review a draft on your phone when you are ready." />
    </div>}
    <aside className="quiet-note">Familiar terms fade from the glasses after three sightings. Swipe down on G2 to let a term go sooner.</aside>
    <footer>Less jargon. More belonging.<span>Footnote / LA Hacks 2026</span></footer>
  </main>;
}

createRoot(document.getElementById('root')!).render(<App />);
