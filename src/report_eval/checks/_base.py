"""Shared pieces for the evaluators.

Every evaluator is a plain function `fn(ctx: Ctx)`; its name (snake_case, prefixed with the
check id such as `a1_`) is its evaluation name. Return an `EvaluationReason`, or `{}` when the
check does not apply to this client.
"""

import asyncio
import json
from collections import Counter
from functools import cache
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelSettings
from pydantic_ai.exceptions import ModelHTTPError, ModelRateLimitError
from pydantic_evals.evaluators import EvaluationReason, EvaluatorContext
from pydantic_evals.evaluators.llm_as_a_judge import judge_input_output

from report_eval.models import CaseMeta, ClientInput, ReportOutput
from report_eval.text_helpers import PLACEHOLDER_RE, quote_in

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


# --- Throttled, retried model calls ----------------------------------------------------------
# Repeated runs with voting fire hundreds of judge calls at once and hit the provider's tokens-per-
# minute limit; a 429 must be retried, never reported as a verdict. Every judge call goes through
# `call_judge`. The semaphore is per event loop because each evaluate_sync runs its own loop.
MAX_CONCURRENT_JUDGES = 6
_RETRIES = 6
_semaphores: dict[asyncio.AbstractEventLoop, asyncio.Semaphore] = {}


async def call_judge(make_call):
    """Await `make_call()` under the shared concurrency cap, retrying rate limits with backoff."""
    loop = asyncio.get_running_loop()
    sem = _semaphores.setdefault(loop, asyncio.Semaphore(MAX_CONCURRENT_JUDGES))
    for attempt in range(_RETRIES):
        async with sem:
            try:
                return await make_call()
            except (ModelRateLimitError, ModelHTTPError) as e:
                limited = isinstance(e, ModelRateLimitError) or e.status_code == 429
                if not limited or attempt == _RETRIES - 1:
                    raise
        await asyncio.sleep(min(2**attempt * 2, 60))


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
    src = source_block(ctx, sources)
    verdict = await call_judge(
        lambda: judge_input_output(
            src or "(no sources needed for this criterion)",
            text,
            JUDGE_PREAMBLE + rubric,
            JUDGE_MODEL,
            JUDGE_SETTINGS,
        )
    )
    return EvaluationReason(value=verdict.pass_, reason=verdict.reason)


def source_block(ctx: Ctx, sources: tuple[str, ...]) -> str:
    """The named sources ("notes", "request", "db") as one labelled text block."""
    meta = ctx.metadata
    parts = {"notes": meta.notes, "request": meta.request, "db": json.dumps(meta.db)}
    return "\n\n".join(f"[{k.upper()}]\n{parts[k]}" for k in sources)


# --- Evidence-backed judging -------------------------------------------------------------------
# A plain pass/fail judge is free to wave an item through (or reject it) without pointing at
# anything, which is where most run-to-run flakiness came from. Here the judge must quote the
# report sentence its verdict rests on, and the quote is checked in code: a verdict whose
# evidence is not actually in the report does not count.

Mode = Literal["support", "violation"]


class QuotedVerdict(BaseModel):
    quotes: list[str] = Field(
        description="Sentences copied VERBATIM from the REPORT that the verdict rests on. Copy, "
        "never paraphrase; use '...' only to skip words inside a sentence. Empty if none exist."
    )
    reason: str = Field(description="One or two sentences explaining the verdict.")
    passed: bool


_QUOTE_RULES = {
    "support": (
        "To PASS you must quote the report sentence(s) that convey the criterion. If you cannot "
        "quote any, the criterion is not met: fail with an empty quote list."
    ),
    "violation": (
        "To FAIL you must quote the report sentence(s) that break the criterion. If you cannot "
        "quote any, pass with an empty quote list."
    ),
}


@cache
def _quoted_agent(mode: Mode) -> Agent[None, QuotedVerdict]:
    return Agent(
        JUDGE_MODEL,
        output_type=QuotedVerdict,
        model_settings=JUDGE_SETTINGS,
        system_prompt=JUDGE_PREAMBLE.removesuffix("Criterion: ").strip()
        + " "
        + _QUOTE_RULES[mode],
    )


def _settle(
    mode: Mode, v: QuotedVerdict, report: str, *, needs_placeholder: bool = False
) -> EvaluationReason:
    """Turn a judge verdict into a result, accepting it only if its quotes are in the report.

    needs_placeholder: (support mode) the evidence must itself contain a [TO BE CONFIRMED: ...]
    placeholder or a TBC cell, so an item can't be "flagged" by prose alone.
    """
    found = [q for q in v.quotes if quote_in(q, report)]
    missing = [q for q in v.quotes if not quote_in(q, report)]
    if mode == "support" and v.passed and needs_placeholder and found:
        if not any(PLACEHOLDER_RE.search(q) or "TBC" in q for q in found):
            return EvaluationReason(
                value=False,
                reason=f"judge passed but evidence has no placeholder: {found}",
            )
    if mode == "support":
        ok = v.passed and bool(found) and not missing
        if v.passed and not ok:
            why = (
                f"judge passed but quoted text not in report: {missing}"
                if missing
                else "judge passed without quoting evidence"
            )
            return EvaluationReason(value=False, reason=why)
        return EvaluationReason(value=ok, reason=v.reason)
    # violation: only a quoted, verifiable breach fails
    if not v.passed and found:
        return EvaluationReason(value=False, reason=f"{v.reason} Quote: {found[0]!r}")
    return EvaluationReason(
        value=True, reason=None if v.passed else "no verifiable quote"
    )


async def judge_quoted(
    ctx: Ctx,
    rubric: str,
    *,
    mode: Mode,
    sources: tuple[str, ...] = (),
    votes: int = 1,
    needs_placeholder: bool = False,
) -> EvaluationReason:
    """LLM-judge with verifiable evidence; with votes > 1, the majority outcome wins."""
    report = ctx.output.raw
    prompt = (
        f"<SOURCES>\n{source_block(ctx, sources) or '(none)'}\n</SOURCES>\n\n"
        f"<REPORT>\n{report}\n</REPORT>\n\n<CRITERION>\n{rubric}\n</CRITERION>"
    )
    agent = _quoted_agent(mode)
    outs = await asyncio.gather(
        *(call_judge(lambda: agent.run(prompt)) for _ in range(votes))
    )
    results = [
        _settle(mode, o.output, report, needs_placeholder=needs_placeholder)
        for o in outs
    ]
    winner = Counter(r.value for r in results).most_common(1)[0][0]
    return next(r for r in results if r.value == winner)
