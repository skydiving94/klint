from abc import ABC, abstractmethod
from typing import Any, Mapping


class BaseKevEvaluator(ABC):
    @abstractmethod
    async def answer(
        self, state: str, questions: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Answer every question about ``state``.

        ``questions`` maps a question id to its type, instructions and
        criteria. The result maps each answered id to the chosen key, with
        an optional confidence and probabilities.
        """
        pass
