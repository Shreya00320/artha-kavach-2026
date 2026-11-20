"""
core/advisor.py — Artha, the conversational money coach (English).

Pipeline for every message:
  1. Safety guards      prompt-injection, requests for specific stock/fund/crypto picks or
                        market predictions, "guaranteed return" bait.
  2. Scam routing       if the text itself looks like a scam message, hand off to Scam Shield rules.
  3. Small talk         greetings / thanks / goodbye.
  4. Personal numbers   if the user loaded their bank data and asks about *their* money, use the
                        existing grounded assistant (core.assistant).
  5. Knowledge answer   retrieve from the KB (core.knowledge, offline TF-IDF). If an LLM adapter
                        is available, let it phrase the answer from the passages; any number not
                        found in the passages/question/history causes a fallback to the offline
                        answer. Low-confidence retrieval -> honest "I'm not sure".

Public API:
  respond(message, history=None, summary=None, txns=None, subscriptions=None, adapter=None) -> Reply
  Reply(text, method, intent, sources, confidence)
  STARTER_QUESTIONS
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field

from core.knowledge import Hit, get_kb
from core.nudges import _extract_numbers, _number_in_summary

logger = logging.getLogger(__name__)

MIN_CONFIDENCE = 0.14          # below this the retriever is guessing -> say "not sure"
SCAM_RULE_THRESHOLD = 0.5      # scam.rules score at which we treat the text as a scam message

STARTER_QUESTIONS = [
    "What is a SIP and how do I start?",
    "Which tax regime should I choose?",
    "How do I build a credit score?",
    "Is it okay to pay only the minimum due on my credit card?",
    "Where should I keep my emergency fund?",
    "I just got my first job, what should I do with my salary?",
]


@dataclass
class Reply:
    text: str
    method: str                    # "rules" | "llm" | "guard"
    intent: str                    # knowledge | personal | scam | refuse_advice | refuse_injection |
                                   # smalltalk | unsure | warn_returns | safety
    sources: list[tuple[str, str]] = field(default_factory=list)   # (kb_id, title)
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------

_INJECTION = re.compile(
    r"ignore (all |your |the )?(previous|prior|above|earlier) (instructions|rules|prompt)|"
    r"disregard (your|the|all) (instructions|rules|guidelines)|reveal (your|the) (system )?prompt|"
    r"show (me )?(your|the) (system )?prompt|you are now (a|an|dan)|pretend (you are|to be)|"
    r"act as (a|an) (?!money|coach)|jailbreak|developer mode|bypass (your|the) (rules|safety)", re.I)

_SPECIFIC_PICK = re.compile(
    r"(which|what|best|top|good)\b.{0,40}\b(stocks?|shares?|mutual funds?|funds?|crypto|coins?|"
    r"bitcoin|etfs?|ipos?|penny stocks?|multibaggers?)\b.{0,30}\b(buy|invest|pick|choose|to buy|"
    r"should i)|"
    r"\b(tell|give|suggest|recommend)\b.{0,25}\b(a |me |some )?(stocks?|shares?|funds?|multibaggers?|"
    r"crypto|coins?)\b|"
    r"\b(multibagger|sure[- ]?shot|hot tip|insider tip)\b|"
    r"\b(will|is) (the )?(nifty|sensex|market|bitcoin|gold|stock market)\b.{0,30}\b(go up|go down|crash|"
    r"rise|fall|hit|reach|rally)|predict (the )?(nifty|sensex|market|bitcoin|stock)|"
    r"should i (buy|sell|invest in|put (my )?(money|savings) (in|into))\b.{0,30}\b(tcs|reliance|infosys|"
    r"adani|zomato|paytm|hdfc|sbi|tata|bitcoin|ethereum|dogecoin|nifty)\b|"
    r"\b(put|invest)\b.{0,20}\ball (my )?(savings|money)\b|"
    r"which\b.{0,25}\b(crypto|coin|stock|share|fund)s?\b.{0,25}\b(give|gives|make|makes|earn|return|10x|moon)",
    re.I)

_RETURN_BAIT = re.compile(
    r"guarantee[sd]?\b.{0,20}\b(return|profit|income)|\b(double|triple) (my|your|the) money|"
    r"(\d+\s?%\s?(per|a|every)?\s?(day|daily|week|weekly|month|monthly))|risk[- ]?free.{0,15}return|"
    r"(fixed|assured) (daily|weekly|monthly) (return|profit|income)", re.I)

_GREETING = re.compile(r"^\s*(hi+|hello+|hey+|hola|namaste|good (morning|afternoon|evening)|yo|sup)\b[\s!.,]*"
                       r"(artha|there|buddy|friend)?[\s!.,?]*$", re.I)
_THANKS = re.compile(r"^\s*(thanks?( you)?|thank u|thx|ty|cheers|great|awesome|got it|ok(ay)?|cool|nice)"
                     r"[\s!.,]*(artha)?[\s!.]*$", re.I)
_BYE = re.compile(r"^\s*(bye+|goodbye|see you|cya|good ?night)[\s!.]*$", re.I)
_META = re.compile(r"\b(who are you|what are you|what can you do|what do you do|are you (a |an )?(bot|ai|human|"
                   r"real|person|sebi|adviser|advisor|registered)|your name|how can you help|"
                   r"can you help me)\b", re.I)

_PERSONAL = re.compile(
    r"\b(did i|have i|am i (overspending|spending|saving)|can i afford|how much (did|have|do) i|"
    r"where (did|does) my|my (spending|expenses?|subscriptions?|savings rate|income|budget|transactions?|"
    r"top categor\w+|biggest expense))\b", re.I)
_PERSONAL_DATA_TOPIC = re.compile(
    r"\b(spend|spent|spending|expenses?|subscriptions?|savings? rate|income|budget|transactions?|"
    r"afford|swiggy|zomato|amazon|uber|netflix|food|shopping|rent|emi|cut back|left over|this month|"
    r"last month|phone|laptop)\b", re.I)

# Advice-seeking phrasing ("how much of my income SHOULD go to EMIs") is a general question,
# not a lookup in the user's own transactions.
_GENERAL_ADVICE = re.compile(r"\b(should|ideal|recommended|rule of thumb|how (does|do|to)|what is|"
                             r"what's a good|good (rate|ratio))\b", re.I)

_SECRET_SHARE = re.compile(
    r"\b(my )?(otp|pin|cvv|password|passcode)\b.{0,20}\b(is|are|:)\s*\d|"
    r"\b(share|give|send|tell)\b.{0,25}\b(otp|pin|cvv|password)\b", re.I)

_OFF_TOPIC = re.compile(r"\b(weather|cricket|movie|recipe|joke|poem|song|football|politics|election|"
                        r"homework|code|python|translate|girlfriend|boyfriend)\b", re.I)

_REGULATED = {"tax", "invest", "investing", "mutual-fund", "sip", "stocks", "equity", "f&o", "crypto",
              "elss", "nps", "ppf", "insurance", "loan", "income-tax", "derivatives"}


def _pick(options: list[str], seed: str) -> str:
    return options[int(hashlib.md5(seed.encode("utf-8")).hexdigest(), 16) % len(options)]


# ---------------------------------------------------------------------------
# Responses for guard intents
# ---------------------------------------------------------------------------

def _refuse_injection() -> Reply:
    return Reply("I'll stay in my lane — I'm Artha, a money coach, and I can't change my rules or share my "
                 "instructions. But I'm happy to help with budgeting, saving, tax basics, credit scores or "
                 "spotting scams. What would you like to know?", "guard", "refuse_injection")


def _refuse_specific_pick() -> Reply:
    kb = get_kb()
    src = [(d.id, d.title) for d in (kb.get("KB046"), kb.get("KB054")) if d]
    return Reply(
        "I can't tell you which stock, fund or coin to buy, or where the market is heading — nobody can do "
        "that reliably, and I'm not a SEBI-registered adviser. What I can do is help you decide *how* to "
        "choose: match each goal to a timeline, keep the risky part to money you won't need for 5+ years, "
        "prefer low-cost diversified index funds over single stocks, and check any adviser on sebi.gov.in "
        "before paying for advice. Want me to explain how asset allocation works?",
        "guard", "refuse_advice", src)


def _warn_returns() -> Reply:
    d = get_kb().get("KB046")
    return Reply(
        "Careful — no genuine investment can guarantee returns, and promises like a fixed daily/monthly "
        "profit or 'double your money' are classic signs of a Ponzi or investment scam. Don't send money or "
        "share OTPs, and check whether the person or platform is registered on sebi.gov.in. If you've "
        "already paid, call 1930 or report at cybercrime.gov.in straight away. Want me to walk through the "
        "red flags?", "guard", "warn_returns", [(d.id, d.title)] if d else [])


def _scam_reply(rules) -> Reply:
    cat = (rules.top_category or "scam").replace("_", " ")
    flags = "; ".join(sorted({m.name for m in rules.matches})[:3])
    return Reply(
        f"That message has the hallmarks of a scam ({cat}{': ' + flags if flags else ''}). Don't click any link, "
        "call back any number in it, or share OTPs, PINs or card details — real banks and agencies never ask "
        "for those. Paste it into the 🛡️ Scam Shield tab for a full check with a trust receipt, and if you "
        "already lost money, call 1930 or report at cybercrime.gov.in immediately.",
        "guard", "scam", [], min(1.0, rules.score))


def _smalltalk(message: str) -> Reply | None:
    if _GREETING.match(message):
        return Reply(_pick([
            "Hey! I'm Artha — your money coach. Ask me anything from 'what is a SIP?' to 'how do I read my "
            "salary slip?', or load your bank SMS in Smart Budget and I'll help with your own numbers.",
            "Hi there! Happy to help with budgeting, saving, tax basics, credit scores or scam checks. "
            "What's on your mind?"], message), "rules", "smalltalk")
    if _THANKS.match(message):
        return Reply(_pick(["Anytime! Want to look at anything else — savings goals, tax, or a suspicious message?",
                            "Glad that helped. Ask away whenever you're stuck on a money question."], message),
                     "rules", "smalltalk")
    if _BYE.match(message):
        return Reply("Take care! Pay yourself first, and come back any time.", "rules", "smalltalk")
    return None


# ---------------------------------------------------------------------------
# Knowledge answers
# ---------------------------------------------------------------------------

def _history_text(history: list[dict] | None, n: int = 6) -> str:
    if not history:
        return "(no earlier messages)"
    return "\n".join(f"{m['role'].upper()}: {m['content'][:400]}" for m in history[-n:])


def _contextual_query(message: str, history: list[dict] | None) -> str:
    """Short follow-ups ('and for freshers?') borrow the previous user question for retrieval."""
    words = re.findall(r"[a-z0-9&]+", message.lower())
    if history and len(words) <= 4:
        prev = [m["content"] for m in history if m["role"] == "user"]
        if prev:
            return f"{prev[-1]} {message}"
    return message


def _followups(hits: list[Hit], used_id: str) -> str:
    others = [h.doc.title.split(" — ")[0] for h in hits if h.doc.id != used_id and h.score >= MIN_CONFIDENCE][:2]
    return ("Related: " + "; ".join(others) + ".") if others else ""


def _offline_answer(message: str, query: str, hits: list[Hit]) -> Reply:
    top = hits[0]
    body = get_kb().best_sentences(top.doc, query)
    opener = _pick(["Good question.", "Happy to explain.", "Here's the short version.", "Sure —"], message)
    parts = [f"{opener} {body}"]
    if "book" in top.doc.topics:
        parts.append("That's the author's perspective — a useful lens, not a rule. Check that the numbers and "
                     "products fit India before acting on it.")
    elif set(top.doc.topics) & _REGULATED:
        parts.append("This is general education, not personalised advice, and rates and limits change — "
                     "confirm current figures on the official site before acting.")
    rel = _followups(hits, top.doc.id)
    if rel:
        parts.append(rel)
    return Reply("\n\n".join(parts), "rules", "knowledge", [(top.doc.id, top.doc.title)], top.score)


def _llm_answer(message: str, history, hits: list[Hit], adapter) -> Reply | None:
    from llm.prompts import ADVISOR_PROMPT_V1
    from llm.schemas import AssistantAnswerLLM

    good = [h for h in hits[:3] if h.score >= MIN_CONFIDENCE]
    if not good:
        return None
    passages = "\n\n".join(f"[{h.doc.id}] {h.doc.title}\n{h.doc.text}" for h in good)
    prompt = ADVISOR_PROMPT_V1.format(history=_history_text(history), passages=passages,
                                      question=message.strip()[:600])
    try:
        out: AssistantAnswerLLM = adapter.generate(prompt=prompt, response_schema=AssistantAnswerLLM,
                                                   temperature=0.3)
    except Exception as exc:
        logger.warning("Advisor LLM failed (%s) — using offline answer.", exc)
        return None
    allowed = (_extract_numbers(passages) | _extract_numbers(message)
               | _extract_numbers(_history_text(history)) | {1930.0})
    bad = {n for n in _extract_numbers(out.answer) if n > 1 and not _number_in_summary(n, allowed)}
    if bad:
        logger.warning("Advisor answer had unbacked numbers %s — using offline answer.", bad)
        return None
    return Reply(out.answer.strip(), "llm", "knowledge", [(h.doc.id, h.doc.title) for h in good[:2]],
                 hits[0].score)


def _unsure(message: str) -> Reply:
    lead = ("That's outside what I do — I stick to money topics." if _OFF_TOPIC.search(message)
            else "I'm not confident I have a reliable answer to that.")
    return Reply(f"{lead} I can help with budgeting, saving and investing basics, tax, credit scores, "
                 "loans, insurance and scam checks. For rules that change often, rbi.org.in, sebi.gov.in and "
                 "incometax.gov.in are the sources to trust. Try one of the starter questions, or rephrase "
                 "and I'll have another go.", "rules", "unsure")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def respond(message: str, history: list[dict] | None = None, summary=None, txns=None,
            subscriptions=None, adapter=None) -> Reply:
    message = (message or "").strip()
    if not message:
        return Reply("Ask me anything about money — saving, SIPs, tax, credit scores, or a message you're "
                     "not sure about.", "rules", "smalltalk")

    if _INJECTION.search(message):
        return _refuse_injection()

    # Scam-looking text outranks everything except injection (a question *about* scams goes to the KB).
    from scam.rules import run_rules
    rules = run_rules(message)
    is_question = bool(re.match(r"\s*(what|how|why|is|are|can|should|explain|tell|do|does|did|will|would|could|when|who)\b", message, re.I)) \
        and len(message) < 140
    if rules.score >= SCAM_RULE_THRESHOLD and not is_question:
        return _scam_reply(rules)

    if _SECRET_SHARE.search(message):
        d = get_kb().get("KB001")
        return Reply("Please don't share that — not with me, and not with anyone who calls, texts or messages "
                     "you. OTPs, PINs, CVVs and passwords are for you alone; real banks, UPI apps and "
                     "government agencies never ask for them. If someone is pressuring you for it, hang up, "
                     "call your bank on its official number, and report it on 1930 or cybercrime.gov.in.",
                     "guard", "safety", [(d.id, d.title)] if d else [])
    if _RETURN_BAIT.search(message):
        return _warn_returns()
    if _SPECIFIC_PICK.search(message):
        return _refuse_specific_pick()

    small = _smalltalk(message)
    if small:
        return small

    if (summary is not None and _PERSONAL.search(message) and _PERSONAL_DATA_TOPIC.search(message)
            and not _GENERAL_ADVICE.search(message)):
        from core.assistant import answer_question
        ans = answer_question(message, summary, txns or [], adapter=adapter, subscriptions=subscriptions)
        return Reply(ans.text, ans.method, "personal", [], 1.0)

    if (summary is None and _PERSONAL.search(message) and _PERSONAL_DATA_TOPIC.search(message)
            and not _GENERAL_ADVICE.search(message)):
        return Reply("I can answer that from your own numbers — load your bank SMS or statement in the "
                     "💰 Smart Budget tab first and ask me again. Meanwhile, a good rule of thumb: keep "
                     "'wants' to about 30% of take-home pay, sleep on any non-essential purchase for 24 "
                     "hours, and don't dip into your emergency fund for it.", "rules", "personal")

    from core.calculator import answer_calculation
    calc = answer_calculation(message)
    if calc:
        return Reply(calc, "rules", "calculator", [], 1.0)

    if _META.search(message) and not _OFF_TOPIC.search(message):
        d = get_kb().get("KB066")
        return Reply(d.text, "rules", "knowledge", [(d.id, d.title)], 1.0)

    kb = get_kb()
    query = message
    hits = kb.search(query, k=4)
    # Short follow-ups ("and for freshers?") borrow the previous question — only if the message alone
    # is weak, and never for off-topic chatter.
    if (not hits or hits[0].score < 0.25) and not _OFF_TOPIC.search(message):
        ctx_query = _contextual_query(message, history)
        if ctx_query != message:
            ctx_hits = kb.search(ctx_query, k=4)
            if ctx_hits and ctx_hits[0].score >= MIN_CONFIDENCE:
                query, hits = ctx_query, ctx_hits
    if not hits or hits[0].score < MIN_CONFIDENCE or (_OFF_TOPIC.search(message) and hits[0].score < 0.3):
        return _unsure(message)

    if adapter is not None:
        llm = _llm_answer(message, history, hits, adapter)
        if llm is not None:
            return llm
    return _offline_answer(message, query, hits)
