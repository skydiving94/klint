"""How a command words the judge's usage over its run."""

from klint.core.models.judging import JudgeUsage


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
