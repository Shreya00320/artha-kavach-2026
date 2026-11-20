"""Turn the public UCI "SMS Spam Collection" into extra ORDINARY-text data for the scam classifier.

Source : https://archive.ics.uci.edu/dataset/228/sms+spam+collection
         Almeida & Hidalgo, 2011 — licensed CC BY 4.0 (attribution required; see README).
Used   : only the 4,827 "ham" (non-spam) messages, as `safe` examples. The spam half is NOT used
         (UK prize-draw texts; mapping them onto our scam/suspicious labels would add label noise).

Usage:
    curl -sSL -o sms.zip "https://archive.ics.uci.edu/static/public/228/sms+spam+collection.zip"
    python -I data/fetch_sms_ham.py path/to/sms.zip

Writes data/external/sms_ham_train.csv (2000 rows) and data/external/sms_ham_test.csv (300 rows).
data/external/ is git-ignored: re-download rather than committing third-party data.
The zip is treated as untrusted data: it is read with the stdlib zipfile module only, never executed.
"""
import csv
import random
import sys
import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parent / "external"


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    with zipfile.ZipFile(sys.argv[1]) as z:
        lines = z.read("SMSSpamCollection").decode("utf-8", "replace").splitlines()
    ham = []
    for line in lines:
        label, _, text = line.partition("\t")
        text = " ".join(text.split())
        if label == "ham" and 8 <= len(text) <= 300:
            ham.append(text)
    ham = sorted(set(ham))
    random.Random(11).shuffle(ham)
    OUT.mkdir(exist_ok=True)
    for name, chunk, split in (("sms_ham_test.csv", ham[:300], "test"), ("sms_ham_train.csv", ham[300:2300], "train")):
        with open(OUT / name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "label", "text", "language", "hinglish", "split", "notes"])
            for i, t in enumerate(chunk, 1):
                w.writerow([f"SMS{split[:2]}{i:04d}", "safe", t, "en", "false", split, "uci-sms-spam-collection-ham"])
        print(name, len(chunk))


if __name__ == "__main__":
    main()
