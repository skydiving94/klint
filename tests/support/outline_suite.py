"""A suite written in test code only: an outline of nested sections, from JSON.

A section is {"id": "<section id>", "text": "<text>", "sections": [...]}; the
document is the outermost section.
"""

import asyncio
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import ClassVar

from injector import Binder

from klint.app.pipeline.audit_pipeline import AuditOutcome, AuditRequest
from klint.catalog.code.common.practice_scale import PRACTICE_SCALE
from klint.catalog.common.sources.json_document_source import (
    JsonDocumentSourceFactory,
)
from klint.cli.runner import AuditCommand
from klint.core.interfaces.extractor import BaseUnitExtractor
from klint.core.interfaces.judge import BaseJudge
from klint.core.interfaces.renderer import BaseUnitRenderer
from klint.core.interfaces.suite import BaseSuite
from klint.core.models.audit_input import AuditInputKind, InMemoryBytesInput
from klint.core.models.audit_kind import AuditKind, UnitSource
from klint.core.models.audit_order import AuditOrder
from klint.core.models.json_value import JsonValue
from klint.core.models.question_type import QuestionType
from klint.core.models.render_input import RenderInput
from klint.core.models.rule import AuditRule
from klint.core.models.unit import AuditableUnit
from klint.core.registry import UnitRegistry
from tests.support.builders import build_audit_pipeline
from tests.support.notes_suite import FixedRuleLoader

OUTLINE_KIND_ID = "outline"
# The same audit, with each section described with the findings on the
# sections directly inside it.
SUMMARIZED_OUTLINE_KIND_ID = "summarized_outline"
OUTLINE_COMMAND = AuditCommand(
    name="klint-outline",
    description="Audits an outline",
    target_argument_name="outline",
    target_argument_help="Outline JSON file",
    audit_kind_id=OUTLINE_KIND_ID,
    json_key="examined_sections",
)
CLEAR_SECTION_RULE = AuditRule(
    rule_id="clear_section",
    question_type=QuestionType.CHOICE,
    instructions="Is the section clear?",
    target_unit_types=["outline_section"],
)


@dataclass(frozen=True)
class OutlineSectionUnit(AuditableUnit):
    """One section of an outline, holding the sections nested in it."""

    unit_type: ClassVar[str] = "outline_section"

    text: str = ""
    sections: tuple["OutlineSectionUnit", ...] = ()

    def get_content(self) -> str:
        return self.text

    def children(self) -> Sequence[AuditableUnit]:
        return self.sections


class OutlineExtractor(BaseUnitExtractor[JsonValue]):
    """Reads an outline document into its sections, each before its own."""

    async def extract(self, audit_input: JsonValue) -> list[AuditableUnit]:
        return list(_yield_section_and_nested(_read_section(audit_input)))


def _read_section(raw_section: JsonValue) -> OutlineSectionUnit:
    if not isinstance(raw_section, Mapping):
        raise ValueError("An outline section is an object")
    raw_sections = raw_section.get("sections", [])
    if not isinstance(raw_sections, Sequence) or isinstance(raw_sections, str):
        raise ValueError("The sections of an outline section are a list")
    return OutlineSectionUnit(
        unit_id=str(raw_section["id"]),
        text=str(raw_section.get("text", "")),
        sections=tuple(_read_section(raw) for raw in raw_sections),
    )


def _yield_section_and_nested(
    section: OutlineSectionUnit,
) -> "Sequence[OutlineSectionUnit]":
    nested: list[OutlineSectionUnit] = [section]
    for child in section.sections:
        nested.extend(_yield_section_and_nested(child))
    return nested


class SummarizedSectionRenderer(BaseUnitRenderer):
    """Writes a section's text, then one line per finding on its subsections."""

    def render_subject(self, render_input: RenderInput) -> str:
        lines = [render_input.unit.get_content()]
        lines.extend(
            f"{finding.unit_id}: {finding.rule_id} = {finding.answer.key}"
            for finding in render_input.child_findings
        )
        return "\n".join(lines)


class OutlineSuite(BaseSuite):
    """Judges each section of an outline after the sections nested in it."""

    def list_audit_kinds(self) -> list[AuditKind]:
        outline_kind = AuditKind(
            kind_id=OUTLINE_KIND_ID,
            accepted_input_kinds=frozenset(
                {AuditInputKind.DISK_PATH, AuditInputKind.IN_MEMORY_BYTES}
            ),
            unit_source=UnitSource(JsonDocumentSourceFactory(), OutlineExtractor()),
            rule_loader=FixedRuleLoader([CLEAR_SECTION_RULE]),
            answer_scale=PRACTICE_SCALE,
            audit_order=AuditOrder.CHILDREN_FIRST,
        )
        return [
            outline_kind,
            replace(
                outline_kind,
                kind_id=SUMMARIZED_OUTLINE_KIND_ID,
                unit_class_to_renderer={
                    OutlineSectionUnit: SummarizedSectionRenderer()
                },
            ),
        ]

    def register_unit_types(self, registry: UnitRegistry) -> None:
        registry.register_unit(OutlineSectionUnit)


def add_the_outline_suite(binder: Binder) -> None:
    binder.multibind(list[BaseSuite], to=[OutlineSuite])


# A three-level outline: the book, its chapters, and their sections.
OUTLINE: JsonValue = {
    "id": "book",
    "text": "The book.",
    "sections": [
        {
            "id": "chapter 1",
            "text": "Chapter 1.",
            "sections": [
                {"id": "section 1.1", "text": "Section 1.1."},
                {"id": "section 1.2", "text": "Section 1.2."},
            ],
        },
        {
            "id": "chapter 2",
            "text": "Chapter 2.",
            "sections": [{"id": "section 2.1", "text": "Section 2.1."}],
        },
    ],
}
SUBJECT_TO_PARENT_SUBJECT = {
    "Chapter 1.": "The book.",
    "Chapter 2.": "The book.",
    "Section 1.1.": "Chapter 1.",
    "Section 1.2.": "Chapter 1.",
    "Section 2.1.": "Chapter 2.",
}


def run_outline_audit(
    judge: BaseJudge,
    min_confidence: float = 0.0,
    outline: JsonValue = OUTLINE,
    audit_kind_id: str = OUTLINE_KIND_ID,
) -> AuditOutcome:
    """Audit ``outline``, held in memory, with a kind of the outline suite."""
    pipeline = build_audit_pipeline(judge, overrides=[add_the_outline_suite])
    request = AuditRequest(
        audit_input=InMemoryBytesInput(
            content=json.dumps(outline).encode(), media_type="application/json"
        ),
        audit_kind_id=audit_kind_id,
        min_confidence=min_confidence,
    )
    return asyncio.run(pipeline.run_audit(request))
