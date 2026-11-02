"""Checks on layout, fixed wording and optional-section inclusion."""

from pydantic_evals.evaluators import EvaluationReason

from report_eval.checks._base import Ctx, Result, judge
import re

from report_eval.models import CaseMeta
from report_eval.text_helpers import RISK_WARNING, norm, sentences

_REGULATORY = re.compile(r"authori[sz]ed\s+(?:and|&)\s+regulated", re.I)
_PROCEED = re.compile(r"\b(proceed|go ahead)\b", re.I)
TAX_TITLE_HINT = "tax"


def _expected_titles(meta: CaseMeta) -> tuple[list[str], list[str]]:
    required = [
        s["title"] for s in meta.config["sections"] if s.get("use_if") == "always"
    ]
    optional = [
        s["title"] for s in meta.config["sections"] if s.get("use_if") != "always"
    ]
    return required, optional


def a1_sections_are_in_order(ctx: Ctx) -> Result:
    """Sections appear in config order, with no extra sections"""
    report, meta = ctx.output, ctx.metadata
    required, optional = _expected_titles(meta)
    allowed = [
        s["title"] for s in meta.config["sections"] if s["title"] in required + optional
    ]
    actual = list(report.sections)
    if any(t not in allowed for t in actual):
        return EvaluationReason(
            value=False,
            reason=f"unexpected sections: {[t for t in actual if t not in allowed]}",
        )
    if any(t not in actual for t in required):
        return EvaluationReason(
            value=False,
            reason=f"missing sections: {[t for t in required if t not in actual]}",
        )
    if actual != [t for t in allowed if t in actual]:
        return EvaluationReason(value=False, reason=f"order is {actual}")
    return EvaluationReason(value=True)


def a2_fca_line_included_once(ctx: Ctx) -> Result:
    """FCA line appears exactly once, verbatim, in the Introduction"""
    report, meta = ctx.output, ctx.metadata
    line = meta.fca_line
    if not line:
        return {}
    total = norm(report.raw).count(line)
    intro = norm(report.sections.get("Introduction", "")).count(line)
    # Paraphrases count too: any other sentence making a regulatory statement.
    others = [
        x
        for x in sentences(report.raw)
        if _REGULATORY.search(x) and norm(x) not in line and line not in norm(x)
    ]
    return EvaluationReason(
        value=total == 1 and intro == 1 and not others,
        reason=f"{total} occurrence(s) in report, {intro} in Introduction"
        + (f"; paraphrased regulatory statement(s): {others}" if others else ""),
    )


def a3_risk_warning_included_once(ctx: Ctx) -> Result:
    """Risk warning appears exactly once, verbatim, in the Conclusion"""
    report = ctx.output
    total = norm(report.raw).count(RISK_WARNING)
    concl = norm(report.sections.get("Conclusion", "")).count(RISK_WARNING)
    return EvaluationReason(
        value=total == 1 and concl == 1,
        reason=f"{total} occurrence(s) in report, {concl} in Conclusion",
    )


def a5_closing_invitation_included_once(ctx: Ctx) -> Result:
    """Exactly one sentence in the Conclusion invites the client to proceed"""
    text = ctx.output.sections.get("Conclusion")
    if text is None:
        return EvaluationReason(value=False, reason="no Conclusion section")
    hits = [x for x in sentences(text) if _PROCEED.search(x)]
    return EvaluationReason(
        value=len(hits) == 1,
        reason=f"{len(hits)} proceed sentence(s): {[h[:60] for h in hits]}",
    )


def a6_tax_section_included_iff_selling(ctx: Ctx) -> Result:
    """Tax Implications present iff the request says investments are being sold"""
    report, meta = ctx.output, ctx.metadata
    selling = meta.sells_investments
    if selling is None:
        return {}
    present = any(TAX_TITLE_HINT in t.lower() for t in report.sections)
    return EvaluationReason(
        value=present == selling,
        reason=f"selling={selling}, section present={present}",
    )


def a7_tax_section_cites_cgt(ctx: Ctx) -> Result:
    """Tax Implications cites a possible CGT liability against the annual exempt amount"""
    report = ctx.output
    text = report.find_section(TAX_TITLE_HINT)
    if text is None:
        return {}
    low = text.lower()
    ok = "capital gains tax" in low and "annual exempt amount" in low
    return EvaluationReason(
        value=ok,
        reason=""
        if ok
        else "missing 'capital gains tax' and/or 'annual exempt amount'",
    )


async def a4_conclusion_is_brief(ctx: Ctx):
    return await judge(
        ctx,
        "The Conclusion contains only the standard risk warning and a short closing line inviting the client to proceed. It must not restate the introduction, the client's circumstances, the recommendation, the fees or the accounts table. A Conclusion that recaps other sections fails.",
    )


EVAL_CHECKS = [
    a1_sections_are_in_order,
    a2_fca_line_included_once,
    a3_risk_warning_included_once,
    a4_conclusion_is_brief,
    a5_closing_invitation_included_once,
    a6_tax_section_included_iff_selling,
    a7_tax_section_cites_cgt,
]
