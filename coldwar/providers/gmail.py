"""Gmail provider — fully implemented.

Quarantine = apply a "Cold" label and remove the INBOX label (non-destructive;
the mail still exists, just not in the inbox). list_unquarantined = messages the
user moved back to the inbox after we quarantined them = "not cold" feedback.

Auth is the OAuth device-code flow. We talk to the Gmail REST API with `requests`
to keep the dependency surface small and the calls easy to read.

Providers are created by the registry with no constructor args, then `configure()`
is called to attach the account id, storage, and OAuth client credentials.
"""

import base64
import os
import time
from email.utils import parseaddr
from typing import Iterable

import requests

from coldwar.auth import device_flow
from coldwar.models import Message
from coldwar.providers.base import BaseProvider
from coldwar.providers.registry import register

DEVICE_ENDPOINT = "https://oauth2.googleapis.com/device/code"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
API = "https://gmail.googleapis.com/gmail/v1/users/me"

# We need to read messages and modify labels (not delete).
SCOPES = "https://www.googleapis.com/auth/gmail.modify"

COLD_LABEL = "Cold"


@register
class GmailProvider(BaseProvider):
    name = "gmail"

    def __init__(self):
        self.account = None
        self.store = None
        self.client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
        self.client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
        self._pending_device_code = None  # set between begin/poll device auth
        self._cold_label_id = None

    def configure(self, account: str, store) -> "GmailProvider":
        """Attach the runtime context the registry cannot pass in __init__."""
        self.account = account
        self.store = store
        return self

    # --- OAuth: device-code flow -----------------------------------------

    def begin_device_auth(self) -> dict:
        resp = device_flow.begin_device_authorization(
            device_endpoint=DEVICE_ENDPOINT,
            client_id=self.client_id,
            scope=SCOPES,
        )
        self._pending_device_code = resp["device_code"]
        return {
            "user_code": resp["user_code"],
            "verification_url": resp.get("verification_url", resp.get("verification_uri")),
            "interval": resp.get("interval", 5),
            "expires_in": resp.get("expires_in", 600),
        }

    def poll_device_auth(self) -> bool:
        """Poll once. Returns True (and persists tokens) when the user consents."""
        if not self._pending_device_code:
            raise RuntimeError("begin_device_auth() must be called first")
        tokens = device_flow.poll_token(
            token_endpoint=TOKEN_ENDPOINT,
            client_id=self.client_id,
            device_code=self._pending_device_code,
            client_secret=self.client_secret,
        )
        if tokens is None:
            return False
        # Record absolute expiry so we know when to refresh.
        tokens["expires_at"] = time.time() + tokens.get("expires_in", 3600) - 60
        self.store.save_tokens(self.account, self.name, tokens)
        self._pending_device_code = None
        return True

    # --- Access-token plumbing -------------------------------------------

    def _access_token(self) -> str:
        tokens = self.store.load_tokens(self.account)
        if not tokens:
            raise RuntimeError(f"account {self.account!r} is not connected")
        if tokens.get("expires_at", 0) < time.time():
            refreshed = device_flow.refresh_access_token(
                token_endpoint=TOKEN_ENDPOINT,
                client_id=self.client_id,
                refresh_token=tokens["refresh_token"],
                client_secret=self.client_secret,
            )
            tokens["access_token"] = refreshed["access_token"]
            tokens["expires_at"] = time.time() + refreshed.get("expires_in", 3600) - 60
            self.store.save_tokens(self.account, self.name, tokens)
        return tokens["access_token"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._access_token()}"}

    def _get(self, path: str, **params) -> dict:
        r = requests.get(f"{API}{path}", headers=self._headers(), params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, json: dict) -> dict:
        r = requests.post(f"{API}{path}", headers=self._headers(), json=json, timeout=30)
        r.raise_for_status()
        return r.json() if r.text else {}

    # --- Label management -------------------------------------------------

    def _ensure_cold_label(self) -> str:
        """Return the id of the "Cold" label, creating it if missing."""
        if self._cold_label_id:
            return self._cold_label_id
        labels = self._get("/labels").get("labels", [])
        for lab in labels:
            if lab["name"] == COLD_LABEL:
                self._cold_label_id = lab["id"]
                return self._cold_label_id
        created = self._post(
            "/labels",
            {
                "name": COLD_LABEL,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        )
        self._cold_label_id = created["id"]
        return self._cold_label_id

    # --- Fetch + normalize ------------------------------------------------

    def fetch_new(self, since) -> Iterable[Message]:
        """Yield new inbox messages received after `since` (epoch seconds)."""
        query = "in:inbox"
        if since:
            query += f" after:{int(since)}"
        listing = self._get("/messages", q=query, maxResults=50)
        for stub in listing.get("messages", []):
            raw = self._get(f"/messages/{stub['id']}", format="full")
            yield self._to_message(raw)

    def _to_message(self, raw: dict) -> Message:
        headers = {
            h["name"]: h["value"]
            for h in raw.get("payload", {}).get("headers", [])
        }
        sender = parseaddr(headers.get("From", ""))[1]
        domain = sender.split("@", 1)[1].lower() if "@" in sender else ""
        received_at = int(raw.get("internalDate", "0")) / 1000.0

        # First contact is a storage question, answered here so classifiers get a
        # ready-to-use Message. Note the sender after asking, so the *next* mail
        # from them is no longer first contact.
        first_contact = True
        if self.store is not None:
            first_contact = self.store.is_first_contact(self.account, sender)
            self.store.note_sender(self.account, sender)

        return Message(
            id=raw["id"],
            sender=sender,
            sender_domain=domain,
            subject=headers.get("Subject", ""),
            body_text=_extract_body_text(raw.get("payload", {})),
            headers=headers,
            is_first_contact=first_contact,
            received_at=received_at,
        )

    # --- Quarantine + feedback -------------------------------------------

    def quarantine(self, message: Message) -> None:
        """Add the Cold label and drop the message out of the inbox."""
        cold_id = self._ensure_cold_label()
        self._post(
            f"/messages/{message.id}/modify",
            {"addLabelIds": [cold_id], "removeLabelIds": ["INBOX"]},
        )

    def list_unquarantined(self) -> Iterable[Message]:
        """Messages we labeled Cold that the user moved back to the inbox.

        If a message still carries the Cold label but is back in INBOX, the user
        dragged it out — treat that as "not cold". We strip the Cold label so we
        don't keep re-reporting it.
        """
        cold_id = self._ensure_cold_label()
        listing = self._get("/messages", q="in:inbox", labelIds=cold_id, maxResults=50)
        for stub in listing.get("messages", []):
            raw = self._get(f"/messages/{stub['id']}", format="full")
            msg = self._to_message(raw)
            # Clean up the label so this is a one-time feedback signal.
            self._post(
                f"/messages/{msg.id}/modify",
                {"removeLabelIds": [cold_id]},
            )
            yield msg


def _extract_body_text(payload: dict) -> str:
    """Walk the MIME tree and return the best-effort plain-text body."""
    mime = payload.get("mimeType", "")
    body = payload.get("body", {})

    if mime == "text/plain" and body.get("data"):
        return _b64url(body["data"])

    # Multipart: prefer text/plain, fall back to recursing into parts.
    if mime.startswith("multipart/"):
        for part in payload.get("parts", []):
            text = _extract_body_text(part)
            if text:
                return text

    # Last resort: a top-level body with data (e.g. text/html), decoded raw.
    if body.get("data"):
        return _b64url(body["data"])
    return ""


def _b64url(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", "replace")
