"""The rules a path would be asked, and what one rule says, without any judging."""

from dataclasses import dataclass

from injector import inject

from klint.app.audit_kind_registry import AuditKindRegistry
from klint.app.pipeline.audit_preparer import AuditPreparer
from klint.core.interfaces import BaseRuleSource
from klint.core.models.audits import AuditInput
from klint.core.models.rules import (
    AppliedRuleExclusion,
    AuditRule,
    RulePackSpec,
    RuleSpec,
)


@dataclass(frozen=True)
class AskedRule:
    """One rule an audit would ask, and the units it would be asked about."""

    rule: AuditRule
    unit_ids: tuple[str, ...]


@dataclass(frozen=True)
class AskedRules:
    """What one kind of audit would ask about an input, rule by rule."""

    audit_kind_id: str
    rules: tuple[AskedRule, ...]
    applied_rule_exclusions: tuple[AppliedRuleExclusion, ...]


@dataclass(frozen=True)
class RuleDefinition:
    """One rule as a pack defines it."""

    pack: RulePackSpec
    rule: RuleSpec


class RuleLookup:
    """Answers what an audit would ask, from the kinds offered and their packs."""

    @inject
    def __init__(
        self, audit_kind_registry: AuditKindRegistry, audit_preparer: AuditPreparer
    ) -> None:
        self._audit_kind_registry = audit_kind_registry
        self._audit_preparer = audit_preparer

    async def list_asked_rules(
        self,
        audit_input: AuditInput,
        audit_kind_id: str,
        custom_rule_source: BaseRuleSource | None = None,
    ) -> AskedRules:
        """Return the rules an audit of ``audit_input`` would ask, in load order.

        The audit is prepared as a run would, the project's exclusions
        applied, and no judge is asked. Raises as the run would when the
        input or a rule source cannot be used.
        """
        audit_kind = self._audit_kind_registry.find_audit_kind(audit_kind_id)
        portfolio = await self._audit_preparer.prepare_audit(
            audit_input, audit_kind, custom_rule_source=custom_rule_source
        )
        rule_id_to_rule: dict[str, AuditRule] = {}
        rule_id_to_unit_ids: dict[str, list[str]] = {}
        for unit in portfolio.units:
            for rule in portfolio.rule_set.select_rules_for(unit):
                rule_id_to_rule.setdefault(rule.rule_id, rule)
                rule_id_to_unit_ids.setdefault(rule.rule_id, []).append(unit.unit_id)
        return AskedRules(
            audit_kind_id=audit_kind_id,
            rules=tuple(
                AskedRule(rule, tuple(rule_id_to_unit_ids[rule_id]))
                for rule_id, rule in rule_id_to_rule.items()
            ),
            applied_rule_exclusions=portfolio.rule_set.list_applied_rule_exclusions(),
        )

    def find_rule_definitions(self, rule_id: str) -> list[RuleDefinition]:
        """Return each definition of ``rule_id``, in the order the packs merge.

        A rule may be defined in several packs, each for its own units. A
        pack that serves several kinds of audit is read once. Empty when no
        pack defines the rule.
        """
        packs: dict[RulePackSpec, None] = {}
        for audit_kind in self._audit_kind_registry.list_audit_kinds():
            packs.update(dict.fromkeys(audit_kind.rule_loader.read_rule_packs()))
        return [
            RuleDefinition(pack, rule)
            for pack in packs
            for rule in pack.rules
            if rule.rule_id == rule_id
        ]
