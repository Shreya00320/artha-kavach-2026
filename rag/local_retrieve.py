"""
rag/local_retrieve.py — a retriever for Scam Shield that needs NO embeddings, key or network.

Same interface as rag.retrieve.Retriever (retrieve, retrieve_as_context, n_documents, and the
`_index.documents` list the claim verifier reads), but it ranks passages with the offline TF-IDF
index in core/knowledge.py instead of Gemini embeddings + FAISS.

It is restricted to the scam / safety advisories (KB001-KB021 by default) so a scam message is
never answered with, say, a book summary. Used when no Gemini key is configured (e.g. LLM_PROVIDER=groq)
or when the embedding index can't be built.

Public API:
  LocalRetriever(max_kb_number=21, min_score=0.15)
"""

from __future__ import annotations

import logging
import re
from types import SimpleNamespace

from core.knowledge import get_kb
from rag.ingest import KBDocument
from rag.retrieve import RetrievalResult

logger = logging.getLogger(__name__)


def _kb_number(doc_id: str) -> int:
    m = re.search(r"(\d+)", doc_id)
    return int(m.group(1)) if m else 10**9


class LocalRetriever:
    """Drop-in replacement for rag.retrieve.Retriever backed by offline TF-IDF."""

    def __init__(self, max_kb_number: int = 21, min_score: float = 0.15):
        self._kb = get_kb()
        self._min_score = min_score
        self._docs: dict[str, KBDocument] = {}
        for d in self._kb.docs:
            if _kb_number(d.id) <= max_kb_number or "genuine-vs-fake" in d.topics:
                self._docs[d.id] = KBDocument(
                    id=d.id, title=d.title, publisher=d.publisher, url=d.url,
                    date_accessed="", topics=list(d.topics), text=d.text,
                )
        # the claim verifier reads retriever._index.documents
        self._index = SimpleNamespace(documents=list(self._docs.values()), ntotal=len(self._docs))

    def retrieve(self, query: str, top_k: int = 3, score_threshold: float | None = None) -> list[RetrievalResult]:
        if not self._docs:
            return []
        # over-fetch, then keep only the advisory docs above the relevance floor
        hits = self._kb.search(query, k=max(top_k * 8, 40))
        out: list[RetrievalResult] = []
        for h in hits:
            if h.doc.id not in self._docs or h.score < self._min_score:
                continue
            out.append(RetrievalResult(rank=len(out) + 1, score=h.score, document=self._docs[h.doc.id]))
            if len(out) >= top_k:
                break
        return out

    def retrieve_as_context(self, query: str, top_k: int = 3) -> str:
        results = self.retrieve(query, top_k=top_k)
        if not results:
            return "(No relevant advisory passages found in the knowledge base.)"
        lines: list[str] = []
        for r in results:
            lines += [f"[{r.source_id}] {r.title}", f"Publisher: {r.publisher}", f"URL: {r.url}",
                      f"Text: {r.document.text}", ""]
        return "\n".join(lines).strip()

    @property
    def n_documents(self) -> int:
        return len(self._docs)
