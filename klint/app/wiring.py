"""Binds what klint's constructors cannot state themselves.

Each class asks for what it needs with @inject. What is left here is what
its signature cannot express: the settings and what is chosen from them.
The suites an audit draws on are added by the caller; each one binds what
it needs itself.
"""

from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import NewType, assert_never

from injector import Binder, Injector, Module, provider, singleton

from klint.app.audit_kind_registry import AuditKindRegistry
from klint.app.judge_mode import JudgeMode
from klint.app.settings import AppSettings
from klint.catalog.common.file_traits_identifiers.extension_identifier import (
    ExtensionFileTraitsIdentifier,
)
from klint.core.interfaces.file_traits_identifier import BaseFileTraitsIdentifier
from klint.core.interfaces.judge import BaseJudge
from klint.core.interfaces.rule_loader import BaseRuleLoader
from klint.core.interfaces.suite import BaseSuite
from klint.core.models.audit_kind import AuditKind
from klint.core.registry import UnitRegistry
from klint.infra.language_to_file_extensions_loader.json_loader import (
    load_file_extension_to_language,
)
from klint.infra.rule_loader.json_rule_loader import JsonRuleLoader
from klint.infra.system_one.remote import RemoteSystemOneJudge

# The language each file extension stands for, loaded once per injector.
FileExtensionToLanguage = NewType("FileExtensionToLanguage", Mapping[str, str])

Override = Module | Callable[[Binder], None]


class KlintModule(Module):
    """Binds everything an audit needs that one AppSettings decides.

    kind_id_to_rule_pack_override names, for a kind of audit, one file that
    replaces every built-in pack, the fallback ones too, so that its rules
    are asked about every unit of that kind.
    """

    def __init__(
        self,
        settings: AppSettings,
        kind_id_to_rule_pack_override: Mapping[str, Path],
    ) -> None:
        self._settings = settings
        self._kind_id_to_rule_pack_override = dict(kind_id_to_rule_pack_override)

    def configure(self, binder: Binder) -> None:
        binder.bind(AppSettings, to=self._settings)
        # The suites an audit can draw on; each one adds itself.
        binder.multibind(list[BaseSuite], to=[])

    @singleton
    @provider
    def provide_unit_registry(self, suites: list[BaseSuite]) -> UnitRegistry:
        registry = UnitRegistry()
        for suite in suites:
            suite.register_unit_types(registry)
        return registry

    @singleton
    @provider
    def provide_judge(self, settings: AppSettings) -> BaseJudge:
        # A single binding, so that the remote mode never loads the model.
        match settings.kev_mode:
            case JudgeMode.LOCAL:
                from klint.infra.system_one.local import LocalKevJudge

                return LocalKevJudge(checkpoint=settings.model_name)
            case JudgeMode.REMOTE:
                return RemoteSystemOneJudge(
                    model_name=settings.model_name,
                    base_url=settings.kev_base_url,
                    api_key=settings.kev_api_key,
                )
            case _:
                assert_never(settings.kev_mode)

    @singleton
    @provider
    def provide_file_extension_to_language(
        self, settings: AppSettings
    ) -> FileExtensionToLanguage:
        return FileExtensionToLanguage(
            load_file_extension_to_language(settings.language_to_file_extensions_path)
        )

    @singleton
    @provider
    def provide_file_traits_identifier(
        self, file_extension_to_language: FileExtensionToLanguage
    ) -> BaseFileTraitsIdentifier:
        return ExtensionFileTraitsIdentifier(file_extension_to_language)

    @singleton
    @provider
    def provide_rule_loader(
        self,
        settings: AppSettings,
        registry: UnitRegistry,
        file_extension_to_language: FileExtensionToLanguage,
    ) -> BaseRuleLoader:
        # The built-in packs, chosen by the traits of each file.
        return JsonRuleLoader(
            settings.built_in_rule_packs,
            settings.fallback_rule_packs,
            registry,
            set(file_extension_to_language.values()),
            project_rule_packs=settings.project_rule_packs,
        )

    @singleton
    @provider
    def provide_audit_kind_registry(
        self,
        settings: AppSettings,
        suites: list[BaseSuite],
        registry: UnitRegistry,
        file_extension_to_language: FileExtensionToLanguage,
    ) -> AuditKindRegistry:
        known_languages = set(file_extension_to_language.values())

        def apply_rule_pack_override(audit_kind: AuditKind) -> AuditKind:
            rule_pack_override = self._kind_id_to_rule_pack_override.get(
                audit_kind.kind_id
            )
            if rule_pack_override is None:
                return audit_kind
            return replace(
                audit_kind,
                rule_loader=JsonRuleLoader(
                    (rule_pack_override,),
                    (rule_pack_override,),
                    registry,
                    known_languages,
                    project_rule_packs=settings.project_rule_packs,
                ),
            )

        return AuditKindRegistry(
            [
                apply_rule_pack_override(audit_kind)
                for suite in suites
                for audit_kind in suite.list_audit_kinds()
            ]
        )


def create_injector(
    settings: AppSettings,
    *overrides: Override,
    kind_id_to_rule_pack_override: Mapping[str, Path] | None = None,
) -> Injector:
    """Return an injector for ``settings``; overrides add or replace bindings.

    No suite is added: an override adds each one the audit draws on.
    kind_id_to_rule_pack_override is as KlintModule takes it.
    """
    return Injector(
        [KlintModule(settings, kind_id_to_rule_pack_override or {}), *overrides]
    )
