r"""
generate_data.py — Synthetic dataset generator for Artha Kavach (Phase 1).

Generates:
  data/scam_eval.csv   — ~155 labelled SMS messages (scam/suspicious/safe)
  data/sample_sms.csv  — ~120 synthetic bank/UPI SMS messages

All data is SYNTHETIC. Marked as such in README.
Run: .venv\Scripts\python.exe data/generate_data.py
"""

import csv
import random
from pathlib import Path

random.seed(42)

DATA_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# 1. scam_eval.csv
# ---------------------------------------------------------------------------

SCAM_MESSAGES = [
    # --- English scam (urgency / OTP / KYC) ---
    ("Your KYC is expiring today. Click http://bit.ly/upd8kyc to avoid account block.", "en", False),
    ("URGENT: Your SBI account will be blocked in 2 hours. Share OTP to verify: 7382.", "en", False),
    ("Congratulations! You won Rs 5,00,000 in NPCI lucky draw. Send Rs 2500 processing fee to claim.", "en", False),
    ("Your UPI collect request of Rs 9999 from FAKE_BANK_REFUND pending. Approve now.", "en", False),
    ("Dear customer, your HDFC account KYC incomplete. Update immediately: http://hdfckyc-update.ml", "en", False),
    ("You have a pending refund of Rs 8,500 from Amazon. Enter PIN at http://amzn-refund.in to receive.", "en", False),
    ("ALERT: 2 failed login attempts on your Paytm. Verify your PIN now: 0000. Reply STOP to cancel.", "en", False),
    ("Job offer: Earn Rs 50,000/month from home! Pay Rs 1,500 registration fee to start today.", "en", False),
    ("Your electricity connection will be cut in 2 hours due to outstanding bill. Pay now: 9876543210", "en", False),
    ("Loan approved Rs 2 lakh! Zero interest. Pay Rs 999 processing fee to disburse. Call 9988776655", "en", False),
    ("Income Tax refund Rs 7,340 approved. Click http://itrefund.in and enter net banking details.", "en", False),
    ("Your Aadhaar linked mobile no. will be deactivated. Call 1800-XXX to verify OTP immediately.", "en", False),
    ("Send Rs 500 on UPI: fraud-collect@fakebank to unlock your frozen account.", "en", False),
    ("Free insurance policy! Just pay Rs 299 stamp duty. Limited offer expires midnight. Click to claim.", "en", False),
    ("Your Google Pay account flagged. Share screen with our agent to verify: Call 8800112233", "en", False),
    ("NPCI lottery: Rs 10 lakh prize. Your UPI ID selected. Send Rs 1000 GST charge to claim prize.", "en", False),
    ("Update PAN card linked to your bank account or face penalty. Visit: http://pancardupdate.xyz", "en", False),
    ("URGENT PM Kisan Yojana bonus Rs 6,000. Enter Aadhaar + OTP at http://pmkisan-gov.in.site to receive.", "en", False),
    ("Your net banking password will expire tonight. Reset via http://sbi-secure.click to avoid lockout.", "en", False),
    ("Fake refund: Rs 1 UPI collect sent to verify account. Accept and your Rs 10,000 refund is processed.", "en", False),
    # --- Hindi scam ---
    ("Aapka KYC khatam ho raha hai. Abhi link par click karein warna account band ho jayega: bit.ly/kyc99", "hi", False),
    ("Badhai ho! Aapne Rs 2,00,000 jeete. Claim karne ke liye Rs 500 registration fee bhejein.", "hi", False),
    ("URGENT: Aapka SBI account block hone wala hai. OTP share karein: 1234 abhi!", "hi", False),
    ("Aapka bijli connection 1 ghante mein katega. Turant bhugtan karein: 9123456789", "hi", False),
    ("Free job offer! Ghar se kaam karein aur Rs 40,000 mahine kamayein. Rs 1000 registration fee.", "hi", False),
    ("Aapka PhonePe account verify karna hai. OTP batayein warna band ho jayega: 7654.", "hi", False),
    ("Income tax refund Rs 4,500 aapke khate mein bheja ja raha hai. Net banking details dijiye.", "hi", False),
    ("PM Awas Yojana ka paise milne wala hai. Aadhaar aur OTP dijiye: http://pmay-gov.xyz", "hi", False),
    ("Lottery jeeti Rs 5 lakh! Processing fee Rs 2000 UPI par bhejein: prize@fakeclaim", "hi", False),
    ("Aapka PhonePe wallet mein Rs 500 cashback pending hai. Sirf OTP dijiye claim karne ke liye.", "hi", False),
    # --- Hinglish scam ---
    ("Yaar tera account block hone wala hai bhai. OTP share kar abhi warna sab kuch close ho jayega!", "hi", True),
    ("Bhai free mein Rs 10,000 mil rahe hain government se. Bas ek baar OTP batao claim ke liye!", "hi", True),
    ("Tera HDFC account mein problem aa gayi hai. Jaldi se is link pe ja: hdfc-fix.ml aur verify kar.", "hi", True),
    ("Paytm se message aaya hai kya? Rs 5000 cashback pending hai. OTP daal de jaldi!", "hi", True),
    ("Yaar lottery jeeta tune! Rs 1 lakh! Bas Rs 500 fee bhej de UPI pe: lotterywinner@collect", "hi", True),
    ("Bhai teri job confirm ho gayi WFH mein. Sirf Rs 999 registration fee pay kar abhi!", "hi", True),
    ("Tera electricity bill overdue hai! 2 ghante mein katega connection. Pay kar: 9988001122", "hi", True),
    ("KYC update karo bhai warna tera Paytm band ho jayega aaj raat ko. Click: paytm-verify.xyz", "hi", True),
    ("Collect request aaya hai Rs 1 ka sirf verify ke liye. Accept kar, uske baad Rs 10,000 milenge.", "hi", True),
    ("Yaar government ka Rs 6000 PM Kisan bonus aa raha hai. Aadhaar + OTP daal de form mein!", "hi", True),
    # --- More English scam (variety) ---
    ("You are selected for SBI special credit card. No documents needed. Pay Rs 750 courier fee.", "en", False),
    ("WhatsApp call recording: someone is monitoring your phone. Install this security app immediately.", "en", False),
    ("Your Jio recharge failed. Account will deactivate in 24 hours. Recharge via our link urgently.", "en", False),
    ("Flipkart Big Billion Day refund Rs 3,200 pending for order cancelled. Enter UPI PIN to receive.", "en", False),
    ("RBI has approved Rs 1.5 lakh loan for you. Paperwork done. Pay stamp duty Rs 1250 to disburse.", "en", False),
    ("Your Netflix subscription cancelled due to payment failure. Update card: netflix-india-pay.com", "en", False),
    ("Cyber Crime Branch: your phone used in fraud. Call officer Sharma 9988XX0011 to avoid arrest.", "en", False),
    ("Aadhaar OTP: 283847. Do NOT share with anyone. — UIDAI [this is a fake forward]", "en", False),
    ("Send money Rs 500 urgently. I am stuck at hospital. This is Rahul. New number 9900112233.", "en", False),
    ("Your EPF withdrawal of Rs 45,000 is on hold. Share KYC on WhatsApp to process within 1 hour.", "en", False),
    ("Mutual fund scheme: 40% guaranteed returns in 6 months. Invest now. Limited slots. Call now!", "en", False),
    ("Free COVID insurance! Register now. Enter Aadhaar and DOB on this form: covidinsure.in", "en", False),
    ("Amazon delivery issue with your package. Verify your address + payment: amzn-verify.in", "en", False),
    ("Tax saving FD: 15% interest! Senior citizen? Extra 2%. Book before 31st. Click: taxfd-special.com", "en", False),
    ("Your car insurance expired. Renew now for Rs 999 (normally Rs 7000). Offer ends tonight!", "en", False),
    ("TRAI: Your mobile number will be suspended in 2 hours for illegal usage. Call 198 to verify.", "en", False),
    ("Online part time job: Rs 500/task, 10 tasks/day. Register Rs 200. 100% trusted. DM for details.", "en", False),
    ("Government crypto scheme: invest Rs 5000, get Rs 50,000 in 7 days. PM endorsed. Limited offer.", "en", False),
    ("Credit card outstanding Rs 23,450 overdue. Pay now to avoid CIBIL score drop: cc-pay-now.in", "en", False),
    ("Your Aadhaar card has been used for a SIM swap. File complaint: Call 9988XXXXXX immediately.", "en", False),
    ("Free upgrade to 5G! Click this link in next 10 minutes or miss your free sim swap offer.", "en", False),
    ("WhatsApp Gold: get extra features! Upgrade now: wa-gold.app. Only for select users like you.", "en", False),
    ("IIT internship offered! Rs 25,000 stipend. Apply fee Rs 500 only. Last date today!", "en", False),
    ("Your Swiggy delivery person needs to collect Rs 50 extra for parking. Pay on UPI: swiggy-extra@upi", "en", False),
    ("RBI monetary policy: extra Rs 10,000 COVID relief to your bank. Share bank details to receive.", "en", False),
    ("Train ticket refund Rs 820 approved. Enter your UPI ID and PIN at irctc-refund.site to receive.", "en", False),
    ("Your health insurance claim Rs 12,000 approved! Pay Rs 299 processing charge to get it credited.", "en", False),
    ("Fake screen-share scam: Our tech team will remote access your phone to fix your UPI problem.", "en", False),
    ("Send a small Rs 1 to UPI: test-collect@icici to verify your account for cashback eligibility.", "en", False),
    ("WhatsApp: your account expires tomorrow unless you share this message to 10 friends.", "en", False),
]

