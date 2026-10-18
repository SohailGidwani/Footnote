"""Read-only answers for the Footnote chat agent."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib import error, request

from prep import meeting_prep


PACK_PATH = Path(__file__).resolve().parent.parent / "data" / "company_pack.json"
HELP = (
    "I can explain Halcyon terms and recap your Footnote meeting. "
    "Try 'What does Bluebird mean at Halcyon?', "
    "'Prep me for a platform sync about Ridgeline and FCS', 'What did I learn today?', "
    "or 'Who should I meet?'"
)


def load_pack(path: Path = PACK_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_digest(backend_url: str) -> dict:
    url = backend_url.rstrip("/") + "/digest"
    with request.urlopen(url, timeout=3) as response:
        return json.load(response)


def _mentioned_term(query: str, pack: dict) -> dict | None:
    """Find the first complete glossary term or alias in the question."""
    matches = []
    for term in pack["terms"]:
        for alias in [term["term"], *term.get("aliases", [])]:
            pattern = r"(?<!\w)" + re.escape(alias).replace(r"\ ", r"\s+") + r"(?!\w)"
            match = re.search(pattern, query, flags=re.IGNORECASE)
            if match:
                matches.append((match.start(), -len(match.group()), term))
    return min(matches, default=(None, None, None))[-1]


def _requested_unknown_term(query: str) -> str | None:
    patterns = (
        r"^what\s+does\s+(.+?)\s+mean(?:\s+at\s+halcyon)?\s*[?.!]*$",
        r"^what\s+is\s+(.+?)(?:\s+at\s+halcyon)?\s*[?.!]*$",
        r"^define\s+(.+?)(?:\s+at\s+halcyon)?\s*[?.!]*$",
    )
    for pattern in patterns:
        match = re.match(pattern, query, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(" .?!\"'")[:80]
    return None


def _term_answer(term: dict, pack: dict) -> str:
    owner = next((p for p in pack["people"] if p["id"] == term["owner_id"]), None)
    owner_text = f"{owner['name']} ({owner['team']})" if owner else "not listed"
    return f"{term['term']}: {term['meaning']}. Owner: {owner_text}."


def _learned_answer(digest: dict) -> str:
    terms = digest.get("terms_learned", [])
    if not terms:
        return "Footnote has not recorded any terms in the last 24 hours."
    lines = [f"{item['term']}: {item['meaning']}" for item in terms[:5]]
    suffix = f" And {len(terms) - 5} more." if len(terms) > 5 else ""
    return "In the last 24 hours, you learned: " + "; ".join(lines) + "." + suffix


def _people_answer(digest: dict) -> str:
    people = digest.get("people_to_meet", [])
    if not people:
        return "Footnote has not suggested anyone to meet in the last 24 hours."
    lines = []
    for person in people[:5]:
        terms = ", ".join(person.get("terms", [])) or "a queued question"
        lines.append(f"{person['name']} ({person['team']}) about {terms}")
    suffix = f" And {len(people) - 5} more." if len(people) > 5 else ""
    return "People to meet: " + "; ".join(lines) + "." + suffix


def answer_text(query: str, pack: dict, backend_url: str) -> str:
    """Answer without creating sightings or changing meeting state."""
    question = re.sub(r"^@agent1[a-z0-9]+\s+", "", query.strip(), flags=re.IGNORECASE)
    if not question:
        return HELP
    lower = question.casefold()
    if re.search(r"\b(prep|prepare)\b", lower):
        digest, history_available = {}, False
        if backend_url:
            try:
                digest = fetch_digest(backend_url)
                history_available = True
            except (error.URLError, TimeoutError, OSError, ValueError):
                pass
        return meeting_prep(question, pack, digest, history_available)
    wants_people = any(phrase in lower for phrase in (
        "who should i meet", "who do i need to meet", "people to meet", "who should i talk to"
    ))
    wants_learning = any(phrase in lower for phrase in (
        "what did i learn", "what have i learned", "what i learned", "my digest", "meeting recap"
    ))
    if wants_people or wants_learning:
        try:
            digest = fetch_digest(backend_url)
        except (error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
            return "I cannot reach the Footnote backend right now. Start it locally and try again."
        return _people_answer(digest) if wants_people else _learned_answer(digest)

    term = _mentioned_term(question, pack)
    if term:
        return _term_answer(term, pack)
    unknown = _requested_unknown_term(question)
    if unknown:
        if backend_url:
            try:
                learned = fetch_digest(backend_url).get("terms_learned", [])
            except (error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
                return (f"I do not have {unknown} in Halcyon's glossary. "
                        "I cannot check your recent meeting terms while the backend is unreachable.")
            term = _mentioned_term(unknown, {"terms": learned})
            if term:
                inferred = term.get("source") == "llm"
                origin = "Inferred from" if inferred else "From"
                label = "Suggested contact" if inferred else "Owner"
                return (f"{term['term']}: {term['meaning']}. {origin} your recent meeting. "
                        f"{label}: {term['owner_name']} ({term['owner_team']}).")
        return (f"I do not have {unknown} in Halcyon's glossary or recent meeting terms. "
                "Mention the full name and a short explanation during a meeting, then ask again.")
    return HELP
