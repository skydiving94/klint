"""The confidence a finding needs to block a commit: the judge's own, or the setting."""

# The least confidence a failure needs to block a commit, by the model name
# the judge settings give it. Kev's confidences run lower than Jev's on the
# code-unit accuracy set, so it blocks from 0.5 and Jev from 0.8.
model_name_to_commit_threshold = {
    "jaredpalmer/kev-0.8b": 0.5,
    "jaredpalmer/kev-4b": 0.5,
    "jaredpalmer/kev-9b": 0.5,
    "jev-latest": 0.8,
}
# A judge not measured blocks only on its most confident findings, so that
# an unknown judge's low confidences do not block true commits.
_UNMEASURED_JUDGE_THRESHOLD = 0.8


def find_default_commit_threshold(model_name: str) -> float:
    """Return the confidence a failure needs to block a commit with ``model_name``."""
    return model_name_to_commit_threshold.get(model_name, _UNMEASURED_JUDGE_THRESHOLD)


def choose_commit_threshold(
    chosen_threshold: float | None, project_threshold: float | None, model_name: str
) -> float:
    """Return the threshold a finding needs to block a change.

    ``chosen_threshold`` is the one the caller asked for, ``project_threshold``
    the project's KLINT_COMMIT_MIN_CONFIDENCE; the first set wins, else the
    judge's own for ``model_name``.
    """
    if chosen_threshold is not None:
        return chosen_threshold
    if project_threshold is not None:
        return project_threshold
    return find_default_commit_threshold(model_name)


def read_commit_min_confidence(value: str, source_description: str) -> float:
    """Return the commit threshold the setting ``value`` gives.

    Raises ValueError naming ``source_description`` when it is not a number
    from 0.0 to 1.0.
    """
    try:
        threshold = float(value)
    except ValueError:
        threshold = -1.0
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(
            f"KLINT_COMMIT_MIN_CONFIDENCE {value!r} set in {source_description} "
            "must be a number from 0.0 to 1.0"
        )
    return threshold
