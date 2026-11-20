"""Tests for the embedding-free retriever used by Scam Shield (rag/local_retrieve.py)."""

from rag.local_retrieve import LocalRetriever
from scam.pipeline import analyse


def test_only_scam_advisories_are_indexed():
    r = LocalRetriever()
    ids = {d.id for d in r._index.documents}
    assert r.n_documents == 21
    assert "KB001" in ids and "KB022" not in ids and "KB067" not in ids   # no finance/book docs


def test_retrieves_the_right_advisory():
    r = LocalRetriever()
    cases = {
        "Mumbai Cyber Crime inspector video call, parcel with drugs, digital arrest, transfer to verify funds": "KB018",
        "Congratulations you won a lottery of 25 lakh, pay a processing fee": "KB006",
        "Dear customer your KYC will expire today, click the link to update or account blocked": "KB004",
    }
    for query, expected in cases.items():
        hits = r.retrieve(query, top_k=3)
        assert hits and hits[0].source_id == expected, (query, [h.source_id for h in hits])


def test_result_shape_matches_faiss_retriever():
    r = LocalRetriever()
    hit = r.retrieve("share OTP to get cashback", top_k=2)[0]
    assert hit.rank == 1 and hit.title and hit.snippet and hit.document.text
    ctx = r.retrieve_as_context("share OTP to get cashback", top_k=2)
    assert ctx.startswith("[KB") and "Text:" in ctx


def test_irrelevant_text_returns_nothing_or_few():
    r = LocalRetriever()
    assert r.retrieve("", top_k=3) == []
    assert len(r.retrieve("zzzz qqqq xxxx", top_k=3)) == 0


def test_pipeline_offline_gets_sources_and_receipt_citations():
    out = analyse("Your KYC will expire today. Click http://sbi-kyc-update.xyz or your account is blocked",
                  retriever=LocalRetriever())
    assert out.retriever_used and out.sources
    assert out.trust_receipt.sources            # citations now available without any API key


def test_pipeline_with_mock_llm_runs_claim_verifier():
    from llm.adapter import LLMAdapter
    adapter = LLMAdapter(provider="mock", cache_enabled=False)
    out = analyse("Your KYC will expire today. Click http://sbi-kyc-update.xyz or your account is blocked",
                  adapter=adapter, retriever=LocalRetriever())
    assert out.llm_used and out.retriever_used
