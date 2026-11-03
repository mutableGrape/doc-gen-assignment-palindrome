"""Checks on what each section covers."""

from pydantic_evals.evaluators import EvaluationReason

from report_eval.checks._base import Ctx, Result, judge
from report_eval.text_helpers import amounts_in, format_money


def e1_background_has_no_amounts(ctx: Ctx) -> Result:
    """Background & Objectives prose has no £ amounts (they belong in the table / Recommendations)"""
    text = ctx.output.find_section("Background", prefix=True)
    if text is None:
        return EvaluationReason(value=False, reason="no Background section")
    prose = "\n".join(
        line for line in text.splitlines() if not line.strip().startswith("|")
    )
    # Account values already in the holdings table may be quoted; transaction amounts may not.
    account_values = {
        round(float(a["value"]), 2)
        for a in ctx.metadata.db_accounts().values()
        if isinstance(a.get("value"), (int, float))
    }
    found = amounts_in(prose) - account_values
    return EvaluationReason(
        value=not found,
        reason=f"amounts in prose: {format_money(found)}" if found else None,
    )


async def e2_recommendations_are_clear(ctx: Ctx):
    return await judge(
        ctx,
        "Recommendations says what the client should do and why, with the amounts involved, and mentions the relevant platform charges (as placeholders if not given). Where a source only gives a vague or stale figure for an amount (e.g. 'a little over £X'), a [TO BE CONFIRMED: ...] placeholder in place of that amount is correct and must not be penalised; do not require a firm figure that the sources do not support. It must still state the action, which account the money comes from, where it goes, and how it is split.",
        section="Recommendations",
        sources=("notes", "request", "db"),
    )


async def e3_agreed_actions_are_covered(ctx: Ctx):
    return await judge(
        ctx,
        "The report covers every action agreed in the meeting note and report request, and recommends nothing that was not agreed.",
        sources=("notes", "request"),
    )


async def e5_introduction_covers_requested_accounts(ctx: Ctx):
    return await judge(
        ctx,
        "The Introduction's scope covers every account the report request says the report covers, "
        "including any new account to be opened, and no account type outside that scope.",
        section="Introduction",
        sources=("request",),
    )


async def e4_risk_profile_is_consistent(ctx: Ctx):
    return await judge(
        ctx,
        "The risk profile stated (if any) matches the report request, and is consistent across sections.",
        sources=("request",),
    )


EVAL_CHECKS = [
    e1_background_has_no_amounts,
    e2_recommendations_are_clear,
    e3_agreed_actions_are_covered,
    e4_risk_profile_is_consistent,
    e5_introduction_covers_requested_accounts,
]
