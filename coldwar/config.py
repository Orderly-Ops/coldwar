"""Load config + env, and wire plugins by name.

This module is the bridge between config.yaml (what the user wants) and the
registries (what the code can do). Nothing here knows about specific providers
or classifiers — it just resolves names.
"""

import os
from dataclasses import dataclass, field

import yaml

# Importing the packages runs the @register decorators on every concrete
# provider and classifier, populating the registries before we resolve names.
import coldwar.classifiers  # noqa: F401
import coldwar.providers  # noqa: F401
from coldwar.classifiers import registry as classifier_registry
from coldwar.providers import registry as provider_registry


@dataclass
class Account:
    id: str
    provider: str


@dataclass
class Config:
    accounts: list[Account] = field(default_factory=list)
    classifier_names: list[str] = field(default_factory=list)

    # Runtime knobs (sourced from env, with sensible defaults).
    db_path: str = "coldwar.db"
    host: str = "127.0.0.1"
    port: int = 8765
    poll_seconds: int = 120
    secret_key: str = "dev-insecure-change-me"


def load_config(path: str = "config.yaml") -> Config:
    """Read config.yaml and overlay environment variables."""
    raw: dict = {}
    if os.path.exists(path):
        with open(path) as f:
            raw = yaml.safe_load(f) or {}

    accounts = [
        Account(id=a["id"], provider=a["provider"])
        for a in raw.get("accounts", [])
    ]

    # `classifier` may be a single name or a list — normalize to a list.
    clf = raw.get("classifier", ["heuristic"])
    classifier_names = [clf] if isinstance(clf, str) else list(clf)

    return Config(
        accounts=accounts,
        classifier_names=classifier_names,
        db_path=os.environ.get("COLDWAR_DB", "coldwar.db"),
        host=os.environ.get("COLDWAR_HOST", "127.0.0.1"),
        port=int(os.environ.get("COLDWAR_PORT", "8765")),
        poll_seconds=int(os.environ.get("COLDWAR_POLL_SECONDS", "120")),
        secret_key=os.environ.get("FLASK_SECRET_KEY", "dev-insecure-change-me"),
    )


def build_provider(name: str):
    """Resolve a provider name to an instance via the registry."""
    return provider_registry.get(name)


def build_classifier(names: list[str]):
    """Resolve one or more classifier names into a single classifier.

    A list forms a pipeline: the message is cold if any classifier flags it, and
    reasons/score are merged. A single name returns that classifier directly.
    """
    if len(names) == 1:
        return classifier_registry.get(names[0])
    return PipelineClassifier([classifier_registry.get(n) for n in names])


class PipelineClassifier:
    """Runs several classifiers in order; cold if ANY of them say cold.

    Lives here (not in classifiers/) because it is core wiring, not detection
    logic — contributors never need to touch it.
    """

    name = "pipeline"

    def __init__(self, classifiers: list):
        self.classifiers = classifiers

    def classify(self, message):
        from coldwar.classifiers.base import Verdict

        is_cold = False
        score = 0.0
        reasons: list[str] = []
        for clf in self.classifiers:
            v = clf.classify(message)
            if v.is_cold:
                is_cold = True
            score = max(score, v.score)
            reasons.extend(f"[{clf.name}] {r}" for r in v.reasons)
        return Verdict(is_cold=is_cold, score=score, reasons=reasons)

    def train(self, message, is_cold: bool) -> None:
        for clf in self.classifiers:
            clf.train(message, is_cold)
