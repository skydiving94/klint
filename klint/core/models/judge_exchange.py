"""What the auditor asks a judge, and what a judge answers."""

from dataclasses import dataclass

from klint.core.models.question_type import QuestionType


@dataclass(frozen=True)
class JudgeQuestion:
    """One question about the subject.

    question_id tells the answers apart. question is what the judge is
    asked, and choice_key_to_criterion holds each answer the judge may pick,
    with when to pick it.
    """

    question_id: str
    question_type: QuestionType
    question: str
    choice_key_to_criterion: dict[str, str]


@dataclass(frozen=True)
class JudgeRequest:
    """Every question asked about one subject, such as the text of a unit."""

    subject: str
    questions: tuple[JudgeQuestion, ...]


@dataclass(frozen=True)
class JudgeAnswer:
    """The judge's answer to the question question_id.

    choice_key is the key of the answer picked. confidence and
    choice_key_to_probability are given when the judge reports them.
    """

    question_id: str
    choice_key: str
    confidence: float | None = None
    choice_key_to_probability: dict[str, float] | None = None
