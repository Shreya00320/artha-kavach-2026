"""Generate extra TRAINING data for the scam classifier: data/scam_train_extra.csv

Why: the original 108 training rows were almost all scam- or bank-style texts, so the model had
no concept of ordinary conversation and flagged "are we still meeting for lunch?" as a scam.
This script composes several hundred varied messages from slot grammars:

  safe        everyday chat (English + a little Hinglish), money between friends, work/study,
              genuine OTP / bank-alert / appointment / delivery / bill messages
  suspicious  pushy marketing, unknown-link offers, vague "verify" nudges
  scam        KYC / lottery / digital-arrest / task-job / loan-fee / refund / SIM-block / remote-app ...

The held-out test sets (data/ordinary_text_eval.csv, data/scam_heldout.csv) are written by hand
with different wording and are NEVER used for training.

Run: python data/build_scam_train.py
"""
import csv
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rng = random.Random(7)

NAMES = ["Rahul", "Priya", "Amit", "Sneha", "Karan", "Neha", "Rohit", "Ananya", "Vikram", "Pooja", "Arjun",
         "Divya", "Sam", "Meera", "Aman", "Isha", "Dev", "Riya", "Nikhil", "Tanvi"]
WHEN = ["tomorrow", "tonight", "this weekend", "on Friday", "next week", "at 6", "after class", "later today",
        "in the evening", "on Sunday", "after work", "at 8 pm", "tomorrow morning"]
EVENTS = ["lunch", "dinner", "the movie", "the match", "coffee", "the study session", "the gym", "the trip",
          "the party", "football", "the group project meeting", "the library", "brunch", "the concert"]
DOCS = ["notes", "assignment", "report", "slides", "project file", "lecture recording", "invoice", "résumé",
        "presentation", "spreadsheet", "draft", "photos from the trip", "syllabus", "lab manual"]
PLACES = ["the canteen", "the station", "your place", "the mall", "campus", "the office", "the cafe", "the airport",
          "the metro", "home", "the library", "the bus stop"]
AMOUNTS = ["₹250", "₹500", "Rs 120", "₹1,200", "Rs 350", "₹80", "₹2,000", "Rs 640", "₹450", "Rs 900"]
FOOD = ["pizza", "biryani", "momos", "chai", "dinner", "the cab", "movie tickets", "groceries", "snacks", "the bill"]
TIMES = ["4 pm", "10:30", "5:45", "noon", "9 am", "7 pm", "3:15", "11 am", "6:30 pm"]
REACT = ["it was insane", "so good", "kinda boring honestly", "you have to watch it", "i cried lol", "what a finish",
         "totally worth it", "not as good as the first one"]
GREET = ["hey", "hi", "hello", "yo", "hey there", "good morning", "heyy", "hii", "bro", "dude", "hey guys"]
END = ["", "", "", " :)", " lol", " 😂", " thanks!", " see you", " 🙂", " haha", " please", "!!"]
FAM = ["Mom", "Dad", "Didi", "Bhaiya", "Nani", "Papa", "Mummy", "Chacha"]
ERR = ["bring milk on your way home", "call me when you reach", "dinner is ready", "don't forget your umbrella",
       "pick up the parcel from the neighbour", "come home early today", "reach home safe", "take your medicine",
       "water the plants please", "your cousin is visiting on Sunday", "eat something, you skipped lunch"]


