"""The answers about a summary that klint knows without asking the judge."""

from collections.abc import Mapping, Sequence

from klint.catalog.change_summary.summary_accuracy_scale import INACCURATE

# The check of whether a summary was written, which klint answers itself.
HAS_SUMMARY_RULE_ID = "has_summary"


def find_summary_known_answers(
    summary: str | None, rule_ids: Sequence[str]
) -> Mapping[str, str | None]:
    """Return the answers known about a unit whose summary is ``summary``.

    A summary left out fails the has_summary check, and no other rule is
    answered about it. A summary that was written gets no answer to that
    check, and the judge is asked every other rule.
    """
    if summary is None:
        return {
            rule_id: INACCURATE.key if rule_id == HAS_SUMMARY_RULE_ID else None
            for rule_id in rule_ids
        }
    return {rule_id: None for rule_id in rule_ids if rule_id == HAS_SUMMARY_RULE_ID}
