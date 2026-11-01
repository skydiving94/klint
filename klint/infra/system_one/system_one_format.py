"""The System One request and response, as /v1/systemone and kev exchange them."""

from typing import TypedDict

from klint.core.models.judge_exchange import JudgeAnswer, JudgeRequest


class SystemOneQuestion(TypedDict):
    """One question as System One reads it."""

    type: str
    instructions: str
    criteria: dict[str, str]


def build_system_one_questions(request: JudgeRequest) -> dict[str, SystemOneQuestion]:
    """Return the questions of ``request`` as System One reads them, keyed by id."""
    return {
        question.question_id: {
            "type": question.question_type.value,
            "instructions": question.question,
            "criteria": dict(question.choice_key_to_criterion),
        }
        for question in request.questions
    }


def read_system_one_answers(response: object) -> list[JudgeAnswer]:
    """Return the answers in a System One response.

    An answer that names no choice is left out, as is a response with no
    answers. Raises ValueError when the response does not have the System
    One shape.
    """
    if not isinstance(response, dict):
        raise ValueError("The judge's response is not a JSON object")
    question_id_to_raw_answer: object = response.get("answers", {})
    if not isinstance(question_id_to_raw_answer, dict):
        raise ValueError("The judge's 'answers' is not a JSON object")
    answers: list[JudgeAnswer] = []
    for question_id, raw_answer in question_id_to_raw_answer.items():
        answer = _read_answer(str(question_id), raw_answer)
        if answer is not None:
            answers.append(answer)
    return answers


def _read_answer(question_id: str, raw_answer: object) -> JudgeAnswer | None:
    """Return the answer to ``question_id``; None when it names no choice."""
    if not isinstance(raw_answer, dict):
        raise ValueError(f"The judge's answer to '{question_id}' is not a JSON object")
    choice_key: object = raw_answer.get("choice")
    if choice_key is None:
        return None
    if not isinstance(choice_key, str):
        raise ValueError(f"The judge's choice for '{question_id}' is not text")
    return JudgeAnswer(
        question_id=question_id,
        choice_key=choice_key,
        confidence=_read_number(
            raw_answer.get("confidence"), f"confidence for '{question_id}'"
        ),
        choice_key_to_probability=_read_choice_key_to_probability(
            raw_answer.get("probabilities"), question_id
        ),
    )


def _read_number(raw_number: object, description: str) -> float | None:
    """Return ``raw_number``, None when it is null; ``description`` names it."""
    if raw_number is None:
        return None
    if isinstance(raw_number, bool) or not isinstance(raw_number, int | float):
        raise ValueError(f"The judge's {description} is not a number")
    return raw_number


def _read_choice_key_to_probability(
    raw_choice_key_to_probability: object, question_id: str
) -> dict[str, float] | None:
    if raw_choice_key_to_probability is None:
        return None
    if not isinstance(raw_choice_key_to_probability, dict):
        raise ValueError(
            f"The judge's probabilities for '{question_id}' are not a JSON object"
        )
    choice_key_to_probability: dict[str, float] = {}
    for choice_key, raw_probability in raw_choice_key_to_probability.items():
        description = f"probability of '{choice_key}' for '{question_id}'"
        probability = _read_number(raw_probability, description)
        if probability is None:
            raise ValueError(f"The judge's {description} is not a number")
        choice_key_to_probability[str(choice_key)] = probability
    return choice_key_to_probability
