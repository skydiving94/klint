"""A suite written in test code only: an outline of nested sections, from JSON.

A section is {"id": "<section id>", "text": "<text>", "sections": [...]}; the
document is the outermost section.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import ClassVar

from injector import Binder

from klint.catalog.code.common.practice_scale import PRACTICE_SCALE
from klint.catalog.common.sources.json_document_source import (
    JsonDocumentSourceFactory,
)
from klint.core.interfaces.extractor import BaseUnitExtractor
from klint.core.interfaces.suite import BaseSuite
from klint.core.models.audit_input import AuditInputKind
from klint.core.models.audit_kind import AuditKind, UnitSource
from klint.core.models.audit_order import AuditOrder
from klint.core.models.json_value import JsonValue
from klint.core.models.question_type import QuestionType
from klint.core.models.rule import AuditRule
from klint.core.models.unit import AuditableUnit
from klint.core.registry import UnitRegistry
from tests.support.notes_suite import FixedRuleLoader

OUTLINE_KIND_ID = "outline"
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


class OutlineSuite(BaseSuite):
    """Judges each section of an outline after the sections nested in it."""

    def list_audit_kinds(self) -> list[AuditKind]:
        return [
            AuditKind(
                kind_id=OUTLINE_KIND_ID,
                accepted_input_kinds=frozenset({AuditInputKind.IN_MEMORY_BYTES}),
                unit_source=UnitSource(JsonDocumentSourceFactory(), OutlineExtractor()),
                rule_loader=FixedRuleLoader([CLEAR_SECTION_RULE]),
                answer_scale=PRACTICE_SCALE,
                audit_order=AuditOrder.CHILDREN_FIRST,
            )
        ]

    def register_unit_types(self, registry: UnitRegistry) -> None:
        registry.register_unit(OutlineSectionUnit)


def add_the_outline_suite(binder: Binder) -> None:
    binder.multibind(list[BaseSuite], to=[OutlineSuite])