def safe_chat() -> str:
    k = rng.randrange(14)
    n, w, e = rng.choice(NAMES), rng.choice(WHEN), rng.choice(EVENTS)
    if k == 0:
        s = f"{rng.choice(GREET)} are we still on for {e} {w}?"
    elif k == 1:
        s = f"can you send me the {rng.choice(DOCS)} from {rng.choice(['yesterday', 'last week', 'the lecture', 'the meeting'])}?"
    elif k == 2:
        s = f"the meeting has been moved to {rng.choice(TIMES)}, same room as before"
    elif k == 3:
        s = f"{rng.choice(FAM)}: {rng.choice(ERR)}"
    elif k == 4:
        s = f"happy birthday {n}! hope you have an amazing day, party {w}?"
    elif k == 5:
        s = f"i'm running late, stuck in traffic. will reach {rng.choice(PLACES)} by {rng.choice(TIMES)}"
    elif k == 6:
        s = f"did you watch {rng.choice(['the match', 'the new episode', 'that movie', 'the finale'])} last night? {rng.choice(REACT)}"
    elif k == 7:
        s = f"i'll pay you back for {rng.choice(FOOD)}, it was {rng.choice(AMOUNTS)}, sending it {w}"
    elif k == 8:
        s = f"you owe me {rng.choice(AMOUNTS)} for {rng.choice(FOOD)} 😂 no rush"
    elif k == 9:
        s = f"thanks for helping with the {rng.choice(DOCS)}, really appreciate it {n}"
    elif k == 10:
        s = f"sorry i missed your call, was in a class. can we talk {w}?"
    elif k == 11:
        s = f"submitted the {rng.choice(DOCS)}, please check and let me know if anything is missing"
    elif k == 12:
        s = f"{n} says the exam is on {rng.choice(['Monday', 'Tuesday', 'the 15th', 'Thursday'])}, did you start preparing?"
    else:
        s = f"let's split the cab fare, it came to {rng.choice(AMOUNTS)} so {rng.choice(AMOUNTS)} each"
    if rng.random() < 0.35:
        s = s.capitalize()
    return s + rng.choice(END)


HINGLISH_SAFE = [
    "kal milte hain canteen mein", "bhai kya haal hai, aaj match dekhega?", "mummy ne bola ghar jaldi aana",
    "assignment ka deadline kab hai yaar", "chal dinner pe chalte hain aaj", "kal class hai ya chhutti?",
    "tu aa raha hai na party mein?", "thoda late ho jaunga, traffic bahut hai", "notes bhej dena please",
    "happy birthday yaar! party kab de raha hai?", "paise kal wapas kar dunga, abhi thoda tight hai",
    "aaj ka lecture bahut boring tha", "ghar pahunch gaya, tension mat lo", "kya plan hai weekend ka?",
    "bhaiya, chai pe aa jao", "exam ki taiyari kaisi chal rahi hai", "maine tera order le liya hai, aa ke le ja",
    "thanks bhai, tune bahut help ki", "movie ke tickets book kar diye hain, 7 baje ka show hai",
    "office se nikal gaya hoon, 20 minute mein pahunchta hoon",
]

