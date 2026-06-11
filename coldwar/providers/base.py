"""The mailbox contract — this is where Gmail-label vs Outlook-folder disappears.

Every provider speaks the same six-method language. The worker never knows or
cares whether quarantine means "add a label" or "move to a folder".
"""

from abc import ABC, abstractmethod
from typing import Iterable

from coldwar.models import Message


class BaseProvider(ABC):
    name: str   # "gmail", "outlook"

    @abstractmethod
    def begin_device_auth(self) -> dict: ...        # returns {user_code, verification_url, ...}

    @abstractmethod
    def poll_device_auth(self) -> bool: ...         # True once the user consents

    @abstractmethod
    def fetch_new(self, since) -> Iterable[Message]: ...

    @abstractmethod
    def quarantine(self, message: Message) -> None: ...
        # gmail.py: add "Cold" label, remove INBOX label
        # outlook.py: move to the "Cold" folder (create if missing)

    @abstractmethod
    def list_unquarantined(self) -> Iterable[Message]: ...
        # messages the user dragged BACK out of Cold = "not cold" feedback
