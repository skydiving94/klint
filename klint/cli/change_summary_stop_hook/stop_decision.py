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

    For BLOCK, message is the reason the agent is told, and must be given.
    For ALLOW, message is a warning shown to the user, or None for none.
    """

    verdict: StopVerdict
    message: str | None = None

    @classmethod
    def allow(cls, warning: str | None = None) -> "StopDecision":
        return cls(StopVerdict.ALLOW, warning)

    @classmethod
    def block(cls, reason: str) -> "StopDecision":
        return cls(StopVerdict.BLOCK, reason)

    def format_hook_output(self) -> str:
        """Return what the hook prints on stdout: JSON, or nothing for a plain stop.

        A message too long for Claude Code to read whole is cut, with a note.
        """
        if self.message is None:
            return ""
        message = self.message
        while True:
            output = self._format_output_holding(message)
            overflow = len(output) - _OUTPUT_LIMIT
            if overflow <= 0:
                return output
            message = message[: len(message) - overflow - len(_CUT_MARKER)]
            message = f"{message}{_CUT_MARKER}"

    def _format_output_holding(self, message: str) -> str:
        match self.verdict:
            case StopVerdict.BLOCK:
                fields = {"decision": "block", "reason": message}
            case StopVerdict.ALLOW:
                fields = {"systemMessage": message}
        return json.dumps(fields, ensure_ascii=False)
