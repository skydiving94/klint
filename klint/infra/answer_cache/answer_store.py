"""Where the answer cache keeps answers: one JSON file per subject key.

A file holds the answers the judge gave about one subject, keyed by question,
with the klint version and the time it was written. It holds answers only,
never the subject, the questions or the API key.
"""

import json
import os
import tempfile
import warnings
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

from klint.core import KlintWarning
from klint.core.models.judging import JudgeAnswer

QuestionKeyToAnswer = dict[str, JudgeAnswer]

_ANSWERS_FIELD = "question_key_to_answer"


class FileAnswerStore:
    """Reads and writes the files of an answer cache folder.

    An entry that cannot be read, or does not have the expected shape, is
    taken as absent, with a warning. A failure to write is warned about
    once per run; the run goes on without storing.
    """

    def __init__(self, folder: Path) -> None:
        self._folder = folder
        self._has_warned_about_writing = False

    @property
    def folder(self) -> Path:
        return self._folder

    def read_answers(self, subject_key: str) -> QuestionKeyToAnswer:
        """Return the stored answers about ``subject_key``, by question key."""
        path = self._locate_entry(subject_key)
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        except OSError as error:
            self._warn_about_entry(path, error.strerror or str(error))
            return {}
        try:
            return _read_entry(json.loads(text))
        except ValueError as error:
            self._warn_about_entry(path, str(error))
            return {}

    def write_answers(
        self,
        subject_key: str,
        model_version: str,
        question_key_to_answer: QuestionKeyToAnswer,
    ) -> None:
        """Store ``question_key_to_answer`` as the answers about ``subject_key``.

        The whole entry is written, replacing the one there; the caller
        merges what it read first.
        """
        path = self._locate_entry(subject_key)
        entry = {
            "klint_version": _read_klint_version(),
            "model_version": model_version,
            "written_at": datetime.now(UTC).isoformat(timespec="seconds"),
            _ANSWERS_FIELD: {
                question_key: _write_answer(answer)
                for question_key, answer in question_key_to_answer.items()
            },
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Written whole, then moved into place, so that another run never
            # reads a half-written entry.
            file_descriptor, temporary_path = tempfile.mkstemp(
                dir=path.parent, prefix=".writing-", suffix=".json"
            )
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as file:
                json.dump(entry, file, indent=1, sort_keys=True)
            os.replace(temporary_path, path)
        except OSError as error:
            if not self._has_warned_about_writing:
                self._has_warned_about_writing = True
                warnings.warn(
                    f"The answer cache at '{self._folder}' cannot be written "
                    f"({error.strerror or error}), so this run's answers are "
                    "not kept for the next",
                    KlintWarning,
                    stacklevel=2,
                )

    def _locate_entry(self, subject_key: str) -> Path:
        # Spread over folders by the key's first characters, so that no one
        # folder grows to thousands of files.
        return self._folder / subject_key[:2] / f"{subject_key}.json"

    def _warn_about_entry(self, path: Path, reason: str) -> None:
        warnings.warn(
            f"The answer cache entry '{path}' is left out: it cannot be read "
            f"({reason}), so its questions are asked again",
            KlintWarning,
            stacklevel=3,
        )


def _read_klint_version() -> str:
    try:
        return metadata.version("klint-auditor")
    except metadata.PackageNotFoundError:
        return "unknown"


def _write_answer(answer: JudgeAnswer) -> dict[str, object]:
    return {
        "question_id": answer.question_id,
        "choice_key": answer.choice_key,
        "confidence": answer.confidence,
        "choice_key_to_probability": answer.choice_key_to_probability,
    }


def _read_entry(raw_entry: object) -> QuestionKeyToAnswer:
    """Return the answers in a stored entry; raise ValueError on another shape."""
    if not isinstance(raw_entry, dict):
        raise ValueError("the entry is not a JSON object")
    raw_answers: object = raw_entry.get(_ANSWERS_FIELD)
    if not isinstance(raw_answers, dict):
        raise ValueError(f"'{_ANSWERS_FIELD}' is not a JSON object")
    return {
        str(question_key): _read_answer(raw_answer)
        for question_key, raw_answer in raw_answers.items()
    }


def _read_answer(raw_answer: object) -> JudgeAnswer:
    if not isinstance(raw_answer, dict):
        raise ValueError("an answer is not a JSON object")
    question_id: object = raw_answer.get("question_id")
    choice_key: object = raw_answer.get("choice_key")
    if not isinstance(question_id, str) or not isinstance(choice_key, str):
        raise ValueError("an answer has no question id or choice")
    confidence: object = raw_answer.get("confidence")
    if confidence is not None and (
        isinstance(confidence, bool) or not isinstance(confidence, int | float)
    ):
        raise ValueError(f"the confidence for '{question_id}' is not a number")
    raw_probabilities: object = raw_answer.get("choice_key_to_probability")
    choice_key_to_probability: dict[str, float] | None = None
    if raw_probabilities is not None:
        if not isinstance(raw_probabilities, dict):
            raise ValueError(f"the probabilities for '{question_id}' are not an object")
        choice_key_to_probability = {}
        for key, raw_probability in raw_probabilities.items():
            if isinstance(raw_probability, bool) or not isinstance(
                raw_probability, int | float
            ):
                raise ValueError(f"a probability for '{question_id}' is not a number")
            choice_key_to_probability[str(key)] = float(raw_probability)
    return JudgeAnswer(
        question_id=question_id,
        choice_key=choice_key,
        confidence=None if confidence is None else float(confidence),
        choice_key_to_probability=choice_key_to_probability,
    )
