from enum import Enum
from typing import Dict


class Judgment(str, Enum):

    criterion: str

    def __new__(cls, value: str, criterion: str) -> "Judgment":
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.criterion = criterion
        return obj

    PASS = (
        "Pass",
        "The provided code or project structure follows the described practice.",
    )
    FAIL = (
        "Fail",
        "The provided code or project structure violates the described practice.",
    )
    IRRELEVANT = (
        "Irrelevant",
        "The described practice does not apply to this specific code or directory.",
    )
    LACK_OF_EVIDENCE = (
        "Lack of Evidence",
        "There is not enough information in the provided context to determine pass, fail, or irrelevance.",
    )

    @classmethod
    def as_criteria_payload(cls) -> Dict[str, str]:
        return {member.name.lower(): member.criterion for member in cls}


class QuestionType(str, Enum):
    CHOICE = "choice"
