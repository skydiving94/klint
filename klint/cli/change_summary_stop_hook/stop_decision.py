"""What a Stop hook answers: let the agent stop, or send it back to work."""

import json
from dataclasses import dataclass
from enum import StrEnum

# Claude Code reads at most this many characters of what a hook prints.
_OUTPUT_LIMIT = 10_000
_CUT_MARKER = "\n[... cut to fit what Claude Code reads of a hook's output]"


class StopVerdict(StrEnum):
    """Whether the agent may stop."""

    ALLOW = "allow"
    BLOCK = "block"


@dataclass(frozen=True)
class StopDecision:
    """The hook's answer to one Stop event.

    For BLOCK, reason is what the agent is told, and must be given. warning
    is shown to the user, with either verdict; None for none.
    """

    verdict: StopVerdict
    reason: str | None = None
    warning: str | None = None

    @classmethod
    def allow(cls, warning: str | None = None) -> "StopDecision":
        return cls(StopVerdict.ALLOW, warning=warning)

    @classmethod
    def block(cls, reason: str) -> "StopDecision":
        return cls(StopVerdict.BLOCK, reason=reason)

    def add_warning(self, warning: str | None) -> "StopDecision":
        """Return the decision with ``warning`` put before any warning it holds."""
        if warning is None:
            return self
        joined = warning if self.warning is None else f"{warning}\n{self.warning}"
        return StopDecision(self.verdict, self.reason, joined)

    def format_hook_output(self) -> str:
        """Return what the hook prints on stdout: JSON, or nothing for a plain stop.

        A reason or warning too long for Claude Code to read whole is cut,
        with a note.
        """
        if self.reason is None and self.warning is None:
            return ""
        reason, warning = self.reason, self.warning
        while True:
            output = self._format_output_holding(reason, warning)
            overflow = len(output) - _OUTPUT_LIMIT
            if overflow <= 0:
                return output
            if len(reason or "") >= len(warning or ""):
                reason = _cut(reason or "", overflow)
            else:
                warning = _cut(warning or "", overflow)

    def _format_output_holding(self, reason: str | None, warning: str | None) -> str:
        fields: dict[str, str] = {}
        if self.verdict is StopVerdict.BLOCK:
            fields["decision"] = "block"
            fields["reason"] = reason or ""
        if warning is not None:
            fields["systemMessage"] = warning
        return json.dumps(fields, ensure_ascii=False)


def _cut(text: str, overflow: int) -> str:
    """Return ``text`` shorter by ``overflow`` characters, ending in the cut marker."""
    return f"{text[: len(text) - overflow - len(_CUT_MARKER)]}{_CUT_MARKER}"
