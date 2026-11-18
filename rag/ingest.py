r"""
rag/ingest.py — Knowledge base ingestion pipeline.

Flow:
  1. Load all JSON documents from data/kb/
  2. Embed each document using the Gemini embedding API (model from EMBEDDING_MODEL env var)
  3. Cache embeddings to disk (.cache/embeddings/) keyed by doc id + content hash
  4. Build a FAISS flat-L2 index over all embeddings
  5. Save FAISS index + document metadata to .cache/faiss/

Public API:
  load_kb_documents(kb_dir) -> list[KBDocument]
  build_index(kb_dir, cache_dir, client) -> FAISSIndex
  load_index(cache_dir) -> FAISSIndex   # load previously built index

Run standalone:
  .venv\Scripts\python.exe rag/ingest.py
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import pickle
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Document model
# ---------------------------------------------------------------------------

@dataclass
class KBDocument:
    """A single knowledge-base document with metadata."""
    id: str
    title: str
    publisher: str
    url: str
    date_accessed: str
    topics: list[str]
    text: str
    # Set after embedding
    embedding: Optional[list[float]] = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# FAISS index wrapper
# ---------------------------------------------------------------------------

@dataclass
class FAISSIndex:
    """Wraps a FAISS flat-L2 index with document metadata."""
    index: object          # faiss.IndexFlatL2
    documents: list[KBDocument]
    embedding_model: str
    dim: int


# ---------------------------------------------------------------------------
# Document loading
# ---------------------------------------------------------------------------

def load_kb_documents(kb_dir: str | Path) -> list[KBDocument]:
    """Load all JSON documents from the knowledge base directory.

    Skips non-JSON files (e.g. .md, .gitkeep).

    Returns:
        List of KBDocument objects sorted by id.
    """
    kb_dir = Path(kb_dir)
    docs = []
    for path in sorted(kb_dir.glob("KB*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            docs.append(KBDocument(
                id=data["id"],
                title=data["title"],
                publisher=data["publisher"],
                url=data["url"],
                date_accessed=data.get("date_accessed", ""),
                topics=data.get("topics", []),
                text=data["text"],
            ))
        except (KeyError, json.JSONDecodeError) as exc:
            logger.warning("Skipping %s: %s", path.name, exc)
    logger.info("Loaded %d KB documents from %s", len(docs), kb_dir)
    return docs


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------

def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _embedding_cache_path(cache_dir: Path, doc_id: str, content_hash: str) -> Path:
    return cache_dir / "embeddings" / f"{doc_id}_{content_hash}.npy"


def _embed_text(client, model: str, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    """Call the Gemini embedding API and return the embedding vector."""
    from google.genai import types
    result = client.models.embed_content(
        model=model,
        contents=text,
        config=types.EmbedContentConfig(task_type=task_type),
    )
    return result.embeddings[0].values


def _load_or_compute_embedding(
    client,
    model: str,
    doc: KBDocument,
    cache_dir: Path,
    sleep_between: float = 0.5,
) -> list[float]:
    """Load embedding from disk cache or compute via API."""
    text_to_embed = f"{doc.title}\n\n{doc.text}"
    h = _content_hash(text_to_embed)
    cache_path = _embedding_cache_path(cache_dir, doc.id, h)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if cache_path.exists():
        logger.debug("Cache hit for %s", doc.id)
        return np.load(str(cache_path)).tolist()

    logger.info("Embedding %s via API...", doc.id)
    embedding = _embed_text(client, model, text_to_embed)
    np.save(str(cache_path), np.array(embedding, dtype=np.float32))
    time.sleep(sleep_between)  # rate-limit courtesy
    return embedding


# ---------------------------------------------------------------------------
# Index build / save / load
# ---------------------------------------------------------------------------

class NumpyFlatL2:
    """Minimal drop-in for faiss.IndexFlatL2 (exact L2 search with numpy).

    Used automatically when FAISS cannot be imported — e.g. Windows machines where
    the FAISS DLL is blocked. With ~20 KB documents exact search is instant.
    """

    def __init__(self, dim: int):
        self.d = dim
        self._xb = np.zeros((0, dim), dtype=np.float32)

    @property
    def ntotal(self) -> int:
        return int(self._xb.shape[0])

    def add(self, x) -> None:
        x = np.asarray(x, dtype=np.float32).reshape(-1, self.d)
        self._xb = np.vstack([self._xb, x])

    def search(self, q, k: int):
        q = np.asarray(q, dtype=np.float32).reshape(-1, self.d)
        n = self.ntotal
        dist = np.full((q.shape[0], k), np.inf, dtype=np.float32)
        idx = np.full((q.shape[0], k), -1, dtype=np.int64)
        if n == 0:
            return dist, idx
        # squared L2, same metric FAISS IndexFlatL2 reports
        d2 = ((q[:, None, :] - self._xb[None, :, :]) ** 2).sum(axis=2)
        kk = min(k, n)
        order = np.argsort(d2, axis=1)[:, :kk]
        idx[:, :kk] = order
        dist[:, :kk] = np.take_along_axis(d2, order, axis=1)
        return dist, idx


def new_flat_index(dim: int):
    """Return a faiss.IndexFlatL2 if FAISS loads, else a NumpyFlatL2."""
    try:
        import faiss
        return faiss.IndexFlatL2(dim)
    except Exception as exc:  # ImportError or blocked DLL (OSError)
        logger.info("FAISS unavailable (%s) — using numpy exact search.", exc)
        return NumpyFlatL2(dim)


def build_index(
    kb_dir: str | Path,
    cache_dir: str | Path,
    client,
    embedding_model: Optional[str] = None,
) -> FAISSIndex:
    """Build (or rebuild) the FAISS index from KB documents.

    Args:
        kb_dir: Path to data/kb/
        cache_dir: Path to .cache/ (embeddings and FAISS index saved here)
        client: google-genai Client instance with EMBEDDING_MODEL configured
        embedding_model: Override model name; if None, reads EMBEDDING_MODEL env var

    Returns:
        FAISSIndex ready for retrieval.
    """
    model = embedding_model or os.environ.get("EMBEDDING_MODEL", "")
    if not model:
        raise ValueError("EMBEDDING_MODEL env var is not set and no model override provided.")

    cache_dir = Path(cache_dir)
    docs = load_kb_documents(kb_dir)
    if not docs:
        raise ValueError(f"No KB documents found in {kb_dir}")

    embeddings = []
    for doc in docs:
        emb = _load_or_compute_embedding(client, model, doc, cache_dir)
        doc.embedding = emb
        embeddings.append(emb)

    matrix = np.array(embeddings, dtype=np.float32)
    dim = matrix.shape[1]

    index = new_flat_index(dim)
    index.add(matrix)
    logger.info("Vector index built (%s): %d vectors, dim=%d", type(index).__name__, index.ntotal, dim)

    # Save
    index_dir = cache_dir / "faiss"
    index_dir.mkdir(parents=True, exist_ok=True)
    if isinstance(index, NumpyFlatL2):
        np.save(index_dir / "kb.npy", matrix)
    else:
        import faiss
        faiss.write_index(index, str(index_dir / "kb.index"))
    with open(index_dir / "metadata.pkl", "wb") as f:
        # Strip embedding arrays from metadata (already on disk per-doc)
        meta_docs = []
        for doc in docs:
            d = KBDocument(
                id=doc.id, title=doc.title, publisher=doc.publisher,
                url=doc.url, date_accessed=doc.date_accessed,
                topics=doc.topics, text=doc.text,
            )
            meta_docs.append(d)
        pickle.dump({"documents": meta_docs, "model": model, "dim": dim}, f)
    logger.info("Index saved to %s", index_dir)

    return FAISSIndex(index=index, documents=docs, embedding_model=model, dim=dim)


def load_index(cache_dir: str | Path) -> FAISSIndex:
    """Load a previously built FAISS index from disk.

    Raises:
        FileNotFoundError if the index has not been built yet.
    """
    cache_dir = Path(cache_dir)
    index_dir = cache_dir / "faiss"
    index_path = index_dir / "kb.index"
    npy_path = index_dir / "kb.npy"
    meta_path = index_dir / "metadata.pkl"

    if not meta_path.exists() or not (index_path.exists() or npy_path.exists()):
        raise FileNotFoundError(
            f"Vector index not found at {index_dir}. Run rag/ingest.py first."
        )

    with open(meta_path, "rb") as f:
        meta = pickle.load(f)

    index = None
    if index_path.exists():
        try:
            import faiss
            index = faiss.read_index(str(index_path))
        except Exception as exc:
            logger.info("Cannot load FAISS index (%s).", exc)
    if index is None:
        if not npy_path.exists():
            # FAISS-built index on a machine without FAISS: rebuild needed
            raise FileNotFoundError(f"{index_path} needs FAISS; no numpy copy at {npy_path}.")
        index = NumpyFlatL2(meta["dim"])
        index.add(np.load(npy_path))

    logger.info("Loaded FAISS index: %d vectors, dim=%d", index.ntotal, meta["dim"])
    return FAISSIndex(
        index=index,
        documents=meta["documents"],
        embedding_model=meta["model"],
        dim=meta["dim"],
    )


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import dotenv
    dotenv.load_dotenv()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    # Import here to avoid circular at module level
    from google import genai

    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        print("ERROR: GOOGLE_API_KEY not set in .env")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    project_root = Path(__file__).parent.parent
    kb_dir = project_root / "data" / "kb"
    cache_dir = project_root / ".cache"

    print(f"Building index from {kb_dir} ...")
    idx = build_index(kb_dir, cache_dir, client)
    print(f"✅ Index built: {idx.index.ntotal} documents, dim={idx.dim}")
    print(f"   Model: {idx.embedding_model}")
    print(f"   Saved to: {cache_dir / 'faiss'}")
