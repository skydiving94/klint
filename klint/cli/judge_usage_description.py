"""How a command words the judge's usage over its run."""

import sys

from klint.core.models.judging import JudgeUsage


def print_judge_usage_lines(command_name: str, usage: JudgeUsage) -> None:
    """Print the answer cache's counts, when it took part, then the judge's usage.

    Both go to stderr, after the report, so that the report on stdout is as
    before. The usage line comes last.
    """
    if usage.did_cache_take_part():
        print(
            f"[{command_name}] Answer cache: {describe_answer_cache(usage)}",
            file=sys.stderr,
        )
    print(
        f"[{command_name}] Judge usage: {describe_judge_usage(usage)}", file=sys.stderr
    )


def describe_judge_usage(usage: JudgeUsage) -> str:
    """Return the requests sent and the input tokens billed, as one phrase.

    For example "723 requests, 412,503 input tokens", or "5 requests, input
    tokens not reported" for a judge that reports none.
    """
    request_noun = "request" if usage.request_count == 1 else "requests"
    requests = f"{usage.request_count:,} {request_noun}"
    if usage.input_token_count is None:
        return f"{requests}, input tokens not reported"
    return f"{requests}, {usage.input_token_count:,} input tokens"


def convert_judge_usage_to_dict(usage: JudgeUsage) -> dict[str, int | None]:
    """Return the judge's usage as --json writes it.

    input_tokens is null when the judge did not report them.
    """
    return {"requests": usage.request_count, "input_tokens": usage.input_token_count}


def describe_answer_cache(usage: JudgeUsage) -> str:
    """Say how many questions the answer cache answered and how many it passed on."""
    cached_noun = "question" if usage.cached_question_count == 1 else "questions"
    return (
        f"{usage.cached_question_count:,} {cached_noun} answered from the cache, "
        f"{usage.asked_question_count:,} asked"
    )


def convert_answer_cache_to_dict(usage: JudgeUsage) -> dict[str, int]:
    """Return the answer cache's counts as --json writes them."""
    return {
        "questions_from_cache": usage.cached_question_count,
        "questions_asked": usage.asked_question_count,
    }
