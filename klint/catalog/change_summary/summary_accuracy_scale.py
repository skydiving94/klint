"""The answer scale for checking a summary against its evidence.

The judge reads the evidence as the premise and the summary as the
hypothesis, as in natural language inference.
"""

from klint.core.models.scale import AnswerChoice, AnswerScale

ACCURATE = AnswerChoice(
    key="accurate",
    label="Accurate",
    criterion=(
        "The premise shows the hypothesis passes: it is true, and it does what "
        "the question asks."
    ),
    is_problem=False,
    sort_rank=2,
)
INACCURATE = AnswerChoice(
    key="inaccurate",
    label="Inaccurate",
    criterion=(
        "The premise shows the hypothesis fails: it is false, it claims "
        "something the premise does not show, or it does not do what the "
        "question asks."
    ),
    is_problem=True,
    sort_rank=0,
)
CANNOT_TELL = AnswerChoice(
    key="cannot_tell",
    label="Cannot Tell",
    criterion="The premise is cut off or empty, so it cannot be judged.",
    is_problem=False,
    sort_rank=1,
)
SUMMARY_ACCURACY_SCALE = AnswerScale(
    name="summary_accuracy", choices=(ACCURATE, INACCURATE, CANNOT_TELL)
)
