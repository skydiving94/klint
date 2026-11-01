"""The answer scale for asking whether content follows a described practice."""

from klint.core.models.scale import AnswerChoice, AnswerScale

PRACTICE_SCALE = AnswerScale(
    name="practice",
    choices=(
        AnswerChoice(
            key="pass",
            label="Pass",
            criterion="The provided content follows the described practice.",
            is_problem=False,
            sort_rank=2,
        ),
        AnswerChoice(
            key="fail",
            label="Fail",
            criterion="The provided content violates the described practice.",
            is_problem=True,
            sort_rank=0,
        ),
        AnswerChoice(
            key="irrelevant",
            label="Irrelevant",
            criterion="The described practice does not apply to the provided content.",
            is_problem=False,
            sort_rank=3,
        ),
        AnswerChoice(
            key="lack_of_evidence",
            label="Lack of Evidence",
            criterion=(
                "There is not enough information in the provided content to "
                "determine pass, fail, or irrelevance."
            ),
            is_problem=False,
            sort_rank=1,
        ),
    ),
)
