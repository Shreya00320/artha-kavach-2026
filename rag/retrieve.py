"""
rag/retrieve.py — Semantic retrieval from the FAISS knowledge base.

Flow:
  1. Embed the query using the Gemini embedding API (task_type=RETRIEVAL_QUERY)
  2. Search the FAISS index for the top-k nearest neighbours
  3. Return ranked KBDocument objects with citation metadata

Public API:
  Retriever — class that holds a loaded FAISSIndex and answers queries
  Retriever.retrieve(query, top_k) -> list[RetrievalResult]
  build_retriever(cache_dir, client) -> Retriever   # from saved index
  build_retriever_from_index(faiss_index, client) -> Retriever
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import numpy as np

from rag.ingest import FAISSIndex, KBDocument, _embed_text

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

@dataclass
class RetrievalResult:
    """A single retrieval result with document and relevance score."""
    rank: int
    score: float           # L2 distance — lower is more similar
    document: KBDocument

    # Convenience citation fields (for Trust Receipt)
    @property
    def source_id(self) -> str:
        return self.document.id

    @property
    def title(self) -> str:
        return self.document.title

    @property
    def publisher(self) -> str:
        return self.document.publisher

    @property
    def url(self) -> str:
        return self.document.url

    @property
    def snippet(self) -> str:
        """First 300 characters of text as a preview snippet."""
        return self.document.text[:300] + ("..." if len(self.document.text) > 300 else "")


# ---------------------------------------------------------------------------
# Retriever class
# ---------------------------------------------------------------------------

class Retriever:
    """Semantic retriever backed by a FAISS flat-L2 index.

    Usage:
        retriever = Retriever(faiss_index, client)
        results = retriever.retrieve("What is a UPI collect request scam?", top_k=3)
    """

    def __init__(self, faiss_index: FAISSIndex, client, embedding_model: str | None = None):
        """
        Args:
            faiss_index: Loaded FAISSIndex (from ingest.load_index or ingest.build_index)
            client: google-genai Client instance
            embedding_model: Override model name; if None uses faiss_index.embedding_model
        """
        self._index = faiss_index
        self._client = client
        self._model = embedding_model or faiss_index.embedding_model
        if not self._model:
            self._model = os.environ.get("EMBEDDING_MODEL", "")
        if not self._model:
            raise ValueError("EMBEDDING_MODEL not set. Pass embedding_model or set env var.")

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        score_threshold: float | None = None,
    ) -> list[RetrievalResult]:
        """Find the top-k most relevant KB documents for a query.

        Args:
            query: Natural language query string.
            top_k: Number of results to return.
            score_threshold: If set, only return results with L2 score <= this value.
                             Lower L2 = more similar (typical good results < 1.0 for normalised embeddings).

        Returns:
            List of RetrievalResult sorted by relevance (best first).
        """
        # Embed query
        query_vec = _embed_text(self._client, self._model, query, task_type="RETRIEVAL_QUERY")
        query_arr = np.array([query_vec], dtype=np.float32)

        # FAISS search
        actual_k = min(top_k, self._index.index.ntotal)
        if actual_k == 0:
            return []
        distances, indices = self._index.index.search(query_arr, actual_k)

        results = []
        for rank, (dist, idx) in enumerate(zip(distances[0], indices[0]), start=1):
            if idx < 0:  # FAISS returns -1 for padding when fewer results exist
                continue
            if score_threshold is not None and dist > score_threshold:
                continue
            doc = self._index.documents[idx]
            results.append(RetrievalResult(rank=rank, score=float(dist), document=doc))

        logger.debug("Query '%s...' → %d results (top score=%.4f)",
                     query[:50], len(results), results[0].score if results else float("inf"))
        return results

    def retrieve_as_context(self, query: str, top_k: int = 3) -> str:
        """Return retrieved passages as a formatted string for LLM prompt injection.

        Format:
            [KB001] NPCI UPI Safety Guidelines
            URL: https://...
            Text: ...

        Args:
            query: Query string.
            top_k: Number of passages to include.

        Returns:
            Multi-line string ready to inject into a prompt.
        """
        results = self.retrieve(query, top_k=top_k)
        if not results:
            return "(No relevant advisory passages found in the knowledge base.)"

        lines = []
        for r in results:
            lines.append(f"[{r.source_id}] {r.title}")
            lines.append(f"Publisher: {r.publisher}")
            lines.append(f"URL: {r.url}")
            lines.append(f"Text: {r.document.text}")
            lines.append("")
        return "\n".join(lines).strip()

    @property
    def n_documents(self) -> int:
        return self._index.index.ntotal


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------

def build_retriever(
    cache_dir: str,
    client,
    embedding_model: str | None = None,
) -> Retriever:
    """Load a saved FAISS index and return a Retriever.

    Args:
        cache_dir: Path to .cache/ directory.
        client: google-genai Client.
        embedding_model: Optional model name override.

    Raises:
        FileNotFoundError if the index has not been built. Run rag/ingest.py first.
    """
    from rag.ingest import load_index
    index = load_index(cache_dir)
    return Retriever(index, client, embedding_model)


def build_retriever_from_index(faiss_index: FAISSIndex, client) -> Retriever:
    """Create a Retriever directly from a FAISSIndex object."""
    return Retriever(faiss_index, client)
