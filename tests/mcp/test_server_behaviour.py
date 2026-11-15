"""What every klint-mcp tool shares: the tools offered, refused paths, a judge down."""

from pathlib import Path

import pytest

from klint.core.models.judging import JudgeReply, JudgeRequest
from klint.mcp import create_mcp_server
from tests.support.builders import write_text
from tests.support.fakes import FakeJudge, JudgeBindingOverride
from tests.support.mcp_client import ProgressReport, call_tool, list_tools


class SwitchableJudge(FakeJudge):
    """Fails every request while ``is_down``, as a judge that cannot be reached."""

    def __init__(self) -> None:
        super().__init__()
        self.is_down = True

    async def answer(self, request: JudgeRequest) -> JudgeReply:
        if self.is_down:
            raise OSError("Connection refused")
        return await super().answer(request)


def test_the_server_offers_one_tool_per_audit_and_two_for_the_rules(
    project: Path,
) -> None:
    server = create_mcp_server(project)

    tools = list_tools(server)

    assert [tool.name for tool in tools] == [
        "audit_files",
        "audit_structure",
        "check_change_summary",
        "list_rules",
        "explain_rule",
    ]
    assert all(tool.description for tool in tools)


@pytest.mark.parametrize("path", ["../outside.py", "/etc/hosts"])
def test_a_path_outside_the_working_directory_is_refused(
    project: Path, path: str
) -> None:
    write_text(project.parent / "outside.py", "x = 1\n")
    judge = FakeJudge()
    server = create_mcp_server(project, JudgeBindingOverride(judge))

    call = call_tool(server, "audit_files", {"path": path})

    assert call.result.is_error
    assert f"'{path}' is outside the server's working directory" in call.read_error()
    assert judge.requests == []


def test_a_judge_that_cannot_be_reached_is_an_error_and_the_server_goes_on(
    project: Path,
) -> None:
    judge = SwitchableJudge()
    server = create_mcp_server(project, JudgeBindingOverride(judge))

    failed = call_tool(server, "audit_files", {"path": "cart.py"})
    judge.is_down = False
    recovered = call_tool(server, "audit_files", {"path": "cart.py"})

    assert failed.result.is_error
    assert (
        "None of the 4 unit(s) to audit could be audited; the judge could not "
        "answer about '"
    ) in failed.read_error()
    assert "': Connection refused" in failed.read_error()
    assert not recovered.result.is_error
    assert recovered.read_content()["examined_files"][0] == "cart.py"


def test_a_judge_run_in_this_process_is_refused(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KLINT_JUDGE_MODE", "local")
    server = create_mcp_server(project, JudgeBindingOverride(FakeJudge()))

    call = call_tool(server, "audit_files", {"path": "cart.py"})

    assert call.result.is_error
    assert "KLINT_JUDGE_MODE=remote" in call.read_error()


def test_a_long_audit_reports_its_progress_unit_by_unit(project: Path) -> None:
    write_text(
        project / "helpers.py", "def shout(text: str) -> str:\n    return text\n"
    )
    server = create_mcp_server(project, JudgeBindingOverride(FakeJudge()))

    call = call_tool(server, "audit_files", {"path": "."})

    unit_ids = call.read_content()["examined_files"]
    unit_count = len(unit_ids)
    assert unit_count == 6
    assert call.progress_reports[0] == ProgressReport(
        0, unit_count, f"Auditing {unit_count} units"
    )
    assert [report.progress for report in call.progress_reports[1:]] == list(
        range(1, unit_count + 1)
    )
    assert {report.total for report in call.progress_reports} == {unit_count}
    assert sorted(
        str(report.message) for report in call.progress_reports[1:]
    ) == sorted(f"Audited {unit_id}" for unit_id in unit_ids)
