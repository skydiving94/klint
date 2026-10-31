from enum import StrEnum


class SummaryCheckTag(StrEnum):
    """What a check of a summary is about; a report lists accuracy first.

    ACCURACY checks that what a summary says is true. COMPLETENESS checks
    that it leaves out nothing it should say.
    """

    ACCURACY = "accuracy"
    COMPLETENESS = "completeness"
