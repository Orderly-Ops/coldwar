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
]


@register
class HeuristicClassifier(BaseClassifier):
    name = "heuristic"

    def classify(self, message: Message) -> Verdict:
        reasons: list[str] = []

        # Gate everything on first contact — replies and known senders are spared.
        if not message.is_first_contact:
            return Verdict(is_cold=False, score=0.0, reasons=[])

        haystack = f"{message.subject}\n{message.body_text}".lower()

        # Signal 1: sales-intent keywords.
        hit_keywords = [kw for kw in SALES_KEYWORDS if kw in haystack]
        if hit_keywords:
            preview = ", ".join(hit_keywords[:3])
            reasons.append(f"sales-intent language ({preview})")

        # Signal 2: a calendar / booking link.
        hit_links = [host for host in BOOKING_LINK_HOSTS if host in haystack]
        if hit_links:
            reasons.append(f"booking link ({hit_links[0]})")

        # Signal 3: outreach-tool fingerprints anywhere in the headers.
        header_blob = " ".join(str(v) for v in message.headers.values()).lower()
        hit_tools = [t for t in OUTREACH_TOOL_FINGERPRINTS if t in header_blob]
        if hit_tools:
            reasons.append(f"outreach-tool fingerprint ({hit_tools[0]})")

        # Decision: first contact + at least one cold signal.
        is_cold = bool(reasons)

        # Confidence grows with the number of independent signals that fired.
        # 1 signal -> 0.5, 2 -> 0.75, 3 -> ~0.83 (capped well under certainty).
        score = round(1 - 0.5 ** len(reasons), 2) if reasons else 0.0

        if is_cold:
            reasons.insert(0, "first contact from this sender")

        return Verdict(is_cold=is_cold, score=score, reasons=reasons)
