"""Checks on the holdings table.

expected.json schema and validation live in report_eval/expected.py. Without the file these
checks fail loudly; with the file, an absent key skips the check.
"""

import re

from pydantic_evals.evaluators import EvaluationReason

from report_eval.checks._base import Ctx, Result, judge, no_expected
from report_eval.models import ReportOutput
from report_eval.text_helpers import amounts_in, markdown_tables, money_values

HEADER = ["Account", "Owner", "Type", "Value"]


def _background(report: ReportOutput) -> str:
    return report.find_section("Background", prefix=True) or ""


def _rows(report: ReportOutput) -> list[list[str]]:
    return [row for table in markdown_tables(_background(report)) for row in table[1:]]


def _matches(row: list[str], pattern: str) -> bool:
    return re.search(pattern, " | ".join(row), re.I) is not None


C5_RUBRIC = (
    "Some accounts have a value that is not yet known. Pass only if the Value cell of every such "
    "account in the holdings table clearly says the value is unknown, unconfirmed or awaited (e.g. 'TBC', 'awaiting "
    "confirmation', 'not yet known'). A blank cell, a dash, or any figure fails."
)


def c1_table_uses_correct_columns(ctx: Ctx) -> Result:
    """Table columns are exactly Account | Owner | Type | Value"""
    report = ctx.output
    tables = markdown_tables(_background(report))
    if not tables:
        return EvaluationReason(
            value=False, reason="no table in Background & Objectives"
        )
    return EvaluationReason(
        value=tables[0][0] == HEADER, reason=f"header is {tables[0][0]}"
    )


def c2_first_table_in_background_section(ctx: Ctx) -> Result:
    """The report has a table, and the first one is in Background & Objectives"""
    report = ctx.output
    total = report.tables
    in_bg = markdown_tables(_background(report))
    return EvaluationReason(
        value=bool(total) and bool(in_bg) and total[0] == in_bg[0],
        reason=f"{len(total)} table(s) in report, {len(in_bg)} in Background",
    )


def c3_accounts_are_listed_once(ctx: Ctx) -> Result:
    """Each expected account appears exactly once (joint accounts de-duplicated)"""
    if (failed := no_expected(ctx)) is not None:
        return failed
    report, meta = ctx.output, ctx.metadata
    accounts = meta.expected.get("accounts")
    if accounts is None:
        return {}
    rows = _rows(report)
    bad = {
        a["match"]: n
        for a in accounts
        if (n := sum(_matches(r, a["match"]) for r in rows)) != 1
    }
    return EvaluationReason(
        value=not bad, reason=f"row counts (want 1): {bad}" if bad else None
    )


def c4_excluded_accounts_are_absent(ctx: Ctx) -> Result:
    """Excluded (e.g. closed) accounts are not in the table"""
    if (failed := no_expected(ctx)) is not None:
        return failed
    report, meta = ctx.output, ctx.metadata
    excluded = meta.expected.get("excluded_accounts")
    if excluded is None:
        return {}
    rows = _rows(report)
    hits = [p for p in excluded if any(_matches(r, p) for r in rows)]
    return EvaluationReason(
        value=not hits,
        reason=f"excluded accounts present: {hits}" if hits else None,
    )


async def c5_unknown_values_flagged_as_tbc(ctx: Ctx) -> Result:
    """Value cells of accounts with unknown value that are not plainly TBC/unconfirmed"""
    if (failed := no_expected(ctx)) is not None:
        return failed
    report, meta = ctx.output, ctx.metadata
    unknown = [a for a in meta.expected.get("accounts", []) if a.get("value") == "TBC"]
    if not unknown:
        return {}
    rows = _rows(report)
    for a in unknown:
        row = next((r for r in rows if _matches(r, a["match"])), None)
        if row is None:
            return EvaluationReason(
                value=False, reason=f"account missing from table: {a['match']}"
            )
        if amounts_in(row[-1]):
            return EvaluationReason(
                value=False,
                reason=f"unknown value shown as an amount: {a['match']} -> {row[-1]}",
            )
    names = ", ".join(a["match"] for a in unknown)
    return await judge(
        ctx,
        f"Accounts with unknown value (row patterns): {names}. " + C5_RUBRIC,
        section="Background",
    )


def c6_table_directly_follows_its_lead_in(ctx: Ctx) -> Result:
    """The line directly above the table is the template's lead-in ('...as follows:')"""
    lines = [line for line in _background(ctx.output).splitlines() if line.strip()]
    first = next(
        (i for i, line in enumerate(lines) if line.strip().startswith("|")), None
    )
    if first is None:
        return EvaluationReason(value=False, reason="no table in Background")
    above = lines[first - 1].strip() if first else ""
    return EvaluationReason(
        value=above.endswith(":"), reason=f"line above table: {above[:80]!r}"
    )


def c7_table_values_match(ctx: Ctx) -> Result:
    """Table values (and owners) match the expected values"""
    if (failed := no_expected(ctx)) is not None:
        return failed
    report, meta = ctx.output, ctx.metadata
    accounts = [
        a
        for a in meta.expected.get("accounts", [])
        if a.get("value") not in (None, "TBC")
    ]
    if not accounts:
        return {}
    rows, bad = _rows(report), []
    for a in accounts:
        row = next((r for r in rows if _matches(r, a["match"])), None)
        want = money_values(a["value"])
        if row is None or amounts_in(row[-1]) != want:
            bad.append(
                f"{a['match']} want {a['value']} got {row[-1] if row else 'no row'}"
            )
        elif a.get("owner") and a["owner"].lower() not in row[1].lower():
            bad.append(f"{a['match']} owner want {a['owner']} got {row[1]}")
    return EvaluationReason(value=not bad, reason="; ".join(bad))


def c8_values_have_pound_sign(ctx: Ctx) -> Result:
    """Every amount in the table's Value column is written with a £ sign"""
    bad = [
        f"{row[0]}: {row[-1]!r}"
        for row in _rows(ctx.output)
        if amounts_in(row[-1]) and not money_values(row[-1])
    ]
    return EvaluationReason(
        value=not bad, reason=f"Value cells without £: {bad}" if bad else None
    )


EVAL_CHECKS = [
    c1_table_uses_correct_columns,
    c2_first_table_in_background_section,
    c3_accounts_are_listed_once,
    c4_excluded_accounts_are_absent,
    c5_unknown_values_flagged_as_tbc,
    c6_table_directly_follows_its_lead_in,
    c7_table_values_match,
    c8_values_have_pound_sign,
]
