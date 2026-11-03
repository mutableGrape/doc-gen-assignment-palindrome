"""Checks driven by the atomic statements in expected.json (required / forbidden / outstanding),
plus h4, a generic check that every recommended action is backed by the sources.

These carry the client-specific advice facts that no generic rubric can know. Each entry is judged in
its own call (one batched call lets the judge stop at the first failure and wave the rest through),
and each verdict must quote its evidence from the report, which is verified in code
(`judge_quoted`). Every check returns a pass/fail assertion plus a `<name>_score` (fraction of
entries passing) so partial progress is visible instead of hidden behind one boolean.
"""

import asyncio

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_evals.evaluators import EvaluationReason

from report_eval.checks._base import (
    JUDGE_MODEL,
    JUDGE_SETTINGS,
    Ctx,
    Mode,
    Result,
    call_judge,
    judge_quoted,
    source_block,
)
from report_eval.text_helpers import quote_in

REQUIRED = (
    "The report must clearly convey this statement (wording may differ, meaning must not). A "
    "[TO BE CONFIRMED: ...] placeholder may stand in for an unknown amount, but not for the "
    "statement itself. Fail if it is absent, contradicted or only vaguely implied. Statement: "
)
FORBIDDEN = "The report must NOT make or imply this claim. Claim: "
OUTSTANDING = (
    "This item is unknown or awaited. The report must flag it with its own [TO BE CONFIRMED: ...] "
    "placeholder (or TBC in the holdings table) at the point it matters, and must not state, assume "
    "or invent it. Quote the sentence containing that placeholder. The placeholder's own wording "
    "must name THIS item: one naming a different unknown (e.g. an amount added, when the item is "
    "an amount sold) does not count, nor does a sentence that only says the item will be "
    "confirmed later. Fail if it is not flagged or is asserted as settled. Item: "
)


# One judge call per entry (cost); raise for a majority vote if an entry proves flaky.
VOTES = 1


async def _each(
    ctx: Ctx, name: str, key: str, rubric: str, mode: Mode, *, needs_placeholder=False
) -> Result:
    items = ctx.metadata.expected.get(key)
    if not items:
        return {}
    verdicts = await asyncio.gather(
        *(
            judge_quoted(
                ctx,
                rubric + t,
                mode=mode,
                sources=("notes", "request"),
                votes=VOTES,
                needs_placeholder=needs_placeholder,
            )
            for t in items
        )
    )
    failed = [f"- {t} -> {v.reason}" for t, v in zip(items, verdicts) if not v.value]
    return {
        name: EvaluationReason(
            value=not failed,
            reason=f"{len(failed)}/{len(items)} failed:\n" + "\n".join(failed)
            if failed
            else None,
        ),
        f"{name}_score": round(1 - len(failed) / len(items), 3),
    }


async def h1_required_statements_are_made(ctx: Ctx) -> Result:
    return await _each(
        ctx,
        "h1_required_statements_are_made",
        "required_statements",
        REQUIRED,
        "support",
    )


async def h2_forbidden_statements_are_not_made(ctx: Ctx) -> Result:
    return await _each(
        ctx,
        "h2_forbidden_statements_are_not_made",
        "forbidden_statements",
        FORBIDDEN,
        "violation",
    )


async def h3_outstanding_items_are_flagged(ctx: Ctx) -> Result:
    return await _each(
        ctx,
        "h3_outstanding_items_are_flagged",
        "outstanding_items",
        OUTSTANDING,
        "support",
        needs_placeholder=True,
    )


# --- h4: every recommended action traces to the sources --------------------------------------
# Generic (no expected.json needed): catches invented actions such as topping up an account the
# notes never mention. The judge lists each action with a quote from the report and a quote from
# the sources; both quotes are verified in code, so an action can't be waved through on a
# paraphrase or a misremembered source.


class TracedAction(BaseModel):
    action: str = Field(description="The recommended action, in a few words.")
    report_quote: str = Field(
        description="VERBATIM sentence from the REPORT recommending it."
    )
    source_quote: str = Field(
        description="VERBATIM sentence from the NOTES or REQUEST that agrees this exact action "
        "for this exact account. Empty string if no source sentence does."
    )
    supported: bool = Field(
        description="True only if source_quote agrees this action for this specific account. "
        "A quote about a different account, a vaguer one, or a mere discussion of the account is "
        "not support; a source saying the opposite (e.g. leave it unchanged, when the report "
        "says sell or surrender) means False."
    )


class TracedActions(BaseModel):
    actions: list[TracedAction]


_TRACE_PROMPT = (
    "You are a strict compliance reviewer of UK financial advice reports. List EVERY action the "
    "REPORT's Recommendations section tells the client to take with a specific account or sum of "
    "money: paying into, adding to, selling from, rebalancing, opening, or leaving unchanged. "
    "Treat each account separately: a sentence recommending additions to two accounts is two "
    "actions. Skip the fixed closing about charges. For each action, find the sentence in the "
    "NOTES or REQUEST that agrees that action for that account."
)


def _trace_agent() -> Agent[None, TracedActions]:
    return Agent(
        JUDGE_MODEL,
        output_type=TracedActions,
        model_settings=JUDGE_SETTINGS,
        system_prompt=_TRACE_PROMPT,
    )


async def h4_recommended_actions_trace_to_sources(ctx: Ctx) -> Result:
    recs = ctx.output.find_section("Recommendations")
    if recs is None:
        return EvaluationReason(value=False, reason="no Recommendations section")
    sources = ctx.metadata.notes + "\n" + ctx.metadata.request
    prompt = (
        f"<SOURCES>\n{source_block(ctx, ('notes', 'request'))}\n</SOURCES>\n\n"
        f"<REPORT>\n## Recommendations\n{recs}\n</REPORT>"
    )
    agent = _trace_agent()
    actions = (await call_judge(lambda: agent.run(prompt))).output.actions
    if not actions:
        return EvaluationReason(
            value=False, reason="judge found no recommended actions"
        )
    bad = []
    for a in actions:
        if not quote_in(a.report_quote, recs):
            continue  # the judge's own misquote of the report is not a report defect
        if not a.supported or not a.source_quote:
            bad.append(f"- {a.action}: no source agrees it ({a.report_quote!r})")
        elif not quote_in(a.source_quote, sources):
            bad.append(
                f"- {a.action}: cited source text not found ({a.source_quote!r})"
            )
    return {
        "h4_recommended_actions_trace_to_sources": EvaluationReason(
            value=not bad,
            reason=f"{len(bad)}/{len(actions)} actions unsupported:\n" + "\n".join(bad)
            if bad
            else None,
        ),
        "h4_recommended_actions_trace_to_sources_score": round(
            1 - len(bad) / len(actions), 3
        ),
    }


EVAL_CHECKS = [
    h1_required_statements_are_made,
    h2_forbidden_statements_are_not_made,
    h3_outstanding_items_are_flagged,
    h4_recommended_actions_trace_to_sources,
]
