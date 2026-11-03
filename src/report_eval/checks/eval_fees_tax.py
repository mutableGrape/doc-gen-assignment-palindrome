"""Checks on fees, rates and placeholders."""

import re

from pydantic_evals.evaluators import EvaluationReason

from report_eval.checks._base import Ctx, Result, judge
from report_eval.text_helpers import PLACEHOLDER_RE, percent_values


async def d3_initial_vs_ongoing_charge(ctx: Ctx) -> Result:
    """The request's initial charge is not presented as an ongoing charge"""
    m = re.search(
        r"Initial charge[\s|]*(\d+(?:\.\d+)?)\s?%", ctx.metadata.request, re.I
    )
    if not m:
        return {}
    return await judge(
        ctx,
        f"The request sets a one-off INITIAL charge of {m.group(1)}%. Pass only if the report "
        "never presents that percentage as an ongoing, annual or recurring charge. Describing it "
        "as the one-off initial charge, or as a different thing entirely, passes; so does a "
        f"report that never states {m.group(1)}% as an ongoing charge. A [TO BE CONFIRMED: "
        "ongoing advice charge] placeholder is not a statement of that percentage. Quote the "
        "offending sentence in your reason.",
        sources=("request",),
    )


async def d5_fee_rates_not_asserted_without_placeholder(ctx: Ctx) -> Result:
    """Platform/ongoing/advice charges are not stated as fact"""
    m = re.search(
        r"Initial charge[\s|]*(\d+(?:\.\d+)?)\s?%", ctx.metadata.request, re.I
    )
    allowed = (
        f"The report request itself gives a one-off INITIAL charge of {m.group(1)}%: stating "
        f"that {m.group(1)}% initial charge is explicitly allowed and must NOT be failed, "
        "even though it is not a placeholder. "
        if m
        else "The one-off initial charge from the request is allowed. "
    )
    return await judge(
        ctx,
        "Platform, ongoing and adviser charges are not yet known and must appear only as "
        "[TO BE CONFIRMED: ...] placeholders. Pass only if the report never states such a charge "
        "as a settled percentage, amount, or as nil/none/not applicable. Fund-level costs (OCF, "
        "ongoing charges figure) are allowed. "
        + allowed
        + "Quote the offending sentence in "
        "your reason.",
        sources=("request",),
    )


def d1_no_unsourced_rates(ctx: Ctx) -> Result:
    """No percentage rate appears unless it comes from the request or notes"""
    report, meta = ctx.output, ctx.metadata
    stray = percent_values(report.raw) - (
        percent_values(meta.request) | percent_values(meta.notes)
    )
    return EvaluationReason(
        value=not stray,
        reason=f"unsourced percentages: {sorted(stray)}" if stray else None,
    )


def d2_fee_placeholders_present(ctx: Ctx) -> Result:
    """Fees & Charges names the platform and ongoing advice charge as placeholders"""
    report = ctx.output
    text = report.find_section("fee")
    if text is None:
        return EvaluationReason(value=False, reason="no Fees & Charges section")
    marks = [m.lower() for m in PLACEHOLDER_RE.findall(text)]
    platform = any("platform" in m for m in marks)
    advice = any("advice" in m or "adviser" in m or "ongoing" in m for m in marks)
    return EvaluationReason(
        value=platform and advice,
        reason=f"platform placeholder={platform}, advice placeholder={advice}",
    )


def d4_placeholder_format_is_correct(ctx: Ctx) -> Result:
    """Every bracketed marker uses the standard [TO BE CONFIRMED: ...] format"""
    report = ctx.output
    brackets = re.findall(r"\[[^\]\n]*\]", report.raw)
    bad = [b for b in brackets if not PLACEHOLDER_RE.fullmatch(b)]
    return EvaluationReason(
        value=not bad, reason=f"non-standard markers: {bad}" if bad else None
    )


EVAL_CHECKS = [
    d1_no_unsourced_rates,
    d2_fee_placeholders_present,
    d3_initial_vs_ongoing_charge,
    d4_placeholder_format_is_correct,
    d5_fee_rates_not_asserted_without_placeholder,
]
