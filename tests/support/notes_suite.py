"""A suite written in test code only: notes, judged polite or rude."""

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from injector import Binder

from klint.cli.runner import AuditCommand
from klint.core.interfaces.extractor import BaseUnitExtractor
from klint.core.interfaces.rule_loader import BaseRuleLoader
from klint.core.interfaces.suite import BaseSuite
from klint.core.models.audit_kind import AuditKind
from klint.core.models.file_traits import FileTraits
from klint.core.models.ignored_names import IgnoredNames
from klint.core.models.question_type import QuestionType
from klint.core.models.rule import AuditRule
from klint.core.models.scale import AnswerChoice, AnswerScale
from klint.core.models.scanned_tree import ScannedTarget
from klint.core.models.unit import AuditableUnit
from klint.core.registry import UnitRegistry

NOTES_KIND_ID = "notes"
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

    def list_audit_kinds(self) -> list[AuditKind]:
        return [
            AuditKind(
                kind_id=NOTES_KIND_ID,
                extractor=NoteExtractor(),
                rule_loader=FixedRuleLoader([POLITE_RULE]),
                answer_scale=POLITENESS_SCALE,
                ignored_names=IgnoredNames(directory_names=frozenset({"drafts"})),
            )
        ]

    def register_unit_types(self, registry: UnitRegistry) -> None:
        registry.register_unit(NoteUnit)


def add_the_notes_suite(binder: Binder) -> None:
    binder.multibind(list[BaseSuite], to=[NotesSuite])
