import pytest

from report_eval.checks._base import QuotedVerdict, _settle
from report_eval.text_helpers import quote_in

REPORT = "## Recs\n\n**Pension contributions.** We recommend a contribution\ninto each SIPP: [TO BE CONFIRMED: amount]."


@pytest.mark.parametrize(
    "quote, ok",
    [
        ("we recommend a contribution into each SIPP", True),  # case, bold, line break
        (
            "Pension contributions. We recommend ... each SIPP",
            True,
        ),  # elision, in order
        ("each SIPP ... We recommend", False),  # elision out of order
        ("We recommend a large contribution", False),  # paraphrase
        ("", False),
        ("...", False),
    ],
)
def test_quote_in(quote, ok):
    assert quote_in(quote, REPORT) is ok


def _v(passed, quotes):
    return QuotedVerdict(quotes=quotes, reason="r", passed=passed)


def test_support_needs_verified_quote():
    assert _settle("support", _v(True, ["We recommend a contribution"]), REPORT).value
    assert not _settle("support", _v(True, []), REPORT).value
    assert not _settle("support", _v(True, ["an invented sentence"]), REPORT).value
    assert not _settle("support", _v(False, []), REPORT).value


def test_violation_needs_verified_quote():
    assert not _settle(
        "violation", _v(False, ["We recommend a contribution"]), REPORT
    ).value
    assert _settle("violation", _v(False, ["an invented sentence"]), REPORT).value
    assert _settle("violation", _v(False, []), REPORT).value
    assert _settle("violation", _v(True, []), REPORT).value


def test_outstanding_evidence_must_hold_a_placeholder():
    prose_only = _v(True, ["We recommend a contribution"])
    flagged = _v(True, ["into each SIPP: [TO BE CONFIRMED: amount]"])
    assert not _settle("support", prose_only, REPORT, needs_placeholder=True).value
    assert _settle("support", flagged, REPORT, needs_placeholder=True).value
