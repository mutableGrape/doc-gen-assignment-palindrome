"""Checks that figures are accurate and traceable to their sources."""

from pydantic_evals.evaluators import EvaluationReason

from report_eval.checks._base import Ctx, Result, no_expected
from report_eval.models import CaseMeta
from report_eval.text_helpers import amounts_in, format_money, parse_expected_money


def _allowed_money(meta: CaseMeta) -> set[float]:
    allowed = amounts_in(meta.notes) | amounts_in(meta.request)
    allowed |= {
        float(a["value"])
        for a in meta.db_accounts().values()
        if a.get("value") is not None
    }
    for key in ("amounts", "live_values", "derived_amounts"):
        allowed |= parse_expected_money(meta.expected.get(key, []))
    return allowed


def b1_figures_are_traceable(ctx: Ctx) -> Result:
    """Every £ figure traces to the DB, meeting note, request or expected derivations"""
    report, meta = ctx.output, ctx.metadata
    stray = amounts_in(report.raw) - _allowed_money(meta)
    return EvaluationReason(
        value=not stray,
        reason=f"untraceable figures: {format_money(stray)}" if stray else None,
    )


def b2_no_distractor_figures(ctx: Ctx) -> Result:
    """No figures from platform updates / model portfolio packs appear"""
    report, meta = ctx.output, ctx.metadata
    leaked = (amounts_in(meta.distractors) - _allowed_money(meta)) & amounts_in(
        report.raw
    )
    return EvaluationReason(
        value=not leaked,
        reason=f"leaked figures: {format_money(leaked)}" if leaked else None,
    )


def b5_no_forbidden_terms(ctx: Ctx) -> Result:
    """None of the client's out-of-scope wording (aspirations, small talk) appears"""
    if (failed := no_expected(ctx)) is not None:
        return failed
    report, meta = ctx.output, ctx.metadata
    terms = meta.expected.get("forbidden_terms")
    if terms is None:
        return {}
    hits = [t for t in terms if t.lower() in report.raw.lower()]
    return EvaluationReason(
        value=not hits, reason=f"forbidden terms present: {hits}" if hits else None
    )


def b3_live_not_stale_values(ctx: Ctx) -> Result:
    """Live (newer) values are used and superseded stale values are not"""
    if (failed := no_expected(ctx)) is not None:
        return failed
    report, meta = ctx.output, ctx.metadata
    live, stale = (
        meta.expected.get("live_values"),
        meta.expected.get("stale_values"),
    )
    if live is None and stale is None:
        return {}
    seen = amounts_in(report.raw)
    missing = parse_expected_money(live or []) - seen
    used_stale = parse_expected_money(stale or []) & seen
    problems = ([f"missing live {format_money(missing)}"] if missing else []) + (
        [f"stale value used {format_money(used_stale)}"] if used_stale else []
    )
    return EvaluationReason(value=not problems, reason="; ".join(problems))


def b4_expected_amounts_only(ctx: Ctx) -> Result:
    """Transaction amounts present; forbidden amounts (e.g. unreceived earnout) absent"""
    if (failed := no_expected(ctx)) is not None:
        return failed
    report, meta = ctx.output, ctx.metadata
    want, forbid = (
        meta.expected.get("amounts"),
        meta.expected.get("forbidden_amounts"),
    )
    if want is None and forbid is None:
        return {}
    seen = amounts_in(report.raw)
    missing = parse_expected_money(want or []) - seen
    present = parse_expected_money(forbid or []) & seen
    problems = ([f"missing {format_money(missing)}"] if missing else []) + (
        [f"forbidden present {format_money(present)}"] if present else []
    )
    return EvaluationReason(value=not problems, reason="; ".join(problems))


EVAL_CHECKS = [
    b1_figures_are_traceable,
    b2_no_distractor_figures,
    b3_live_not_stale_values,
    b4_expected_amounts_only,
    b5_no_forbidden_terms,
]
