"""How a request is keyed in the answer cache.

A key names what the judge would be shown, so that two requests share a key
only when the judge would get the same input, from the same model.
"""

import hashlib
import json

from klint.core.models.judging import JudgeQuestion


def build_subject_key(model_version: str, subject: str) -> str:
    """Return the key of ``subject`` as read by the model ``model_version``."""
    return _hash_json({"model_version": model_version, "subject": subject})


def build_question_key(question: JudgeQuestion) -> str:
    """Return the key of ``question``: its id, type, text and each criterion."""
    return _hash_json(
        {
            "question_id": question.question_id,
            "question_type": question.question_type.value,
            "question": question.question,
            "choice_key_to_criterion": question.choice_key_to_criterion,
        }
    )


def _hash_json(value: dict[str, object]) -> str:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
