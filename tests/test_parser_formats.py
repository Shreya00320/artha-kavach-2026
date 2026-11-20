"""Parser: realistic SMS formats from many banks (field-based fallback) and non-transactions that must be rejected.

Batch A was used to design the fallback parser; batch B was written afterwards and scored 32/35 on its first run
(three fixes were then made: 'a/c no.' context, 'purchase of', cheque-clearing notices).
Formats are representative of public bank SMS styles, not verbatim real messages.
"""

import pytest

from core.parser import parse_message

BATCH_A = [('Dear UPI user A/C X1234 debited by 500.0 on date 13Nov26 trf to SWIGGY Refno 633212345678 If not u? call 1800111109. -SBI', 'debit', 500.0),
    ('Dear Customer, A/C X1234 credited by Rs 25,000.00 on 05Nov26 transfer from RAHUL KUMAR Ref No 123456789012 -SBI', 'credit', 25000.0),
    ('Your a/c no. XXXXXXXX1234 is credited by Rs.1,00,000.00 on 30-10-2026 by transfer-NEFT*ACME PVT LTD*SALARY OCT. -SBI', 'credit', 100000.0),
    ('Rs.2000 withdrawn from A/C XXXX1234 at ATM on 12-11-2026. Avl Bal Rs 8,432.55 -SBI', 'debit', 2000.0),
    ('Dear Customer, your A/c X1234 is debited with Rs.499.00 on 10-11-26 by NACH/NETFLIX. Avl Bal Rs.3,210.10 -SBI', 'debit', 499.0),
    ('Rs 500.00 debited from a/c **1234 on 13-11-26 to VPA zomato@hdfcbank(UPI Ref No 633212345678). Not you? Call 18002586161', 'debit', 500.0),
    ('UPI txn. Rs.1,250.00 debited from HDFC Bank A/c XX1234 on 13-NOV-26 to VPA bigbasket@ybl (UPI Ref No 633212345678)', 'debit', 1250.0),
    ('Rs. 45,000.00 credited to a/c XX1234 on 01-11-26 by NEFT-ACME LTD-SALARY. Avl bal Rs 61,200.45', 'credit', 45000.0),
    ('Spent Rs.1,250.00 On HDFC Bank Card x1234 At AMAZON On 2026-11-13:12:34:56.Not You? To Block+Reissue Call 18002586161', 'debit', 1250.0),
    ('HDFC Bank: Rs 12,000.00 paid via Credit Card XX9012 at FLIPKART on 12-11-26. Avl Cr Limit Rs 88,000', 'debit', 12000.0),
    ('ICICI Bank Acct XX123 debited for Rs 500.00 on 13-Nov-26; ZOMATO credited. UPI:633212345678. Call 18002662 for dispute. SMS BLOCK 123 to 9215676766', 'debit', 500.0),
    ('ICICI Bank Acct XX123 credited with Rs 15,000.00 on 05-Nov-26. Info: UPI/633212345678/RAHUL. Avl Bal Rs 20,331.00', 'credit', 15000.0),
    ('Rs 3,499.00 spent on ICICI Bank Card XX4321 on 11-Nov-26 at MYNTRA. Avl Limit: Rs 96,501.00', 'debit', 3499.0),
    ('INR 500.00 debited A/c no. XX1234 13-11-26 12:34:56 UPI/P2M/633212345678/Swiggy SMS BLOCKUPI Cust ID to 919951860002 if not you - Axis Bank', 'debit', 500.0),
    ('INR 30,000.00 credited to A/c no. XX1234 on 01-11-26 12:00:00 NEFT/ACME LTD/SALARY. Axis Bank', 'credit', 30000.0),
    ('Sent Rs.500.00 from Kotak Bank AC X1234 to merchant@ybl on 13-11-26.UPI Ref 633212345678. Not you? Call 18602662666', 'debit', 500.0),
    ('Received Rs.1,500.00 in your Kotak Bank AC X1234 from friend@okaxis on 12-11-26.UPI Ref:633212345678', 'credit', 1500.0),
    ('A/c XX1234 debited INR 500.00 Dt 13-11-26 12:34 trf to MERCHANT Ref No 633212345678 -PNB', 'debit', 500.0),
    ('Rs.500 Dr. from A/c XXXXXX1234 and Cr. to merchant@ybl. Ref:633212345678. AvlBal:Rs 1234.56(2026:11:13 12:34:56) -BOB', 'debit', 500.0),
    ('Rs. 1,000.00 credited to your Canara Bank A/c XX1234 on 10/11/2026 by UPI Ref 633212345678', 'credit', 1000.0),
    ('Your a/c XX1234 debited with Rs.250.00 on 13-Nov-2026 to UPI/Chai Point. Union Bank of India', 'debit', 250.0),
    ('Rs 750 spent via IDFC FIRST Bank Debit Card ending 1234 at DMART on 12-Nov-26', 'debit', 750.0),
    ('You paid Rs.350 to Uber India via PhonePe. UPI Ref 633212345678', 'debit', 350.0),
    ('Paid Rs. 120 to Chai Sutta Bar using Google Pay. UPI transaction ID 633212345678', 'debit', 120.0),
    ('Rs.2,499 debited from your Paytm Payments Bank a/c for Amazon Pay', 'debit', 2499.0),
    ('EMI of Rs 8,450 for loan XX8899 debited from your a/c XX1234 on 03-Nov-26', 'debit', 8450.0),
    ('Your salary of INR 55,000.00 has been credited to A/c XX1234 on 01-11-2026', 'credit', 55000.0),
    ('Refund of Rs 1,299.00 for your Amazon order has been credited to a/c XX1234 on 09-Nov-26', 'credit', 1299.0),
    ('Rs 5,00,000.00 credited to your account XX1234 on 02-Nov-26 by RTGS from ACME CORP', 'credit', 500000.0),
    ('Rs.99 deducted from A/c XX1234 for Spotify subscription on 08-11-26', 'debit', 99.0),
    ('₹1,200 debited from A/c XX1234 on 07-Nov-26 UPI-RENT-landlord@oksbi', 'debit', 1200.0),
    ('Your OTP for UPI transaction of Rs 500.00 is 482913. Do not share with anyone. -HDFC Bank', None, None),
    ('Dear Customer, Rs 8,450 will be auto-debited from your a/c XX1234 on 03-Dec-26 towards your loan EMI. Please maintain balance.', None, None),
    ('Your txn of Rs 500.00 to merchant@ybl has failed. Amount not debited. -SBI', None, None),
    ('Transaction of Rs.1,000 declined due to insufficient funds. A/c XX1234 -ICICI Bank', None, None),
    ('Avl Bal in A/c XX1234 is Rs 4,500.25 as on 13-Nov-26. -SBI', None, None),
    ('Congratulations! You are eligible for a pre-approved loan of Rs 5,00,000. Apply now http://bit.ly/abc', None, None),
    ('Get 10% cashback up to Rs 500 on your next UPI payment. T&C apply', None, None),
    ('Your credit card statement of Rs 12,430 is due on 18-Nov-26. Min due Rs 620. Pay now to avoid late fee.', None, None),
    ("Rs 500 collect request from rahul@ybl. Approve in your UPI app. Do not approve if you don't know the sender.", None, None),
    ('hey are we meeting tomorrow? i paid 500 for the tickets already', None, None)]

