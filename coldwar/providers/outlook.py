"""Outlook / Microsoft Graph provider — WORKING STUB.

The device-code flow is wired so you can authenticate today. The mail operations
(fetch/quarantine/feedback) are outlined with clear TODOs against the Graph API
so a contributor can finish them without reverse-engineering the design.

Quarantine on Outlook = MOVE the message to a "Cold" mail folder (create it if
missing). list_unquarantined = messages moved back to the Inbox. This is the
folder analogue of Gmail's label dance — and the worker never sees the
difference, because both speak the BaseProvider contract.
"""

import os
import time
from typing import Iterable

import requests

from coldwar.auth import device_flow
from coldwar.models import Message
from coldwar.providers.base import BaseProvider
from coldwar.providers.registry import register

TENANT = os.environ.get("MS_TENANT_ID", "common")
DEVICE_ENDPOINT = f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/devicecode"
TOKEN_ENDPOINT = f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/token"
GRAPH = "https://graph.microsoft.com/v1.0/me"

# Read mail + move it between folders. offline_access yields a refresh token.
SCOPES = "offline_access Mail.ReadWrite"

COLD_FOLDER = "Cold"


@register
class OutlookProvider(BaseProvider):
    name = "outlook"

    def __init__(self):
        self.account = None
        self.store = None
        self.client_id = os.environ.get("MS_CLIENT_ID", "")
        self._pending_device_code = None
        self._cold_folder_id = None

    def configure(self, account: str, store) -> "OutlookProvider":
        self.account = account
        self.store = store
        return self

    # --- OAuth: device-code flow (WIRED) ---------------------------------

    def begin_device_auth(self) -> dict:
        resp = device_flow.begin_device_authorization(
            device_endpoint=DEVICE_ENDPOINT,
            client_id=self.client_id,
            scope=SCOPES,
        )
        self._pending_device_code = resp["device_code"]
        return {
            "user_code": resp["user_code"],
            "verification_url": resp.get("verification_uri", resp.get("verification_url")),
            "interval": resp.get("interval", 5),
            "expires_in": resp.get("expires_in", 900),
        }

    def poll_device_auth(self) -> bool:
        if not self._pending_device_code:
            raise RuntimeError("begin_device_auth() must be called first")
        # Microsoft's device endpoint does not use a client secret for public
        # clients — pass client_id only.
        tokens = device_flow.poll_token(
            token_endpoint=TOKEN_ENDPOINT,
            client_id=self.client_id,
            device_code=self._pending_device_code,
        )
        if tokens is None:
            return False
        tokens["expires_at"] = time.time() + tokens.get("expires_in", 3600) - 60
        self.store.save_tokens(self.account, self.name, tokens)
        self._pending_device_code = None
        return True

    def _access_token(self) -> str:
        tokens = self.store.load_tokens(self.account)
        if not tokens:
            raise RuntimeError(f"account {self.account!r} is not connected")
        if tokens.get("expires_at", 0) < time.time():
            refreshed = device_flow.refresh_access_token(
                token_endpoint=TOKEN_ENDPOINT,
                client_id=self.client_id,
                refresh_token=tokens["refresh_token"],
            )
            tokens.update(refreshed)
            tokens["expires_at"] = time.time() + refreshed.get("expires_in", 3600) - 60
            self.store.save_tokens(self.account, self.name, tokens)
        return tokens["access_token"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._access_token()}"}

    # --- Mail operations (TODO: implement against Graph) ------------------

    def fetch_new(self, since) -> Iterable[Message]:
        # TODO: GET {GRAPH}/mailFolders/inbox/messages
        #       ?$filter=receivedDateTime gt {iso(since)}&$top=50&$orderby=receivedDateTime
        #   For each Graph message, normalize into a Message:
        #     - sender    -> message["from"]["emailAddress"]["address"]
        #     - subject   -> message["subject"]
        #     - body_text -> message["body"]["content"] (strip HTML if needed)
        #     - headers   -> message["internetMessageHeaders"] (list -> dict)
        #   Set is_first_contact via self.store.is_first_contact(...) then
        #   self.store.note_sender(...), exactly like gmail.py does.
        return []

    def _ensure_cold_folder(self) -> str:
        # TODO: GET {GRAPH}/mailFolders?$filter=displayName eq 'Cold'
        #   If absent: POST {GRAPH}/mailFolders {"displayName": "Cold"}
        #   Cache and return the folder id.
        raise NotImplementedError("Outlook _ensure_cold_folder is a stub")

    def quarantine(self, message: Message) -> None:
        # TODO: folder_id = self._ensure_cold_folder()
        #   POST {GRAPH}/messages/{message.id}/move {"destinationId": folder_id}
        #   This MOVES (non-destructive) — it never deletes.
        raise NotImplementedError("Outlook quarantine is a stub")

    def list_unquarantined(self) -> Iterable[Message]:
        # TODO: Detect messages that were in the Cold folder but are now back in
        #   the Inbox (user dragged them out) and yield them as "not cold"
        #   feedback. One approach: track quarantined ids in storage and check
        #   their current parentFolderId via Graph.
        return []
