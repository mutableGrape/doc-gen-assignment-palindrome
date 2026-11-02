"""Checks on handling of client-specific circumstances."""

from report_eval.checks._base import Ctx, judge


async def f1_phrasing_is_bereavement_sensitive(ctx: Ctx):
    return await judge(
        ctx,
        "If the new money comes from a bereavement/inheritance, it is referenced with sensitivity (respectful, non-clinical). Answer na if there is no bereavement.",
    )


async def f2_charges_flagged_per_platform(ctx: Ctx):
    return await judge(
        ctx,
        "If accounts are on more than one platform, charges are set out or flagged per platform. Answer na if there is a single platform.",
    )


async def f3_outstanding_items_are_flagged(ctx: Ctx):
    return await judge(
        ctx,
        "Items the notes say are unconfirmed or outstanding (unknown balances, timings) are flagged as outstanding, not assumed or invented. Answer na if none.",
    )


EVAL_CHECKS = [
    f1_phrasing_is_bereavement_sensitive,
    f2_charges_flagged_per_platform,
    f3_outstanding_items_are_flagged,
]
