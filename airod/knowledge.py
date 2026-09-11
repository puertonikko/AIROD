"""Knowledge sectors — the information a given agent learns from.

A *sector* is just a folder of ``.md`` / ``.txt`` documents. AIROD chunks them,
builds a lightweight BM25 index (pure Python, no external services or model
downloads), and retrieves the most relevant passages for a query at run time.

This is how an agent "learns from a sector": it retrieves from it, so the
grounding is always traceable to a real quoted passage. Swap this module for an
embedding-based vector store later without touching the rest of the system —
the ``retrieve`` contract is all the orchestrator depends on.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


@dataclass
class Passage:
    source: str    # filename the chunk came from
    text: str      # the chunk itself

    _tokens: list[str] | None = None

    @property
    def tokens(self) -> list[str]:
        if self._tokens is None:
            self._tokens = _tokenize(self.text)
        return self._tokens


def _chunk(text: str, target_words: int = 120) -> list[str]:
    """Split a document into ~paragraph-sized chunks, respecting blank lines."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buf: list[str] = []
    count = 0
    for para in paras:
        words = para.split()
        if count + len(words) > target_words and buf:
            chunks.append(" ".join(buf))
            buf, count = [], 0
        buf.append(para)
        count += len(words)
    if buf:
        chunks.append(" ".join(buf))
    return chunks


class KnowledgeSector:
    """A BM25 index over the documents in one sector folder."""

    def __init__(self, path: str, k1: float = 1.5, b: float = 0.75) -> None:
        self.path = Path(path)
        self.k1 = k1
        self.b = b
        self.passages: list[Passage] = []
        self._df: Counter[str] = Counter()   # document frequency per term
        self._avg_len = 0.0
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        for file in sorted(self.path.rglob("*")):
            if file.suffix.lower() not in {".md", ".txt"}:
                continue
            text = file.read_text(encoding="utf-8", errors="replace")
            for chunk in _chunk(text):
                self.passages.append(Passage(source=file.name, text=chunk))

        for p in self.passages:
            for term in set(p.tokens):
                self._df[term] += 1
        if self.passages:
            self._avg_len = sum(len(p.tokens) for p in self.passages) / len(self.passages)

    @property
    def is_empty(self) -> bool:
        return not self.passages

    def _idf(self, term: str) -> float:
        n = len(self.passages)
        df = self._df.get(term, 0)
        # BM25 idf with +1 smoothing to stay non-negative.
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def retrieve(self, query: str, k: int = 4) -> list[Passage]:
        """Return the top-k passages most relevant to ``query``."""
        if self.is_empty:
            return []
        q_terms = _tokenize(query)
        scored: list[tuple[float, Passage]] = []
        for p in self.passages:
            freqs = Counter(p.tokens)
            dl = len(p.tokens) or 1
            score = 0.0
            for term in q_terms:
                if term not in freqs:
                    continue
                tf = freqs[term]
                idf = self._idf(term)
                denom = tf + self.k1 * (1 - self.b + self.b * dl / (self._avg_len or 1))
                score += idf * (tf * (self.k1 + 1)) / denom
            if score > 0:
                scored.append((score, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored[:k]]
