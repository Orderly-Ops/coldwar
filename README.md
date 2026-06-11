# Cold War

**Self-hosted, open-source defense against cold sales email.** Cold War connects
to your mailbox through the provider's own API (Microsoft Graph, Gmail API),
detects unwanted cold outreach, and quarantines it — moving it to a **Cold**
folder (Outlook) or applying a **Cold** label and pulling it out of the inbox
(Gmail). It **never deletes anything**, and because it sits beside the mailbox
rather than in the mail flow, it can never block legitimate mail.

> Enterprise-grade cold-outreach protection for small businesses and nonprofits —
> built as a community project. Detection logic and mail backends are **pluggable**:
> add your own without touching the core.

## Why API, not MX?

Cold War talks to mailboxes over **post-delivery APIs**. It is not a mail server
and not in the delivery path, so a bug can mis-label a message but can **never
bounce or drop** real mail. Quarantine is always reversible — drag a message back
and Cold War learns from it.

## 60-second run

```bash
# 1. Install (Python 3.11+)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env                 # add your OAuth client id/secret
cp config.yaml.example config.yaml   # pick provider(s) + classifier pipeline

# 3. Run BOTH the UI and the worker (one command, on purpose)
python run.py
```

Open <http://127.0.0.1:8765>, click **Connect** on your mailbox, and complete the
**device-code flow**: Cold War shows a short code and a URL; you approve on any
device. No passwords ever touch Cold War. The worker then checks your inbox on an
interval and the dashboard shows what it quarantined — and **why**.

> You need an OAuth client to use a real mailbox: a Google Cloud OAuth client
> (type "TVs and Limited Input devices", Gmail API enabled) and/or an Entra ID app
> for Microsoft. The heuristic classifier and tests run with no credentials.

## Where do I add my idea? (the contribution map)

Cold War is a **boring core with two obvious extension seams**. You should never
edit the worker, Flask app, or storage to extend it.

| I want to… | Write a… | In… | Then… |
|---|---|---|---|
| **Detect cold mail better** | `BaseClassifier` subclass with one `classify()` method | [`coldwar/classifiers/`](coldwar/classifiers/) | name it in `config.yaml` |
| **Support another mailbox** | `BaseProvider` subclass | [`coldwar/providers/`](coldwar/providers/) | name it on an account in `config.yaml` |

Each plugin decorates itself with `@register` and is selected **by name** in
`config.yaml`. That's the whole wiring. See [CONTRIBUTING.md](CONTRIBUTING.md).

## How it works

```
                  ┌─────────── run.py (one process) ───────────┐
                  │                                             │
   Flask UI  ◄────┤  /connect  → device-code flow → tokens      │
   (dashboard)    │  /          → quarantined mail + reasons     │
                  │                                             │
   Worker  ◄──────┤  every N seconds, per account:              │
                  │    fetch_new → classify → quarantine → learn │
                  └─────────────────────────────────────────────┘
                         providers/        classifiers/
                       (label vs folder)  (the war effort)
```

Every email is normalized into a single [`Message`](coldwar/models.py) shape
before any classifier sees it, so a detector written once works across providers.
Quarantine is provider-specific (Gmail label vs Outlook folder) but hidden behind
[`BaseProvider`](coldwar/providers/base.py) — the worker never knows the difference.

## Status

- **Gmail:** fully implemented (device auth, fetch, label-based quarantine, feedback).
- **Outlook (Graph):** working **stub** — device auth wired; fetch/move/feedback
  outlined with clear `TODO`s for contributors.
- **Classifier:** a default [`heuristic`](coldwar/classifiers/heuristic.py) that
  flags first-contact mail showing sales-intent language, booking links, or
  outreach-tool fingerprints — so Cold War flags something useful out of the box.
- **Signals:** content-free campaign [fingerprints](coldwar/signals/fingerprint.py)
  are extracted and stored **locally** — the seed of a future community feed
  (not networked in V1).

## Running the tests

```bash
pip install -r requirements.txt
pytest
```

## License

[MIT](LICENSE).