SUSPICIOUS_MESSAGES = [
    ("Urgent: Your account shows unusual activity. Please verify transactions by calling 1800-XXX-1234.", "en", False),
    ("You have been shortlisted for a part-time online job. Reply for more details. No fee mentioned.", "en", False),
    ("Congratulations! You have won a gift voucher from Amazon. Click here to claim.", "en", False),
    ("Your CIBIL score has dropped. Click to view free report: cibil-free.in. No fee required.", "en", False),
    ("Reminder: KYC update pending on your account. Visit your nearest branch or call us.", "en", False),
    ("Aapka account mein kuch problem hai. Please bank branch mein jaiye ya helpline call karein.", "hi", False),
    ("Free credit card offer for salaried individuals. No annual fee. Apply now. Income proof needed.", "en", False),
    ("Online survey: Earn Rs 200 Amazon voucher. 5 mins only. No personal info required.", "en", False),
    ("Your order is on the way. Track here: short-url/track123. Delivery today before 6 PM.", "en", False),
    ("Mutual fund SIP reminder: Rs 2,000 auto-debit scheduled for 5th. Ensure sufficient balance.", "en", False),
    ("Job opening: Data entry. Rs 15,000/month. No experience needed. Email your CV to hr@jobsite.com", "en", False),
    ("Refer a friend to our app and earn Rs 100 cashback for each successful referral. T&C apply.", "en", False),
    ("Your loan EMI of Rs 4,500 is due on 15th. Set reminder or auto-pay to avoid late fee.", "en", False),
    ("New offer on your credit card: 20% cashback at partner restaurants this weekend only.", "en", False),
    ("Update your registered mobile number to continue receiving SMS alerts from your bank.", "en", False),
    ("Re: Your complaint #45678: Our team is investigating. Resolution in 48 hours.", "en", False),
    ("Flipkart Big Sale starts midnight. Add items to cart. Genuine offer from official Flipkart.", "en", False),
    ("Auto insurance renewal reminder. Your policy expires on 20 Nov. Renew via official app.", "en", False),
    ("Claim your reward points before they expire. 5000 points = Rs 50 voucher. Redeem in app.", "en", False),
    ("WhatsApp: Missed call from +91-9900XXXXXX. Number not in contacts. Possibly unknown caller.", "en", False),
    ("Aapka recharge successful hua. 1 GB data mile hain. Balance: Rs 45. — Jio", "hi", False),
    ("Ek nayi banking suvidha launch hui hai. Jankari ke liye bank ki website dekhein ya branch jayein.", "hi", False),
    ("Yaar ek mutual fund scheme hai jo zyada return deta hai apparently. Dekh ek baar details.", "hi", True),
    ("Bhai is link pe click mat kar abhi, pehle verify kar ki genuine hai ya nahi.", "hi", True),
    ("Koi bol raha tha lottery jeeti hai humne, par mujhe nahi pata real hai ya scam.", "hi", True),
    ("Kuch log bol rahe hain ki government Rs 2000 de rahi hai. Confirm karna chahiye pehle.", "hi", True),
    ("Ek app hai jo data entry karwata hai aur paisa deta hai. Genuine lagta hai, par sure nahi.", "hi", True),
    ("Unknown number se message aya hai job ke baare mein. Apply karein ya nahi?", "hi", True),
    ("Is offer mein no catch nahi hai apparently, par 100% sure nahi hoon — official website check karo.", "en", False),
    ("New UPI feature: pay with sound. Download beta app from Play Store link given here.", "en", False),
]

