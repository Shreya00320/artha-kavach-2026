"""
core/report.py — one-page-ish "money report" PDF from the budget engine output.

Idea taken from open-source finance advisors that export a PDF summary (the code here is original:
a tiny dependency-free PDF writer using the built-in Helvetica fonts, so there is nothing to install
and nothing that can be blocked on a locked-down machine).

Every number in the report comes straight from the BudgetSummary / subscriptions computed in code.
The built-in PDF fonts have no ₹ glyph, so amounts are written as "Rs".

Public API:
  build_monthly_report_pdf(summary, subscriptions=None, weeks=None) -> bytes
"""

from __future__ import annotations

from datetime import date

PAGE_W, PAGE_H = 595, 842          # A4 in points
MARGIN = 48
NAVY, TEAL, GREY, RED, GREEN, LIGHT = (0.10, 0.17, 0.30), (0.05, 0.56, 0.55), (0.45, 0.47, 0.52), \
    (0.80, 0.22, 0.20), (0.15, 0.55, 0.30), (0.90, 0.92, 0.95)


def _inr(x: float) -> str:
    """Indian digit grouping, 'Rs' prefix (no rupee glyph in the core PDF fonts)."""
    neg = x < 0
    n = f"{abs(round(x)):d}"
    if len(n) > 3:
        head, tail = n[:-3], n[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        n = ",".join(parts + [tail])
    return f"{'-' if neg else ''}Rs {n}"


def _latin1(text: str) -> str:
    text = (text.replace("₹", "Rs ").replace("—", "-").replace("–", "-").replace("’", "'").replace("‘", "'")
            .replace("“", '"').replace("”", '"').replace("•", "-").replace("…", "..."))
    return text.encode("latin-1", "replace").decode("latin-1")


def _esc(text: str) -> str:
    return _latin1(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _text_width(text: str, size: float) -> float:
    """Approximate Helvetica width (digits/space exact enough for right-aligning numbers)."""
    w = 0.0
    for ch in _latin1(text):
        if ch.isdigit():
            w += 0.556
        elif ch in ",. ":
            w += 0.278
        elif ch in "il|!'":
            w += 0.25
        elif ch in "mwMW":
            w += 0.85
        elif ch.isupper():
            w += 0.68
        else:
            w += 0.52
    return w * size


class _Pdf:
    """Minimal multi-page PDF writer: text, rectangles, lines."""

    def __init__(self) -> None:
        self.pages: list[list[str]] = []
        self.y = PAGE_H - MARGIN
        self.new_page()

    def new_page(self) -> None:
        self.pages.append([])
        self.y = PAGE_H - MARGIN

    @property
    def ops(self) -> list[str]:
        return self.pages[-1]

    def ensure(self, height: float) -> None:
        if self.y - height < MARGIN + 20:
            self.new_page()

    def text(self, x: float, y: float, s: str, size: float = 10, bold: bool = False,
             color: tuple = (0, 0, 0), align: str = "left") -> None:
        if align == "right":
            x -= _text_width(s, size)
        font = "F2" if bold else "F1"
        self.ops.append(f"BT /{font} {size} Tf {color[0]:.2f} {color[1]:.2f} {color[2]:.2f} rg "
                        f"{x:.1f} {y:.1f} Td ({_esc(s)}) Tj ET")

    def rect(self, x: float, y: float, w: float, h: float, color: tuple) -> None:
        if w <= 0 or h <= 0:
            return
        self.ops.append(f"{color[0]:.2f} {color[1]:.2f} {color[2]:.2f} rg {x:.1f} {y:.1f} {w:.1f} {h:.1f} re f")

    def line(self, x1: float, y1: float, x2: float, y2: float, color: tuple = LIGHT, width: float = 0.8) -> None:
        self.ops.append(f"{color[0]:.2f} {color[1]:.2f} {color[2]:.2f} RG {width} w {x1:.1f} {y1:.1f} m {x2:.1f} {y2:.1f} l S")

    def heading(self, s: str) -> None:
        self.ensure(34)
        self.y -= 22
        self.text(MARGIN, self.y, s, 13, True, NAVY)
        self.line(MARGIN, self.y - 5, PAGE_W - MARGIN, self.y - 5, TEAL, 1.2)
        self.y -= 22

    def paragraph(self, s: str, size: float = 9.5, color: tuple = (0.15, 0.15, 0.15), width: float | None = None) -> None:
        width = width or (PAGE_W - 2 * MARGIN)
        words, line = _latin1(s).split(), ""
        for w in words:
            trial = f"{line} {w}".strip()
            if _text_width(trial, size) > width and line:
                self.ensure(size + 4)
                self.text(MARGIN, self.y, line, size, color=color)
                self.y -= size + 3.5
                line = w
            else:
                line = trial
        if line:
            self.ensure(size + 4)
            self.text(MARGIN, self.y, line, size, color=color)
            self.y -= size + 3.5

    def to_bytes(self) -> bytes:
        objs: list[bytes] = []
        n_pages = len(self.pages)
        first_page_obj = 5
        kids = " ".join(f"{first_page_obj + 2 * i} 0 R" for i in range(n_pages))
        objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
        objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode())
        objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        for i, ops in enumerate(self.pages):
            footer = (f"BT /F1 8 Tf 0.45 0.47 0.52 rg {MARGIN} 28 Td "
                      f"(Artha Kavach money report - page {i + 1} of {n_pages} - general information, not financial advice) Tj ET")
            stream = ("\n".join(ops + [footer])).encode("latin-1", "replace")
            content_obj = first_page_obj + 2 * i + 1
            objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
                        f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {content_obj} 0 R >>".encode())
            objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for n, body in enumerate(objs, 1):
            offsets.append(len(out))
            out += f"{n} 0 obj\n".encode() + body + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
        for off in offsets:
            out += f"{off:010d} 00000 n \n".encode()
        out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
        return bytes(out)


# ---------------------------------------------------------------------------
# Report content
# ---------------------------------------------------------------------------

def _tips(s) -> list[str]:
    """Plain-language observations derived only from the summary's own numbers."""
    tips = []
    if s.total_income > 0:
        if s.savings_rate >= 20:
            tips.append(f"You kept {s.savings_rate:.0f}% of income - at or above the 20% guideline. Keep it automatic.")
        elif s.savings_rate > 0:
            tips.append(f"You kept {s.savings_rate:.0f}% of income. Raising it towards 20% "
                        f"(about {_inr(s.savings_target)} on this income) is a good next step.")
        else:
            tips.append("Spending was at or above income this period. Start by finding one recurring cost to trim.")
    if s.wants_delta > 0:
        tips.append(f"'Wants' spending is {_inr(s.wants_delta)} above the 30% guideline.")
    if s.needs_delta > 0:
        tips.append(f"'Needs' are {_inr(s.needs_delta)} above the 50% guideline - fixed costs like rent or EMIs "
                    "are the lever to look at.")
    top = sorted(((k, v) for k, v in s.by_category.items() if v > 0), key=lambda kv: -kv[1])[:1]
    if top:
        tips.append(f"Your biggest category was {top[0][0].replace('_', ' / ')} at {_inr(top[0][1])}.")
    return tips


def build_monthly_report_pdf(summary, subscriptions=None, weeks=None) -> bytes:
    s = summary
    pdf = _Pdf()
    W = PAGE_W - 2 * MARGIN

    # ---- title band
    pdf.rect(0, PAGE_H - 92, PAGE_W, 92, NAVY)
    pdf.text(MARGIN, PAGE_H - 48, "Artha Kavach - Money Report", 22, True, (1, 1, 1))
    pdf.text(MARGIN, PAGE_H - 70, f"{s.period_start or '-'}  to  {s.period_end or '-'}   |   generated {date.today().isoformat()}",
             10, False, (0.8, 0.9, 0.95))
    pdf.y = PAGE_H - 112

    # ---- headline numbers
    pdf.heading("At a glance")
    cards = [("Income", _inr(s.total_income), NAVY), ("Spending", _inr(s.total_expense), NAVY),
             ("Left over", _inr(s.net), GREEN if s.net >= 0 else RED), ("Savings rate", f"{s.savings_rate:.0f}%", TEAL)]
    cw = (W - 3 * 10) / 4
    top = pdf.y - 4
    for i, (label, value, col) in enumerate(cards):
        x = MARGIN + i * (cw + 10)
        pdf.rect(x, top - 50, cw, 50, LIGHT)
        pdf.text(x + 8, top - 18, label, 8.5, False, GREY)
        pdf.text(x + 8, top - 40, value, 13, True, col)
    pdf.y = top - 62

    # ---- 50/30/20
    pdf.heading("50 / 30 / 20 check")
    rows = [("Needs", s.needs_total, s.needs_target, 50), ("Wants", s.wants_total, s.wants_target, 30),
            ("Savings & investing", s.savings_total, s.savings_target, 20)]
    bar_x, bar_w = MARGIN + 130, W - 130 - 150
    for name, actual, target, pct in rows:
        pdf.ensure(24)
        mx = max(actual, target, 1)
        pdf.text(MARGIN, pdf.y, f"{name} ({pct}%)", 9.5, True)
        pdf.rect(bar_x, pdf.y - 1, bar_w * actual / mx, 7, TEAL)
        pdf.rect(bar_x, pdf.y - 9, bar_w * target / mx, 4, (0.7, 0.75, 0.82))
        pdf.text(PAGE_W - MARGIN, pdf.y, f"{_inr(actual)}  /  target {_inr(target)}", 9, False, (0.2, 0.2, 0.2), "right")
        pdf.y -= 24
    pdf.text(bar_x, pdf.y + 4, "teal = actual, grey = target", 7.5, False, GREY)
    pdf.y -= 6

    # ---- categories
    cats = sorted(((k, v) for k, v in s.by_category.items() if v > 0), key=lambda kv: -kv[1])[:8]
    if cats:
        pdf.heading("Where the money went")
        mx = cats[0][1]
        for name, amt in cats:
            pdf.ensure(18)
            share = (amt / s.total_expense * 100) if s.total_expense else 0
            pdf.text(MARGIN, pdf.y, name.replace("_", " / "), 9.5)
            pdf.rect(bar_x, pdf.y - 1, bar_w * amt / mx, 8, TEAL)
            pdf.text(PAGE_W - MARGIN, pdf.y, f"{_inr(amt)}  ({share:.0f}%)", 9, False, (0.2, 0.2, 0.2), "right")
            pdf.y -= 17

    # ---- weekly spend
    if weeks and len(weeks) >= 2:
        pdf.heading("Weekly spending")
        pdf.ensure(110)
        weeks = weeks[-12:]
        mx = max(w["spend"] for w in weeks) or 1
        base, h = pdf.y - 90, 80
        bw = W / len(weeks)
        for i, w in enumerate(weeks):
            bh = h * w["spend"] / mx
            pdf.rect(MARGIN + i * bw + 3, base, bw - 6, bh, TEAL)
            pdf.text(MARGIN + i * bw + bw / 2 - 8, base - 10, str(w["week_start"])[5:], 6.5, False, GREY)
        pdf.text(PAGE_W - MARGIN, base + h + 4, f"peak week {_inr(mx)}", 8, False, GREY, "right")
        pdf.y = base - 22

    # ---- subscriptions
    if subscriptions:
        pdf.heading("Subscriptions and recurring payments")
        total_m = sum(x.monthly_amount for x in subscriptions)
        total_y = sum(x.annual_cost for x in subscriptions)
        for x in subscriptions[:10]:
            pdf.ensure(14)
            pdf.text(MARGIN, pdf.y, x.merchant, 9.5)
            pdf.text(PAGE_W - MARGIN, pdf.y, f"{_inr(x.monthly_amount)}/month   {_inr(x.annual_cost)}/year", 9,
                     False, (0.2, 0.2, 0.2), "right")
            pdf.y -= 14
        pdf.ensure(16)
        pdf.text(MARGIN, pdf.y - 2, f"Total: {_inr(total_m)} a month, {_inr(total_y)} a year. "
                 "Cancel any you haven't used in the last month.", 9, True, NAVY)
        pdf.y -= 16

    # ---- observations
    tips = _tips(s)
    if tips:
        pdf.heading("Worth a look")
        for t in tips:
            pdf.paragraph("- " + t)

    pdf.y -= 8
    pdf.paragraph("All figures are computed from the transactions you loaded. This report is general information "
                  "for budgeting, not personalised financial, tax or investment advice.", 8, GREY)
    return pdf.to_bytes()
