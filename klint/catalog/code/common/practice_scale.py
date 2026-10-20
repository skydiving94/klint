"""The answer scale for asking whether content follows a described practice."""

from klint.core.models.scale import AnswerScale, Choice

PRACTICE_SCALE = AnswerScale(
    name="practice",
    choices=(
        Choice(
            key="pass",
            label="Pass",
            criterion="The provided content follows the described practice.",
            is_finding=False,
            priority=2,
        ),
        Choice(
            key="fail",
            label="Fail",
            criterion="The provided content violates the described practice.",
            is_finding=True,
            priority=0,
        ),
        Choice(
            key="irrelevant",
            label="Irrelevant",
            criterion="The described practice does not apply to the provided content.",
            is_finding=False,
            priority=3,
        ),
        Choice(
            key="lack_of_evidence",
            label="Lack of Evidence",
            criterion=(
                "There is not enough information in the provided content to "
                "determine pass, fail, or irrelevance."
            ),
            is_finding=False,
            priority=1,
        ),
    ),
)