SAFE_MESSAGES = [
    # Real bank SMS formats
    ("Rs 1,250.00 debited from A/c XX4521 on 14-Nov-26 at SWIGGY. Avl Bal: Rs 12,340.50 —SBI", "en", False),
    ("Rs 2,000 credited to your A/c XX8810 on 13-Nov-26. UPI Ref: 423891234567. —HDFC Bank", "en", False),
    ("Your ICICI Bank A/c XX2341 is debited Rs 450.00 on 14-Nov-26. Info: UBER. Avl Bal: Rs 5,672.00", "en", False),
    ("Sent Rs 500.00 to rahul.kumar@oksbi via UPI on 13-Nov-26. UPI Ref: 123456789012. —PhonePe", "en", False),
    ("Received Rs 15,000.00 from SALARY CORP via UPI on 01-Nov-26. UPI Ref: 234567890123. —GPay", "en", False),
    ("Rs 8,500.00 debited from A/c XX9910 on 10-Nov-26 at AMAZON IN. Avl Bal: Rs 23,100.00 —Axis", "en", False),
    ("Your A/c XX6712 is debited Rs 12,000.00 on 05-Nov-26 for EMI-HDFC LOAN. Avl Bal: Rs 4,320.00 —HDFC", "en", False),
    ("ATM WDL Rs 2,000.00 from A/c XX1122 on 12-Nov-26 at SBI ATM DELHI. Avl Bal: Rs 7,890.00 —SBI", "en", False),
    ("Rs 3,200.00 debited from A/c XX3344 on 11-Nov-26 at ZOMATO. Avl Bal: Rs 15,600.00 —Kotak", "en", False),
    ("Rs 5,000.00 transferred to A/c XX5566 (ICICI) on 09-Nov-26 via NEFT. Ref: ICIC0000012. —SBI", "en", False),
    ("Received Rs 2,500.00 from friends.name@paytm via UPI. Available Bal: Rs 9,870.00 —Paytm", "en", False),
    ("Rs 999.00 debited from A/c XX7788 on 08-Nov-26 at NETFLIX. Avl Bal: Rs 6,120.00 —HDFC", "en", False),
    ("Rs 300.00 credited to your A/c XX9900 on 07-Nov-26 (CASHBACK-HDFC-CC). Avl Bal: Rs 4,350.00", "en", False),
    ("Your SIP of Rs 2,000.00 has been placed for AXIS BLUECHIP FUND on 05-Nov-26. —Groww", "en", False),
    ("Rs 1,800.00 debited from A/c XX1234 on 06-Nov-26 at MakeMyTrip. Avl Bal: Rs 11,200.00 —SBI", "en", False),
    ("Sent Rs 150.00 to autorickshaw@ybl via UPI on 13-Nov-26. Balance: Rs 2,800.00 —PhonePe", "en", False),
    ("Rs 350.00 debited from A/c XX5678 on 04-Nov-26 at BLINKIT. Avl Bal: Rs 8,900.00 —ICICI", "en", False),
    ("Rs 7,500.00 debited from A/c XX2222 on 02-Nov-26 at RENT-LANDLORD. Avl Bal: Rs 3,250.00 —Axis", "en", False),
    ("Your HDFC credit card bill of Rs 14,350.00 is due on 20-Nov. Pay to avoid late charges.", "en", False),
    ("Rs 60.00 debited from A/c XX3456 on 14-Nov-26 at IRCTC. Avl Bal: Rs 5,480.00 —SBI", "en", False),
    ("Rs 2,500.00 debited from A/c XX4567 on 03-Nov-26 at LIC PREMIUM. Avl Bal: Rs 9,000.00 —Kotak", "en", False),
    ("Sent Rs 800.00 to plumber.helper@paytm via UPI on 12-Nov-26. Bal: Rs 1,900.00 —Paytm", "en", False),
    ("Rs 400.00 debited from A/c XX5679 on 11-Nov-26 at BOOKMYSHOW. Avl Bal: Rs 7,600.00 —HDFC", "en", False),
    ("Rs 1,100.00 debited from A/c XX6789 on 10-Nov-26 at D-MART. Avl Bal: Rs 4,200.00 —SBI", "en", False),
    ("Rs 200.00 credited to A/c XX7890 on 09-Nov-26 (UPI REFUND-ZOMATO). Avl Bal: Rs 6,350.00", "en", False),
    ("Your Jio prepaid recharge of Rs 239.00 is successful. Validity 28 days. —Jio", "en", False),
    ("Reminder: Your auto-pay of Rs 3,500 for HDFC home loan EMI is scheduled for 05-Dec.", "en", False),
    ("Rs 580.00 debited from A/c XX8901 on 08-Nov-26 at MYNTRA. Avl Bal: Rs 12,780.00 —ICICI", "en", False),
    ("Rs 1,250.00 debited from A/c XX9012 on 07-Nov-26 at DECATHLON. Avl Bal: Rs 5,100.00 —Axis", "en", False),
    ("Rs 450.00 debited from A/c XX0123 on 06-Nov-26 at CROSSWORD. Avl Bal: Rs 3,650.00 —SBI", "en", False),
    # Hindi safe
    ("Aapke khate se Rs 500 kat gaye hain SWIGGY ke liye. Baaki bakiya: Rs 3,200. —SBI", "hi", False),
    ("Aapke khate mein Rs 15,000 salary credit hui hai. —HDFC Bank", "hi", False),
    ("Aapka UPI payment Rs 300 Rahul ko bheja gaya. Reference: 1234567890. —PhonePe", "hi", False),
    ("Aapke account se Rs 1,500 EMI kata. Baaki bakiya: Rs 4,500. —Kotak Bank", "hi", False),
    ("Rs 2,000 ATM se nikale. Baaki bakiya: Rs 8,000. —SBI ATM Jaipur", "hi", False),
    # Hinglish safe
    ("Bhai payment ho gayi Rs 500 Zomato pe. Balance abhi 2800 hai account mein.", "hi", True),
    ("Yaar salary aa gayi account mein Rs 25,000. NEFT se aaya hai company se.", "hi", True),
    ("Aaj UPI se Rs 1,000 mama ko bhej diya. PhonePe se gaya, ref no. 9988XX", "hi", True),
    ("Teri Netflix payment cut gayi Rs 649. HDFC account mein balance check kar.", "hi", True),
    ("Dekh tera rent auto-debit hua Rs 7,500. Landlord account mein chala gaya.", "hi", True),
    # Tricky legitimate alerts (should NOT trigger as scam)
    ("HDFC Bank: OTP for your net banking login is 783921. Valid 10 minutes. Do not share with anyone.", "en", False),
    ("Your OTP for UPI PIN setup on PhonePe is 456123. Never share this with anyone. —NPCI", "en", False),
    ("Rs 1 debited from A/c XX1234 as UPI verification charge. It will be refunded in 2 days. —SBI", "en", False),
    ("Transaction alert: A debit of Rs 9,999 at APPLE STORE was made. If not done by you, call 1800XX.", "en", False),
    ("Your account XX5678 is linked to Aadhaar. This is an automated confirmation. —SBI", "en", False),
    ("Low balance alert: Avl Bal in A/c XX9900 is Rs 234.50. Consider topping up. —HDFC", "en", False),
    ("Reminder: File your ITR before 31 July to avoid penalty. Visit incometax.gov.in for details.", "en", False),
    ("Your EPF passbook updated. Total balance Rs 1,23,456. View at epfindia.gov.in. —EPFO", "en", False),
    ("KYC completed successfully for A/c XX3344. No further action needed. —Axis Bank", "en", False),
    ("Your nominee has been updated for your SBI account. If not done by you, contact branch. —SBI", "en", False),
    ("Passbook: 10 transactions this month. Net debit: Rs 14,500. Net credit: Rs 25,000. —HDFC", "en", False),
    ("Your standing instruction of Rs 5,000 for PPF has been executed. Ref: 2345678. —SBI", "en", False),
    ("Credit card payment of Rs 8,000 received. Outstanding: Rs 2,350. Due date: 20-Nov. —HDFC", "en", False),
    ("Your cheque No. 002345 for Rs 3,000 has been cleared. Avl Bal: Rs 7,890. —Kotak", "en", False),
    ("IMPS transfer of Rs 500 from XX1234 to XX5678 successful. Ref: IMPS20241114. —SBI", "en", False),
]

