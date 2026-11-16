"""Pydantic schemas for structured LLM input and output validation.

Defines typed data models for scam verdicts, red flags, claims, parsed SMS entities,
and nudges to ensure type safety and schema compliance across all LLM responses.

Phase 1 adds: ParsedTransactionLLM, MerchantCategoryLLM, NudgeListLLM
Phase 3 adds: ScamVerdict, ClaimVerifyResult (stubs here)
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Smoke test (Phase 0)
# ---------------------------------------------------------------------------

class SmokeTestResult(BaseModel):
    """Schema for validating smoke test responses from the LLM adapter."""
    status: str = Field(description="Execution status, e.g., 'ok' or 'success'")
    message: str = Field(description="Short human-readable confirmation message")
    timestamp: Optional[str] = Field(default=None, description="ISO timestamp if provided")


# ---------------------------------------------------------------------------
# Phase 1: Smart Budget schemas
# ---------------------------------------------------------------------------

class ParsedTransactionLLM(BaseModel):
    """LLM output schema for parsing a single bank/UPI SMS message."""
    parseable: bool = Field(description="True if the message is a bank transaction SMS")
    amount: Optional[float] = Field(default=None, description="Transaction amount in INR")
    transaction_type: Optional[Literal["debit", "credit"]] = Field(
        default=None, description="debit = money left account, credit = money received"
    )
    merchant: Optional[str] = Field(default=None, description="Merchant or payee name")
    vpa: Optional[str] = Field(default=None, description="UPI VPA address if present")
    date: Optional[str] = Field(default=None, description="Transaction date YYYY-MM-DD")
    balance: Optional[float] = Field(default=None, description="Available balance after transaction")
    bank: Optional[str] = Field(default=None, description="Bank name, e.g. SBI, HDFC")
    account_last4: Optional[str] = Field(default=None, description="Last 4 digits of account number")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Parser confidence 0-1")


class MerchantCategoryLLM(BaseModel):
    """LLM output schema for categorising a merchant name."""
    category: Literal[
        "Food", "Transport", "Shopping", "Entertainment", "Utilities",
        "Healthcare", "Education", "Rent", "EMI_Loan", "Savings_Investment",
        "Salary", "Transfer", "ATM", "Other"
    ] = Field(description="Spending category")
    confidence: float = Field(ge=0.0, le=1.0, description="Category confidence 0-1")
    reasoning: str = Field(description="One-line explanation of the category assignment")


class NudgeItem(BaseModel):
    """A single financial nudge."""
    text: str = Field(description="The nudge text (< 25 words)")
    category: str = Field(description="Related spending category")
    type: Literal["positive", "suggestion", "warning"] = Field(
        description="Tone of the nudge"
    )


class NudgeListLLM(BaseModel):
    """LLM output schema for a list of financial nudges."""
    nudges: list[NudgeItem] = Field(
        description="2-3 nudges based strictly on engine-computed numbers"
    )


# ---------------------------------------------------------------------------
# Phase 3: Scam Shield schemas (stubs — implemented in Phase 3)
# ---------------------------------------------------------------------------

class RedFlag(BaseModel):
    """A red flag identified in a scam message."""
    flag: str = Field(description="Short name for the red flag type")
    quote_from_message: str = Field(description="Exact quoted text from the message")
    why_it_matters: str = Field(description="Plain-language explanation")


class VerifiableClaim(BaseModel):
    """A claim made by the LLM judge that cites a knowledge-base source."""
    text: str = Field(description="The claim text")
    source_id: str = Field(description="Knowledge base document ID")


class ScamVerdict(BaseModel):
    """Full LLM judge output for scam detection."""
    verdict: Literal["scam", "suspicious", "safe"] = Field(description="Verdict")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence 0-1")
    red_flags: list[RedFlag] = Field(default_factory=list)
    what_to_do: list[str] = Field(default_factory=list)
    claims: list[VerifiableClaim] = Field(default_factory=list)


class ClaimVerifyItem(BaseModel):
    """Verification result for a single claim."""
    claim_text: str
    source_id: str
    verified: bool
    evidence_quote: Optional[str] = None


class ClaimVerifyResult(BaseModel):
    """Full claim verification output."""
    results: list[ClaimVerifyItem] = Field(default_factory=list)
