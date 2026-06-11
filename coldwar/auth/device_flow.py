"""OAuth 2.0 device authorization grant (RFC 8628) helpers.

The "enter this code" flow:

  1. begin_device_authorization() asks the provider for a user_code +
     verification_url and a device_code we hold onto.
  2. We show the user the code and URL. They open it on any device and consent.
  3. poll_token() exchanges the device_code for tokens once they have. Until then
     it returns None (authorization_pending) — the caller polls on an interval.

This module is provider-agnostic: pass the right endpoints and it works for both
Google and Microsoft. Token storage is the provider's job, not this module's.
"""

import time

import requests


class DeviceFlowError(RuntimeError):
    """Raised when the provider returns a terminal error (denied, expired)."""


def begin_device_authorization(
    *,
    device_endpoint: str,
    client_id: str,
    scope: str,
    extra: dict | None = None,
) -> dict:
    """Step 1: request a device + user code.

    Returns the provider's raw response, which includes:
      device_code, user_code, verification_url (or verification_uri),
      expires_in, interval.
    """
    data = {"client_id": client_id, "scope": scope}
    if extra:
        data.update(extra)
    resp = requests.post(device_endpoint, data=data, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    # Normalize the verification URL field name across providers (RFC says
    # verification_uri; Google historically used verification_url).
    if "verification_url" not in payload and "verification_uri" in payload:
        payload["verification_url"] = payload["verification_uri"]
    return payload


def poll_token(
    *,
    token_endpoint: str,
    client_id: str,
    device_code: str,
    client_secret: str | None = None,
) -> dict | None:
    """Step 3: try once to exchange the device_code for tokens.

    Returns the token dict on success, or None while the user has not yet
    consented (authorization_pending / slow_down). Raises DeviceFlowError on a
    terminal failure (access_denied, expired_token).
    """
    data = {
        "client_id": client_id,
        "device_code": device_code,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
    }
    if client_secret:
        data["client_secret"] = client_secret

    resp = requests.post(token_endpoint, data=data, timeout=30)
    if resp.status_code == 200:
        return resp.json()

    err = (resp.json() or {}).get("error", "")
    if err in ("authorization_pending", "slow_down"):
        return None  # keep polling
    raise DeviceFlowError(f"device-code authorization failed: {err or resp.text}")


def poll_until_authorized(
    *,
    token_endpoint: str,
    client_id: str,
    device_code: str,
    interval: int = 5,
    expires_in: int = 600,
    client_secret: str | None = None,
) -> dict:
    """Convenience: block, polling on `interval`, until tokens arrive or expiry.

    Useful for CLIs/tests. The Flask UI instead calls poll_token() once per
    browser poll so the request thread never blocks.
    """
    deadline = time.monotonic() + expires_in
    while time.monotonic() < deadline:
        tokens = poll_token(
            token_endpoint=token_endpoint,
            client_id=client_id,
            device_code=device_code,
            client_secret=client_secret,
        )
        if tokens is not None:
            return tokens
        time.sleep(interval)
    raise DeviceFlowError("device-code authorization timed out")


def refresh_access_token(
    *,
    token_endpoint: str,
    client_id: str,
    refresh_token: str,
    client_secret: str | None = None,
) -> dict:
    """Exchange a refresh_token for a fresh access_token."""
    data = {
        "client_id": client_id,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    if client_secret:
        data["client_secret"] = client_secret
    resp = requests.post(token_endpoint, data=data, timeout=30)
    resp.raise_for_status()
    return resp.json()
