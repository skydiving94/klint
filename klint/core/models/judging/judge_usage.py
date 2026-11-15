"""What the judge was sent, and what it reported billing for it."""

from dataclasses import dataclass


@dataclass(frozen=True)
class JudgeUsage:
    """The requests sent to the judge, and the input tokens it billed for them.

    request_count counts the requests the judge answered. input_token_count
    is the input tokens the judge reported for them; None when one of them
    was answered without a report, so that a partial count is never shown
    as the whole. asked_question_count and cached_question_count tell, where
    an answer cache stands before the judge, how many questions it sent on
    and how many it answered itself; both stay 0 without one.
    """

    request_count: int = 0
    input_token_count: int | None = 0
    asked_question_count: int = 0
    cached_question_count: int = 0

    def add(self, other: "JudgeUsage") -> "JudgeUsage":
        """Return the usage of the requests counted here and in ``other``."""
        return JudgeUsage(
            request_count=self.request_count + other.request_count,
            input_token_count=(
                None
                if self.input_token_count is None or other.input_token_count is None
                else self.input_token_count + other.input_token_count
            ),
            asked_question_count=(
                self.asked_question_count + other.asked_question_count
            ),
            cached_question_count=(
                self.cached_question_count + other.cached_question_count
            ),
        )

    def did_cache_take_part(self) -> bool:
        """Return True when an answer cache answered or passed on a question."""
        return bool(self.asked_question_count or self.cached_question_count)
