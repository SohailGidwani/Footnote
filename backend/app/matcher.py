"""Glossary fast path: normalize a transcript, then find known terms and aliases.

Exact token match first; fuzzy (rapidfuzz token_set_ratio >= 90) only for phrases of
5+ characters, so short acronyms like DRI/RFC never fuzzy-match ordinary words.
"""
import re
import unicodedata

from rapidfuzz import fuzz

FUZZY_THRESHOLD = 90
FUZZY_MIN_CHARS = 5

_NUMBER_WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
                 "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"}
_TOKEN = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> list[str]:
    """Lowercase ASCII tokens. 'F.C.S.' -> ['fcs'], 'SEV two' -> ['sev', '2']."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    raw = [_NUMBER_WORDS.get(t, t) for t in _TOKEN.findall(text)]
    out: list[str] = []
    run: list[str] = []

    def flush() -> None:
        if len(run) >= 2:  # spelled-out letters: "f c s" / "p m"
            out.append("".join(run))
        else:
            out.extend(run)
        run.clear()

    for tok in raw:
        if len(tok) == 1 and tok.isalpha():
            run.append(tok)
        else:
            flush()
            out.append(tok)
    flush()
    return out


class Matcher:
    def __init__(self, terms: list[dict]):
        self.exact: dict[tuple[str, ...], str] = {}
        self.compact: dict[str, str] = {}
        self.fuzzy: dict[int, list[tuple[str, str]]] = {}  # n tokens -> [(phrase, term_id)]
        self.lengths: set[int] = set()
        self.known_words: set[str] = set()
        for t in terms:
            for phrase in {t["term"], *t["aliases"]}:
                toks = tokens(phrase)
                if not toks:
                    continue
                self.exact.setdefault(tuple(toks), t["id"])
                self.lengths.add(len(toks))
                compact = "".join(toks)
                if len(compact) >= FUZZY_MIN_CHARS:
                    self.compact.setdefault(compact, t["id"])
                    self.lengths.update(range(1, len(toks) + 2))
                self.known_words.update(toks)
                self.known_words.add(compact)
                joined = " ".join(toks)
                if len(joined) >= FUZZY_MIN_CHARS:
                    self.fuzzy.setdefault(len(toks), []).append((joined, t["id"]))

    def find(self, text: str) -> list[str]:
        """Term ids in order of first appearance in the transcript."""
        toks = tokens(text)
        hits: dict[str, int] = {}
        for i in range(len(toks)):
            for n in self.lengths:
                if i + n > len(toks):
                    continue
                window = toks[i:i + n]
                term_id = self.exact.get(tuple(window)) or self.compact.get("".join(window))
                if term_id:
                    hits.setdefault(term_id, i)
                    continue
                joined = " ".join(window)
                for phrase, tid in self.fuzzy.get(n, ()):
                    if tid not in hits and fuzz.token_set_ratio(joined, phrase) >= FUZZY_THRESHOLD:
                        hits[tid] = i
        return sorted(hits, key=hits.__getitem__)
