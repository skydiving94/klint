"""An error a command does not expect ends it with exit 2, never a crash's 1.

Exit 1 means that problems were found, so a crash must not end with it.
"""

import asyncio
import sys
from pathlib import Path

import pytest

from klint.cli import FILE_AUDIT_COMMAND, ExitCode, run_command_from_shell
from tests.support.builders import write_text


def test_local_judge_without_its_runtime_exits_2_with_an_error_line(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    shell_env: dict[str, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = write_text(tmp_path / "a.py", "x = 1\n")
    shell_env["KLINT_JUDGE_MODE"] = "local"
    # As when klint is installed without its "local" extra: the model runtime
    # cannot be imported.
    monkeypatch.setitem(sys.modules, "torch", None)
    monkeypatch.setitem(sys.modules, "kev", None)
    monkeypatch.delitem(
        sys.modules, "klint.infra.system_one.in_process_judge", raising=False
    )
    monkeypatch.setattr(sys, "argv", ["klint", str(target)])

    exit_code = asyncio.run(run_command_from_shell(FILE_AUDIT_COMMAND))

    err_lines = capsys.readouterr().err.splitlines()
    assert exit_code == ExitCode.RUN_ERROR
    # One line says why the command stopped; no traceback is shown.
    assert len(err_lines) == 1
    assert err_lines[0].startswith("[klint] Error: unexpected ModuleNotFoundError: ")
