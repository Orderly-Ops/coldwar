"""Produce a shareable, content-free campaign signature from a message.

The fingerprint is a hash of *structural* features — never the message body or
subject text. Two emails from the same cold campaign (same ESP, same sender
domain, same shape) hash to the same value, so a future community feed could
match them across installs without exposing anyone's mail.

V1: extract and store only. Do NOT network or share.
"""

import hashlib
import re

from coldwar.models import Message

# ESP / outreach-tool tokens we look for in headers to identify the sender's
# sending infrastructure (NOT the content).
ESP_TOKENS = [
    "instantly",
    "smartlead",
    "apollo",
    "lemlist",
    "outreach",
    "mailshake",
    "reply.io",
    "woodpecker",
    "salesloft",
    "sendgrid",
    "mailgun",
    "amazonses",
]

_URL_RE = re.compile(r"https?://([^/\s]+)", re.IGNORECASE)


def _esp_fingerprint(headers: dict) -> str:
    blob = " ".join(str(v) for v in headers.values()).lower()
    found = sorted({t for t in ESP_TOKENS if t in blob})
    return ",".join(found)


def _structural_features(message: Message) -> dict:
    """Content-free shape features. Lengths and counts, never the text itself."""
    body = message.body_text or ""
    link_hosts = sorted({h.lower() for h in _URL_RE.findall(body)})
    return {
        # Bucketed lengths so near-identical sends collide but unrelated ones don't.
        "subject_len_bucket": len(message.subject or "") // 10,
        "body_len_bucket": len(body) // 100,
        "link_host_count": len(link_hosts),
        # The set of link hosts is structural (where it points), not what it says.
        "link_hosts": link_hosts,
    }


def fingerprint(message: Message) -> str:
    """Return a stable hex digest identifying the message's campaign shape."""
    feats = _structural_features(message)
    parts = [
        message.sender_domain.lower(),
        _esp_fingerprint(message.headers),
        str(feats["subject_len_bucket"]),
        str(feats["body_len_bucket"]),
        str(feats["link_host_count"]),
        "|".join(feats["link_hosts"]),
    ]
    raw = "::".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]
