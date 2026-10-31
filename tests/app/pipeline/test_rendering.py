"""What the judge reads about each unit, as the renderers of its kind write it."""

from tests.support.fakes import SubjectJudge
from tests.support.outline_suite import SUMMARIZED_OUTLINE_KIND_ID, run_outline_audit


def _map_first_line_to_subject(judge: SubjectJudge) -> dict[str, str]:
    return {
        request.subject.splitlines()[0]: request.subject for request in judge.requests
    }


def test_parent_renderer_receives_the_findings_on_its_children() -> None:
    judge = SubjectJudge({"Section 1.1.": "fail"})

    run_outline_audit(judge, audit_kind_id=SUMMARIZED_OUTLINE_KIND_ID)

    first_line_to_subject = _map_first_line_to_subject(judge)
    assert first_line_to_subject["Chapter 1."] == (
        "Chapter 1.\n"
        "section 1.1: clear_section = fail\n"
        "section 1.2: clear_section = pass"
    )
    # Only the sections directly inside: the book does not see section 1.1.
    assert first_line_to_subject["The book."] == (
        "The book.\nchapter 1: clear_section = pass\nchapter 2: clear_section = pass"
    )
    assert first_line_to_subject["Section 1.1."] == "Section 1.1."


def test_child_whose_audit_failed_gives_its_parent_no_findings() -> None:
    judge = SubjectJudge({}, refused_subjects=frozenset({"Section 1.1."}))

    run_outline_audit(judge, audit_kind_id=SUMMARIZED_OUTLINE_KIND_ID)

    assert _map_first_line_to_subject(judge)["Chapter 1."] == (
        "Chapter 1.\nsection 1.2: clear_section = pass"
    )
