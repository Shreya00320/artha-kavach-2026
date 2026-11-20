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
    "https://hdfcbk.io/HDFCBK/abc123",      # HDFC says its SMS links are always under hdfcbk.io
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
    "http://hdfcbk.co/x",                           # one letter off the genuine hdfcbk.io
    "http://hdfcbk.xyz/x",
    "http://hdfc-bk.io/x",
])
def test_lookalikes_are_not_official(url):
    r = check_url(url)
    assert not r.official_org and r.verdict in ("caution", "danger"), (url, r.reasons)


@pytest.mark.parametrize("url", [
    "https://8ef628b4602c.ngrok.io/sbibank",              # the fake link SBI itself cites on its cyber-security page
    "https://sbi-kyc-update-immediately.web.app/SBI-KYC.apk",   # Zscaler: SBI KYC campaign
    "https://applicationkyc.pages.dev/SBI-KYC.apk",
    "https://calm-garden-42338.herokuapp.com/SBI-KYC.apk",
    "https://sbi-update.netlify.app/login",
    "https://updateyourcard.in/HDFC_Credit_Card.apk",     # Zscaler: HDFC/Axis card-points campaign
    "https://cardupdate.in/",
    "https://my-site.blogspot.com/p/sbi.html",
])
def test_real_campaign_domains_are_danger(url):
    r = check_url(url)
    assert r.verdict == "danger", (url, r.verdict, r.reasons)


def test_plain_free_hosting_is_only_caution():
    assert check_url("https://some-portfolio.github.io/about").verdict == "caution"
