#!/usr/bin/env python3
"""Mint a Gmail OAuth token for live testing and store it for the worker.

Why this exists: Google's OAuth *device-code* flow does NOT support Gmail
scopes (it allows only email/openid/profile + a couple of Drive/YouTube scopes).
`gmail.modify` — which Cold War needs to label mail and drop it from the inbox —
can only be granted through the installed-app / authorization-code flow. This
script runs that flow once (a browser window opens for consent) and writes the
resulting token into the same SQLite store the worker reads from, in the exact
shape coldwar/providers/gmail.py expects.

Prereqs (see README / the Cloud Console steps):
  - Gmail API enabled on your Google Cloud project.
  - An OAuth client of type "Desktop app".
  - GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET set (e.g. in .env).

Usage:
  python scripts/get_gmail_token.py --account my-gmail

`--account` must match an account id in config.yaml.
"""

import argparse
import os
import sys
import time

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # noqa: BLE001 — dotenv is optional
    pass

from coldwar.config import load_config
from coldwar.providers.gmail import SCOPES
from coldwar.storage import Storage

# Loopback redirect requires the same scope the provider uses, so the refresh
# token we save can mint access tokens with the right permissions.
GMAIL_SCOPES = [SCOPES]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", default="my-gmail", help="account id from config.yaml")
    args = parser.parse_args()

    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("ERROR: set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET (e.g. in .env)", file=sys.stderr)
        return 1

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("ERROR: pip install -r requirements.txt (need google-auth-oauthlib)", file=sys.stderr)
        return 1

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, scopes=GMAIL_SCOPES)
    # access_type=offline + prompt=consent guarantees a refresh_token comes back.
    creds = flow.run_local_server(
        port=0, access_type="offline", prompt="consent", open_browser=True
    )

    if not creds.refresh_token:
        print("ERROR: no refresh_token returned. Revoke prior grants and retry.", file=sys.stderr)
        return 1

    # Shape this exactly like coldwar/providers/gmail.py reads it.
    expires_in = int((creds.expiry.timestamp() - time.time())) if creds.expiry else 3600
    tokens = {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "expires_in": expires_in,
        "expires_at": time.time() + max(expires_in, 0) - 60,
        "token_type": "Bearer",
        "scope": " ".join(creds.scopes or GMAIL_SCOPES),
    }

    config = load_config()
    store = Storage(config.db_path)
    store.save_tokens(args.account, "gmail", tokens)
    print(f"✓ saved Gmail token for account '{args.account}' to {config.db_path}")
    print("  now run: python run.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
