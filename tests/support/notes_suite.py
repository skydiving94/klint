"""A suite written in test code only: notes, judged polite or rude."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from injector import Binder, inject

from klint.catalog.common.sources.directory_tree_source import (
    DirectoryTreeSourceFactory,
)
from klint.catalog.common.sources.json_document_source import (
    JsonDocumentSourceFactory,
)
from klint.cli.runner import AuditCommand
from klint.core.interfaces.extractor import BaseUnitExtractor
from klint.core.interfaces.file_traits_identifier import BaseFileTraitsIdentifier
from klint.core.interfaces.rule_loader import BaseRuleLoader
from klint.core.interfaces.suite import BaseSuite
from klint.core.models.audit_input import AuditInputKind
from klint.core.models.audit_kind import AuditKind, UnitSource
from klint.core.models.file_traits import FileTraits
from klint.core.models.ignored_names import IgnoredNames
from klint.core.models.json_value import JsonValue
from klint.core.models.question_type import QuestionType
from klint.core.models.rule import AuditRule
from klint.core.models.scale import AnswerChoice, AnswerScale
from klint.core.models.scanned_tree import ScannedTarget
from klint.core.models.unit import AuditableUnit
from klint.core.registry import UnitRegistry

NOTES_KIND_ID = "notes"
# Notes held in one JSON document: {"notes": {"<note id>": "<text>", ...}}.
NOTES_DOCUMENT_KIND_ID = "notes_document"
POLITENESS_SCALE = AnswerScale(
    name="politeness",
    choices=(
        AnswerChoice(
            key="polite", label="Polite", criterion="The note is polite.", sort_rank=2
        ),
        AnswerChoice(
            key="rude", label="Rude", criterion="The note is rude.", is_problem=True
        ),
    ),
)
POLITE_RULE = AuditRule(
    rule_id="polite_note",
    question_type=QuestionType.CHOICE,
    instructions="Is the note polite?",
    target_unit_types=["note"],
)
NOTES_COMMAND = AuditCommand(
    name="klint-notes",
    description="Audits notes",
    target_argument_name="folder",
    target_argument_help="Folder of notes",
    audit_kind_id=NOTES_KIND_ID,
    json_key="examined_notes",
)


@dataclass(frozen=True)
class NoteUnit(AuditableUnit):
    """One note: the text of a .txt file."""

    unit_type: ClassVar[str] = "note"

    text: str = ""

    def get_content(self) -> str:
        return self.text


class NoteExtractor(BaseUnitExtractor[ScannedTarget]):
    """Reads each .txt file of a target as one note."""

    async def extract(self, audit_input: ScannedTarget) -> list[AuditableUnit]:
        return [
            NoteUnit(unit_id=str(scanned_file.path), text=scanned_file.path.read_text())
            for scanned_file in audit_input.files
            if scanned_file.path.suffix == ".txt"
        ]


class NoteDocumentExtractor(BaseUnitExtractor[JsonValue]):
    """Reads each entry under "notes" in a JSON document as one note."""

    async def extract(self, audit_input: JsonValue) -> list[AuditableUnit]:
        notes = audit_input.get("notes") if isinstance(audit_input, Mapping) else None
        if not isinstance(notes, Mapping):
            raise ValueError("A notes document holds an object under 'notes'")
        return [
            NoteUnit(unit_id=note_id, text=str(text)) for note_id, text in notes.items()
        ]


class FixedRuleLoader(BaseRuleLoader):
    """Gives the same rules for every file; a custom rules file is not read."""

    def __init__(self, rules: list[AuditRule]) -> None:
        self._rules = rules

    async def load_rules(
        self, traits: FileTraits, custom_rules_source: str | Path | None = None
    ) -> list[AuditRule]:
        del traits, custom_rules_source
        return list(self._rules)


class NotesSuite(BaseSuite):
    """Audits notes for politeness; a scan leaves out the drafts folder."""

    @inject
    def __init__(self, file_traits_identifier: BaseFileTraitsIdentifier) -> None:
        self._directory_tree_source_factory = DirectoryTreeSourceFactory(
            file_traits_identifier,
            IgnoredNames(directory_names=frozenset({"drafts"})),
        )

    def list_audit_kinds(self) -> list[AuditKind]:
        return [
            AuditKind(
                kind_id=NOTES_KIND_ID,
                accepted_input_kinds=frozenset({AuditInputKind.DISK_PATH}),
                unit_source=UnitSource(
                    self._directory_tree_source_factory, NoteExtractor()
                ),
                rule_loader=FixedRuleLoader([POLITE_RULE]),
                answer_scale=POLITENESS_SCALE,
            )
        ]

    def register_unit_types(self, registry: UnitRegistry) -> None:
        registry.register_unit(NoteUnit)


class NotesDocumentSuite(BaseSuite):
    """Audits the notes of one JSON document, from a file or from memory."""

    def list_audit_kinds(self) -> list[AuditKind]:
        return [
            AuditKind(
                kind_id=NOTES_DOCUMENT_KIND_ID,
                accepted_input_kinds=frozenset(
                    {AuditInputKind.DISK_PATH, AuditInputKind.IN_MEMORY_BYTES}
                ),
                unit_source=UnitSource(
                    JsonDocumentSourceFactory(), NoteDocumentExtractor()
                ),
                rule_loader=FixedRuleLoader([POLITE_RULE]),
                answer_scale=POLITENESS_SCALE,
            )
        ]

    def register_unit_types(self, registry: UnitRegistry) -> None:
        registry.register_unit(NoteUnit)


def add_the_notes_suite(binder: Binder) -> None:
    binder.multibind(list[BaseSuite], to=[NotesSuite])


def add_the_notes_document_suite(binder: Binder) -> None:
    binder.multibind(list[BaseSuite], to=[NotesDocumentSuite])
