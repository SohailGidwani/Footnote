"""SQLite store: people, terms, sessions, seen, queue, drafts (+ cards).

All access happens on the event-loop thread, so one shared connection is safe.
"""
import json
import re
import sqlite3
import time
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path

SEEN_LIMIT = 3  # a term stops appearing after this many sightings

SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, short_name TEXT NOT NULL,
  team TEXT NOT NULL, role TEXT NOT NULL DEFAULT '', email TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS terms (
  id TEXT PRIMARY KEY, term TEXT NOT NULL, aliases TEXT NOT NULL DEFAULT '[]',
  meaning TEXT NOT NULL, owner_id TEXT NOT NULL REFERENCES people(id),
  source TEXT NOT NULL CHECK (source IN ('glossary','llm')),
  confidence REAL NOT NULL DEFAULT 1.0
);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY, started_at REAL NOT NULL, ended_at REAL
);
CREATE TABLE IF NOT EXISTS seen (
  term_id TEXT PRIMARY KEY REFERENCES terms(id),
  count INTEGER NOT NULL DEFAULT 0, muted INTEGER NOT NULL DEFAULT 0,
  last_seen REAL
);
CREATE TABLE IF NOT EXISTS cards (
  card_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
  term_id TEXT NOT NULL REFERENCES terms(id), created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
  term_id TEXT NOT NULL, owner_id TEXT NOT NULL, created_at REAL NOT NULL,
  UNIQUE (session_id, term_id)
);
CREATE TABLE IF NOT EXISTS drafts (
  id TEXT PRIMARY KEY, session_id TEXT NOT NULL, owner_id TEXT NOT NULL,
  subject TEXT NOT NULL, body TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','sent')),
  sent_at REAL
);
"""

_ASCII_FIXES = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": "...", " ": " ",
})


def ascii_clean(text: str) -> str:
    """The G2 font drops characters outside its table, so keep cards plain ASCII."""
    text = unicodedata.normalize("NFKD", str(text).translate(_ASCII_FIXES))
    text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text).strip()


def clip(text: str, limit: int) -> str:
    text = ascii_clean(text)
    return text if len(text) <= limit else text[:limit].rstrip()


def short_name(full: str) -> str:
    parts = full.split()
    return f"{parts[0]} {parts[-1][0]}." if len(parts) > 1 else full


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class Store:
    def __init__(self, path: str, pack_path: Path):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.pack = json.loads(Path(pack_path).read_text(encoding="utf-8"))
        self.terms_version = 0  # bumps whenever the glossary changes (matcher rebuilds)
        self.seed()

    # --- seeding -----------------------------------------------------------
    def seed(self) -> None:
        """Reseed people and glossary terms from the company pack. Seen counts and
        cached LLM terms are kept."""
        c = self.conn
        people_ids = [p["id"] for p in self.pack["people"]]
        for p in self.pack["people"]:
            c.execute(
                "INSERT INTO people (id,name,short_name,team,role,email) VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, short_name=excluded.short_name, "
                "team=excluded.team, role=excluded.role, email=excluded.email",
                (p["id"], p["name"], short_name(p["name"]), p["team"], p.get("role", ""), p["email"]),
            )
        term_ids = [t["id"] for t in self.pack["terms"]]
        for t in self.pack["terms"]:
            if t["owner_id"] not in people_ids:
                raise ValueError(f"term {t['id']} has unknown owner {t['owner_id']}")
            c.execute(
                "INSERT INTO terms (id,term,aliases,meaning,owner_id,source,confidence) "
                "VALUES (?,?,?,?,?, 'glossary', 1.0) "
                "ON CONFLICT(id) DO UPDATE SET term=excluded.term, aliases=excluded.aliases, "
                "meaning=excluded.meaning, owner_id=excluded.owner_id, source='glossary', confidence=1.0",
                (t["id"], t["term"], json.dumps(t.get("aliases", [])), t["meaning"], t["owner_id"]),
            )
        marks = ",".join("?" * len(term_ids))
        stale = [r["id"] for r in c.execute(
            f"SELECT id FROM terms WHERE source='glossary' AND id NOT IN ({marks})", term_ids)]
        for tid in stale:
            self._delete_term(tid)
        c.commit()
        self.terms_version += 1

    def _delete_term(self, term_id: str) -> None:
        for table, col in (("seen", "term_id"), ("cards", "term_id"), ("queue", "term_id"), ("terms", "id")):
            self.conn.execute(f"DELETE FROM {table} WHERE {col}=?", (term_id,))

    def reset(self) -> None:
        """Rehearsal helper: forget sightings, meetings and cached LLM terms."""
        for table in ("seen", "cards", "queue", "drafts", "sessions"):
            self.conn.execute(f"DELETE FROM {table}")
        self.conn.execute("DELETE FROM terms WHERE source='llm'")
        self.conn.commit()
        self.terms_version += 1

    # --- people / terms -----------------------------------------------------
    def people_text(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM people ORDER BY name")]

    def person(self, person_id: str):
        return self.conn.execute("SELECT * FROM people WHERE id=?", (person_id,)).fetchone()

    def all_terms(self) -> list[dict]:
        out = []
        for r in self.conn.execute("SELECT * FROM terms"):
            d = dict(r)
            d["aliases"] = json.loads(d["aliases"])
            out.append(d)
        return out

    def term(self, term_id: str):
        return self.conn.execute(
            "SELECT t.*, p.short_name AS owner_name, p.team AS owner_team, p.name AS owner_full, "
            "p.email AS owner_email FROM terms t JOIN people p ON p.id=t.owner_id WHERE t.id=?",
            (term_id,)).fetchone()

    def add_llm_term(self, term: str, meaning: str, owner_id: str, confidence: float) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", term.lower()).strip("_") or uuid.uuid4().hex[:8]
        term_id = f"t_llm_{slug}"
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO terms (id,term,aliases,meaning,owner_id,source,confidence) "
            "VALUES (?,?,?,?,?, 'llm', ?)",
            (term_id, clip(term, 24), json.dumps([]), clip(meaning, 44), owner_id, confidence))
        self.conn.commit()
        if cur.rowcount:
            self.terms_version += 1
        return term_id

    # --- seen / mute --------------------------------------------------------
    def seen_state(self, term_id: str) -> tuple[int, bool]:
        r = self.conn.execute("SELECT count, muted FROM seen WHERE term_id=?", (term_id,)).fetchone()
        return (r["count"], bool(r["muted"])) if r else (0, False)

    def is_hidden(self, term_id: str) -> bool:
        count, muted = self.seen_state(term_id)
        return muted or count >= SEEN_LIMIT

    def bump_seen(self, term_id: str) -> None:
        self.conn.execute(
            "INSERT INTO seen (term_id,count,muted,last_seen) VALUES (?,1,0,?) "
            "ON CONFLICT(term_id) DO UPDATE SET count=count+1, last_seen=excluded.last_seen",
            (term_id, time.time()))
        self.conn.commit()

    def mute(self, term_id: str) -> bool:
        if not self.conn.execute("SELECT 1 FROM terms WHERE id=?", (term_id,)).fetchone():
            return False
        self.conn.execute(
            "INSERT INTO seen (term_id,count,muted,last_seen) VALUES (?,0,1,?) "
            "ON CONFLICT(term_id) DO UPDATE SET muted=1", (term_id, time.time()))
        self.conn.commit()
        return True

    # --- sessions / cards / queue ------------------------------------------
    def create_session(self) -> str:
        sid = new_id("s")
        self.conn.execute("INSERT INTO sessions (id,started_at) VALUES (?,?)", (sid, time.time()))
        self.conn.commit()
        return sid

    def session(self, session_id: str):
        return self.conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()

    def shown_for_session(self, session_id: str) -> set[str]:
        return {r["term_id"] for r in self.conn.execute(
            "SELECT DISTINCT term_id FROM cards WHERE session_id=?", (session_id,))}

    def make_card(self, session_id: str, term_id: str) -> dict:
        t = self.term(term_id)
        card_id = new_id("c")
        self.conn.execute("INSERT INTO cards (card_id,session_id,term_id,created_at) VALUES (?,?,?,?)",
                          (card_id, session_id, term_id, time.time()))
        self.conn.commit()
        owner_name = clip(t["owner_name"], 40)
        owner_team = clip(t["owner_team"], max(0, 40 - len(owner_name)))
        return {
            "card_id": card_id, "term_id": term_id,
            "term": clip(t["term"].upper(), 24), "line1": clip(t["meaning"], 44),
            "owner_name": owner_name, "owner_team": owner_team,
            "source": t["source"], "confidence": round(float(t["confidence"]), 2),
        }

    def card(self, card_id: str):
        return self.conn.execute("SELECT * FROM cards WHERE card_id=?", (card_id,)).fetchone()

    def queue_card(self, session_id: str, term_id: str, owner_id: str) -> bool:
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO queue (session_id,term_id,owner_id,created_at) VALUES (?,?,?,?)",
            (session_id, term_id, owner_id, time.time()))
        self.conn.commit()
        return bool(cur.rowcount)

    def queued_by_owner(self, session_id: str) -> dict[str, list]:
        grouped: dict[str, list] = {}
        for r in self.conn.execute(
                "SELECT q.owner_id, t.term, t.meaning FROM queue q JOIN terms t ON t.id=q.term_id "
                "WHERE q.session_id=? ORDER BY q.id", (session_id,)):
            grouped.setdefault(r["owner_id"], []).append(r)
        return grouped

    # --- drafts ---------------------------------------------------------------
    def add_draft(self, session_id: str, owner_id: str, subject: str, body: str) -> str:
        did = new_id("d")
        self.conn.execute("INSERT INTO drafts (id,session_id,owner_id,subject,body) VALUES (?,?,?,?,?)",
                          (did, session_id, owner_id, subject, body))
        self.conn.commit()
        return did

    def draft_owners(self, session_id: str) -> set[str]:
        return {r["owner_id"] for r in self.conn.execute(
            "SELECT owner_id FROM drafts WHERE session_id=?", (session_id,))}

    def save_preview_draft(self, session_id: str, owner_id: str, subject: str, body: str) -> None:
        """Save a usable template before queue returns. A new term invalidates old prose."""
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            session = self.session(session_id)
            if not session or session["ended_at"] is not None:
                raise ValueError("Session already ended")
            row = self.conn.execute(
                "SELECT id, subject, status FROM drafts WHERE session_id=? AND owner_id=? ORDER BY rowid LIMIT 1",
                (session_id, owner_id)).fetchone()
            if row is None:
                self.conn.execute(
                    "INSERT INTO drafts (id,session_id,owner_id,subject,body) VALUES (?,?,?,?,?)",
                    (new_id("d"), session_id, owner_id, subject, body))
            elif row["status"] == "draft" and row["subject"] != subject:
                self.conn.execute("UPDATE drafts SET subject=?, body=? WHERE id=?", (subject, body, row["id"]))
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise

    def update_preview_if_current(self, session_id: str, owner_id: str,
                                  subject: str, body: str) -> bool:
        """Use StepFun prose only if the queue still matches and the meeting is open."""
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            row = self.conn.execute(
                "SELECT d.id FROM drafts d JOIN sessions s ON s.id=d.session_id "
                "WHERE d.session_id=? AND d.owner_id=? AND d.subject=? "
                "AND d.status='draft' AND s.ended_at IS NULL ORDER BY d.rowid LIMIT 1",
                (session_id, owner_id, subject)).fetchone()
            if row:
                self.conn.execute("UPDATE drafts SET body=? WHERE id=?", (body, row["id"]))
            self.conn.commit()
            return row is not None
        except BaseException:
            self.conn.rollback()
            raise

    def complete_session(self, session_id: str, drafts: list[tuple[str, str, str]]) -> None:
        """Write every missing owner draft and the end marker as one transaction.

        This also repairs a session left with partial drafts by an older server.
        BEGIN IMMEDIATE serializes writers from separate server processes.
        """
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            existing = {r["owner_id"]: r for r in self.conn.execute(
                "SELECT id, owner_id, subject, status FROM drafts WHERE session_id=? ORDER BY rowid",
                (session_id,))}
            for owner_id, subject, body in drafts:
                row = existing.get(owner_id)
                if row is None:
                    self.conn.execute(
                        "INSERT INTO drafts (id,session_id,owner_id,subject,body) VALUES (?,?,?,?,?)",
                        (new_id("d"), session_id, owner_id, subject, body))
                    existing[owner_id] = True
                elif row["status"] == "draft" and row["subject"] != subject:
                    self.conn.execute("UPDATE drafts SET subject=?, body=? WHERE id=?", (subject, body, row["id"]))
            expected = {r["owner_id"] for r in self.conn.execute(
                "SELECT DISTINCT owner_id FROM queue WHERE session_id=?", (session_id,))}
            if not expected.issubset(existing.keys()):
                raise RuntimeError("Cannot end session with missing owner drafts")
            self.conn.execute("UPDATE sessions SET ended_at=COALESCE(ended_at,?) WHERE id=?",
                              (time.time(), session_id))
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise

    def draft_dict(self, row) -> dict:
        p = self.person(row["owner_id"])
        terms = [r["term"] for r in self.conn.execute(
            "SELECT t.term FROM queue q JOIN terms t ON t.id=q.term_id "
            "WHERE q.session_id=? AND q.owner_id=? ORDER BY q.id", (row["session_id"], row["owner_id"]))]
        return {"draft_id": row["id"], "to_name": p["name"], "to_email": p["email"],
                "subject": row["subject"], "body": row["body"], "terms": terms}

    def drafts_for_session(self, session_id: str) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM drafts WHERE session_id=? ORDER BY rowid", (session_id,))
        return [self.draft_dict(r) for r in rows.fetchall()]

    def draft(self, draft_id: str):
        return self.conn.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()

    def mark_sent(self, draft_id: str) -> None:
        self.conn.execute("UPDATE drafts SET status='sent', sent_at=? WHERE id=?", (time.time(), draft_id))
        self.conn.commit()

    # --- digest ---------------------------------------------------------------
    def _person_entry(self, person_id: str) -> dict:
        p = self.person(person_id)
        return {"name": p["name"], "team": p["team"], "email": p["email"], "terms": [], "question_queued": False}

    def digest(self, window_s: float = 24 * 3600) -> dict:
        since = time.time() - window_s
        terms, people = [], {}
        rows = self.conn.execute(
            "SELECT t.id, t.term, t.meaning, t.source, s.count, s.muted, p.id AS pid, p.name, p.team "
            "FROM seen s JOIN terms t ON t.id=s.term_id JOIN people p ON p.id=t.owner_id "
            "WHERE (s.count>0 OR s.muted=1) AND s.last_seen>=? ORDER BY s.last_seen DESC", (since,))
        for r in rows:
            terms.append({"term": r["term"], "meaning": r["meaning"], "owner_name": r["name"],
                          "owner_team": r["team"], "seen_count": r["count"], "muted": bool(r["muted"]),
                          "source": r["source"]})
            people.setdefault(r["pid"], self._person_entry(r["pid"]))["terms"].append(r["term"])
        for r in self.conn.execute("SELECT DISTINCT owner_id FROM queue WHERE created_at>=?", (since,)):
            people.setdefault(r["owner_id"], self._person_entry(r["owner_id"]))["question_queued"] = True
        ordered = sorted(people.values(), key=lambda i: not i["question_queued"])  # asked-about people first
        sent = []
        for r in self.conn.execute(
                "SELECT d.*, p.name, p.team FROM drafts d JOIN people p ON p.id=d.owner_id "
                "WHERE d.status='sent' ORDER BY d.sent_at DESC"):
            sent.append({"to_name": r["name"], "to_team": r["team"], "subject": r["subject"],
                         "sent_at": datetime.fromtimestamp(r["sent_at"], timezone.utc).isoformat(timespec="seconds")})
        return {"terms_learned": terms, "people_to_meet": ordered, "sent": sent}
