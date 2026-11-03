"""Shared pieces for the evaluators.

Every evaluator is a plain function `fn(ctx: Ctx)`; its name (snake_case, prefixed with the
check id such as `a1_`) is its evaluation name. Return an `EvaluationReason`, or `{}` when the
check does not apply to this client.
"""

import json

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
        value=False,
        reason="expected.json not found for this client; check cannot run "
        f"(create it: python -m report_eval.run --client {ctx.inputs.client} --draft-expected)",
    )


async def judge(
    ctx: Ctx,
    rubric: str,
    *,
    section: str | None = None,
    sources: tuple[str, ...] = (),
) -> EvaluationReason:
    """LLM-judge the report against `rubric`, sending only the context the rubric needs.

    section: judge only the section whose title contains this text (default: whole report).
    sources: which of "notes", "request", "db" to include (default: none, i.e. report-only).
    """
    text = ctx.output.raw
    if section is not None:
        body = ctx.output.find_section(section)
        if body is None:
            return EvaluationReason(value=False, reason=f"no {section} section")
        text = f"## {section}\n{body}"
    meta = ctx.metadata
    parts = {"notes": meta.notes, "request": meta.request, "db": json.dumps(meta.db)}
    src = "\n\n".join(f"[{k.upper()}]\n{parts[k]}" for k in sources)
    verdict = await judge_input_output(
        src or "(no sources needed for this criterion)",
        text,
        JUDGE_PREAMBLE + rubric,
        JUDGE_MODEL,
        JUDGE_SETTINGS,
    )
    return EvaluationReason(value=verdict.pass_, reason=verdict.reason)
