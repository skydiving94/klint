from enum import Enum


class Judgment(str, Enum):
    PASS = "Pass"
    FAIL = "Fail"
    IRRELEVANT = "Irrelevant"


class QuestionType(str, Enum):
    CHOICE = "choice"


class UnitType(str, Enum):
    # This is the only supported unit type at the moment.
    FILE = "file"

    # The ones below will be supported in the future and they can be renamed.
    CODE_SNIPPET = "code_snippet"
    FUNCTION_OR_CLASS = "function_or_class"
    STATIC_METADATA = "static_metadata"
