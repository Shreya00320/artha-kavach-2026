"""Pasted message text and merchant names must never become live HTML."""

from app.components import highlight_red_flags_html


def test_markup_in_message_is_escaped():
    out = highlight_red_flags_html('Click <img src=x onerror=alert(1)> now', ["Click"])
    assert "<img" not in out and "&lt;img" in out
    assert out.startswith('<mark class="rf">Click</mark>')


def test_quote_that_looks_like_markup_cannot_corrupt_tags():
    msg = "Verify now or your class will be marked"
    out = highlight_red_flags_html(msg, ["Verify now", "class", "mark", "rf"])
    assert out.count("<mark") == out.count("</mark>")
    assert 'class="rf">class</mark>' in out
    assert "<mark <mark" not in out


def test_quote_with_html_characters_still_highlights():
    out = highlight_red_flags_html("Pay <b>now</b> & win", ["<b>now</b>"])
    assert '<mark class="rf">&lt;b&gt;now&lt;/b&gt;</mark>' in out


def test_overlapping_and_repeated_quotes_are_skipped():
    out = highlight_red_flags_html("send your OTP today", ["your OTP", "OTP today", "your OTP"])
    assert out.count("<mark") == 1


def test_missing_quote_is_ignored():
    assert highlight_red_flags_html("hello", ["not there", ""]) == "hello"
