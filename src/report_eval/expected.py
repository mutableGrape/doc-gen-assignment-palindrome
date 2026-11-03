"""Per-client answer key: `data/<client>/expected.json` (schema_version 2).

The DB (client_data_db.json) is the baseline. Without any entry, each open account is expected at its
DB value, a blank value is expected as TBC, and closed accounts are expected to be absent.
expected.json holds only what the DB cannot know, and every entry carries a `why` naming its source:

  overrides:         {account_id: {value, why}}  a newer source disagrees with the DB. `value` is
                     "£X", or "TBC" when the newer source is vague ("around £38,000").
                     The superseded DB figure is automatically treated as stale.
  exclude:           {account_id: why}           open in the DB but out of scope for the report.
  amounts:           [{value, why}]  stated in the notes/request; the report must show them.
  derived_amounts:   [{value, why}]  computed from sources; allowed in the report, not required.
  forbidden_amounts: [{value, why}]  traps the report must not show (figures from distractor
                     documents are already caught by b2).
  forbidden_terms:   [{value, why}]  wording the report must not use.

A `why` starting "CONFIRM" is an unreviewed draft entry and will not load until it is rewritten.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError

from report_eval.text_helpers import money_values

if TYPE_CHECKING:
    from report_eval.models import CaseMeta


def _why(v: str) -> str:
    if len(v) < 3 or v.startswith("CONFIRM"):
        raise ValueError(
            "write the evidence for this entry (drafts start with 'CONFIRM' until reviewed)"
        )
    return v


def _money(v: str) -> str:
    if len(money_values(v)) != 1:
        raise ValueError(f"expected a single £ amount, got {v!r}")
    return v


Why = Annotated[str, AfterValidator(_why)]
Money = Annotated[str, AfterValidator(_money)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Amount(_Strict):
    value: Money
    why: Why


class Override(_Strict):
    value: Literal["TBC"] | Money
    why: Why


class Term(_Strict):
    value: str = Field(min_length=1)
    why: Why


class Expected(_Strict):
    schema_version: Literal[2] = 2
    overrides: dict[str, Override] = {}
    exclude: dict[str, Why] = {}
    amounts: list[Amount] = []
    derived_amounts: list[Amount] = []
    forbidden_amounts: list[Amount] = []
    forbidden_terms: list[Term] = []


class ExpectedError(Exception):
    """expected.json is missing, malformed or contradicts the sources."""


def _gbp(v: float) -> str:
    return f"£{v:,.2f}".removesuffix(".00")


def _is_open(acc: dict) -> bool:
    return acc.get("status", "open") == "open"


def check(exp: Expected, meta: CaseMeta) -> list[str]:
    """Problems the schema cannot see: entries that point at nothing, or at nothing in the sources."""
    db = meta.db_accounts()
    said = money_values(meta.notes) | money_values(meta.request)
    errs = [
        f"{kind}: {i!r} is not a DB account id (have {sorted(db)})"
        for kind, ids in (("overrides", exp.overrides), ("exclude", exp.exclude))
        for i in ids
        if i not in db
    ]
    errs += [
        f"{i} is in both overrides and exclude"
        for i in exp.overrides.keys() & exp.exclude.keys()
    ]
    errs += [
        f"overrides.{i}: {o.value} is not in the notes or request"
        for i, o in exp.overrides.items()
        if o.value != "TBC" and money_values(o.value) - said
    ]
    errs += [
        f"amounts: {a.value} is not in the notes or request"
        for a in exp.amounts
        if money_values(a.value) - said
    ]
    return errs


def load_expected(path: Path, meta: CaseMeta) -> Expected:
    """Parse and check `path`; raises ExpectedError listing every problem."""
    try:
        exp = Expected.model_validate_json(path.read_text("utf-8"))
    except ValidationError as e:
        errs = [
            f"{'.'.join(map(str, x['loc'])) or '(root)'}: {x['msg']}"
            for x in e.errors()
        ]
    else:
        if not (errs := check(exp, meta)):
            return exp
    raise ExpectedError("\n".join([f"{path}:", *(f"  {m}" for m in errs)]))


def resolve(exp: Expected, meta: CaseMeta) -> dict:
    """DB baseline + overrides, in the flat shape the checks read (`meta.expected`). Empty keys are omitted."""
    db = meta.db_accounts()
    multi_platform = len({a["platform"] for a in db.values()}) > 1

    def who(a: dict) -> str:
        return "Joint" if a["owner"] == "Joint" else a["owner"].split()[0]

    def row_pattern(a: dict) -> str:
        """Regex for the account's table row; names the platform only when there are several."""
        return ".*".join(
            map(
                re.escape,
                [*([a["platform"]] if multi_platform else []), who(a), a["type"]],
            )
        )

    live = {i: a for i, a in db.items() if _is_open(a) and i not in exp.exclude}
    accounts = []
    for i, a in live.items():
        o = exp.overrides.get(i)
        value = o.value if o else "TBC" if a.get("value") is None else _gbp(a["value"])
        accounts.append({"match": row_pattern(a), "value": value, "owner": who(a)})

    # An account that cannot be told apart from a live one (e.g. an old closed twin) is covered by
    # the "listed exactly once" check instead.
    taken = {row_pattern(a) for a in live.values()}
    excluded = [
        p for i, a in db.items() if i not in live and (p := row_pattern(a)) not in taken
    ]

    changed = {
        i: o
        for i, o in exp.overrides.items()
        if i in db
        and db[i].get("value") is not None
        and money_values(o.value) != {db[i]["value"]}
    }
    return {
        k: v
        for k, v in {
            "accounts": accounts,
            "excluded_accounts": excluded,
            "stale_values": [_gbp(db[i]["value"]) for i in changed],
            "live_values": [o.value for o in changed.values() if o.value != "TBC"],
            "amounts": [a.value for a in exp.amounts],
            "derived_amounts": [a.value for a in exp.derived_amounts],
            "forbidden_amounts": [a.value for a in exp.forbidden_amounts],
            "forbidden_terms": [t.value for t in exp.forbidden_terms],
        }.items()
        if v
    }


def draft_expected(meta: CaseMeta) -> dict:
    """Candidates for the author to confirm. Every entry starts 'CONFIRM' so an unreviewed draft will not load.

    Overrides: open accounts whose DB figure was struck before the snapshot date.
    Amounts: £ figures in the notes/request that are not a DB value.
    """
    snap, db = meta.db["snapshot_date"], meta.db_accounts()
    db_values = {a["value"] for a in db.values() if a.get("value") is not None}
    return {
        "schema_version": 2,
        "overrides": {
            i: {
                "value": "TBC",
                "why": f"CONFIRM: DB {_gbp(a['value'])} was struck {a['valuation_date']}, before the {snap} snapshot. "
                "Does a newer source give a figure (exact -> that figure, vague -> TBC)? If not, delete.",
            }
            for i, a in db.items()
            if _is_open(a)
            and a.get("value") is not None
            and a.get("valuation_date", snap) < snap
        },
        "amounts": [
            {
                "value": _gbp(v),
                "why": "CONFIRM: appears in the notes/request. Must the report show it? If not, delete.",
            }
            for v in sorted(
                (money_values(meta.notes) | money_values(meta.request)) - db_values
            )
        ],
    }
