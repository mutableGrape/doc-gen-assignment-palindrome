import asyncio
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from report_eval.checks import eval_figures as F
from report_eval.checks import eval_holdings_table as H
from report_eval.models import ClientInput, ReportOutput, build_meta
from report_eval.text_helpers import amounts_in, money_values

DATA, CONFIG = Path("data"), Path("config/template_config.json")


@pytest.mark.parametrize(
    "text, want",
    [
        ("61,000.00", {61000.0}),
        ("£61,000", {61000.0}),
        ("GBP 61,000", {61000.0}),
        ("£61,000.00", {61000.0}),
        ("worth 40k", {40000.0}),
        ("£40k", {40000.0}),
        ("52,000, which", {52000.0}),
        ("1,234,567", {1234567.0}),
        ("40000", {40000.0}),
        ("£20,000 and 505,000", {20000.0, 505000.0}),
    ],
)
def test_amounts_in_finds(text, want):
    assert amounts_in(text) == want


@pytest.mark.parametrize(
    "text",
    [
        "2026",
        "risk profile 5",
        "0%",
        "30 Apr 2026",
        "H-ISA-01",
        "4000",
        "15 March",
        "version 1.2.3",
    ],
)
def test_amounts_in_ignores_non_money(text):
    assert amounts_in(text) == set()


def test_money_values_stays_strict():
    # expected.json validation relies on needing a £/GBP marker
    assert money_values("61,000") == set()
    assert money_values("£61,000") == {61000.0}


def _ctx(client: str, raw: str):
    meta = build_meta(client, DATA, CONFIG)
    return NS(
        output=ReportOutput.parse(raw), metadata=meta, inputs=ClientInput(client, "")
    )


def test_b3_catches_bare_stale_value():
    assert not F.b3_live_not_stale_values(
        _ctx("client_02_medium", "The GIA holds 40,000.")
    ).value


def test_b2_catches_bare_distractor():
    assert not F.b2_no_distractor_figures(
        _ctx("client_02_medium", "Kestrel stands at 505,000.")
    ).value


def test_b1_catches_untraceable_bare_number():
    assert not F.b1_figures_are_traceable(
        _ctx("client_02_medium", "Each ISA gets 22,500.")
    ).value


TABLE = """## Background & Objectives

| Account | Owner | Type | Value |
|---|---|---|---|
| Holloway GIA | Joint | General Investment Account | {v} |
"""


def test_c5_flags_bare_amount_in_tbc_row():
    r = asyncio.run(
        H.c5_unknown_values_flagged_as_tbc(
            _ctx("client_02_medium", TABLE.format(v="40,000.00"))
        )
    )
    assert not r.value and "unknown value shown as an amount" in r.reason


ISAS = """## Background & Objectives

| Account | Owner | Type | Value |
|---|---|---|---|
| Holloway ISA | David Clarke | Stocks & Shares ISA | {d} |
| Holloway ISA | Susan Clarke | Stocks & Shares ISA | {s} |
"""


def test_c7_reads_bare_values():
    ok = H.c7_table_values_match(
        _ctx("client_02_medium", ISAS.format(d="61,000.00", s="58,500"))
    )
    assert ok.value, ok.reason
    bad = H.c7_table_values_match(
        _ctx("client_02_medium", ISAS.format(d="61,000.00", s="58,000"))
    )
    assert not bad.value and "58,500" in bad.reason


def test_c8_requires_pound_sign():
    assert not H.c8_values_have_pound_sign(
        _ctx("client_02_medium", TABLE.format(v="40,000.00"))
    ).value
    assert H.c8_values_have_pound_sign(
        _ctx("client_02_medium", TABLE.format(v="£40,000"))
    ).value
    assert H.c8_values_have_pound_sign(
        _ctx("client_02_medium", TABLE.format(v="TBC"))
    ).value
