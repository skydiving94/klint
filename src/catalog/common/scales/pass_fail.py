"""The default four-way answer scale for pass/fail audits."""

from src.core.models.scale import AnswerScale, Choice

PASS_FAIL_SCALE = AnswerScale(
    name="pass_fail",
    choices=(
        Choice(
            key="pass",
            label="Pass",
            criterion="The provided code or project structure follows the described practice.",
            is_finding=False,
            priority=2,
        ),
        Choice(
            key="fail",
            label="Fail",
            criterion="The provided code or project structure violates the described practice.",
            is_finding=True,
            priority=0,
        ),
        Choice(
            key="irrelevant",
            label="Irrelevant",
            criterion="The described practice does not apply to this specific code or directory.",
            is_finding=False,
            priority=3,
        ),
        Choice(
            key="lack_of_evidence",
            label="Lack of Evidence",
            criterion="There is not enough information in the provided context to determine pass, fail, or irrelevance.",
            is_finding=False,
            priority=1,
        ),
    ),
)
