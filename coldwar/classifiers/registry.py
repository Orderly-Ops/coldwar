"""Classifier registry.

Concrete classifiers decorate themselves with @register; config.yaml selects them
by name. This is what makes the pipeline data-driven instead of hard-wired.
"""

_REGISTRY = {}


def register(cls):
    _REGISTRY[cls.name] = cls
    return cls


def get(name):
    return _REGISTRY[name]()


def available() -> list[str]:
    """Names of every registered classifier — handy for the UI and errors."""
    return sorted(_REGISTRY)
