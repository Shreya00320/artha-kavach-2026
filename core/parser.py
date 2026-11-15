"""Hybrid SMS parser for Indian bank and UPI SMS messages.

Uses regex templates for common Indian bank formats (amount, debit/credit, merchant/VPA,
date, balance) with an LLM fallback for messages that cannot be parsed by regex.
"""
