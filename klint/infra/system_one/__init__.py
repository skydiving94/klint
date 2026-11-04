"""Judges that answer in the System One format: over HTTP, or in this process."""

from typing import TYPE_CHECKING

from klint.infra.system_one.http_judge import HttpSystemOneJudge

if TYPE_CHECKING:
    from klint.infra.system_one.in_process_judge import InProcessSystemOneJudge

__all__ = ["HttpSystemOneJudge", "InProcessSystemOneJudge"]


def __getattr__(name: str) -> object:
    # The in-process judge loads the model runtime, so it is imported only
    # when it is asked for.
    if name == "InProcessSystemOneJudge":
        from klint.infra.system_one.in_process_judge import InProcessSystemOneJudge

        return InProcessSystemOneJudge
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
