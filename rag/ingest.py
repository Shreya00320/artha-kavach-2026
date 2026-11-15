"""Knowledge base document ingestion and indexing service.

Loads structured advisories from /data/kb/, generates embeddings via the
configured embedding model, and constructs the local FAISS index.
"""
