"""The change-summary example: two documents that differ in two planted summaries."""

import json
from dataclasses import asdict
from pathlib import Path

from tests.support.change_summary import extract_summary_units
from tests.support.paths import REPO_ROOT

_EXAMPLE = REPO_ROOT / "examples" / "change_summary"


def _map_unit_id_to_summary(path: Path) -> dict[str, str]:
    units = extract_summary_units(json.loads(path.read_text(encoding="utf-8")))
    return {unit.unit_id: asdict(unit.get_context())["summary"] for unit in units}


def test_the_planted_document_differs_only_in_its_two_planted_summaries() -> None:
    clean = _map_unit_id_to_summary(_EXAMPLE / "summaries.json")
    planted = _map_unit_id_to_summary(_EXAMPLE / "summaries_with_planted_errors.json")

    assert clean.keys() == planted.keys()
    assert len(clean) == 17
    assert sorted(
        unit_id for unit_id in clean if clean[unit_id] != planted[unit_id]
    ) == [
        "src/catalog/code/common/extractors/traits_based_extraction_delegator.py#3",
        "tests/",
    ]
