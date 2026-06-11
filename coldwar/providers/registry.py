"""Provider registry.

Concrete providers decorate themselves with @register; config.yaml selects them
by name (per account). Same shape as the classifier registry on purpose.
"""

_REGISTRY = {}


def register(cls):
    _REGISTRY[cls.name] = cls
    return cls


def get(name):
    return _REGISTRY[name]()


def available() -> list[str]:
    """Names of every registered provider."""
    return sorted(_REGISTRY)
