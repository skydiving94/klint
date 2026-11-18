"""The klint-pull-request command: the threshold and report of a pull request's check.

The GitHub Action runs klint and klint-structure on a pull request's diff,
then this command: ``threshold`` prints the confidence a finding needs to
fail the check, the same the commit gate uses, and ``report`` combines the
two audits' ``--json`` reports into one file and prints the job summary.
``review`` posts that report as a review on the pull request, with the
job's token in GITHUB_TOKEN, and prints what it posted.
"""

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from klint.app import AppSettings
from klint.app.acknowledgements import find_repository_root
from klint.app.commit_threshold import choose_commit_threshold
from klint.cli.audit_command import KlintCommand
from klint.cli.console import print_error_line
from klint.cli.exit_code import ExitCode
from klint.cli.pull_request.job_summary import format_job_summary
from klint.cli.pull_request.pull_request_report import (
    AuditReportFile,
    PullRequestAudit,
    read_pull_request_report,
)
from klint.cli.pull_request.review_posting import (
    ReviewArguments,
    post_pull_request_review,
)
from klint.infra.github import GitHubReviewApi, PullRequestAddress

_NO_TOKEN_LINE = "klint posted no review comments: GITHUB_TOKEN is not set."

PULL_REQUEST_COMMAND = KlintCommand(
    name="klint-pull-request",
    description=(
        "klint - the threshold and the report of a pull request's check, "
        "for the GitHub Action"
    ),
)


class PullRequestSubcommand(StrEnum):
    """What klint-pull-request is asked to do."""

    THRESHOLD = "threshold"
    REPORT = "report"
    REVIEW = "review"


@dataclass(frozen=True)
class ReportArguments:
    """What ``report`` was asked: the two reports, the threshold, the output."""

    file_report: Path
    structure_report: Path
    min_confidence: float
    output: Path


def print_threshold() -> ExitCode:
    """Print the confidence a finding needs to fail a pull request's check.

    The project's KLINT_COMMIT_MIN_CONFIDENCE when set, else the judge's own,
    as for the commit gate.
    """
    try:
        settings = AppSettings.from_env()
    except (OSError, ValueError) as error:
        print_error_line(PULL_REQUEST_COMMAND, error)
        return ExitCode.RUN_ERROR
    print(
        choose_commit_threshold(
            None, settings.commit_min_confidence, settings.model_name
        )
    )
    return ExitCode.NO_PROBLEMS


async def write_report(arguments: ReportArguments, working_directory: Path) -> ExitCode:
    """Combine the two reports into ``arguments.output`` and print the summary.

    Exits with PROBLEMS_FOUND when either report holds a finding.
    """
    report_files = (
        AuditReportFile(PullRequestAudit.FILE, arguments.file_report),
        AuditReportFile(PullRequestAudit.STRUCTURE, arguments.structure_report),
    )
    repository_root = await find_repository_root(working_directory)
    try:
        report = read_pull_request_report(
            report_files, arguments.min_confidence, repository_root, working_directory
        )
        arguments.output.write_text(
            json.dumps(report.convert_to_dict(), indent=2) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError) as error:
        print_error_line(PULL_REQUEST_COMMAND, error)
        return ExitCode.RUN_ERROR
    print(format_job_summary(report), end="")
    return ExitCode.PROBLEMS_FOUND if report.findings else ExitCode.NO_PROBLEMS


async def run_pull_request_arguments(
    argv: Sequence[str], working_directory: Path
) -> ExitCode:
    """Run the subcommand ``argv`` names, from ``working_directory``."""
    parser = _build_parser()
    namespace = parser.parse_args(argv)
    if namespace.subcommand == PullRequestSubcommand.THRESHOLD:
        return print_threshold()
    if namespace.subcommand == PullRequestSubcommand.REVIEW:
        return post_review(namespace)
    arguments = ReportArguments(
        file_report=namespace.file_report,
        structure_report=namespace.structure_report,
        min_confidence=namespace.min_confidence,
        output=namespace.output,
    )
    return await write_report(arguments, working_directory)


def post_review(namespace: argparse.Namespace) -> ExitCode:
    """Post the review ``namespace`` describes and print what was posted.

    Always exits with NO_PROBLEMS: the review never changes the check.
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print(_NO_TOKEN_LINE)
        return ExitCode.NO_PROBLEMS
    address = PullRequestAddress(
        repository=namespace.repository,
        number=namespace.pull_request,
        api_url=os.environ.get("GITHUB_API_URL") or PullRequestAddress.api_url,
        graphql_url=(
            os.environ.get("GITHUB_GRAPHQL_URL") or PullRequestAddress.graphql_url
        ),
    )
    arguments = ReviewArguments(
        findings_json=namespace.findings_json,
        diff_file=namespace.diff_file,
        commit_id=namespace.commit,
    )
    print(post_pull_request_review(arguments, GitHubReviewApi(address, token)), end="")
    return ExitCode.NO_PROBLEMS


def run_pull_request_command() -> int:
    return asyncio.run(run_pull_request_arguments(sys.argv[1:], Path.cwd()))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PULL_REQUEST_COMMAND.name, description=PULL_REQUEST_COMMAND.description
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    subparsers.add_parser(
        PullRequestSubcommand.THRESHOLD.value,
        help="Print the confidence a finding needs to fail the check",
    )
    report = subparsers.add_parser(
        PullRequestSubcommand.REPORT.value,
        help="Combine the two audits' --json reports and print the summary",
    )
    report.add_argument("--file-report", type=Path, required=True)
    report.add_argument("--structure-report", type=Path, required=True)
    report.add_argument("--min-confidence", type=float, required=True)
    report.add_argument("--output", type=Path, required=True)
    review = subparsers.add_parser(
        PullRequestSubcommand.REVIEW.value,
        help="Post the combined report as a review on the pull request",
    )
    review.add_argument("--findings-json", type=Path, required=True)
    review.add_argument("--diff-file", type=Path, required=True)
    review.add_argument("--repository", required=True, help="owner/name")
    review.add_argument("--pull-request", type=int, required=True)
    review.add_argument("--commit", required=True, help="the head commit's SHA")
    return parser
