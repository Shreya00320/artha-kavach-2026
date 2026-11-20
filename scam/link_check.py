"""
scam/link_check.py — Offline link safety checker.

Never opens or fetches the link (visiting a phishing page is itself risky);
it only inspects the text of the URL:

  * known official domains of Indian banks, payment apps and government portals
  * lookalike / typosquatted domains (sbi-kyc.in, hdfcbank-secure.com, icicl.com)
  * URL shorteners that hide the real destination
  * raw IP addresses, punycode (xn--), '@' tricks, http without TLS
  * risky top-level domains and direct .apk downloads

Public API:
  extract_urls(text) -> list[str]
  check_url(url) -> LinkReport
  check_text(text) -> list[LinkReport]
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

# Official domains (registrable domain → organisation). Subdomains are accepted.
OFFICIAL_DOMAINS: dict[str, str] = {
    # Banks
    "sbi.co.in": "State Bank of India", "onlinesbi.sbi": "State Bank of India",
    "sbi.bank.in": "State Bank of India", "onlinesbi.com": "State Bank of India",
    "hdfcbank.com": "HDFC Bank", "hdfc.bank.in": "HDFC Bank",
    # HDFC states its SMS links are always under hdfcbk.io (looks like a typo of hdfcbank.com, so it must be allow-listed)
    "hdfcbk.io": "HDFC Bank (SMS link domain)",
    "icicibank.com": "ICICI Bank", "icici.bank.in": "ICICI Bank",
    "axisbank.com": "Axis Bank", "axis.bank.in": "Axis Bank",
    "kotak.com": "Kotak Mahindra Bank", "kotak.bank.in": "Kotak Mahindra Bank",
    "pnbindia.in": "Punjab National Bank", "bankofbaroda.in": "Bank of Baroda",
    "canarabank.com": "Canara Bank", "unionbankofindia.co.in": "Union Bank of India",
    "idfcfirstbank.com": "IDFC FIRST Bank", "yesbank.in": "Yes Bank",
    "indusind.com": "IndusInd Bank", "aubank.in": "AU Small Finance Bank",
    # Payments / fintech
    "npci.org.in": "NPCI", "bhimupi.org.in": "BHIM (NPCI)",
    "paytm.com": "Paytm", "phonepe.com": "PhonePe", "pay.google.com": "Google Pay",
    "amazon.in": "Amazon India", "flipkart.com": "Flipkart", "cred.club": "CRED",
    "zerodha.com": "Zerodha", "groww.in": "Groww",
    # Government / regulators
    "rbi.org.in": "Reserve Bank of India", "incometax.gov.in": "Income Tax Department",
    "uidai.gov.in": "UIDAI (Aadhaar)", "cybercrime.gov.in": "National Cyber Crime Portal",
    "sancharsaathi.gov.in": "Sanchar Saathi (DoT)", "india.gov.in": "Government of India",
    "epfindia.gov.in": "EPFO", "irctc.co.in": "IRCTC", "indiapost.gov.in": "India Post",
    "sebi.gov.in": "SEBI", "gst.gov.in": "GST Portal", "parivahan.gov.in": "Parivahan",
    "digilocker.gov.in": "DigiLocker", "npscra.nsdl.co.in": "NPS (NSDL)",
}

# Free hosting / tunnelling services. Real Indian bank-SMS phishing campaigns (Zscaler, CERT-In, SBI's own
# warning page) are served from these (e.g. sbi-kyc-update-immediately.web.app, x.ngrok.io/sbibank,
# applicationkyc.pages.dev). A bank never hosts customer pages on them.
FREE_HOSTING = (
    "ngrok.io", "ngrok-free.app", "ngrok.app", "trycloudflare.com", "glitch.me", "repl.co",
    "web.app", "firebaseapp.com", "pages.dev", "workers.dev", "herokuapp.com", "netlify.app",
    "vercel.app", "onrender.com", "github.io", "gitlab.io", "blogspot.com", "weebly.com",
    "wixsite.com", "000webhostapp.com",
)
_TUNNELS = ("ngrok", "trycloudflare", "glitch", "repl.co")
_LURE_WORDS = re.compile(r"(?i)(kyc|verify|update|secure|login|reward|refund|claim|bonus|helpdesk|support|card|points|activate|unlock|aadhaar|pan)")

# Brand tokens scammers put into fake domains
BRAND_TOKENS = {
    "sbi": "sbi.co.in", "onlinesbi": "onlinesbi.sbi", "yono": "sbi.co.in",
    "hdfc": "hdfcbank.com", "icici": "icicibank.com", "axis": "axisbank.com",
    "kotak": "kotak.com", "pnb": "pnbindia.in", "paytm": "paytm.com",
    "phonepe": "phonepe.com", "gpay": "pay.google.com", "googlepay": "pay.google.com",
    "npci": "npci.org.in", "bhim": "bhimupi.org.in", "rbi": "rbi.org.in",
    "uidai": "uidai.gov.in", "aadhaar": "uidai.gov.in", "aadhar": "uidai.gov.in",
    "incometax": "incometax.gov.in", "itr": "incometax.gov.in", "epfo": "epfindia.gov.in",
    "irctc": "irctc.co.in", "indiapost": "indiapost.gov.in", "amazon": "amazon.in",
    "flipkart": "flipkart.com", "sebi": "sebi.gov.in", "parivahan": "parivahan.gov.in",
    "echallan": "parivahan.gov.in", "fastag": "npci.org.in",
}

SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "short.gy", "cutt.ly",
    "rb.gy", "ow.ly", "shorturl.at", "tiny.cc", "rebrand.ly", "s.id", "t.ly",
    "v.gd", "bl.ink", "lnkd.in", "wa.me", "shorturl.gg",
}

RISKY_TLDS = {
    "xyz", "top", "click", "site", "online", "live", "icu", "buzz", "tk", "ml", "ga",
    "cf", "gq", "pw", "rest", "cyou", "sbs", "cfd", "lol", "monster", "info", "support",
    "help", "link", "work", "shop", "vip", "app",
}

# Two-label public suffixes common in India
_TWO_LEVEL = {"co.in", "gov.in", "org.in", "net.in", "ac.in", "nic.in", "res.in",
              "edu.in", "bank.in", "firm.in", "gen.in", "ind.in", "co.uk", "com.au"}

_URL_RE = re.compile(
    r"""(?xi)
    \b(
      (?:https?://|www\.)[^\s<>"'`]+                     # with scheme or www
      |
      (?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+       # bare domain …
      (?:com|in|net|org|co|info|xyz|top|click|site|online|live|icu|ly|gl|gd|gy|me|io|app|
         buzz|tk|ml|ga|cf|gq|pw|shop|vip|link|support|help|bank|sbi|cc|at|id|to|us)
      (?:/[^\s<>"'`]*)?                                  # … with optional path
    )""",
)

SEVERITY_ORDER = {"safe": 0, "caution": 1, "danger": 2}


@dataclass
class LinkReport:
    url: str
    host: str
    registrable_domain: str
    verdict: str                      # "safe" | "caution" | "danger"
    official_org: str | None = None
    reasons: list[str] = field(default_factory=list)


def extract_urls(text: str) -> list[str]:
    seen, out = set(), []
    for m in _URL_RE.finditer(text or ""):
        u = m.group(1).rstrip(".,);:!?]'\"")
        # skip e-mail addresses and UPI IDs (handled elsewhere)
        start = m.start(1)
        if start > 0 and text[start - 1] == "@":
            continue
        if u.lower() not in seen:
            seen.add(u.lower())
            out.append(u)
    return out


def registrable_domain(host: str) -> str:
    parts = host.lower().strip(".").split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in _TWO_LEVEL:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host.lower()


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _official_for(host: str) -> str | None:
    h = host.lower()
    for dom, org in OFFICIAL_DOMAINS.items():
        if h == dom or h.endswith("." + dom):
            return org
    # RBI (circular of 22 Apr 2025) told banks to move to the restricted ".bank.in" domain; IDRBT is the
    # only registrar and only licensed banks qualify, so <name>.bank.in is a bank's own site.
    # (host must END with ".bank.in" — "sbi.bank.in.evil.com" and "sbi-bank.in" do not match.)
    if h.endswith(".bank.in") and h.count(".") >= 2:
        return "a licensed bank (.bank.in domain)"
    return None


def check_url(url: str) -> LinkReport:
    raw = url.strip()
    parsed = urlsplit(raw if re.match(r"(?i)^[a-z][a-z0-9+.\-]*://", raw) else "http://" + raw)
    netloc = parsed.netloc
    reasons: list[str] = []
    verdict = "safe"

    def bump(level: str, why: str) -> None:
        nonlocal verdict
        reasons.append(why)
        if SEVERITY_ORDER[level] > SEVERITY_ORDER[verdict]:
            verdict = level

    if "@" in netloc:
        bump("danger", "Contains '@' before the domain — the real site is what comes after the '@'.")
        netloc = netloc.split("@")[-1]
    host = netloc.split(":")[0].lower()
    reg = registrable_domain(host)
    official = _official_for(host)

    if official:
        if re.match(r"(?i)^http://", raw):
            bump("caution", f"Official {official} domain, but the link is not HTTPS.")
        if parsed.path.lower().endswith(".apk"):
            bump("caution", "Direct app download — install banking apps only from the Play Store / App Store.")
        if not reasons:
            reasons.append(f"Official domain of {official}.")
        return LinkReport(raw, host, reg, verdict, official, reasons)

    if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", host):
        bump("danger", "Uses a raw IP address instead of a website name.")
    if "xn--" in host:
        bump("danger", "Punycode domain — can imitate a real name with look-alike characters.")
    if reg in SHORTENERS or host in SHORTENERS:
        bump("danger" if reg != "wa.me" else "caution",
             "Link shortener hides the real destination. Banks and government never send shortened links.")

    free = next((d for d in FREE_HOSTING if host == d or host.endswith("." + d)), None)
    if free:
        ctx = (host + parsed.path).lower()
        risky = (free.startswith(_TUNNELS) or bool(_LURE_WORDS.search(ctx))
                 or any(tok in ctx.replace("-", "") for tok in BRAND_TOKENS if len(tok) >= 3))
        bump("danger" if risky else "caution",
             f"Hosted on a free/temporary web service ({free}). Banks and government never use these for customer pages.")

    labels = re.split(r"[.\-_]", host)
    host_compact = host.replace("-", "").replace(".", "")
    for token, real in BRAND_TOKENS.items():
        if token in labels or (len(token) >= 5 and token in host_compact):
            bump("danger", f"Mentions '{token}' but is not the official domain ({real}). Classic phishing pattern.")
            break
    else:
        # typosquatting: domain name is 1-2 edits away from an official one
        name = reg.split(".")[0]
        for dom, org in OFFICIAL_DOMAINS.items():
            off = dom.split(".")[0]
            if len(off) >= 4 and 0 < _levenshtein(name, off) <= (1 if len(off) < 7 else 2):
                bump("danger", f"Looks like a misspelling of {dom} ({org}).")
                break

    tld = host.rsplit(".", 1)[-1] if "." in host else ""
    if tld in RISKY_TLDS:
        bump("caution", f"'.{tld}' domains are cheap and frequently used in scam campaigns.")
    if parsed.path.lower().endswith(".apk") or ".apk?" in raw.lower():
        bump("danger", "Downloads an Android app (.apk) from outside the Play Store — a common way to steal OTPs.")
    lures = {m.lower() for m in _LURE_WORDS.findall(host)}
    if len(lures) >= 2:
        bump("danger", "Domain stacks words like 'update', 'card', 'kyc' or 'verify' to look official.")
    elif lures:
        bump("caution", "Domain uses words like 'kyc', 'verify', 'reward' or 'refund' to look official.")
    if host.count("-") >= 2 or host.count(".") >= 4:
        bump("caution", "Unusually long or hyphenated domain.")
    if re.match(r"(?i)^http://", raw) and verdict == "safe":
        bump("caution", "Not HTTPS — anything you type can be read in transit.")
    if not reasons:
        reasons.append("No known red flags in the address. That does not prove the site is genuine — "
                       "never enter OTP, PIN or card details on a site you reached from a message.")
    return LinkReport(raw, host, reg, verdict, None, reasons)


def check_text(text: str) -> list[LinkReport]:
    return [check_url(u) for u in extract_urls(text)]
