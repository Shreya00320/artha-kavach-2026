"""Pydantic schemas for structured LLM input and output validation.

Defines typed data models for scam verdicts, red flags, claims, parsed SMS entities,
and nudges to ensure type safety and schema compliance across all LLM responses.
"""

from typing import Optional
from pydantic import BaseModel, Field


class SmokeTestResult(BaseModel):
    """Schema for validating smoke test responses from the LLM adapter."""
    status: str = Field(description="Execution status, e.g., 'ok' or 'success'")
    message: str = Field(description="Short human-readable confirmation message")
    timestamp: Optional[str] = Field(default=None, description="ISO timestamp if provided")