SERVICE_SAFE = [
    "Your OTP for login is {otp}. Do not share it with anyone.",
    "{otp} is the OTP for your {app} login. It expires in 5 minutes. Do not share it with anyone.",
    "Use OTP {otp} to verify your mobile number on {app}. Never share this OTP with anyone.",
    "OTP for your {bank} net banking login is {otp}. Do not disclose it to anyone, including bank employees.",
    "Dear user, {otp} is your one time password for {app}. Valid for 10 minutes. Please do not share.",
    "Your verification code is {otp}. Don't share this code with anyone. If you didn't request it, ignore this message.",
    "{otp} is your {app} security code. Keep it confidential. Our team will never ask you for it.",
    "Your OTP for card ending {ac} transaction of {amt} at {merchant} is {otp}. Do not share it. -{bank}",
    "Use code {otp} to reset your {app} password. If you did not ask for this, you can safely ignore it.",
    "Do not share your OTP, PIN or password with anyone. {bank} will never call to ask for them.",
    "{otp} is your OTP for logging in to {app}. It is valid for 10 minutes. Do not share it with anyone.",
    "Your OTP for the transaction of {amt} at {merchant} is {otp}. Never share this OTP with anyone, including bank staff. —{bank}",
    "{amt} debited from A/c XX{ac} on {date} at {merchant}. Avl Bal: {bal}. If not done by you, call the number on the back of your card. —{bank}",
    "{amt} credited to your A/c XX{ac} on {date} by NEFT from {name}. Avl Bal: {bal}. —{bank}",
    "Reminder: your appointment with Dr. {name} is on {day} at {time}. Reply C to confirm or call the clinic to reschedule.",
    "Your order from {merchant} has been delivered. We hope you enjoyed it. Rate your experience in the app.",
    "Your {merchant} order is out for delivery and will arrive by {time}. Track it in the app.",
    "Payment of {amt} received for your electricity bill. Thank you. Receipt no. {otp}.",
    "Your train ticket is confirmed. PNR {otp}. Departure {day} {time} from platform 3. Carry a valid ID. —IRCTC",
    "Your cab {name} is arriving in 3 minutes. Vehicle number MH12AB{ac}. Share OTP {otp} with the driver only at pickup.",
    "Your monthly statement for A/c XX{ac} is ready. Log in to the official app to view it. —{bank}",
    "Your mobile recharge of {amt} was successful. Validity 28 days. Thanks for choosing us.",
    "Library notice: the book you reserved is available for pickup until {day}.",
    "Your flight to Delhi is on time. Check-in opens {day} {time}. Have a great trip! —{merchant}",
    "Your package from {merchant} was delivered to the front desk. Thank you for shopping with us.",
]
APPS = ["Swiggy", "Zomato", "PhonePe", "Amazon", "Flipkart", "Uber", "Ola", "BookMyShow", "Paytm", "Myntra"]
BANKS = ["SBI", "HDFC Bank", "ICICI Bank", "Axis Bank", "Kotak Bank", "PNB", "Bank of Baroda", "Canara Bank"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "12 Dec", "3 Jan", "21 Nov"]


def safe_service() -> str:
    t = rng.choice(SERVICE_SAFE)
    return t.format(
        otp=rng.randint(100000, 999999), app=rng.choice(APPS), amt=rng.choice(AMOUNTS), merchant=rng.choice(APPS),
        bank=rng.choice(BANKS), ac=rng.randint(1000, 9999), date=f"{rng.randint(1, 28)}-Nov-26",
        bal=f"Rs {rng.randint(500, 90000):,}.00", name=rng.choice(NAMES), day=rng.choice(DAYS), time=rng.choice(TIMES))


# ---------------------------------------------------------------- suspicious
SUSP = [
    "Flash sale! {pct}% off on everything, today only. Shop now: {url}",
    "You have been selected for a free survey. Complete it and get a ₹500 voucher: {url}",
    "Your parcel could not be delivered. Reschedule here: {url}",
    "Pre-approved offer just for you! Get a personal loan in minutes. Apply: {url}",
    "Hi, I'm {name} from a recruitment agency. We have a work-from-home opportunity, interested? Message me.",
    "Congrats! You qualify for a free gift card. Tap to see if you won: {url}",
    "Unusual activity noticed on your account. Please review here: {url}",
    "Last chance! Your subscription expires today. Renew now at {url}",
    "Earn extra income from home, no experience needed. Details: {url}",
    "Dear user, claim your cashback before it expires: {url}",
    "Your package is waiting. Confirm your address within 24 hours: {url}",
    "Exclusive invite: join our trading community and learn how members earn daily. {url}",
    "Hi {name}, we noticed you haven't logged in for a while. Come back and get ₹200 off: {url}",
    "Get a free demo class today! Limited seats for the coaching batch. Reserve yours: {url}",
    "Your credit limit has been increased. See your new limit: {url}",
    "Hello! I found your profile online. We are hiring part-time assistants, flexible hours. Reply YES for details.",
    "Win a chance to travel to Dubai! Enter the contest now: {url}",
    "Your free trial ends tomorrow. Continue for just ₹1 at {url}",
    "Book your insurance renewal now and save big. Click: {url}",
    "New message from an unknown contact. View it here: {url}",
]
URLS = ["bit.ly/3xKd9", "tinyurl.com/a8Rt2", "rb.gy/p4kz1", "short.link/offer", "goo.su/xT9aL", "cutt.ly/Qw3dE",
        "is.gd/k92Lz", "t.ly/9fGh"]