BATCH_B = [('Dear SBI Customer, your A/c X5678 has been debited with Rs.3,200.00 on 14/11/2026 towards BESCOM BILL PAYMENT. Bal Rs.18,450.30', 'debit', 3200.0),
    ('Rs.18,000 credited to a/c ending 4411 on 03-Nov-2026 via IMPS from PRIYA SHARMA. Ref 631234567890', 'credit', 18000.0),
    ('Alert: INR 1,499.00 spent on your SBI Card ending 7766 at NETFLIX COM on 12/11/26. Avl limit INR 48,501.00', 'debit', 1499.0),
    ('HDFC BANK: Rs.640.00 debited from A/C XX9988 on 11-NOV-26 towards UPI/zepto@ybl/Groceries. Ref 633000111222', 'debit', 640.0),
    ('Your HDFC Bank NetBanking: Rs 25,000.00 transferred from A/c XX9988 to Beneficiary RAJESH K on 10-11-2026 via NEFT. Ref N312345678', 'debit', 25000.0),
    ('ICICI Bank Acct XX771 debited with Rs 2,150.00 on 09-Nov-26 & Acct XX445 credited. IMPS Ref no 631111222333', 'debit', 2150.0),
    ('Rs 120.00 paid to IRCTC via Paytm UPI on 08-11-2026. Txn ID 633444555666', 'debit', 120.0),
    ('Amount of Rs.700.00 has been debited from your a/c no. XXXXXX3344 on 07/11/2026 by ATM WDL at CP DELHI', 'debit', 700.0),
    ('You have received INR 4,200.00 in your Axis Bank account no. XX5566 on 06-11-26 from UPI/aman.k@okicici/633777888999', 'credit', 4200.0),
    ('Kotak Bank: Your a/c XX3210 has been credited with Rs.62,300.00 on 01-Nov-26. Narration: NEFT-INFOSYS LTD-SAL OCT26', 'credit', 62300.0),
    ('Rs. 349.00 deducted from your A/C XXXX2200 for Hotstar mandate on 05-Nov-2026. Bal: Rs 9,001.20', 'debit', 349.0),
    ('Rs 85,000.00 credited to your A/c XX1100 on 31-Oct-26 -Interest on FD', 'credit', 85000.0),
    ('Payment of Rs 6,210.00 received towards your HDFC Bank Credit Card XX9012 on 04-Nov-26. Thank you', 'credit', 6210.0),
    ('Rs.1,000 sent to ramesh@okhdfcbank from A/c X4432 on 02-Nov-26 UPI Ref 632000111000', 'debit', 1000.0),
    ('Money Received! Rs.2,500 from DIVYA via BHIM UPI to A/c XX3399 on 02-11-2026', 'credit', 2500.0),
    ('Rs 15.50 debited from A/c XX7777 for SMS charges on 30-Oct-26', 'debit', 15.5),
    ('Acct XX2468 credited INR 9,999.00 on 29-Oct-26 by CASH DEPOSIT at ATM. Avl Bal INR 12,111.00', 'credit', 9999.0),
    ('Rs.5,60,000.00 debited from A/c XX8080 on 28-Oct-26 for RTGS to LANDLORD PROPERTIES. Ref RTGS123', 'debit', 560000.0),
    ('Your Swiggy Money wallet debited Rs 245 for order #123456 on 27-Oct-26', 'debit', 245.0),
    ('Purchase of Rs 1,899.00 at AMAZON PAY INDIA on card XX1357 dt 26-Oct-26 successful', 'debit', 1899.0),
    ('Use OTP 551230 to approve debit of Rs 5,000 to rahul@ybl. Valid 3 min. Do not share. -SBI', None, None),
    ('Your UPI collect request of Rs 799.00 from adidas@ybl is pending. Approve only if you know the sender.', None, None),
    ('Rs 3,000.00 will be debited from your a/c XX1234 on 05-Dec-26 for SIP. Ensure balance.', None, None),
    ('Alert: payment of Rs 1,200.00 to AMAZON could not be completed. No amount debited.', None, None),
    ('Statement for card XX9012: Total due Rs 22,340.00, Min due Rs 1,120.00 by 20-Nov-26', None, None),
    ('Dear customer, your a/c XX1234 balance is Rs 3,456.00 as of 13-Nov-26 08:00', None, None),
    ('Get Rs 500 cashback on UPI payments above Rs 2000. Offer valid till 30 Nov. T&C', None, None),
    ('Win Rs 10,00,000 in the lucky draw! Pay Rs 999 to claim. Click http://bit.ly/x1', None, None),
    ('Rs 2,000 credited as free points to your account! Visit store now', None, None),
    ("can u send me 500 rs on gpay? i'll pay back tomorrow", None, None),
    ('Your account XX1234 will be debited Rs 999 automatically for the annual fee if not cancelled', None, None),
    ('Congratulations, you are eligible for a loan of Rs 3,00,000. Call now.', None, None),
    ('Cheque no 123456 for Rs 5,000 has been received for clearing in a/c XX1234', None, None),
    ('Your Rs 5000 loan application is under review. Ref 99887766', None, None),
    ('Order #7766 for Rs 1,299 has been shipped via UPI pre-payment. Track here.', None, None)]


