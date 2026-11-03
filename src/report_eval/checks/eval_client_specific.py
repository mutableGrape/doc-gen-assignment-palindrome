"""Checks on handling of client-specific circumstances."""

from report_eval.checks._base import Ctx, judge


async def f1_phrasing_is_bereavement_sensitive(ctx: Ctx):
    return await judge(
        ctx,
        "If the new money comes from a bereavement/inheritance, it is referenced with sensitivity (respectful, non-clinical). Answer na if there is no bereavement.",
        sources=("notes", "request"),
    )


async def f2_charges_flagged_per_platform(ctx: Ctx):
    # The premise is checkable from the db, so gate on it instead of leaving it to the judge.
    if len({a.get("platform") for a in ctx.metadata.db_accounts().values()}) < 2:
        return {}
    return await judge(
        ctx,
        "Accounts are on more than one platform: charges must be set out or flagged per platform.",
        sources=("db",),
    )


async def f3_outstanding_items_are_flagged(ctx: Ctx):
    return await judge(
        ctx,
        "Items the notes say are unconfirmed or outstanding (unknown balances, timings) are flagged as outstanding, not assumed or invented. Answer na if none.",
        sources=("notes", "request"),
    )


EVAL_CHECKS = [
    f1_phrasing_is_bereavement_sensitive,
    f2_charges_flagged_per_platform,
    f3_outstanding_items_are_flagged,
]
