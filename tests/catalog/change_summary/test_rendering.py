"""What the judge reads about each summary: its evidence, then the summary."""

import re

from tests.support.change_summary import (
    GREETING_HUNK,
    README_HUNK,
    REMOVED_IMPORT_HUNK,
    HypothesisJudge,
    copy_greeting_document,
    run_change_summary_audit,
)

_GREET_FILE_SUMMARY = (
    "Greets a stripped name with 'Hello, <name>!' and drops an unused import."
)
_APP_SUMMARY = "Greets a stripped name with 'Hello, <name>!'."
_README_SUMMARY = "Adds a README that names and describes the greeter."
_COMMIT_SUMMARY = "Greets people by their stripped name, and adds a README."


def test_a_hunk_summary_is_judged_against_its_code_as_a_diff() -> None:
    judge = HypothesisJudge()

    run_change_summary_audit(judge)

    assert judge.find_subject(str(GREETING_HUNK["summary"])) == (
        "Premise: this code change to app/greet.py (modified); a line starting "
        "with - is removed, with + is added.\n"
        "@@ -3 +3,2 @@\n"
        "-    return 'hi'\n"
        "+    name = name.strip()\n"
        "+    return f'Hello, {name}!'\n"
        "\n"
        "Hypothesis: Strips the name and greets it with 'Hello, <name>!' "
        "instead of 'hi'."
    )
    assert judge.find_subject(str(REMOVED_IMPORT_HUNK["summary"])).splitlines()[
        1:3
    ] == ["@@ -1 +0,0 @@", "-import os"]


def test_a_file_summary_is_judged_against_its_checked_hunk_summaries() -> None:
    judge = HypothesisJudge({"unused import": {"no_false_statement": "inaccurate"}})

    run_change_summary_audit(judge)

    assert judge.find_subject(_GREET_FILE_SUMMARY) == (
        "Premise: summaries of the 2 hunks changed in the file app/greet.py "
        "(modified).\n"
        f"- Hunk 1: {GREETING_HUNK['summary']}\n"
        f"- Hunk 2 (its summary failed its own check): "
        f"{REMOVED_IMPORT_HUNK['summary']}\n"
        "\n"
        f"Hypothesis: {_GREET_FILE_SUMMARY}"
    )


def test_package_and_commit_summaries_are_judged_against_those_inside() -> None:
    judge = HypothesisJudge()

    run_change_summary_audit(judge)

    assert judge.find_subject(_APP_SUMMARY) == (
        "Premise: summaries of the files changed in the package app.\n"
        f"- File greet.py: {_GREET_FILE_SUMMARY}\n"
        "\n"
        f"Hypothesis: {_APP_SUMMARY}"
    )
    assert judge.find_subject(_COMMIT_SUMMARY) == (
        "Premise: summaries of the packages and files changed in the commit.\n"
        f"- Package app: {_APP_SUMMARY}\n"
        f"- File README.md: {_README_SUMMARY}\n"
        "\n"
        f"Hypothesis: {_COMMIT_SUMMARY}"
    )


def test_no_code_is_shown_above_the_hunks() -> None:
    judge = HypothesisJudge()

    run_change_summary_audit(judge)

    for summary in (_GREET_FILE_SUMMARY, _APP_SUMMARY, _COMMIT_SUMMARY):
        subject = judge.find_subject(summary)
        assert "@@" not in subject
        assert "name.strip()" not in subject


def test_each_child_summary_says_what_its_checks_found() -> None:
    judge = HypothesisJudge(
        {
            "Strips the name": {"covers_every_change": "inaccurate"},
            "Removes the unused import": {"no_unsupported_reason": "cannot_tell"},
        },
        refused_phrases=frozenset({"Adds a title"}),
    )

    run_change_summary_audit(judge)

    assert judge.find_subject(_GREET_FILE_SUMMARY).splitlines()[1:3] == [
        f"- Hunk 1 (its summary may leave out changes): {GREETING_HUNK['summary']}",
        "- Hunk 2 (its summary could not be fully checked): "
        f"{REMOVED_IMPORT_HUNK['summary']}",
    ]
    assert judge.find_subject(_README_SUMMARY).splitlines()[1] == (
        f"- Hunk 1 (its summary was not checked): {README_HUNK['summary']}"
    )


def test_a_file_with_no_hunks_says_its_diff_changes_no_line() -> None:
    document = copy_greeting_document()
    readme = document["root_package"]["files"][0]
    readme.update(change_kind="renamed", old_path="README.txt", hunks=[])
    judge = HypothesisJudge()

    run_change_summary_audit(judge, document)

    assert judge.find_subject(_README_SUMMARY) == (
        "Premise: the diff of the file README.md (renamed from README.txt) adds "
        "and removes no line, as for a binary file or a rename without edits.\n"
        "\n"
        f"Hypothesis: {_README_SUMMARY}"
    )


def test_a_long_hunk_is_cut_in_its_code_and_keeps_its_summary_whole() -> None:
    document = copy_greeting_document()
    added_lines = [
        f"    step_{number} = compute_step({number})" for number in range(90)
    ]
    document["root_package"]["files"][0]["hunks"][0].update(
        new_line_count=len(added_lines), added_lines=added_lines
    )
    judge = HypothesisJudge()

    run_change_summary_audit(judge, document)

    subject = judge.find_subject(str(README_HUNK["summary"]))
    premise, hypothesis = subject.split("\n\n")
    assert len(subject) <= 2_000
    assert hypothesis == f"Hypothesis: {README_HUNK['summary']}"
    trimming_line = premise.splitlines()[-1]
    match = re.fullmatch(
        r"\[\.\.\. (\d+) more lines of the code change left out to stay within "
        r"2000 characters\]",
        trimming_line,
    )
    assert match is not None, trimming_line
    shown_line_count = len(premise.splitlines()) - 3
    assert shown_line_count + int(match.group(1)) == len(added_lines)


def test_a_summary_too_long_for_its_code_is_shown_alone_and_cut() -> None:
    document = copy_greeting_document()
    long_summary = "Adds a title. " + "It is a fine title. " * 120
    document["root_package"]["files"][0]["hunks"][0]["summary"] = long_summary
    judge = HypothesisJudge()

    run_change_summary_audit(judge, document)

    (subject,) = [
        request.subject
        for request in judge.requests
        if request.subject.startswith("Premise: the code change, left out")
    ]
    assert len(subject) <= 2_000
    assert subject.startswith(
        "Premise: the code change, left out: the hypothesis takes up the 2000 "
        "characters there is room for.\n\nHypothesis: Adds a title."
    )
    assert re.search(r"left out to stay within \d+ characters\]$", subject)
    assert "+# Greeter" not in subject
