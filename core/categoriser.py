"""Merchant and transaction categoriser.

Uses a dictionary lookup for common Indian merchants (e.g., Swiggy, Zomato, Uber,
Amazon, rent, electricity) with an LLM fallback and cache for unknown merchants.
"""