# Assign labels
all_messages = []
for text, lang, hinglish in SCAM_MESSAGES:
    all_messages.append(("scam", text, lang, hinglish))
for text, lang, hinglish in SUSPICIOUS_MESSAGES:
    all_messages.append(("suspicious", text, lang, hinglish))
for text, lang, hinglish in SAFE_MESSAGES:
    all_messages.append(("safe", text, lang, hinglish))

# Shuffle with seed
random.shuffle(all_messages)

# 70/30 train/test split stratified by label
from collections import defaultdict
by_label = defaultdict(list)
for row in all_messages:
    by_label[row[0]].append(row)

rows_with_split = []
for label, rows in by_label.items():
    n_train = int(len(rows) * 0.7)
    for i, row in enumerate(rows):
        split = "train" if i < n_train else "test"
        rows_with_split.append(row + (split,))

random.shuffle(rows_with_split)

scam_csv = DATA_DIR / "scam_eval.csv"
with open(scam_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["id", "label", "text", "language", "hinglish", "split", "notes"])
    for i, (label, text, lang, hinglish, split) in enumerate(rows_with_split, 1):
        writer.writerow([
            f"SE{i:04d}", label, text, lang, str(hinglish).lower(), split, "synthetic"
        ])

print(f"✅ scam_eval.csv written: {len(rows_with_split)} rows")

# Count stats
from collections import Counter
label_counts = Counter(r[0] for r in rows_with_split)
hinglish_count = sum(1 for r in rows_with_split if r[3])
print(f"   Labels: {dict(label_counts)}")
print(f"   Hinglish: {hinglish_count}")


