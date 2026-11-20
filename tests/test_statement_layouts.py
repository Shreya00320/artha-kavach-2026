"""Bank-statement CSV import: layouts exported by the major banks and finance apps.

Before the rewrite only the HDFC and SBI layouts worked; ICICI/Axis/Kotak/semicolon/tab files imported nothing,
and signed or Dr/Cr amounts turned salary credits into expenses.
"""

import pytest

from core.parser import parse_message
from core.statement import statement_to_sms

LAYOUTS = {'HDFC': 'Date,Narration,Chq./Ref.No.,Value Dt,Withdrawal Amt.,Deposit Amt.,Closing Balance\n01/11/26,NEFT CR-ACME LTD-SALARY NOV,N123,01/11/26,,55000.00,68000.00\n03/11/26,UPI-SWIGGY-SWIGGY@YBL-YESB0YBLUPI-633000111222-PAYMENT,633000111222,03/11/26,450.00,,67550.00\n05/11/26,UPI-ZOMATO-ZOMATO@HDFCBANK-HDFC0000001-633000111333-PAYMENT,633000111333,05/11/26,320.50,,67229.50\n', 'SBI': 'Txn Date,Value Date,Description,Ref No./Cheque No.,Debit,Credit,Balance\n1 Nov 2026,1 Nov 2026,TRANSFER FROM ACME PVT LTD SALARY,,,55000.00,68000.00\n3 Nov 2026,3 Nov 2026,UPI/DR/633000111222/SWIGGY/YESB/swiggy@ybl,,450.00,,67550.00\n', 'ICICI': 'S No.,Value Date,Transaction Date,Cheque Number,Transaction Remarks,Withdrawal Amount (INR ),Deposit Amount (INR ),Balance (INR )\n1,01/11/2026,01/11/2026,,NEFT-ACME LTD-SALARY,0.00,55000.00,68000.00\n2,03/11/2026,03/11/2026,,UPI/633000111222/SWIGGY/swiggy@ybl,450.00,0.00,67550.00\n', 'AXIS': 'Tran Date,CHQNO,PARTICULARS,DR,CR,BAL,SOL\n01-11-2026,,NEFT/ACME LTD/SALARY,,55000.00,68000.00,1234\n03-11-2026,,UPI/P2M/633000111222/SWIGGY,450.00,,67550.00,1234\n', 'KOTAK': 'Date,Narration,Chq/Ref No,Withdrawal (Dr),Deposit (Cr),Balance\n01-Nov-2026,NEFT-ACME LTD-SALARY,N1,,"55,000.00","68,000.00"\n03-Nov-2026,UPI/SWIGGY/633000111222,633000111222,450.00,,"67,550.00"\n', 'SINGLE-COL signed': 'Date,Description,Amount,Balance\n2026-11-01,SALARY ACME LTD,55000.00,68000.00\n2026-11-03,SWIGGY ORDER,-450.00,67550.00\n2026-11-04,AMAZON,-1299.00,66251.00\n', 'Dr/Cr suffix': 'Date,Narration,Amount,Balance\n01/11/2026,SALARY ACME LTD,"55,000.00 Cr","68,000.00 Cr"\n03/11/2026,SWIGGY,"450.00 Dr","67,550.00 Cr"\n', 'semicolon': 'Date;Narration;Debit;Credit;Balance\n01/11/2026;SALARY ACME;;55000;68000\n03/11/2026;SWIGGY;450;;67550\n', 'tab': 'Date\tNarration\tWithdrawal\tDeposit\tBalance\n01/11/2026\tSALARY ACME\t\t55000\t68000\n03/11/2026\tSWIGGY\t450\t\t67550\n', 'no balance col, identical rows': 'Date,Narration,Debit,Credit\n03/11/2026,CHAI POINT,20.00,\n03/11/2026,CHAI POINT,20.00,\n', 'preamble + footer': 'Account Statement for XXXX1234\nPeriod: 01/11/2026 to 30/11/2026\n\nDate,Narration,Debit,Credit,Balance\n03/11/2026,SWIGGY,450.00,,67550.00\nOpening Balance,,,,\nClosing balance as on 30/11/2026,,,,67550.00\n'}

EXPECTED = {'HDFC': [('credit', 55000.0), ('debit', 450.0), ('debit', 320.5)], 'SBI': [('credit', 55000.0), ('debit', 450.0)], 'ICICI': [('credit', 55000.0), ('debit', 450.0)], 'AXIS': [('credit', 55000.0), ('debit', 450.0)], 'KOTAK': [('credit', 55000.0), ('debit', 450.0)], 'SINGLE-COL signed': [('credit', 55000.0), ('debit', 450.0), ('debit', 1299.0)], 'Dr/Cr suffix': [('credit', 55000.0), ('debit', 450.0)], 'semicolon': [('credit', 55000.0), ('debit', 450.0)], 'tab': [('credit', 55000.0), ('debit', 450.0)], 'no balance col, identical rows': [('debit', 20.0), ('debit', 20.0)], 'preamble + footer': [('debit', 450.0)]}


@pytest.mark.parametrize("name", list(LAYOUTS))
def test_layout_imports_with_correct_direction_and_amount(name):
    parsed = [parse_message(m) for m in statement_to_sms(LAYOUTS[name])]
    assert [(p.transaction_type, p.amount) for p in parsed] == EXPECTED[name]


def test_salary_credit_is_never_a_debit_in_signed_layouts():
    for name in ("SINGLE-COL signed", "Dr/Cr suffix"):
        first = parse_message(statement_to_sms(LAYOUTS[name])[0])
        assert first.transaction_type == "credit" and first.amount == 55000.0


def test_no_invented_balance_and_identical_rows_survive():
    sms = statement_to_sms(LAYOUTS["no balance col, identical rows"])
    assert len(sms) == 2 and all("Bal" not in m for m in sms)
    from core.parser import dedupe_messages
    assert len(dedupe_messages(sms)[0]) == 2          # two real Rs 20 chai payments are both kept


def test_sbi_upi_narration_gives_the_merchant_not_DR():
    p = parse_message(statement_to_sms(LAYOUTS["SBI"])[1])
    assert p.merchant == "SWIGGY"


def test_non_statement_still_returns_empty():
    assert statement_to_sms("raw_sms
Rs 5 debited
") == []
