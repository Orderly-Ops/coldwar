"""The normalization layer.

Classifiers must never see raw Gmail or Graph JSON. Every email — regardless of
provider — funnels through this one shape before a classifier ever touches it.
That is what lets a detector written for Gmail also work for Outlook unchanged.
"""

from dataclasses import dataclass, field


@dataclass
class Message:
    id: str                          # provider-native id
    sender: str
    sender_domain: str
    subject: str
    body_text: str
    headers: dict = field(default_factory=dict)
    is_first_contact: bool = False   # have we ever seen this sender before?
    received_at: float = 0.0
