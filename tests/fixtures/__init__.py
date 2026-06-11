"""Sample emails used by the tests, as normalized Message objects.

These encode the heuristic's weighted model (see coldwar/classifiers/heuristic.py):

  COLD       — strong enough to quarantine:
                 * outreach-tool fingerprint (near-certain), or
                 * booking link AND sales-intent language (the classic shape).
  BORDERLINE — a single weak signal that should NOT be quarantined on its own
                 (a booking link alone, or sales keywords alone — an internal
                 email pitching a meeting trips these too).
  WANTED     — legitimate mail: known sender, or no signals at all.

Keep these realistic so contributors can sanity-check new detectors against them.
"""

from coldwar.models import Message

# --- COLD: should be quarantined ------------------------------------------

# Strong signal alone: an outreach automation tool in the headers. No booking
# link, no sales keywords — the fingerprint by itself is enough.
COLD_OUTREACH_TOOL = Message(
    id="cold-tool",
    sender="hello@coldco.com",
    sender_domain="coldco.com",
    subject="Following up",
    body_text="Wanted to introduce our platform — let me know if it's useful.",
    headers={
        "From": "Alex <hello@coldco.com>",
        "X-Mailer": "Instantly.ai",
        "List-Unsubscribe": "<https://smartlead.ai/unsubscribe/abc>",
    },
    is_first_contact=True,
)

# Two weak signals together: a booking link AND sales-intent language. Neither
# would be enough alone, but the pair is the textbook cold-sales pattern.
COLD_BOOKING_AND_KEYWORDS = Message(
    id="cold-booking-kw",
    sender="sales@pipelinepro.com",
    sender_domain="pipelinepro.com",
    subject="Quick question",
    body_text=(
        "I came across your site and would love to connect. "
        "Grab a time that works: https://calendly.com/pipelinepro/demo"
    ),
    headers={"From": "Sam <sales@pipelinepro.com>"},
    is_first_contact=True,
)

# --- BORDERLINE: a single weak signal — must NOT be flagged ----------------

# Sales-intent keywords but no booking link and no tool fingerprint.
BORDERLINE_KEYWORDS_ONLY = Message(
    id="borderline-kw",
    sender="rep@growthscale.io",
    sender_domain="growthscale.io",
    subject="Quick question about your team",
    body_text=(
        "Reaching out because I noticed that you might want to grow your "
        "pipeline. Worth a chat?"
    ),
    headers={"From": "Jordan <rep@growthscale.io>"},
    is_first_contact=True,
)

# A booking link but no sales-intent language — e.g. a colleague sending a
# scheduling link for a 1:1. First contact, but not cold.
BORDERLINE_BOOKING_ONLY = Message(
    id="borderline-booking",
    sender="dana@partnerorg.com",
    sender_domain="partnerorg.com",
    subject="Link for our sync",
    body_text="Here's the link to schedule our sync: https://calendly.com/dana/30min",
    headers={"From": "Dana <dana@partnerorg.com>"},
    is_first_contact=True,
)

# --- WANTED: legitimate mail that must NOT be flagged ----------------------

# Same cold-looking words AND a booking link, but NOT first contact -> spared.
WANTED_KNOWN_SENDER = Message(
    id="wanted-1",
    sender="jamie@knownvendor.com",
    sender_domain="knownvendor.com",
    subject="Re: 15 minutes to review the invoice?",
    body_text=(
        "Reaching out again with the numbers we discussed. "
        "Book time here: https://calendly.com/jamie/review"
    ),
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

COLD = [COLD_OUTREACH_TOOL, COLD_BOOKING_AND_KEYWORDS]
BORDERLINE = [BORDERLINE_KEYWORDS_ONLY, BORDERLINE_BOOKING_ONLY]
WANTED = [WANTED_KNOWN_SENDER, WANTED_FIRST_CONTACT_NO_SIGNALS]