def suspicious() -> str:
    return rng.choice(SUSP).format(pct=rng.choice([50, 60, 70, 80, 90]), url="http://" + rng.choice(URLS),
                                   name=rng.choice(NAMES))


# --------------------------------------------------------------------- scam
SCAM = [
    "Dear customer, your {bank} account will be blocked today as your KYC has expired. Update immediately: {url}",
    "URGENT: Your {bank} KYC is pending. Share the OTP you receive to avoid account suspension.",
    "Congratulations! You have won ₹{prize} in the {lot} lucky draw. Pay a processing fee of ₹{fee} to claim your prize: {url}",
    "This is {agency}. A parcel in your name contains illegal items. You are under digital arrest. Stay on this video call and do not tell anyone. Transfer ₹{fee} for verification.",
    "Part-time job offer: earn ₹{prize} per day by liking videos. Join our Telegram channel now: {url}",
    "Your electricity connection will be disconnected tonight at 9:30 pm due to unpaid bill. Call {phone} immediately.",
    "Your courier is held at customs. Pay ₹{fee} clearance charges immediately to release the parcel: {url}",
    "Your loan of ₹{prize} is approved! Pay ₹{fee} processing fee first to receive the amount today: {url}",
    "{name} has sent you a collect request of ₹{fee}. Enter your UPI PIN to receive the money.",
    "To complete the refund, install AnyDesk and share the 9-digit code with our executive.",
    "Guaranteed {pct}% returns every month on crypto trading. Invest ₹{fee} today, limited slots: {url}",
    "Income tax refund of ₹{prize} is pending. Verify your bank details here to receive it: {url}",
    "Your SIM will be deactivated in 2 hours. Verify your Aadhaar now: {url}",
    "Your {bank} credit card reward points worth ₹{prize} expire today. Download the app to redeem: {url}.apk",
    "I am from the CBI. Your Aadhaar is linked to a money laundering case. Do not disconnect the call and transfer funds to a safe account.",
    "Your PAN card is blocked. Update it within 24 hours to avoid penalty: {url}",
    "Hi, I accidentally sent ₹{fee} to your account. Please send it back to this number urgently.",
    "Dear {bank} user, your net banking has been locked. Login here to unlock: {url}",
    "You have won a free iPhone! Pay only ₹{fee} shipping to claim: {url}",
    "Your WhatsApp will be banned today. Share the 6-digit code you received to verify your account.",
    "Your {bank} account has been temporarily limited. To restore access, confirm your PAN and net banking password at {url}",
    "Hello, I'm {name} from {company} HR. You are selected for a work-from-home role paying ₹{prize} weekly. To begin, pay a refundable deposit of ₹{fee}.",
    "An FIR has been registered against you. Pay ₹{fee} immediately or you will be arrested within 2 hours.",
    "Earn ₹{prize} every day just by rating products online. No investment needed. WhatsApp {phone} to join.",
    "Our records show you overpaid your {utility} bill. Click {url} to claim a refund of ₹{prize}. Enter your card number and CVV.",
    "Your {bank} debit card has been deactivated. Call {phone} now and give the OTP to our executive to reactivate it.",
    "VIP stock tips group: 300% returns assured in 10 days. Deposit ₹{fee} to join. Telegram: {url}",
    "Your {company} order of ₹{prize} has been placed. If this wasn't you, call {phone} now to cancel it.",
    "This is {company} support. Your device is infected with a virus. Install TeamViewer so we can fix it right away.",
    "Government subsidy: ₹{prize} is waiting in your account. Pay ₹{fee} GST to release it. {url}",
    "Your child has met with an accident. Transfer ₹{fee} to this account immediately for treatment.",
    "Your FASTag is blocked. Recharge now via {url} to avoid a penalty.",
    "Customs has held a gift sent by {name} from abroad. Pay ₹{fee} duty to receive it: {url}",
    "Win ₹{prize} cash daily playing online rummy! Download the app {url}.apk and deposit ₹{fee} to start.",
    "Your insurance policy bonus of ₹{prize} is ready. Share your Aadhaar and OTP to claim it today.",
    "Urgent: your UPI ID will be blocked. Scan this QR code to verify your account and avoid suspension.",
    "Dear customer, your SIM KYC is incomplete. Reply with your Aadhaar number or the SIM will be blocked in 24 hours.",
    "Loan waiver! Your pending EMI of ₹{prize} has been waived. Share the OTP to confirm the waiver.",
    "I am {name}, an army officer being transferred, selling my bike for ₹{prize}. Pay ₹{fee} advance to get it delivered.",
    "Click {url} to track your parcel and pay a ₹{fee} redelivery fee.",
    "Congratulations, you are shortlisted for a ₹{prize}/month job. Pay a ₹{fee} registration fee to confirm your interview.",
    "Your account will be closed in 24 hours for non-compliance. Contact our officer on {phone} and share your card details.",
    "Invest ₹{fee} in our AI trading bot and earn {pct}% daily returns. Withdraw anytime. Join now: {url}",
    "We detected a login to your {bank} account from another city. Share the OTP to block the unauthorised user.",
    "Pay the pending traffic challan of ₹{fee} now at {url} to avoid court proceedings.",
]
AGENCIES = ["the cyber crime branch", "the CBI", "Mumbai Police", "the customs department", "the narcotics bureau", "TRAI"]


