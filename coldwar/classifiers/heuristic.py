"""The naive default detector — dumb but non-trivial, so Cold War flags
something useful out of the box.

A message is treated as cold when it is *first contact* AND at least one cold
signal fires: sales-intent phrasing, a calendar/booking link, or an outreach-tool
fingerprint in the headers. Each fired signal is returned as a human-readable
reason so the dashboard can show *why* a message was quarantined.
"""

import re

from coldwar.classifiers.base import BaseClassifier, Verdict
from coldwar.classifiers.registry import register
from coldwar.models import Message

# Sales-intent phrases common in cold outreach. Lowercased; matched as substrings.
SALES_KEYWORDS = [
    "quick question",
    "15 minutes",
    "reaching out",
    "increase your",
    "book a demo",
    "hop on a call",
    "jump on a call",
    "circle back",
    "touch base",
    "free trial",
    "grow your",
    "boost your",
    "drive more",
    "i came across",
    "noticed that you",
    "would love to connect",
    "worth a chat",
]

# Calendar / booking link hosts used by outreach reps.
BOOKING_LINK_HOSTS = [
    "calendly.com",
    "meetings.hubspot.com",
    "savvycal.com",
    "cal.com",
    "chilipiper.com",
    "you.can.book.me",
    "calendarhippo",
]

# Outreach automation tools leave detectable traces in headers. We look across all
# header values (e.g. X-Mailer, List-Unsubscribe, Message-ID domains, custom
# X-* headers these tools inject).
OUTREACH_TOOL_FINGERPRINTS = [
    "instantly",
    "smartlead",
    "apollo.io",
    "apollo",
    "lemlist",
    "outreach.io",
    "mailshake",
    "reply.io",
    "woodpecker",
    "salesloft",
    "sparkle.io",
    "thriwin.io",
]

# Not every signal means the same thing, so we score them and threshold the sum
# instead of flagging the instant anything matches:
#
#   - An outreach-tool fingerprint is near-certain on its own (real reps don't
#     send through Instantly/Smartlead/Apollo).
#   - A booking link OR sales-intent language alone is weak — an internal email
#     pitching a meeting trips these too. Either one alone stays under threshold.
#   - A booking link AND sales-intent language together is the classic cold-sales
#     shape, so the pair clears the bar.
#
# Tune these freely; the tests in tests/test_heuristic.py pin the intended
# behavior (tool => cold, booking+keywords => cold, either alone => not cold).
WEIGHT_OUTREACH_TOOL = 0.8
WEIGHT_BOOKING_LINK = 0.35
WEIGHT_SALES_KEYWORDS = 0.35

# Score at or above this is "cold". 0.6 lets the tool fingerprint (0.8) and the
# booking+keywords pair (0.70) through, while either weak signal alone (0.35)
# falls short.
COLD_THRESHOLD = 0.6


@register
class HeuristicClassifier(BaseClassifier):
    name = "heuristic"

    def classify(self, message: Message) -> Verdict:
        reasons: list[str] = []
        score = 0.0

        # Gate everything on first contact — replies and known senders are spared.
        if not message.is_first_contact:
            return Verdict(is_cold=False, score=0.0, reasons=[])

        haystack = f"{message.subject}\n{message.body_text}".lower()

        # Signal 1: sales-intent keywords (weak — internal pitches use these too).
        hit_keywords = [kw for kw in SALES_KEYWORDS if kw in haystack]
        if hit_keywords:
            score += WEIGHT_SALES_KEYWORDS
            preview = ", ".join(hit_keywords[:3])
            reasons.append(f"sales-intent language ({preview})")

        # Signal 2: a calendar / booking link (weak on its own).
        hit_links = [host for host in BOOKING_LINK_HOSTS if host in haystack]
        if hit_links:
            score += WEIGHT_BOOKING_LINK
            reasons.append(f"booking link ({hit_links[0]})")

        # Signal 3: outreach-tool fingerprints in the headers (near-certain).
        header_blob = " ".join(str(v) for v in message.headers.values()).lower()
        hit_tools = [t for t in OUTREACH_TOOL_FINGERPRINTS if t in header_blob]
        if hit_tools:
            score += WEIGHT_OUTREACH_TOOL
            reasons.append(f"outreach-tool fingerprint ({hit_tools[0]})")

        # Decision: cold only when the weighted evidence clears the threshold, so
        # a single weak signal (booking link OR keywords alone) is NOT cold.
        score = round(min(score, 1.0), 2)
        is_cold = score >= COLD_THRESHOLD

        if is_cold:
            reasons.insert(0, "first contact from this sender")

        return Verdict(is_cold=is_cold, score=score, reasons=reasons)
