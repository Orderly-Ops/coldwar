"""Extension seam #1 — detection logic.

To add smarts, write a BaseClassifier subclass here, decorate it with @register,
and name it in config.yaml. You never touch the core to add a detector.
"""

# Import concrete classifiers so their @register decorators run on package load.
from coldwar.classifiers import heuristic  # noqa: F401
