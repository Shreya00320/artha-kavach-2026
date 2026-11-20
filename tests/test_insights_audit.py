"""Insights audit: alerts must catch a big transfer to a new payee; bills are not 'subscriptions'; clean merchant names."""

from core.categoriser import categorise
from core.insights import detect_anomalies, detect_subscriptions
from core.parser import parse_message


def _tx(msgs):
    return [categorise(parse_message(m)) for m in msgs]


def test_large_transfer_to_new_payee_is_flagged():
    msgs = ["Rs 500.00 debited from A/c XX1234 on 10-11-26 to chai@ybl UPI Ref 633000000001",
            "Rs 85,000.00 debited from A/c XX1234 on 14-11-26 to UNKNOWN_TRADER@ybl UPI Ref 633999000111"]
    alerts = detect_anomalies(_tx(msgs))
    big = [a for a in alerts if a.amount == 85000]
    assert big and big[0].severity == "high" and "payee" in big[0].reason


def test_repeat_payee_or_small_transfer_is_not_flagged():
    msgs = [f"Rs 12,000.00 debited from A/c XX1234 on 0{d}-11-26 to rahul.k@okaxis UPI Ref 63300000000{d}" for d in (1, 2)]
    assert not [a for a in detect_anomalies(_tx(msgs)) if a.category == "Transfer"]
    one_small = _tx(["Rs 2,000.00 debited from A/c XX1234 on 10-11-26 to rahul.k@okaxis UPI Ref 633000000009"])
    assert not detect_anomalies(one_small)


def test_electricity_bill_is_not_a_subscription_but_netflix_is():
    msgs = []
    for m in ("09", "10", "11"):
        msgs += [f"Rs 1,200.00 debited from A/c XX1234 on 15-{m}-26 for ELECTRICITY BILL. Avl Bal Rs 30,000.00",
                 f"Rs 499.00 debited from A/c XX1234 on 10-{m}-26 by NACH/NETFLIX. Avl Bal Rs 39,500.00"]
    names = [s.merchant.lower() for s in detect_subscriptions(_tx(msgs))]
    assert "netflix" in names and not any("electric" in n for n in names)


def test_channel_prefixes_are_stripped_from_merchant_names():
    assert parse_message("Rs 499.00 debited from A/c XX1234 on 10-11-26 by NACH/NETFLIX. Avl Bal Rs 39,500.00").merchant == "NETFLIX"
    assert parse_message("Rs 15,000.00 debited from A/c XX1234 on 05-11-26 for RTGS to LANDLORD PROPERTIES. Avl Bal Rs 40,000.00").merchant == "LANDLORD PROPERTIES"