@pytest.mark.parametrize("text,kind,amount", BATCH_A + BATCH_B)
def test_sms_format(text, kind, amount):
    r = parse_message(text)
    if kind is None:
        assert r.parse_method == "failed", f"not a transaction but parsed: {r.transaction_type} {r.amount}"
    else:
        assert r.parse_method != "failed", "transaction not parsed"
        assert r.transaction_type == kind
        assert r.amount == pytest.approx(amount)


def test_merchants_and_dates_are_extracted():
    r = parse_message("Dear UPI user A/C X1234 debited by 500.0 on date 13Nov26 trf to SWIGGY Refno 633212345678 If not u? call 1800111109. -SBI")
    assert r.merchant == "SWIGGY" and r.date == "2026-11-13" and r.bank == "SBI"
    r = parse_message("Rs.500 Dr. from A/c XXXXXX1234 and Cr. to merchant@ybl. Ref:633212345678. AvlBal:Rs 1234.56(2026:11:13 12:34:56) -BOB")
    assert r.vpa == "merchant@ybl" and r.date == "2026-11-13" and r.balance == pytest.approx(1234.56)
    r = parse_message("Rs 5,00,000.00 credited to your account XX1234 on 02-Nov-26 by RTGS from ACME CORP")
    assert r.amount == 500000 and r.merchant == "ACME CORP"


def test_balance_is_never_mistaken_for_the_amount():
    r = parse_message("Rs 3,499.00 spent on ICICI Bank Card XX4321 on 11-Nov-26 at MYNTRA. Avl Limit: Rs 96,501.00")
    assert r.amount == 3499.0
    r = parse_message("Rs.2000 withdrawn from A/C XXXX1234 at ATM on 12-11-2026. Avl Bal Rs 8,432.55 -SBI")
    assert r.amount == 2000.0 and r.balance == pytest.approx(8432.55)
