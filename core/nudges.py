"""Budget nudge generator with strict numeric hallucination checks.

Prompts the LLM to write kind, actionable financial nudges using only engine-computed
numbers, followed by a post-check rejecting any nudge containing unverified numbers.
"""
