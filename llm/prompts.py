"""Versioned LLM prompts for extraction, classification, and verification.

Rules:
- Prompt constants are versioned (e.g. SCAM_JUDGE_PROMPT_V1).
- Prompts forbid hallucination or inventing figures.
- Explicitly instruct the model to report 'unsure' if evidence is weak.
- Demand strict JSON outputs matching corresponding Pydantic schemas.
"""
