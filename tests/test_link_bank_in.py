"""Link checker: the RBI-mandated .bank.in domain (circular 22 Apr 2025) and look-alikes."""

import pytest

from scam.link_check import check_url


@pytest.mark.parametrize("url", [
    "https://sbi.bank.in/web/personal-banking/cyber-security",
    "https://pnb.bank.in/SMS-banking.html",
    "https://bankofbaroda.bank.in/",
    "https://idfcfirst.bank.in/finfirst-blogs",
    "https://www.onlinesbi.com",
    "https://www.onlinesbi.sbi/",
])
def test_genuine_bank_domains_are_official(url):
    r = check_url(url)
    assert r.verdict == "safe" and r.official_org, (url, r.reasons)


@pytest.mark.parametrize("url", [
    "http://sbi.bank.in.evil-site.com/login",     # real domain only as a prefix
    "http://sbi-bank.in/kyc",                      # hyphen instead of the dot
    "http://sbi.bank-in.com/activate",
    "https://sbi.co.in.verify-card.xyz/pin",
    "http://bit.ly/3xK9aLp",
])
def test_lookalikes_are_not_official(url):
    r = check_url(url)
    assert not r.official_org and r.verdict in ("caution", "danger"), (url, r.reasons)