# ---------------------------------------------------------------------------
# 2. sample_sms.csv
# ---------------------------------------------------------------------------

SAMPLE_SMS = [
    # SBI debit format
    ("Rs 1,250.00 debited from A/c XX4521 on 01-Nov-26 at SWIGGY. Avl Bal: Rs 12,340.50 —SBI", 1250.00, "debit", "Swiggy", "SBI", True),
    ("Rs 500.00 debited from A/c XX4521 on 02-Nov-26 at UBER. Avl Bal: Rs 11,840.50 —SBI", 500.00, "debit", "Uber", "SBI", True),
    ("Rs 8,500.00 debited from A/c XX4521 on 03-Nov-26 at AMAZON IN. Avl Bal: Rs 3,340.50 —SBI", 8500.00, "debit", "Amazon", "SBI", True),
    ("Rs 7,500.00 debited from A/c XX4521 on 05-Nov-26 at RENT-LANDLORD. Avl Bal: Rs 15,840.50 —SBI", 7500.00, "debit", "Rent", "SBI", True),
    ("Rs 1,800.00 debited from A/c XX4521 on 06-Nov-26 at MAKEMYTRIP. Avl Bal: Rs 14,040.50 —SBI", 1800.00, "debit", "MakeMyTrip", "SBI", True),
    ("Rs 60.00 debited from A/c XX4521 on 07-Nov-26 at IRCTC. Avl Bal: Rs 13,980.50 —SBI", 60.00, "debit", "IRCTC", "SBI", True),
    ("Rs 2,000.00 debited from A/c XX4521 on 08-Nov-26 at D-MART. Avl Bal: Rs 11,980.50 —SBI", 2000.00, "debit", "D-Mart", "SBI", True),
    ("ATM WDL Rs 2,000.00 from A/c XX4521 on 09-Nov-26 at SBI ATM DELHI. Avl Bal: Rs 9,980.50 —SBI", 2000.00, "debit", "ATM", "SBI", True),
    ("Rs 25,000.00 credited to A/c XX4521 on 01-Nov-26 (SALARY CORP NEFT). Avl Bal: Rs 34,980.50 —SBI", 25000.00, "credit", "Salary", "SBI", True),
    ("Rs 300.00 credited to A/c XX4521 on 10-Nov-26 (CASHBACK-AMAZON). Avl Bal: Rs 10,280.50 —SBI", 300.00, "credit", "Amazon", "SBI", True),
    # HDFC debit format
    ("Your HDFC Bank A/c XX8810 is debited Rs 450.00 on 02-Nov-26. Info: UBER EATS. Avl Bal Rs 22,550.00", 450.00, "debit", "Uber Eats", "HDFC", True),
    ("Your HDFC Bank A/c XX8810 is debited Rs 999.00 on 03-Nov-26. Info: NETFLIX. Avl Bal Rs 21,551.00", 999.00, "debit", "Netflix", "HDFC", True),
    ("Your HDFC Bank A/c XX8810 is debited Rs 12,000.00 on 05-Nov-26 for EMI-HDFC LOAN. Avl Bal Rs 9,551.00", 12000.00, "debit", "EMI", "HDFC", True),
    ("Your HDFC Bank A/c XX8810 is debited Rs 580.00 on 06-Nov-26. Info: MYNTRA. Avl Bal Rs 8,971.00", 580.00, "debit", "Myntra", "HDFC", True),
    ("Your HDFC Bank A/c XX8810 is debited Rs 400.00 on 07-Nov-26. Info: BOOKMYSHOW. Avl Bal Rs 8,571.00", 400.00, "debit", "BookMyShow", "HDFC", True),
    ("Rs 30,000.00 credited to your A/c XX8810 on 01-Nov-26. NEFT from ACME PVTLTD. —HDFC Bank", 30000.00, "credit", "Salary", "HDFC", True),
    ("Your HDFC Bank A/c XX8810 is debited Rs 2,500.00 on 08-Nov-26. Info: LIC PREMIUM. Avl Bal Rs 6,071.00", 2500.00, "debit", "LIC", "HDFC", True),
    ("Your credit card payment of Rs 14,350.00 received on 10-Nov-26. Due: Rs 0. —HDFC", 14350.00, "credit", "CC Payment", "HDFC", True),
    # ICICI format
    ("Your ICICI Bank A/c XX2341 is debited Rs 3,200.00 on 03-Nov-26. Info: ZOMATO. Avl Bal: Rs 7,800.00", 3200.00, "debit", "Zomato", "ICICI", True),
    ("Your ICICI Bank A/c XX2341 is debited Rs 1,250.00 on 04-Nov-26. Info: DECATHLON. Avl Bal: Rs 6,550.00", 1250.00, "debit", "Decathlon", "ICICI", True),
    ("Rs 2,000.00 credited to your ICICI Bank A/c XX2341 on 02-Nov-26. UPI Ref: 56789012. —ICICI", 2000.00, "credit", "UPI", "ICICI", True),
    ("Your ICICI Bank A/c XX2341 is debited Rs 450.00 on 05-Nov-26. Info: CROSSWORD. Avl Bal: Rs 6,100.00", 450.00, "debit", "Crossword", "ICICI", True),
    # Axis format
    ("Rs 7,500.00 debited from A/c XX9910 on 02-Nov-26 at RENT-LANDLORD. Avl Bal: Rs 23,100.00 —Axis", 7500.00, "debit", "Rent", "Axis", True),
    ("Rs 1,100.00 debited from A/c XX9910 on 04-Nov-26 at D-MART. Avl Bal: Rs 22,000.00 —Axis", 1100.00, "debit", "D-Mart", "Axis", True),
    # Kotak format
    ("Rs 3,200.00 debited from your Kotak A/c XX3344 on 05-Nov-26 for ZOMATO. Bal: Rs 15,600.00", 3200.00, "debit", "Zomato", "Kotak", True),
    ("Rs 2,500.00 debited from your Kotak A/c XX3344 on 06-Nov-26 for LIC PREMIUM. Bal: Rs 13,100.00", 2500.00, "debit", "LIC", "Kotak", True),
    # UPI formats (PhonePe / GPay style)
    ("Sent Rs 500.00 to rahul.kumar@oksbi via UPI on 02-Nov-26. UPI Ref: 123456789012. —PhonePe", 500.00, "debit", "Transfer", "PhonePe", True),
    ("Received Rs 1,000.00 from anita.sharma@paytm via UPI on 03-Nov-26. UPI Ref: 234567890123. —PhonePe", 1000.00, "credit", "Transfer", "PhonePe", True),
    ("Sent Rs 150.00 to autorickshaw@ybl via UPI on 06-Nov-26. Balance: Rs 2,800.00 —PhonePe", 150.00, "debit", "Transport", "PhonePe", True),
    ("Received Rs 15,000.00 from SALARY CORP via UPI on 01-Nov-26. UPI Ref: 345678901234. —GPay", 15000.00, "credit", "Salary", "GPay", True),
    ("Sent Rs 800.00 to plumber@paytm via UPI on 05-Nov-26. Balance: Rs 1,900.00 —Paytm", 800.00, "debit", "Services", "Paytm", True),
    ("Sent Rs 2,000.00 to mama@upi via UPI on 07-Nov-26. Ref: 456789012345. —GPay", 2000.00, "debit", "Transfer", "GPay", True),
    # Mixed/unusual merchants (LLM fallback candidates)
    ("Rs 350.00 debited from A/c XX4521 on 10-Nov-26 at BLINKIT. Avl Bal: Rs 8,900.00 —SBI", 350.00, "debit", "Blinkit", "SBI", True),
    ("Rs 299.00 debited from A/c XX8810 on 11-Nov-26. Info: JIO RECHARGE. Avl Bal: Rs 5,100.00 —HDFC", 299.00, "debit", "Jio", "HDFC", True),
    ("Rs 1,999.00 debited from A/c XX2341 on 11-Nov-26. Info: SPOTIFY PREMIUM. Avl Bal: Rs 4,101.00 —ICICI", 1999.00, "debit", "Spotify", "ICICI", True),
    ("Rs 180.00 debited from A/c XX9910 on 09-Nov-26 at RAPIDO. Avl Bal: Rs 21,000.00 —Axis", 180.00, "debit", "Rapido", "Axis", True),
    ("Rs 1,500.00 debited from A/c XX4521 on 12-Nov-26 at NYKAA. Avl Bal: Rs 7,250.00 —SBI", 1500.00, "debit", "Nykaa", "SBI", True),
    ("Rs 750.00 debited from A/c XX8810 on 12-Nov-26. Info: CULT.FIT. Avl Bal Rs 4,350.00 —HDFC", 750.00, "debit", "Cult.fit", "HDFC", True),
    ("Rs 1,200.00 debited from A/c XX2341 on 13-Nov-26. Info: MEESHO. Avl Bal: Rs 2,901.00 —ICICI", 1200.00, "debit", "Meesho", "ICICI", True),
    ("Rs 500.00 debited from A/c XX9910 on 10-Nov-26 at LENSKART. Avl Bal: Rs 20,500.00 —Axis", 500.00, "debit", "Lenskart", "Axis", True),
    ("Rs 2,100.00 debited from A/c XX4521 on 13-Nov-26 at CROMA. Avl Bal: Rs 5,150.00 —SBI", 2100.00, "debit", "Croma", "SBI", True),
    ("Rs 890.00 debited from A/c XX8810 on 13-Nov-26. Info: TATA CLIQ. Avl Bal Rs 3,460.00 —HDFC", 890.00, "debit", "Tata Cliq", "HDFC", True),
    # Salary credits
    ("Rs 45,000.00 credited to A/c XX5566 on 01-Nov-26. NEFT SALARY-INFOSYS. Avl Bal: Rs 50,000.00 —SBI", 45000.00, "credit", "Salary", "SBI", True),
    ("Rs 28,000.00 credited to A/c XX4521 on 01-Nov-26 (SALARY). Avl Bal: Rs 32,000.00 —HDFC", 28000.00, "credit", "Salary", "HDFC", True),
    # EMI / loan
    ("Rs 5,500.00 debited from A/c XX4521 on 05-Nov-26 at EMI-BAJAJ FINANCE. Avl Bal: Rs 26,500.00 —SBI", 5500.00, "debit", "EMI", "SBI", True),
    ("Your A/c XX8810 is debited Rs 3,200.00 on 05-Nov-26 for EMI-HDFC PERSONAL LOAN. Avl Bal Rs 15,000.00", 3200.00, "debit", "EMI", "HDFC", True),
    # Utilities
    ("Rs 1,450.00 debited from A/c XX4521 on 03-Nov-26 at ELECTRICITY BOARD. Avl Bal: Rs 11,050.00 —SBI", 1450.00, "debit", "Electricity", "SBI", True),
    ("Rs 850.00 debited from A/c XX8810 on 04-Nov-26. Info: PIPED GAS. Avl Bal Rs 10,200.00 —HDFC", 850.00, "debit", "Gas", "HDFC", True),
    ("Rs 500.00 debited from A/c XX9910 on 02-Nov-26 at INTERNET BILL. Avl Bal: Rs 19,500.00 —Axis", 500.00, "debit", "Internet", "Axis", True),
    # Healthcare
    ("Rs 1,200.00 debited from A/c XX4521 on 08-Nov-26 at APOLLO PHARMACY. Avl Bal: Rs 9,850.00 —SBI", 1200.00, "debit", "Healthcare", "SBI", True),
    ("Rs 800.00 debited from A/c XX8810 on 09-Nov-26. Info: DR CONSULT FEE. Avl Bal Rs 8,160.00 —HDFC", 800.00, "debit", "Healthcare", "HDFC", True),
    # Education
    ("Rs 2,500.00 debited from A/c XX9910 on 07-Nov-26 at UDEMY COURSE. Avl Bal: Rs 18,500.00 —Axis", 2500.00, "debit", "Education", "Axis", True),
    ("Rs 1,800.00 debited from A/c XX4521 on 11-Nov-26 at COURSERA. Avl Bal: Rs 7,350.00 —SBI", 1800.00, "debit", "Education", "SBI", True),
    # Savings / investments
    ("Rs 5,000.00 debited from A/c XX4521 on 05-Nov-26 at GROWW-MF. Avl Bal: Rs 15,000.00 —SBI", 5000.00, "debit", "Investment", "SBI", True),
    ("Rs 2,000.00 debited from A/c XX8810 on 05-Nov-26. Info: ZERODHA SIP. Avl Bal Rs 12,000.00 —HDFC", 2000.00, "debit", "Investment", "HDFC", True),
    # Shopping
    ("Rs 450.00 debited from A/c XX2341 on 09-Nov-26. Info: BIG BAZAAR. Avl Bal: Rs 5,650.00 —ICICI", 450.00, "debit", "Shopping", "ICICI", True),
    ("Rs 1,350.00 debited from A/c XX4521 on 14-Nov-26 at RELIANCE SMART. Avl Bal: Rs 5,900.00 —SBI", 1350.00, "debit", "Shopping", "SBI", True),
    ("Rs 2,200.00 debited from A/c XX9910 on 12-Nov-26 at FABINDIA. Avl Bal: Rs 18,300.00 —Axis", 2200.00, "debit", "Shopping", "Axis", True),
    # Entertainment
    ("Rs 649.00 debited from A/c XX2341 on 03-Nov-26. Info: HOTSTAR PREMIUM. Avl Bal: Rs 7,151.00 —ICICI", 649.00, "debit", "Entertainment", "ICICI", True),
    ("Rs 199.00 debited from A/c XX8810 on 04-Nov-26. Info: YOUTUBE PREMIUM. Avl Bal Rs 9,951.00 —HDFC", 199.00, "debit", "Entertainment", "HDFC", True),
    # Food
    ("Rs 220.00 debited from A/c XX4521 on 06-Nov-26 at CHAI POINT. Avl Bal: Rs 13,760.50 —SBI", 220.00, "debit", "Food", "SBI", True),
    ("Rs 480.00 debited from A/c XX8810 on 07-Nov-26. Info: DOMINOS. Avl Bal Rs 7,591.00 —HDFC", 480.00, "debit", "Food", "HDFC", True),
    ("Rs 310.00 debited from A/c XX2341 on 08-Nov-26. Info: BOX8. Avl Bal: Rs 5,790.00 —ICICI", 310.00, "debit", "Food", "ICICI", True),
    # Transport
    ("Rs 250.00 debited from A/c XX9910 on 09-Nov-26 at OLA. Avl Bal: Rs 20,750.00 —Axis", 250.00, "debit", "Transport", "Axis", True),
    ("Rs 100.00 debited from A/c XX4521 on 11-Nov-26 at METRO CARD RECHARGE. Avl Bal: Rs 7,150.50 —SBI", 100.00, "debit", "Transport", "SBI", True),
    ("Rs 180.00 debited from A/c XX8810 on 12-Nov-26. Info: RAPIDO. Avl Bal Rs 7,391.00 —HDFC", 180.00, "debit", "Transport", "HDFC", True),
    # Recurring (duplicates to aid detection)
    ("Rs 7,500.00 debited from A/c XX4521 on 01-Oct-26 at RENT-LANDLORD. Avl Bal: Rs 42,340.50 —SBI", 7500.00, "debit", "Rent", "SBI", True),
    ("Rs 12,000.00 debited from A/c XX8810 on 05-Oct-26 for EMI-HDFC LOAN. Avl Bal Rs 30,551.00", 12000.00, "debit", "EMI", "HDFC", True),
    ("Rs 999.00 debited from A/c XX8810 on 03-Oct-26. Info: NETFLIX. Avl Bal Rs 29,552.00", 999.00, "debit", "Netflix", "HDFC", True),
    # Unparseable on purpose (no amount or format broken)
    ("Hi, please check your bank statement for a discrepancy noted on your account.", None, None, None, None, False),
    ("Bank maintenance scheduled tonight. Services may be intermittently unavailable. —SBI", None, None, None, None, False),
    ("Your account nomination update is complete. Nominee: Rahul Kumar. —HDFC", None, None, None, None, False),
    ("Reminder: submit Form 15G/15H to avoid TDS on FD interest. Contact your branch. —SBI", None, None, None, None, False),
    ("Mobile banking transaction successful. —Axis Bank", None, None, None, None, False),
    # Fraud-like entries (but parseable)
    ("Sent Rs 9,999.00 to unknown-collect@fakebank via UPI on 10-Nov-26. —PhonePe", 9999.00, "debit", "Unknown", "PhonePe", True),
    ("Rs 500.00 debited from A/c XX4521 on 10-Nov-26 at PROCESSING FEE-LOAN. Avl Bal: Rs 6,750.50 —SBI", 500.00, "debit", "Unknown", "SBI", True),
    # More normal transactions to reach ~120
    ("Rs 650.00 debited from A/c XX4521 on 04-Nov-26 at HALDIRAMS. Avl Bal: Rs 13,390.50 —SBI", 650.00, "debit", "Food", "SBI", True),
    ("Rs 280.00 debited from A/c XX8810 on 05-Nov-26. Info: CAFE COFFEE DAY. Avl Bal Rs 20,671.00 —HDFC", 280.00, "debit", "Food", "HDFC", True),
    ("Rs 1,600.00 debited from A/c XX2341 on 06-Nov-26. Info: VIJAY SALES. Avl Bal: Rs 4,950.00 —ICICI", 1600.00, "debit", "Shopping", "ICICI", True),
    ("Rs 390.00 debited from A/c XX9910 on 07-Nov-26 at PHARMACY NEAR. Avl Bal: Rs 20,110.00 —Axis", 390.00, "debit", "Healthcare", "Axis", True),
    ("Rs 240.00 debited from A/c XX4521 on 08-Nov-26 at PETROL PUMP. Avl Bal: Rs 9,610.50 —SBI", 240.00, "debit", "Transport", "SBI", True),
    ("Rs 3,500.00 debited from A/c XX8810 on 09-Nov-26. Info: DENTIST FEE. Avl Bal Rs 7,160.00 —HDFC", 3500.00, "debit", "Healthcare", "HDFC", True),
    ("Rs 2,800.00 debited from A/c XX2341 on 10-Nov-26. Info: TUITION FEES. Avl Bal: Rs 2,101.00 —ICICI", 2800.00, "debit", "Education", "ICICI", True),
    ("Rs 5,000.00 transferred to A/c XX5566 on 11-Nov-26 via NEFT. Ref: NEFT2411XX. —SBI", 5000.00, "debit", "Transfer", "SBI", True),
    ("Rs 100.00 debited from A/c XX9910 on 12-Nov-26 at NEWSPAPERS. Avl Bal: Rs 20,400.00 —Axis", 100.00, "debit", "Entertainment", "Axis", True),
    ("Rs 4,500.00 debited from A/c XX4521 on 13-Nov-26 at FURNITURE SHOP. Avl Bal: Rs 650.50 —SBI", 4500.00, "debit", "Shopping", "SBI", True),
    ("Rs 1,000.00 debited from A/c XX8810 on 14-Nov-26. Info: MOBILE REPAIR. Avl Bal Rs 2,460.00 —HDFC", 1000.00, "debit", "Shopping", "HDFC", True),
    ("Rs 300.00 debited from A/c XX2341 on 02-Nov-26. Info: PARKING FEE. Avl Bal: Rs 7,951.00 —ICICI", 300.00, "debit", "Transport", "ICICI", True),
    ("Rs 1,700.00 debited from A/c XX9910 on 03-Nov-26 at HOTEL STAY. Avl Bal: Rs 19,800.00 —Axis", 1700.00, "debit", "Entertainment", "Axis", True),
    ("Rs 600.00 debited from A/c XX4521 on 06-Nov-26 at GYM MEMBERSHIP. Avl Bal: Rs 13,440.50 —SBI", 600.00, "debit", "Healthcare", "SBI", True),
    ("Rs 2,000.00 credited to A/c XX4521 on 10-Nov-26 (FREELANCE PAYMENT). Avl Bal: Rs 11,440.50 —SBI", 2000.00, "credit", "Salary", "SBI", True),
    ("Rs 500.00 debited from A/c XX8810 on 11-Nov-26. Info: WEDDING GIFT UPI. Avl Bal Rs 6,660.00 —HDFC", 500.00, "debit", "Transfer", "HDFC", True),
    ("Rs 1,200.00 debited from A/c XX2341 on 12-Nov-26. Info: AMAZON SUBSCRIBE. Avl Bal: Rs 901.00 —ICICI", 1200.00, "debit", "Shopping", "ICICI", True),
    ("Rs 750.00 debited from A/c XX9910 on 13-Nov-26 at BARBER SHOP. Avl Bal: Rs 19,650.00 —Axis", 750.00, "debit", "Shopping", "Axis", True),
    ("Rs 3,000.00 debited from A/c XX4521 on 14-Nov-26 at CLOTHING STORE. Avl Bal: Rs 2,650.50 —SBI", 3000.00, "debit", "Shopping", "SBI", True),
    ("Rs 50.00 debited from A/c XX8810 on 14-Nov-26. Info: NEWSPAPER DIGITAL. Avl Bal Rs 2,410.00 —HDFC", 50.00, "debit", "Entertainment", "HDFC", True),
]

