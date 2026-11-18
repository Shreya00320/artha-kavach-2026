"""
core/knowledge.py — offline retrieval over the whole knowledge base (data/kb/*.json).

The FAISS index in rag/ needs Gemini embeddings (network + key). This module gives the
chat advisor a local TF-IDF retriever so it can answer finance questions with no key,
including Hindi / Hinglish questions (via core.lang.expand_query).

Public API:
  KnowledgeBase(kb_dir=None)
  KnowledgeBase.search(query, k=3) -> list[Hit]
  KnowledgeBase.best_sentences(doc, query, max_chars=650) -> str
  get_kb() -> process-wide cached KnowledgeBase
"""

from __future__ import annotations

import json
import re
import warnings
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np

from core.lang import expand_query, tokenize

_STOP = {
    "a", "an", "the", "is", "are", "was", "were", "be", "to", "of", "in", "on", "for", "and", "or",
    "it", "its", "my", "me", "i", "you", "your", "do", "does", "did", "can", "should", "would",
    "will", "this", "that", "with", "as", "at", "by", "from", "about", "if", "so", "how", "what",
    "which", "who", "when", "where", "why", "there", "their", "they", "we", "us", "am", "have",
    "has", "had", "not", "no", "yes", "than", "then", "also", "just", "very", "much", "more",
    # Hinglish glue words
    "hai", "hain", "ho", "hota", "hoti", "hote", "ka", "ki", "ke", "ko", "se", "me", "mein",
    "par", "aur", "toh", "to", "bhi", "kya", "kaise", "karun", "karein", "karna", "chahiye",
    # Devanagari glue words
    "है", "हैं", "का", "की", "के", "को", "में", "से", "पर", "और", "भी", "तो", "क्या", "कैसे",
    "होता", "होती", "होते", "करें", "करना", "चाहिए", "कर",
}

HEAD_WEIGHT = 0.8
# Book summaries should surface for book/author/concept questions, not crowd out the core
# how-to entries on general questions ("how do I save money?").
BOOK_PENALTY = 0.75
_BOOK_CUES = re.compile(r"(book|books|author|wrote|written|read|reading|chapter|says|according to|recommend)", re.I)

_ABBREV = re.compile(r"\b(?:Mr|Mrs|Ms|Dr|Prof|St|vs|etc|approx|Rs|No)\.", re.I)
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(‘'\"₹])")


@dataclass
class Doc:
    id: str
    title: str
    publisher: str
    url: str
    text: str
    summary_hi: str = ""
    summary_hinglish: str = ""
    aliases: str = ""
    topics: list[str] = field(default_factory=list)
    verified: bool = True


@dataclass
class Hit:
    doc: Doc
    score: float


def _stem(t: str) -> str:
    """Tiny plural stemmer: taxes->tax, stocks->stock, policies->policy (leaves 'loss', 'gas' alone)."""
    if not t.isascii() or len(t) <= 3:
        return t
    if t.endswith("ies") and len(t) > 4:
        return t[:-3] + "y"
    if re.search(r"(xes|ches|shes|sses|zes)$", t):
        return t[:-2]
    if t.endswith("s") and not t.endswith(("ss", "us", "is")):
        return t[:-1]
    return t


def _analyse(text: str) -> list[str]:
    toks = [t for t in tokenize(text) if t not in _STOP and len(t) > 1]
    toks = [_stem(t) for t in toks]
    bigrams = [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
    return toks + bigrams


class KnowledgeBase:
    def __init__(self, kb_dir: Path | str | None = None):
        from sklearn.feature_extraction.text import TfidfVectorizer

        kb_dir = Path(kb_dir) if kb_dir else Path(__file__).resolve().parent.parent / "data" / "kb"
        self.docs: list[Doc] = []
        for path in sorted(kb_dir.glob("KB*.json")):
            try:
                d = json.loads(path.read_text(encoding="utf-8"))
                self.docs.append(Doc(
                    id=d["id"], title=d["title"], publisher=d.get("publisher", ""),
                    url=d.get("url", ""), text=d["text"], summary_hi=d.get("summary_hi", ""),
                    summary_hinglish=d.get("summary_hinglish", ""), aliases=d.get("aliases", ""),
                    topics=d.get("topics", []), verified=d.get("verified", True),
                ))
            except (KeyError, json.JSONDecodeError):
                continue
        self._by_id = {d.id: d for d in self.docs}
        self._book_mask = np.array([BOOK_PENALTY if "book" in d.topics else 1.0 for d in self.docs])

        corpus = [
            f"{d.title} {d.title} {d.aliases} {d.aliases} {' '.join(d.topics)} "
            f"{d.text} {d.summary_hinglish} {d.summary_hi}"
            for d in self.docs
        ]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._vec = TfidfVectorizer(analyzer=_analyse, sublinear_tf=True, norm="l2")
            self._matrix = self._vec.fit_transform(corpus) if corpus else None
            # Second, short-field index (title + aliases + topics): a distinctive term such as
            # "ppf" or "liquid fund" should win even if the long text is full of generic words.
            head = [f"{d.title} {d.aliases} {' '.join(d.topics)}" for d in self.docs]
            self._head_vec = TfidfVectorizer(analyzer=_analyse, sublinear_tf=True, norm="l2")
            self._head_matrix = self._head_vec.fit_transform(head) if head else None

    def get(self, doc_id: str) -> Doc | None:
        return self._by_id.get(doc_id)

    def search(self, query: str, k: int = 3) -> list[Hit]:
        if self._matrix is None or not query.strip():
            return []
        expanded = expand_query(query)
        q = self._vec.transform([expanded])
        sims = (self._matrix @ q.T).toarray().ravel()
        qh = self._head_vec.transform([expanded])
        sims = sims + HEAD_WEIGHT * (self._head_matrix @ qh.T).toarray().ravel()
        if not _BOOK_CUES.search(query):
            sims = sims * self._book_mask
        order = np.argsort(-sims)[:k]
        return [Hit(self.docs[i], float(sims[i])) for i in order if sims[i] > 0]

    def best_sentences(self, doc: Doc, query: str, max_chars: int = 650) -> str:
        """First sentence (the definition) + the sentences most similar to the query."""
        protected = _ABBREV.sub(lambda m: m.group(0).replace(".", "․"), doc.text)   # keep "Mr. Market" whole
        sents = [s.strip().replace("․", ".") for s in _SENT_SPLIT.split(protected) if s.strip()]
        if len(sents) <= 2:
            return doc.text
        q = self._vec.transform([expand_query(query)])
        scores = (self._vec.transform(sents) @ q.T).toarray().ravel()
        chosen = {0}
        used = len(sents[0])
        for i in np.argsort(-scores):
            i = int(i)
            if i in chosen:
                continue
            if used + len(sents[i]) > max_chars:
                continue
            chosen.add(i)
            used += len(sents[i])
            if used >= max_chars * 0.85:
                break
        return " ".join(sents[i] for i in sorted(chosen))


@lru_cache(maxsize=1)
def get_kb() -> KnowledgeBase:
    return KnowledgeBase()
