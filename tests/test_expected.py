import json
from pathlib import Path

import pytest

from report_eval.expected import (
    Expected,
    ExpectedError,
    draft_expected,
    load_expected,
    resolve,
)
from report_eval.models import build_meta

DATA, CONFIG = Path("data"), Path("config/template_config.json")


def _meta(client="client_02_medium"):
    return build_meta(client, DATA, CONFIG)


def _load(tmp_path, doc, client="client_02_medium"):
    p = tmp_path / "expected.json"
    p.write_text(json.dumps(doc))
    meta = _meta(client)
    return resolve(load_expected(p, meta), meta)


def _error(tmp_path, doc) -> str:
    with pytest.raises(ExpectedError) as e:
        _load(tmp_path, doc)
    return str(e.value)


def test_empty_file_is_db_baseline(tmp_path):
    got = _load(tmp_path, {"schema_version": 2})
    assert {a["value"] for a in got["accounts"]} == {"£61,000", "£58,500", "£40,000"}
    assert "stale_values" not in got


def test_tbc_override_marks_db_figure_stale(tmp_path):
    got = _load(
        tmp_path, {"overrides": {"H-GIA-J": {"value": "TBC", "why": "notes: vague"}}}
    )
    assert [a["value"] for a in got["accounts"]].count("TBC") == 1
    assert got["stale_values"] == ["£40,000"]


def test_numeric_override_is_live(tmp_path):
    # £45,000 is in the 02 notes only as "a little over", but money_values reads it as a figure
    got = _load(
        tmp_path, {"overrides": {"H-GIA-J": {"value": "£45,000", "why": "notes"}}}
    )
    assert got["live_values"] == ["£45,000"] and got["stale_values"] == ["£40,000"]


def test_blank_db_value_is_tbc_and_closed_is_excluded():
    got = resolve(Expected(), _meta("client_04_stretch"))
    assert sum(a["value"] == "TBC" for a in got["accounts"]) == 1
    # the closed account has the same row pattern as the open Meridian cash twin, so it is not matched on
    assert "excluded_accounts" not in got


@pytest.mark.parametrize(
    "doc, fragment",
    [
        (
            {"overrides": {"NOPE": {"value": "TBC", "why": "x y z"}}},
            "not a DB account id",
        ),
        (
            {"overrides": {"H-GIA-J": {"value": "£99,999", "why": "x y z"}}},
            "not in the notes or request",
        ),
        (
            {"amounts": [{"value": "£7,777", "why": "made up"}]},
            "not in the notes or request",
        ),
        (
            {
                "overrides": {"H-GIA-J": {"value": "TBC", "why": "x y z"}},
                "exclude": {"H-GIA-J": "x y z"},
            },
            "both overrides and exclude",
        ),
        ({"overrides": {"H-GIA-J": {"value": "TBC", "why": ""}}}, "write the evidence"),
        (
            {
                "overrides": {"H-GIA-J": {"value": "TBC", "why": "x y z"}},
                "stale_value": [],
            },
            "stale_value",
        ),
    ],
)
def test_rejected(tmp_path, doc, fragment):
    assert fragment in _error(tmp_path, doc)


def test_unreviewed_draft_does_not_load(tmp_path):
    draft = draft_expected(_meta())
    assert list(draft["overrides"]) == ["H-GIA-J"]
    assert "write the evidence" in _error(tmp_path, draft)


def test_shipped_files_load():
    for c in (
        "client_01_clean",
        "client_02_medium",
        "client_03_hard",
        "client_04_stretch",
    ):
        assert _meta(c).has_expected
