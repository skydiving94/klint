"""The rule selection stage: the rules a run asks about its units."""

from collections.abc import Sequence
from pathlib import Path

from klint.core.models.audit_kind import AuditKind
from klint.core.models.file_traits import FileTraits
from klint.core.models.rule import AuditRule
from klint.core.models.unit import AuditableUnit


class RuleSelection:
    """Loads the rules of a kind of audit by the traits of the units."""

    async def select_rules(
        self,
        units: Sequence[AuditableUnit],
        audit_kind: AuditKind,
        custom_rules_source: Path | None = None,
    ) -> dict[str | None, list[AuditRule]]:
        """Return the rules to ask, for each language the units are written in.

        The key None is for units whose language is not identified. The rules
        in ``custom_rules_source``, when given, merge over the loaded ones.
        Raises when a rules file cannot be used. With no unit, the rules are
        still loaded once, so that such a file stops the audit whatever the
        target holds.
        """
        languages = list(dict.fromkeys(unit.language for unit in units)) or [None]
        return {
            language: await audit_kind.rule_loader.load_rules(
                FileTraits(language=language), custom_rules_source
            )
            for language in languages
        }
