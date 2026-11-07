"""The answers about a summary that klint knows without asking the judge."""

from collections.abc import Mapping, Sequence

from klint.catalog.change_summary.summary_accuracy_scale import CANNOT_TELL, INACCURATE

# The check of whether a summary was written, which klint answers itself.
HAS_SUMMARY_RULE_ID = "has_summary"


def find_summary_known_answers(
    summary: str | None,
    rule_ids: Sequence[str],
    child_summaries: Sequence[str | None] = (),
) -> Mapping[str, str | None]:
    """Return the answers known about a unit whose summary is ``summary``.

    A summary left out fails the has_summary check, and no other rule is
    answered about it. A summary that was written gets no answer to that
    check. Its other rules are answered "cannot tell" when one of
    ``child_summaries``, the summaries one level down that are its premise,
    was left out; the judge is asked them otherwise.
    """
    if summary is None:
        return {
            rule_id: INACCURATE.key if rule_id == HAS_SUMMARY_RULE_ID else None
            for rule_id in rule_ids
        }
    if any(child_summary is None for child_summary in child_summaries):
        return {
            rule_id: None if rule_id == HAS_SUMMARY_RULE_ID else CANNOT_TELL.key
            for rule_id in rule_ids
        }
    return {rule_id: None for rule_id in rule_ids if rule_id == HAS_SUMMARY_RULE_ID}
