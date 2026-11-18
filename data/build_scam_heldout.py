"""Hand-written HELD-OUT test sets for the scam classifier (never used for training).

  data/ordinary_text_eval.csv   ordinary, non-scam texts (label safe) — incl. tricky look-alikes
  data/scam_heldout.csv         new scam / suspicious messages with wording unlike the training data

Run: python data/build_scam_heldout.py
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ORDINARY = [
    # casual chat
    "Hey, are you free for a quick call this evening?",
    "Can't believe how good that match was last night!",
    "Happy anniversary to the best parents in the world ❤️",
    "I left my charger at your place, can I pick it up tomorrow?",
    "lol that meme is hilarious, sending it to the group",
    "What time does the library close today?",
    "Got the job!!! Will tell you everything when we meet",
    "Mom says come for lunch on Sunday, she's making rajma chawal",
    "Just landed. Will text when I'm at the hotel.",
    "Do you have the chemistry notes from Tuesday's class?",
    "Sorry, my phone died. What did I miss?",
    "Let's catch up soon, it's been ages since we last talked",
    "Can you water my plants while I'm away this weekend?",
    "Traffic is awful, I'll be about twenty minutes late.",
    "good night! sleep well and see you at college tomorrow",
    "Thanks a lot for the birthday wishes, you guys are the best",
    "I think the movie starts at 7:40, not 7. Let's leave a bit early.",
    "Did you finish reading chapter 5? The quiz is on Monday.",
    "Could you please review my pull request when you get a chance?",
    "Team lunch is at 1 pm in the cafeteria, ping me if you're joining.",
    "The professor extended the deadline to Friday, finally some relief",
    "Congratulations on your promotion! Well deserved.",
    "Wanna grab chai after class? My treat today.",
    "Please find the attached minutes of yesterday's meeting. Let me know if I missed anything.",
    "The wifi password at the new cafe is on the board near the counter.",
    "Rain is pouring here, bring an umbrella when you come",
    "I'm at the gate, come down whenever you're ready",
    "Remember to carry your ID card for the exam tomorrow.",
    "Our flight got delayed by an hour, so no need to rush to the airport",
    "Can we reschedule our 3 pm call to 4? Something came up.",
    "My cousin's wedding is next month, you're invited of course!",
    "Booked the tickets for Saturday's concert, check your email for the PDF",
    "Dad's surgery went well, he's resting now. Thanks for all the prayers.",
    "Bro send me the location, I can't find the building",
    "Lecture got cancelled, we're all at the canteen",
    "I'll call you back in ten minutes, in a meeting right now",
    "The plumber is coming at 11 tomorrow, someone needs to be home",
    "Which colour looks better on me, the blue or the green?",
    "Are you coming to the reunion? We're booking a table for twelve.",
    "Just finished my first marathon! 42 km, still can't feel my legs 😅",
    # money between people, benign
    "Can you send me ₹300 for my share of the pizza? I'll forward the bill.",
    "I transferred the rent to the landlord this morning, he confirmed.",
    "Paid the electricity bill online, receipt saved in the shared folder",
    "Dinner was ₹1,800 in total, so ₹450 each. Settle whenever.",
    "Don't forget to pay the hostel fees before the 10th, the office closes at 4.",
    "Salary got credited today, finally! Treat you guys this weekend.",
    "I returned the ₹2,000 I borrowed, check your account",
    "Booking the cab, it shows around ₹380, should I go ahead?",
    # legitimate service / transactional
    "Your OTP for logging in to Zomato is 482910. It is valid for 10 minutes. Do not share it with anyone.",
    "Rs 1,249.00 debited from A/c XX4521 on 14-Nov-26 at AMAZON. Avl Bal: Rs 8,430.55. If not you, call the number on your card. —HDFC Bank",
    "Rs 15,000.00 credited to your account XX7788 by NEFT from ACME PVT LTD (salary). —ICICI Bank",
    "Reminder: you have a dental check-up tomorrow at 10:30 am. Reply YES to confirm.",
    "Your Swiggy order has been delivered. Enjoy your meal!",
    "Your cab is arriving in 4 minutes. Driver: Suresh, KA01AB1234.",
    "Your electricity bill for October is Rs 1,240, due on 25 Nov. Pay via the official app.",
    "Your PNR 4521398765 is confirmed for 21 Nov, departure 6:40 am. Happy journey! —IRCTC",
    "Thank you for shopping with us. Your invoice for order #88213 is attached to the email we sent you.",
    "Your prescription is ready for pickup at the pharmacy counter. Open till 9 pm.",
    "Your Jio recharge of Rs 299 was successful. Validity: 28 days.",
    "Your Uber trip receipt: Rs 214. Thanks for riding with us.",
    "Library: your book is due on 20 Nov. Please renew or return it.",
    "Your package has been delivered and left with the security guard. —Amazon",
    "Your bank statement for October is ready. Log in to the official net banking site to download it.",
    # hinglish ordinary
    "yaar kal ka assignment submit kar diya kya tune?",
    "mummy bol rahi hai aaj sabzi le aana",
    "bhai tu kab aa raha hai, sab log wait kar rahe hain",
    "chalo thik hai, kal subah 9 baje milte hain",
    "aaj ka match kaisa tha? maine to dekha hi nahi",
    "tu paise baad mein de dena, koi jaldi nahi hai",
    "office mein aaj bahut kaam tha, ab ghar ja raha hoon",
    "diwali pe ghar aa raha hai na? sab poochh rahe hain",
    # tricky formal / official-sounding but benign
    "Dear students, the semester results will be published on the university website on 30 November.",
    "Notice: the college will remain closed on 14 November on account of a public holiday.",
    "Your interview is scheduled for Thursday at 11 am. Please carry a copy of your résumé.",
    "Hi, this is Dr. Mehta's clinic confirming your appointment on Friday at 5 pm.",
    "The bank will be closed tomorrow for the second Saturday holiday.",
]

SCAM_HELDOUT = [
    ("scam", "ALERT: Your SBI YONO account has been suspended. Reactivate now by verifying your details at sbi-yono-secure.in/login"),
    ("scam", "Dear Customer, your bank KYC will expire today. Click https://kyc-bank-update.co/verify and enter your debit card PIN to continue."),
    ("scam", "You are the lucky winner of the Jio Anniversary lottery worth Rs 25 lakh! To receive the prize deposit Rs 3,500 as tax at the number below."),
    ("scam", "Officer Rajesh Kumar from Delhi Police: illegal items were found in a courier sent using your Aadhaar. Do not end this video call. You must pay a security deposit to avoid arrest."),
    ("scam", "Hello! We are hiring for a simple online task job. Earn Rs 800-5000 daily. Add us on WhatsApp now, limited seats."),
    ("scam", "Your electricity will be cut off tonight as last month's bill is unpaid. Contact our officer immediately on 98XXXXXX10."),
    ("scam", "Your account shows an unclaimed income tax refund of Rs 18,420. Submit your card details here to receive it: itd-refund.in"),
    ("scam", "Sir I sent money by mistake to your PhonePe, please return Rs 15000 urgently, I have an emergency."),
    ("scam", "Please download the QuickSupport app and tell us the code so that our agent can process your refund."),
    ("scam", "Invest Rs 10,000 in our crypto pool and get Rs 40,000 in 7 days, 100% guaranteed. Join the Telegram group before slots close."),
    ("scam", "Your Aadhaar is linked to illegal SIM cards. Your number will be blocked in 2 hours. Press 1 to talk to the TRAI officer."),
    ("scam", "Dear user your HDFC credit card reward points of Rs 9,800 will expire today. Download the HDFC Rewards app from this link to redeem: hdfc-rewards.apk-download.in"),
    ("scam", "Get an instant loan of Rs 2 lakh without documents! Pay Rs 2,999 insurance fee in advance and the money will be credited in 10 minutes."),
    ("scam", "Congratulations, your number won a Samsung Galaxy in the Flipkart Big Billion lucky draw. Pay the delivery fee of Rs 999 now."),
    ("scam", "I am calling from the cyber crime department. A case has been filed against your mobile number. Transfer your funds to the RBI safe account to clear it."),
    ("scam", "Your Netflix account is on hold. Update your payment info within 12 hours at netflix-billing-update.com to avoid cancellation."),
    ("scam", "Your PAN will be deactivated today. Click here to update your PAN with Aadhaar immediately: pan-link-update.in/verify"),
    ("scam", "Work from home! Rate hotels on Google Maps and earn Rs 100 per rating. Message 'JOIN' on Telegram to start earning today."),
    ("scam", "Dear sir your parcel is stuck at Mumbai customs. Pay Rs 4,200 clearance fee today or the shipment will be destroyed."),
    ("scam", "To receive your money, please accept the collect request and enter your UPI PIN."),
    ("scam", "FINAL WARNING: your electricity meter will be disconnected, pay Rs 10 at the link to update KYC: bses-kyc.in/pay"),
    ("scam", "Hi, I'm from Amazon customer care. You were charged Rs 49,999 by mistake. Install AnyDesk so we can reverse it."),
    ("scam", "Earn 3% daily returns with our AI trading bot. Minimum deposit Rs 5,000. Withdraw anytime. Join today!"),
    ("scam", "Your WhatsApp account is expiring. Forward this message to 10 contacts and share the OTP you get to keep it active."),
    ("scam", "Bank of Baroda: your debit card is blocked. To unblock call 9XXXXXXXXX and share the OTP sent to your phone."),
    ("scam", "Government scheme: get Rs 5,000 monthly under PM Yojana. Register with your Aadhaar and bank PIN here: pm-yojana-apply.in"),
    ("scam", "Your son has been in an accident and is at the hospital. Send Rs 30,000 urgently to this UPI ID for the surgery."),
    ("scam", "Dear customer, your gas connection will be cancelled. Verify KYC immediately by sharing the OTP with our delivery agent."),
    ("scam", "You have an unpaid traffic challan of Rs 2,000. Pay now at echallan-pay.in or face legal action tomorrow."),
    ("scam", "Hello, you've been shortlisted for a Rs 70,000/month job at Amazon. Pay Rs 1,500 registration fee to confirm your interview slot."),
    ("suspicious", "Your parcel couldn't be delivered. Re-schedule delivery at http://bit.ly/ship-update"),
    ("suspicious", "Mega offer! 90% off on branded watches today only. Click to shop: http://tinyurl.com/watch-deal"),
    ("suspicious", "Hey, this is Anita from XYZ Consultants. We have a high-paying WFH opportunity for you. Interested?"),
    ("suspicious", "You are eligible for a pre-approved credit card with zero fee. Apply in 2 minutes: http://short.link/cardnow"),
    ("suspicious", "Participate in our survey and win exciting gifts. Tap here: http://rb.gy/surveyprize"),
    ("suspicious", "Unusual sign-in detected on your account. Review activity: http://is.gd/account-review"),
    ("suspicious", "Last day to claim your cashback! Offer ends at midnight: http://cutt.ly/claimnow"),
    ("suspicious", "Join our trading webinar and learn how others make daily profits from home. Register: http://t.ly/webinar"),
]


def main() -> None:
    with open(ROOT / "data" / "ordinary_text_eval.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "label", "text", "language", "hinglish", "split", "notes"])
        for i, t in enumerate(ORDINARY, 1):
            w.writerow([f"OT{i:03d}", "safe", t, "en", "false", "test", "handwritten-heldout"])
    with open(ROOT / "data" / "scam_heldout.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "label", "text", "language", "hinglish", "split", "notes"])
        for i, (lab, t) in enumerate(SCAM_HELDOUT, 1):
            w.writerow([f"SH{i:03d}", lab, t, "en", "false", "test", "handwritten-heldout"])
    print(len(ORDINARY), "ordinary,", len(SCAM_HELDOUT), "scam/suspicious held-out rows")


if __name__ == "__main__":
    main()
