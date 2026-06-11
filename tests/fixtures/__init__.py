"""Sample emails used by the tests, as normalized Message objects.

`COLD_*` should be flagged by the heuristic classifier; `WANTED_*` should not.
Keep these realistic so contributors can sanity-check new detectors against them.
"""

from coldwar.models import Message

# --- COLD: classic cold outreach, first contact ---------------------------

COLD_SALES_KEYWORDS = Message(
    id="cold-1",
    sender="rep@growthscale.io",
    sender_domain="growthscale.io",
    subject="Quick question about Orderly Ops",
    body_text=(
        "Hi there,\n\nI was reaching out because I noticed that you run a growing "
        "team. We help companies increase your pipeline by 30%.\n\n"
        "Do you have 15 minutes this week to hop on a call?\n\nBest,\nJordan"
    ),
    headers={"From": "Jordan <rep@growthscale.io>"},
    is_first_contact=True,
)

COLD_BOOKING_LINK = Message(
    id="cold-2",
    sender="sales@pipelinepro.com",
    sender_domain="pipelinepro.com",
    subject="Worth a chat?",
    body_text=(
        "Hey, I'd love to connect and show you what we built. "
        "Grab a time that works: https://calendly.com/pipelinepro/demo"
    ),
    headers={"From": "Sam <sales@pipelinepro.com>"},
    is_first_contact=True,
)

COLD_OUTREACH_TOOL = Message(
    id="cold-3",
    sender="hello@coldco.com",
    sender_domain="coldco.com",
    subject="Reaching out",
    body_text="Just reaching out to introduce our platform. Worth a chat?",
    headers={
        "From": "Alex <hello@coldco.com>",
        "X-Mailer": "Instantly.ai",
        "List-Unsubscribe": "<https://smartlead.ai/unsubscribe/abc>",
    },
    is_first_contact=True,
)

# --- WANTED: legitimate mail that must NOT be flagged ----------------------

WANTED_KNOWN_SENDER = Message(
    id="wanted-1",
    # Same cold-looking words, but NOT first contact -> should be spared.
    sender="jamie@knownvendor.com",
    sender_domain="knownvendor.com",
    subject="Re: 15 minutes to review the invoice?",
    body_text="Reaching out again with the numbers we discussed. Book a demo anytime.",
    headers={"From": "Jamie <jamie@knownvendor.com>"},
    is_first_contact=False,
)

WANTED_FIRST_CONTACT_NO_SIGNALS = Message(
    id="wanted-2",
    sender="customer@realbusiness.com",
    sender_domain="realbusiness.com",
    subject="Order #4821 shipping question",
    body_text=(
        "Hi, my order from last week hasn't arrived yet. Could you check the "
        "tracking? Order number is 4821. Thanks!"
    ),
    headers={"From": "Pat <customer@realbusiness.com>"},
    is_first_contact=True,
)

COLD = [COLD_SALES_KEYWORDS, COLD_BOOKING_LINK, COLD_OUTREACH_TOOL]
WANTED = [WANTED_KNOWN_SENDER, WANTED_FIRST_CONTACT_NO_SIGNALS]
