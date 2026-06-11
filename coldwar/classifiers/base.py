"""The main extension point — deliberately tiny.

The barrier to contributing a detector is exactly one method: classify(). An
optional train() lets a classifier learn from "this wasn't cold" feedback.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from coldwar.models import Message


@dataclass
class Verdict:
    is_cold: bool
    score: float          # 0..1 confidence
    reasons: list[str]    # which signals fired — surface these in the UI


class BaseClassifier(ABC):
    name: str

    @abstractmethod
    def classify(self, message: Message) -> Verdict: ...

    def train(self, message: Message, is_cold: bool) -> None:
        """Optional: learn from drag-back feedback. No-op by default."""