sample_csv = DATA_DIR / "sample_sms.csv"
with open(sample_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["id", "raw_sms", "expected_amount", "expected_type",
                     "expected_merchant", "expected_bank", "parseable", "date", "notes"])
    for i, (sms, amount, txn_type, merchant, bank, parseable) in enumerate(SAMPLE_SMS, 1):
        # Extract date from SMS or use default
        date = "2026-11-14"
        if "-Nov-26" in sms or "-Oct-26" in sms:
            import re
            m = re.search(r'(\d{2}-(?:Nov|Oct|Sep)-26)', sms)
            if m:
                raw_date = m.group(1)
                month_map = {"Nov": "11", "Oct": "10", "Sep": "09"}
                parts = raw_date.split("-")
                date = f"2026-{month_map.get(parts[1], '11')}-{parts[0]}"
        writer.writerow([
            f"SMS{i:04d}", sms,
            "" if amount is None else amount,
            txn_type or "",
            merchant or "",
            bank or "",
            str(parseable).lower(),
            date,
            "synthetic"
        ])

print(f"✅ sample_sms.csv written: {len(SAMPLE_SMS)} rows")
parseable_count = sum(1 for r in SAMPLE_SMS if r[5])
print(f"   Parseable: {parseable_count}, Unparseable: {len(SAMPLE_SMS) - parseable_count}")
