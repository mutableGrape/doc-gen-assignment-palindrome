"""Checks driven by the atomic statements in expected.json (required / forbidden / outstanding).

These carry the client-specific advice facts that no generic rubric can know. Each entry is judged in
its own call: one batched call lets the judge stop at the first failure and wave the rest through.
The result is a single pass/fail whose reason lists every entry that failed.
"""

import asyncio

from pydantic_evals.evaluators import EvaluationReason

from report_eval.checks._base import Ctx, Result, judge

REQUIRED = (
    "The report must clearly convey this statement (wording may differ, meaning must not). A "
    "[TO BE CONFIRMED: ...] placeholder may stand in for an unknown amount, but not for the "
    "statement itself. Fail if it is absent, contradicted or only vaguely implied. Statement: "
)
FORBIDDEN = (
    "The report must NOT make or imply this claim. Fail only if you can quote a sentence that makes "
    "it; if you cannot quote one, pass. Claim: "
)
OUTSTANDING = (
    "This is unknown or awaited. The report must flag it as outstanding with a [TO BE CONFIRMED: ...] "
    "placeholder (or TBC in the holdings table) at the point it matters, and must not state, assume "
    "or invent it. A single placeholder that lumps several different unknowns together does not "
    "count for this one. Fail if it is not flagged or is asserted as settled. Item: "
)


async def _each(ctx: Ctx, key: str, rubric: str) -> Result:
    items = ctx.metadata.expected.get(key)
    if not items:
        return {}
    verdicts = await asyncio.gather(
        *(judge(ctx, rubric + t, sources=("notes", "request")) for t in items)
    )
    failed = [f"- {t} -> {v.reason}" for t, v in zip(items, verdicts) if not v.value]
    return EvaluationReason(
        value=not failed,
        reason=f"{len(failed)}/{len(items)} failed:\n" + "\n".join(failed)
        if failed
        else None,
    )


async def h1_required_statements_are_made(ctx: Ctx) -> Result:
    return await _each(ctx, "required_statements", REQUIRED)


async def h2_forbidden_statements_are_not_made(ctx: Ctx) -> Result:
    return await _each(ctx, "forbidden_statements", FORBIDDEN)


async def h3_outstanding_items_are_flagged(ctx: Ctx) -> Result:
    return await _each(ctx, "outstanding_items", OUTSTANDING)


EVAL_CHECKS = [
    h1_required_statements_are_made,
    h2_forbidden_statements_are_not_made,
    h3_outstanding_items_are_flagged,
]
