# Contributing to Cold War

Cold War is built so that **all interesting work happens in two folders**, and the
core never needs to change:

- **Add smarts → write a Classifier** (`coldwar/classifiers/`)
- **Add a mailbox → write a Provider** (`coldwar/providers/`)

If you find yourself editing `worker.py`, `app.py`, `storage.py`, or `config.py`
to add a detector or a mailbox, stop — that's a sign the seam needs widening, and
it's worth an issue rather than a workaround.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
```

Python **3.11+**. Keep code clear, minimal, and well-commented — readability beats
cleverness here, because the whole point is a low barrier to contribution.

## Add a detector (Classifier)

A classifier implements exactly one required method. The barrier is one method on
purpose.

```python
# coldwar/classifiers/mydetector.py
from coldwar.classifiers.base import BaseClassifier, Verdict
from coldwar.classifiers.registry import register
from coldwar.models import Message

@register
class MyDetector(BaseClassifier):
    name = "mydetector"          # the name you'll put in config.yaml

    def classify(self, message: Message) -> Verdict:
        reasons = []
        if "lottery" in message.subject.lower():
            reasons.append("subject mentions a lottery")
        is_cold = bool(reasons)
        return Verdict(is_cold=is_cold, score=0.9 if is_cold else 0.0, reasons=reasons)

    # Optional — learn when a user says "this wasn't cold".
    def train(self, message: Message, is_cold: bool) -> None:
        ...
```

Then import it so the `@register` runs (add it to
`coldwar/classifiers/__init__.py`) and name it in `config.yaml`:

```yaml
classifier:
  - heuristic
  - mydetector      # a list forms a pipeline: cold if ANY classifier flags it
```

**Always populate `reasons`** with the specific signals that fired — the dashboard
shows them so users understand *why* a message was quarantined.

## Add a mailbox (Provider)

A provider hides label-vs-folder and provider-specific JSON behind six methods
(see [`coldwar/providers/base.py`](coldwar/providers/base.py)). Classifiers must
never see raw provider data — normalize everything into a
[`Message`](coldwar/models.py).

Key rules:

- **Auth is device-code flow only.** No passwords, ever. Reuse the helpers in
  [`coldwar/auth/device_flow.py`](coldwar/auth/device_flow.py).
- **Quarantine is non-destructive** — move or label, never delete.
- `list_unquarantined()` returns mail the user pulled **back out** of quarantine;
  that's the "not cold" feedback signal.

Use [`gmail.py`](coldwar/providers/gmail.py) as the reference implementation and
[`outlook.py`](coldwar/providers/outlook.py) as a stub showing the shape. Decorate
with `@register`, give it a `name`, and import it in
`coldwar/providers/__init__.py`.

> Providers are constructed by the registry with no arguments, then `configure()`
> is called to attach the account id and storage. Read OAuth client credentials
> from environment variables (see `.env.example`).

## Tests

- Put sample cold + wanted emails in [`tests/fixtures/`](tests/fixtures/).
- A new classifier should come with tests that prove cold mail is flagged and
  wanted mail is spared. Mirror [`tests/test_heuristic.py`](tests/test_heuristic.py).
- Run `pytest` before opening a PR.

## V1 scope

Please keep PRs within V1. Out of scope for now: MX/inline interception, deleting
mail, multi-tenant hosting, and networking the campaign signatures (local
extraction only). See the roadmap in the project brief for what's coming.

## License

By contributing you agree your contributions are licensed under the
[MIT License](LICENSE).
