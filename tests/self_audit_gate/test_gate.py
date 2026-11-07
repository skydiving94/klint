"""The Self-Audit gate: open findings fail it, listed rebuttals clear them."""

import json
from pathlib import Path

import pytest

from self_audit_gate.gate import GateExitCode, run_gate

Capture = pytest.CaptureFixture[str]

LINK = "https://github.com/skydiving94/klint/pull/79#issuecomment-1"


def write_report(path: Path, *findings: tuple[str, str]) -> Path:
    """Write a klint ``--json`` report holding failures of (rule, unit)."""
    path.write_text(
        json.dumps(
            {
                "examined_directories": [],
                "unit_id_to_roll_up_status": {},
                "findings": [
                    {
                        "rule_id": rule_id,
                        "unit_id": unit_id,
                        "answer": "Fail",
                        "confidence": 0.93,
                    }
                    for rule_id, unit_id in findings
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def write_rebuttals(path: Path, *entries: dict[str, str]) -> Path:
    path.write_text(json.dumps({"rebuttals": list(entries)}), encoding="utf-8")
    return path


def rebuttal(audit: str, rule_id: str, unit_id: str) -> dict[str, str]:
    return {"audit": audit, "rule_id": rule_id, "unit_id": unit_id, "rebuttal": LINK}


@pytest.fixture(autouse=True)
def _no_job_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)


def test_an_unlisted_finding_fails_the_gate_and_is_named(
    tmp_path: Path, capsys: Capture
) -> None:
    structure = write_report(tmp_path / "s.json", ("flat_structure", "klint/app"))
    rebuttals = write_rebuttals(tmp_path / "r.json")

    exit_code = run_gate(["--structure", str(structure), "--rebuttals", str(rebuttals)])

    out = capsys.readouterr().out
    assert exit_code == GateExitCode.OPEN_FINDINGS
    assert "| structure | `flat_structure` | `klint/app` | 93% | **Open** |" in out
    assert "**1 open finding(s).**" in out


def test_listed_findings_pass_and_show_their_rebuttal(
    tmp_path: Path, capsys: Capture, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    structure = write_report(tmp_path / "s.json", ("excessive_nesting_depth", "klint"))
    file_report = write_report(tmp_path / "f.json")
    rebuttals = write_rebuttals(
        tmp_path / "r.json", rebuttal("structure", "excessive_nesting_depth", "klint")
    )

    exit_code = run_gate(
        [
            "--structure",
            str(structure),
            "--file",
            str(file_report),
            "--rebuttals",
            str(rebuttals),
        ]
    )

    assert exit_code == GateExitCode.PASSED
    assert f"Rebutted ([comment]({LINK}))" in capsys.readouterr().out
    assert "Every finding is fixed or rebutted." in summary.read_text(encoding="utf-8")


def test_a_rebuttal_counts_only_for_its_own_audit(tmp_path: Path) -> None:
    file_report = write_report(tmp_path / "f.json", ("god_component", "klint"))
    rebuttals = write_rebuttals(
        tmp_path / "r.json", rebuttal("structure", "god_component", "klint")
    )

    exit_code = run_gate(["--file", str(file_report), "--rebuttals", str(rebuttals)])

    assert exit_code == GateExitCode.OPEN_FINDINGS


def test_a_listed_finding_no_run_finds_is_reported(
    tmp_path: Path, capsys: Capture
) -> None:
    structure = write_report(tmp_path / "s.json")
    rebuttals = write_rebuttals(
        tmp_path / "r.json",
        rebuttal("structure", "dead_code_module", "klint/resources"),
    )

    exit_code = run_gate(["--structure", str(structure), "--rebuttals", str(rebuttals)])

    assert exit_code == GateExitCode.PASSED
    assert "Listed but not found in this run: structure `dead_code_module`" in (
        capsys.readouterr().out
    )


@pytest.mark.parametrize(
    ("list_text", "reason"),
    [
        ("not json", "cannot read the rebuttal list"),
        ('{"rebuttals": {}}', "must hold an object with a 'rebuttals' list"),
        ('{"rebuttals": [{"audit": "structure"}]}', "must hold exactly"),
        (
            json.dumps({"rebuttals": [{**rebuttal("project", "r", "u")}]}),
            "audit must be one of ['structure', 'file']",
        ),
        (
            json.dumps(
                {"rebuttals": [{**rebuttal("file", "r", "u"), "rebuttal": "see PR"}]}
            ),
            "rebuttal must link to the comment",
        ),
    ],
)
def test_a_malformed_list_stops_the_gate_with_the_reason(
    tmp_path: Path, capsys: Capture, list_text: str, reason: str
) -> None:
    structure = write_report(tmp_path / "s.json")
    rebuttals = tmp_path / "r.json"
    rebuttals.write_text(list_text, encoding="utf-8")

    exit_code = run_gate(["--structure", str(structure), "--rebuttals", str(rebuttals)])

    assert exit_code == GateExitCode.INPUT_ERROR
    assert reason in capsys.readouterr().err


def test_a_report_that_is_not_klint_json_stops_the_gate(
    tmp_path: Path, capsys: Capture
) -> None:
    structure = tmp_path / "s.json"
    structure.write_text('{"results": []}', encoding="utf-8")
    rebuttals = write_rebuttals(tmp_path / "r.json")

    exit_code = run_gate(["--structure", str(structure), "--rebuttals", str(rebuttals)])

    assert exit_code == GateExitCode.INPUT_ERROR
    assert "cannot read the structure report" in capsys.readouterr().err
