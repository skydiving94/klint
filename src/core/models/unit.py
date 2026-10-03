from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Type


@dataclass(frozen=True)
class AuditableUnit(ABC):
    """Abstract base node for any auditable code or project structure unit.

    unit_type is a per-class string tag (not a per-instance field). Each
    concrete subclass declares its own constant and is auto-registered
    here via __init_subclass__ -- this is the tag JSON rules use in
    target_unit_types; there's no separate enum to keep in sync.

    language is the language this unit's content is written in, programming
    or natural (for example "python" or "english"). It is None when unknown
    or when the content has no language, such as an image.
    """

    unit_id: str
    language: Optional[str] = field(default=None, kw_only=True)

    unit_type: ClassVar[str]
    _registry: ClassVar[Dict[str, Type["AuditableUnit"]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        tag = getattr(cls, "unit_type", None)
        if tag:
            AuditableUnit._registry[tag] = cls

    @classmethod
    def known_unit_types(cls) -> List[str]:
        """All unit_type tags currently registered by a concrete subclass."""
        return sorted(AuditableUnit._registry.keys())

    @abstractmethod
    def get_content(self) -> str:
        """Return the string representation of this unit (and any child units) for evaluation."""
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Return unit-specific context metadata to attach to an AuditFinding."""
        pass
