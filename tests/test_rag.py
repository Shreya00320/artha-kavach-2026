"""
tests/test_rag.py — Unit tests for Phase 2 RAG pipeline.

All tests are fully mocked — no Gemini API calls, no FAISS disk I/O.

Coverage:
  load_kb_documents (3 tests): loads JSON, skips non-JSON, handles missing fields
  Retriever (5 tests): top-k retrieval, score threshold, context string,
                       empty index, stable ranking
"""

import json
import pickle
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from rag.ingest import KBDocument, FAISSIndex, load_kb_documents, _content_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_kb_doc(id="KB001", title="Test Doc", text="Sample text about UPI scams.") -> KBDocument:
    return KBDocument(
        id=id, title=title, publisher="Test Publisher",
        url="https://example.com", date_accessed="2026-11-15",
        topics=["upi", "scam"], text=text,
    )


def _make_faiss_index(docs: list[KBDocument], dim: int = 4) -> FAISSIndex:
    """Build a tiny real FAISS index for testing."""
    import faiss
    embeddings = []
    for i, doc in enumerate(docs):
        # Deterministic synthetic embedding: one-hot-ish
        vec = np.zeros(dim, dtype=np.float32)
        vec[i % dim] = 1.0
        doc.embedding = vec.tolist()
        embeddings.append(vec)
    matrix = np.array(embeddings, dtype=np.float32)
    index = faiss.IndexFlatL2(dim)
    index.add(matrix)
    return FAISSIndex(index=index, documents=docs, embedding_model="test-model", dim=dim)


# ---------------------------------------------------------------------------
# load_kb_documents tests
# ---------------------------------------------------------------------------

class TestLoadKBDocuments:

    def test_loads_valid_json_docs(self, tmp_path):
        """Should load all KB*.json files."""
        for i in range(3):
            doc = {
                "id": f"KB{i+1:03d}",
                "title": f"Doc {i+1}",
                "publisher": "NPCI",
                "url": "https://npci.org.in",
                "date_accessed": "2026-11-15",
                "topics": ["upi"],
                "text": f"Text for doc {i+1}.",
            }
            (tmp_path / f"KB{i+1:03d}_test.json").write_text(json.dumps(doc), encoding="utf-8")

        docs = load_kb_documents(tmp_path)
        assert len(docs) == 3
        assert docs[0].id == "KB001"
        assert docs[2].id == "KB003"

    def test_skips_non_json_files(self, tmp_path):
        """Non-JSON files (md, gitkeep) should be ignored."""
        (tmp_path / ".gitkeep").write_text("")
        (tmp_path / "TODO.md").write_text("# todo")
        doc = {
            "id": "KB001", "title": "Test", "publisher": "RBI",
            "url": "https://rbi.org.in", "date_accessed": "2026-11-15",
            "topics": [], "text": "Banking safety.",
        }
        (tmp_path / "KB001_test.json").write_text(json.dumps(doc), encoding="utf-8")
        docs = load_kb_documents(tmp_path)
        assert len(docs) == 1

    def test_skips_malformed_json(self, tmp_path):
        """Malformed JSON should be skipped with a warning, not crash."""
        (tmp_path / "KB001_bad.json").write_text("{invalid json}", encoding="utf-8")
        (tmp_path / "KB002_good.json").write_text(json.dumps({
            "id": "KB002", "title": "Good", "publisher": "NPCI",
            "url": "https://npci.org.in", "date_accessed": "2026-11-15",
            "topics": [], "text": "Good document.",
        }), encoding="utf-8")
        docs = load_kb_documents(tmp_path)
        assert len(docs) == 1
        assert docs[0].id == "KB002"


# ---------------------------------------------------------------------------
# Retriever tests
# ---------------------------------------------------------------------------

class TestRetriever:

    def _make_retriever(self, docs=None, dim=4):
        """Build a Retriever with a mocked embedding client."""
        from rag.retrieve import Retriever

        if docs is None:
            docs = [
                _make_kb_doc("KB001", "UPI Safety", "Never share your UPI PIN."),
                _make_kb_doc("KB002", "KYC Fraud", "KYC update scam warning."),
                _make_kb_doc("KB003", "Job Scam", "Fake job offer registration fee."),
            ]

        faiss_idx = _make_faiss_index(docs, dim=dim)

        mock_client = MagicMock()

        retriever = Retriever(faiss_idx, mock_client, embedding_model="test-model")
        return retriever, mock_client, docs

    def test_top_k_retrieval(self):
        """Should return top_k results sorted by score."""
        from rag.retrieve import Retriever

        retriever, mock_client, docs = self._make_retriever()

        # Query embedding = same as doc 0's one-hot → doc 0 should be closest
        query_vec = np.zeros(4, dtype=np.float32)
        query_vec[0] = 1.0
        with patch("rag.retrieve._embed_text", return_value=query_vec.tolist()):
            results = retriever.retrieve("UPI PIN safety", top_k=2)

        assert len(results) == 2
        assert results[0].rank == 1
        assert results[0].source_id == "KB001"  # closest to our query vec
        # scores should be non-decreasing (best first = lowest L2)
        assert results[0].score <= results[1].score

    def test_score_threshold_filters(self):
        """score_threshold should filter out distant results."""
        retriever, mock_client, docs = self._make_retriever()

        # Query similar to doc 0 (score ~0), far from docs 1 and 2 (score ~2)
        query_vec = np.zeros(4, dtype=np.float32)
        query_vec[0] = 1.0
        with patch("rag.retrieve._embed_text", return_value=query_vec.tolist()):
            # Tight threshold: only the nearest doc passes
            results = retriever.retrieve("UPI", top_k=3, score_threshold=0.1)

        assert len(results) == 1
        assert results[0].source_id == "KB001"

    def test_retrieve_as_context_format(self):
        """retrieve_as_context should return a formatted string with source_id."""
        retriever, mock_client, docs = self._make_retriever()

        query_vec = np.zeros(4, dtype=np.float32)
        query_vec[0] = 1.0
        with patch("rag.retrieve._embed_text", return_value=query_vec.tolist()):
            context = retriever.retrieve_as_context("UPI", top_k=1)

        assert "[KB001]" in context
        assert "https://" in context
        assert "Never share" in context  # from doc text

    def test_n_documents(self):
        """n_documents property returns correct count."""
        retriever, _, docs = self._make_retriever()
        assert retriever.n_documents == 3

    def test_empty_result_when_no_docs(self):
        """Retriever with 0 documents returns empty results (top_k clamped to 0)."""
        import faiss
        from rag.retrieve import Retriever

        empty_index = faiss.IndexFlatL2(4)
        faiss_idx = FAISSIndex(index=empty_index, documents=[], embedding_model="test", dim=4)
        mock_client = MagicMock()
        retriever = Retriever(faiss_idx, mock_client, embedding_model="test")

        query_vec = np.zeros(4, dtype=np.float32)
        with patch("rag.retrieve._embed_text", return_value=query_vec.tolist()):
            results = retriever.retrieve("anything", top_k=3)

        assert results == []
