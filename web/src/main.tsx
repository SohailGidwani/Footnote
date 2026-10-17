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

function DigestList({ title, entries, kind, empty }: { title: string; entries: DigestEntry[]; kind: 'terms' | 'people' | 'sent'; empty: string }) {
  const names = kind === 'terms' ? ['term', 'name'] : kind === 'people' ? ['name', 'owner_name', 'to_name'] : ['subject', 'to_name', 'owner_name'];
  const details = kind === 'terms' ? ['meaning', 'line1', 'definition'] : kind === 'people' ? ['team', 'owner_team'] : ['to_name', 'body'];
  return <section className={`digest-section ${kind}`} aria-label={title}>
    <div className="section-heading"><h2>{title}</h2><span>{entries.length}</span></div>
    <ul className="entries">{entries.length ? entries.map((entry, index) => {
      const name = field(entry, names);
      const detail = typeof entry === 'string' ? '' : field(entry, details);
      return <li key={index}><strong>{name || 'Details available in your meeting'}</strong>{detail && <span>{detail}</span>}</li>;
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
  return <main className="digest">
    <header className="masthead"><a className="wordmark" href="./">footnote<span aria-hidden="true">*</span></a><span className="mode">{__MOCK_MODE__ ? 'Sample digest / demo data' : 'Your meeting digest'}</span></header>
    <div className="digest-intro"><p className="context">Halcyon Robotics / Your first week</p><h1>A little more<br />familiar.</h1><p>The words make sense. The names become people.<br className="desktop-break" /> Your next conversation already has a starting point.</p></div>
    <div className="digest-toolbar"><h2>Your day, with context.</h2><button disabled={loading} onClick={() => setRevision(value => value + 1)}>{loading ? 'Refreshing…' : 'Refresh digest'}</button></div>
    {loading && !digest && <p className="secondary" role="status">Gathering your meeting notes…</p>}
    {error && <div className="error" role="alert">{error} Use Refresh digest to try again.</div>}
    {digest && <div aria-busy={loading}>
      <DigestList title="Terms learned today" entries={digest.terms_learned} kind="terms" empty="New words will land here after your first meeting. A little context goes a long way." />
      <DigestList title="People to meet" entries={digest.people_to_meet} kind="people" empty="When a term has an owner, you'll find your person here." />
      <DigestList title="Conversations started" entries={digest.sent} kind="sent" empty="No messages sent yet. Approve a follow-up on your phone when you're ready." />
    </div>}
    <aside className="quiet-note"><span aria-hidden="true">*</span><p>It gets quieter as you learn.<small>After three sightings, familiar terms step out of the way. Swipe down on G2 to let a term go sooner.</small></p></aside>
    <footer>Less jargon. More belonging.<span>Footnote / LA Hacks 2026</span></footer>
  </main>;
}

createRoot(document.getElementById('root')!).render(<App />);
