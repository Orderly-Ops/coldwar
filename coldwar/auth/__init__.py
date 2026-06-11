"""OAuth helpers — device authorization grant only.

Google and Microsoft no longer permit email/password or basic auth. The
device-code flow shows the user a short code + a verification URL; they consent
on another device. No passwords ever touch Cold War.
"""
