"""Generate data/bank_genuine_train.csv — genuine bank SERVICE notices (safe) plus look-alike scams.

Why: a real SBI "your debit card has been delivered, generate Green PIN" message was flagged
suspicious/scam, because the model had seen few genuine bank service notices and many phishing
texts using the same words (activate, PIN, card, verify). This adds:

  safe        calm, informational bank notices: card delivered / PIN generation, new chip card,
              e-statement, mandate / auto-debit, bill reminder, FD maturity, new-device login,
              branch KYC reminder ... NO link, or only the bank's official domain; never asks you to
              share an OTP/PIN/CVV, never threatens.
  scam        HARD NEGATIVES using the same vocabulary: lookalike domains, urgency / blocking threats,
              requests for PIN / OTP / card details.
  suspicious  unknown short link, vague nudge, no explicit threat.

Genuine notices are NOT proof of safety on wording alone (a scammer can copy the text; the link
domain and sender header are what differ) — so the scam rows keep the same words but add the tells.

Hand-written held-out messages (different wording) live in data/bank_genuine_heldout.csv and are
never used for training.

Run: python data/build_bank_genuine.py
"""
import csv
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rng = random.Random(11)

# (display name, official domain, helpline phrase)
BANKS = [
    ("SBI", "sbi.co.in", "the number on the back of your card"),
    ("HDFC Bank", "hdfcbank.com", "the number printed on your card"),
    ("ICICI Bank", "icicibank.com", "the customer care number on your card"),
    ("Axis Bank", "axis.bank.in", "the number on your card"),
    ("Kotak Mahindra Bank", "kotak.bank.in", "the number on your card"),
    ("Canara Bank", "canarabank.com", "the helpline on your card"),
    ("Punjab National Bank", "pnb.bank.in", "the helpline on your passbook"),
    ("Bank of Baroda", "bankofbaroda.in", "the helpline on your card"),
    ("IDFC FIRST Bank", "idfcfirstbank.com", "the number on your card"),
    ("Union Bank of India", "unionbankofindia.co.in", "the helpline on your card"),
]
NAMES = ["Asha", "Rahul", "Priya", "Amit", "Sneha", "Karan", "Neha", "Rohit", "Meera", "Vikram", "Divya", "Nikhil"]
LAST4 = lambda: f"{rng.randint(1000, 9999)}"
XX = lambda: f"XX{rng.randint(10, 99)}"
DAYS = ["12-Dec-2026", "05-Jan-2027", "20-Nov-2026", "28-Feb-2027", "15-Dec-2026", "03-Mar-2027"]
AMT = lambda: rng.choice(["₹1,250", "Rs 3,480", "₹12,000", "Rs 540", "₹7,899", "Rs 2,100", "₹25,000", "Rs 899"])
SHORT = ["bit.ly/3xK9aLp", "tinyurl.com/yk4m2pzs", "cutt.ly/Qa7fRt", "t.co/7sKq2LmP", "goo.su/xT9aL"]
BADTLD = [".xyz", ".top", ".in.net", "-secure.com", "-verify.in", ".co", "-support.in", ".site"]


def bad_domain(bank: str) -> str:
    slug = bank.lower().replace(" bank", "").replace(" mahindra", "").replace(" of ", "").replace(" ", "")
    return rng.choice([f"{slug}-kyc{rng.choice(BADTLD)}", f"{slug}card-activate{rng.choice(BADTLD)}",
                       f"{slug}-update{rng.choice(BADTLD)}", f"secure-{slug}{rng.choice(BADTLD)}"])


def greet(bank: str) -> str:
    return rng.choice([f"Hi {rng.choice(NAMES)},", f"Dear {rng.choice(NAMES)},", "Dear Customer,", f"Hello {rng.choice(NAMES)},", ""])