def scam() -> str:
    return rng.choice(SCAM).format(
        bank=rng.choice(BANKS), url="http://" + rng.choice(URLS), prize=rng.choice(["25,000", "5,00,000", "50,000", "2,500", "1,00,000"]),
        fee=rng.choice(["500", "1,999", "4,500", "9,800", "250", "15,000"]), lot=rng.choice(["KBC", "Jio", "Amazon", "Flipkart"]),
        agency=rng.choice(AGENCIES), phone="9" + "".join(rng.choice("0123456789") for _ in range(9)),
        name=rng.choice(NAMES), pct=rng.choice([15, 20, 30, 45]),
        company=rng.choice(["Amazon", "Flipkart", "Google", "Microsoft", "Infosys", "Reliance", "Paytm", "Meesho"]),
        utility=rng.choice(["electricity", "gas", "water", "broadband", "mobile"]))


# ------------------------------------------------------------- Hinglish
HG_SCAM = [
    "Aapka {bank} account band ho jayega. KYC abhi update karein: {url}",
    "Aapne ₹{prize} ki lottery jeeti hai! Claim karne ke liye pehle ₹{fee} bhejein.",
    "Aapka bijli connection aaj raat kat jayega. Turant is number par call karein: {phone}",
    "Part time job: ghar baithe ₹{prize} roz kamayein. Telegram join karein: {url}",
    "Aapke parcel mein drugs mile hain. Police case se bachne ke liye ₹{fee} transfer karein.",
    "Apna OTP share karein warna aapka {bank} card block ho jayega.",
    "Loan approve ho gaya hai! Processing fee ₹{fee} pehle bhejein, paisa 10 minute mein aa jayega.",
    "Aapka SIM 2 ghante mein band ho jayega. Aadhaar verify karein: {url}",
    "Sir mujhse galti se ₹{fee} aapke account mein chale gaye, please wapas bhej dijiye jaldi.",
    "Task complete karo aur roz ₹{prize} kamao. Pehle ₹{fee} registration fee jama karein.",
    "Aapka PAN card block ho gaya hai. Abhi update karein warna jurmana lagega: {url}",
    "Income tax refund ₹{prize} ka aaya hai. Card details daal kar claim karein: {url}",
]
HG_SUSP = [
    "Offer! ₹{prize} ka cashback paane ke liye click karein: {url}",
    "Aapka parcel deliver nahi ho paya. Dobara schedule karein: {url}",
    "Aapke liye special loan offer! Turant apply karein: {url}",
    "Ghar baithe paise kamane ka mauka. Details ke liye reply karein.",
]
HG_SERVICE = [
    "Aapke account se {amt} kata. Baaki balance {bal}. —{bank}",
    "Aapke account mein {amt} aaye. Baaki balance {bal}. —{bank}",
    "Reminder: kal aapki EMI {amt} auto-debit hogi. Balance rakhein. —{bank}",
    "Aapka OTP {otp} hai. Ise kisi ke saath share na karein. —{bank}",
    "Aapka {app} order deliver ho gaya hai. Dhanyavaad!",
    "Aapka recharge {amt} ka safal raha. Validity 28 din. Dhanyavaad.",
    "Aapki bijli ka bill {amt} jama ho gaya hai. Dhanyavaad.",
    "Kal subah 10 baje aapka appointment hai. Confirm karne ke liye C bhejein.",
]


