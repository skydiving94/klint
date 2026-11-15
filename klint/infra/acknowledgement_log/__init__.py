"""The acknowledgement log on disk: one JSON file per entry, committed with the code."""

from klint.infra.acknowledgement_log.file_acknowledgement_log import (
    FileAcknowledgementLog,
)

__all__ = ["FileAcknowledgementLog"]