def safe_msgs() -> list[str]:
    out = []
    for bank, dom, help_ in BANKS:
        g = greet(bank)
        card = XX()
        out += [
            f"{g} Your {bank} Debit card ending with {card} has been delivered. You can generate your Green PIN through our app, ATM or IVR. Card will be enabled for ATM and PoS use after PIN generation.",
            f"{g} Your new {bank} chip-based debit card ending {card} has been dispatched and will reach your registered address in 3-5 working days. Your old card will continue to work until you activate the new one.",
            f"{g} Your {bank} debit card ending {card} was delivered today. Set your PIN at any {bank} ATM or via the official app. Never share your PIN or OTP with anyone, including bank staff.",
            f"{g} Your {bank} account statement for Oct 2026 is ready. Log in to the official app or net banking to view it. We never ask for your password or OTP over SMS or call.",
            f"{g} Your e-statement for account {card} has been sent to your registered email. For help call {help_}.",
            f"{g} Standing instruction of {AMT()} to your SIP has been registered on your {bank} account {card}. First debit on {rng.choice(DAYS)}. If you did not set this up, visit your branch or call {help_}.",
            f"{g} Reminder: EMI of {AMT()} for your {bank} loan will be auto-debited on {rng.choice(DAYS)}. Please keep sufficient balance in account {card}.",
            f"{g} Your {bank} credit card ending {card} statement is generated. Total due {AMT()}, minimum due {AMT()}, due date {rng.choice(DAYS)}. Pay via the official app. Ignore if already paid.",
            f"{g} Your fixed deposit {card} matures on {rng.choice(DAYS)}. Visit your branch or the {bank} app to renew or withdraw. Maturity amount will be credited to your account.",
            f"{g} Interest of {AMT()} has been credited to your {bank} savings account {card}. Thank you for banking with us.",
            f"{g} Your {bank} net banking was accessed from a new device on {rng.choice(DAYS)}. If this was you, no action is needed. If not, call {help_} immediately. Do not share your OTP with anyone.",
            f"{g} Your {bank} UPI PIN was changed successfully. If you did not do this, call {help_} right away.",
            f"{g} As per RBI guidelines, periodic KYC update is due for your account. Please visit your nearest {bank} branch with your ID and address proof. No documents are needed by SMS or call.",
            f"{g} Your cheque no. {rng.randint(100000, 999999)} for {AMT()} has been presented for clearing in account {card}.",
            f"{g} Cheque book request received for account {card}. It will be delivered to your registered address within 7 working days.",
            f"{g} Your {bank} debit card ending {card} international usage has been switched off as requested. You can turn it on anytime from the app.",
            f"{g} Your ATM withdrawal limit has been changed to {AMT()} per day as requested. Not you? Call {help_}.",
            f"{g} Your mobile number has been updated in {bank} records. If you did not request this, please contact your branch.",
            f"{g} Thank you for visiting our branch. Your service request has been completed. For feedback, visit {dom}.",
            f"{g} Your {bank} home loan interest certificate for FY 2025-26 is available in net banking at {dom}. Download it anytime.",
            f"{g} Your account {card} will be debited {AMT()} on {rng.choice(DAYS)} towards insurance premium. This is an auto-pay reminder.",
            f"{g} Your OTP for {bank} net banking login is {rng.randint(100000, 999999)}. Do not share this OTP with anyone. {bank} never calls to ask for it.",
            f"{g} Your Green PIN request has been received. Complete it using the OTP sent to your registered mobile. Do not share the OTP with anyone.",
            f"{g} Your {bank} debit card ending {card} has been blocked as requested. Visit a branch or use the app to apply for a new card.",
        ]
        # a few that reference the official domain only
        out += [
            f"{g} Manage your debit card limits, PIN and online usage at {dom} or in the official {bank} app.",
            f"{g} Your new card is ready. Generate your PIN securely at https://{dom}/green-pin or from any ATM.",
        ]
    # Hinglish
    for bank, dom, help_ in BANKS[:6]:
        out += [
            f"{bank}: Aapka debit card {XX()} deliver ho gaya hai. PIN banane ke liye app ya ATM ka use karein. PIN ya OTP kisi ke saath share na karein.",
            f"{bank}: Aapka e-statement taiyaar hai. Official app me login karke dekhein. Hum kabhi password ya OTP nahi maangte.",
            f"{bank}: Aapke account ka EMI {AMT()} {rng.choice(DAYS)} ko katega. Kripya balance rakhein.",
        ]
    return out


def scam_msgs() -> list[str]:
    out = []
    for bank, dom, help_ in BANKS:
        bd = bad_domain(bank)
        card = XX()
        out += [
            f"{bank}: Your debit card ending {card} will be BLOCKED today. Activate now at http://{bd} and enter your PIN to avoid suspension.",
            f"Dear Customer, your {bank} card has been delivered. Generate Green PIN here http://{bd} and enter card number, CVV and OTP to activate within 1 hour.",
            f"URGENT {bank}: your KYC expired. Update immediately at https://{bd} or your account will be frozen. Share OTP received to complete.",
            f"{bank} ALERT: unusual activity on card {card}. Verify your card details now: http://{bd} . Failing to do so will block your account today.",
            f"Your {bank} reward points worth {AMT()} will expire today. Redeem now http://{bd}/redeem and enter your net banking password.",
            f"{bank} Dear user, your card {card} is deactivated. Call 98{rng.randint(10000000, 99999999)} and share the OTP to reactivate within 30 minutes.",
            f"{bank}: Your new debit card is on hold. Pay a delivery fee of Rs 49 at http://{bd} and enter your card PIN to release it.",
            f"{bank} PAN update required today! Click http://{bd} and enter your PIN and OTP or your account will be suspended.",
        ]
    return out


def suspicious_msgs() -> list[str]:
    out = []
    for bank, dom, help_ in BANKS[:7]:
        out += [
            f"Your {bank} card is ready for activation. Tap to continue: {rng.choice(SHORT)}",
            f"{bank}: complete your account verification here {rng.choice(SHORT)} to keep enjoying benefits.",
            f"Dear customer, update your {bank} details at {rng.choice(SHORT)}",
        ]
    return out


def main() -> int:
    rows = []
    n = 0

    def add(label: str, texts: list[str], notes: str, k: int | None = None):
        nonlocal n
        texts = list(dict.fromkeys(t.replace("  ", " ").strip() for t in texts))
        rng.shuffle(texts)
        for t in (texts[:k] if k else texts):
            n += 1
            lang = "hinglish" if any(w in t for w in ("Aapka", "karein", "katega", "nahi maangte")) else "en"
            rows.append({"id": f"BG{n:04d}", "label": label, "text": t, "language": lang,
                         "hinglish": str(lang == "hinglish").lower(), "split": "train", "notes": notes})

    add("safe", safe_msgs(), "synthetic-genuine-bank")
    add("scam", scam_msgs(), "synthetic-lookalike-scam")
    add("suspicious", suspicious_msgs(), "synthetic-lookalike-suspicious")

    out = ROOT / "data" / "bank_genuine_train.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "label", "text", "language", "hinglish", "split", "notes"])
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    print(f"wrote {out.relative_to(ROOT)}: {len(rows)} rows", dict(Counter(r["label"] for r in rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
