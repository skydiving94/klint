"""Reads an audit input as one JSON document, from a file on disk or from memory."""

import asyncio
import json

from klint.core.interfaces.scan_progress_listener import BaseScanProgressListener
from klint.core.interfaces.source import BaseAuditSource, BaseAuditSourceFactory
from klint.core.models.audit_input import (
    AuditInput,
    DiskPathInput,
    InMemoryBytesInput,
)
from klint.core.models.json_value import JsonValue

# The media type of JSON content; a type with the "+json" suffix is JSON too.
JSON_MEDIA_TYPE = "application/json"
_JSON_MEDIA_TYPE_SUFFIX = "+json"


class JsonDocumentSource(BaseAuditSource[JsonValue]):
    """Parses one JSON document, read from a file or held in memory."""

    def __init__(self, audit_input: AuditInput) -> None:
        self._audit_input = audit_input
        self._scanned_file_count = 0

    async def read_input(self) -> JsonValue:
        """Return the parsed document.

        Raises OSError when the file cannot be read, and ValueError when the
        content is not valid JSON.
        """
        match self._audit_input:
            case DiskPathInput(path=path):
                content = await asyncio.to_thread(path.read_bytes)
                self._scanned_file_count = 1
                where = f"File '{path}'"
            case InMemoryBytesInput(content=content):
                where = "The content in memory"
        try:
            document: JsonValue = json.loads(content)
        except ValueError as error:
            raise ValueError(f"{where} is not valid JSON: {error}") from error
        return document

    def count_scanned_files(self) -> int:
        return self._scanned_file_count


class JsonDocumentSourceFactory(BaseAuditSourceFactory[JsonValue]):
    """Makes a JSON document source for a file on disk or for JSON in memory."""

    def create_source(
        self,
        audit_input: AuditInput,
        scan_progress_listener: BaseScanProgressListener | None = None,
    ) -> JsonDocumentSource:
        """Return the source of ``audit_input``; no directory is scanned.

        Raises ValueError when content in memory has a media type other than
        JSON's.
        """
        del scan_progress_listener
        if isinstance(audit_input, InMemoryBytesInput) and not _is_json_media_type(
            audit_input.media_type
        ):
            raise ValueError(
                f"A JSON document is read from content of media type "
                f"'{JSON_MEDIA_TYPE}', not '{audit_input.media_type}'"
            )
        return JsonDocumentSource(audit_input)


def _is_json_media_type(media_type: str) -> bool:
    """Return True for JSON's media type, any parameters such as charset aside."""
    essence = media_type.split(";", 1)[0].strip().lower()
    return essence == JSON_MEDIA_TYPE or essence.endswith(_JSON_MEDIA_TYPE_SUFFIX)
