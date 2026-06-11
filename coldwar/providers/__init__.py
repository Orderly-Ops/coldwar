"""Extension seam #2 — mail backends.

To add a mailbox, write a BaseProvider subclass here, decorate it with @register,
and name it from config.yaml. The provider hides label-vs-folder and all
provider-specific JSON behind the BaseProvider contract.
"""

# Import concrete providers so their @register decorators run on package load.
from coldwar.providers import gmail   # noqa: F401
from coldwar.providers import outlook  # noqa: F401