def hg_scam() -> str:
    return rng.choice(HG_SCAM).format(
        bank=rng.choice(BANKS), url="http://" + rng.choice(URLS), prize=rng.choice(["25,000", "5,00,000", "50,000", "2,500"]),
        fee=rng.choice(["500", "1,999", "4,500", "9,800", "250"]), phone="9" + "".join(rng.choice("0123456789") for _ in range(9)))


def hg_susp() -> str:
    return rng.choice(HG_SUSP).format(prize=rng.choice(["500", "1,000", "250"]), url="http://" + rng.choice(URLS))


def hg_service() -> str:
    return rng.choice(HG_SERVICE).format(
        amt=rng.choice(AMOUNTS), bal=f"Rs {rng.randint(500, 90000):,}.00", bank=rng.choice(BANKS),
        otp=rng.randint(100000, 999999), app=rng.choice(APPS))


def build(generator, n: int, seen: set) -> list[str]:
    out, tries = [], 0
    while len(out) < n and tries < n * 30:
        tries += 1
        s = generator().strip()
        if s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out


def main() -> None:
    seen: set = set()
    rows = []
    for text in build(safe_chat, 330, seen):
        rows.append(("safe", text, "en", "false", "synthetic-chat"))
    for text in build(safe_service, 260, seen):
        rows.append(("safe", text, "en", "false", "synthetic-service"))
    for text in HINGLISH_SAFE:
        rows.append(("safe", text, "hinglish", "true", "synthetic-chat"))
    for text in build(suspicious, 110, seen):
        rows.append(("suspicious", text, "en", "false", "synthetic"))
    for text in build(scam, 380, seen):
        rows.append(("scam", text, "en", "false", "synthetic"))
    for text in build(hg_scam, 90, seen):
        rows.append(("scam", text, "hinglish", "true", "synthetic"))
    for text in build(hg_susp, 20, seen):
        rows.append(("suspicious", text, "hinglish", "true", "synthetic"))
    for text in build(hg_service, 70, seen):
        rows.append(("safe", text, "hinglish", "true", "synthetic-service"))
    rng.shuffle(rows)
    with open(ROOT / "data" / "scam_train_extra.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "label", "text", "language", "hinglish", "split", "notes"])
        for i, (label, text, lang, hing, note) in enumerate(rows, 1):
            w.writerow([f"TX{i:04d}", label, text, lang, hing, "train", note])
    from collections import Counter
    print(len(rows), "rows", dict(Counter(r[0] for r in rows)))


if __name__ == "__main__":
    main()
