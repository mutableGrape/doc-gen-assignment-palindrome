"""Shared pieces for the evaluators.

Every evaluator is a plain function `fn(ctx: Ctx)`; its name (snake_case, prefixed with the
check id such as `a1_`) is its evaluation name. Return an `EvaluationReason`, or `{}` when the
check does not apply to this client.
"""

from pydantic_ai import ModelSettings
from pydantic_evals.evaluators import EvaluationReason, EvaluatorContext
from pydantic_evals.evaluators.llm_as_a_judge import judge_input_output

from report_eval.models import CaseMeta, ClientInput, ReportOutput

Ctx = EvaluatorContext[ClientInput, ReportOutput, CaseMeta]
Result = EvaluationReason | dict

JUDGE_MODEL = "openai-chat:gpt-4o"
JUDGE_SETTINGS = ModelSettings(temperature=0.0)  # deterministic evaluation

JUDGE_PREAMBLE = (
    "You are a strict compliance reviewer of UK financial advice reports. The input is the "
    "client's SOURCES (meeting notes, report request, database). The output is the REPORT. "
    "Judge only against the sources. If the premise of the criterion does not apply to this "
    "client, pass. Criterion: "
)


def no_expected(ctx: Ctx) -> EvaluationReason | None:
    """A failing result if this client has no expected.json, else None.

    Checks that compare against expected.json call this first so they fail loudly instead of
    silently skipping when the file is missing.
    """
    if ctx.metadata.has_expected:
        return None
    return EvaluationReason(
        value=False, reason="expected.json not found for this client; check cannot run"
    )


async def judge(ctx: Ctx, rubric: str) -> EvaluationReason:
    """LLM-judge the whole report against `rubric`, given the client's sources."""
    verdict = await judge_input_output(
        ctx.inputs.sources,
        ctx.output.raw,
        JUDGE_PREAMBLE + rubric,
        JUDGE_MODEL,
        JUDGE_SETTINGS,
    )
    return EvaluationReason(value=verdict.pass_, reason=verdict.reason)
