"""Typed task output and per-case metadata for the report evals.

ClientInput  - the case inputs: client id plus source text (what the LLM judge sees).
ReportOutput - what the task returns: the raw markdown plus its parsed sections.
CaseMeta     - what a Case carries as `metadata`: the source material and expectations
               the checks compare a report against (nothing here depends on the report).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from document_formatter.loading import read_file

from report_eval.expected import load_expected, resolve

from report_eval.text_helpers import (
    find_line,
    markdown_tables,
    sells_investments,
    split_sections,
)

# Sources the report is written from; every other docx in a client folder is a distractor.
CORE_SOURCES = {"meeting_notes.docx", "report_request.docx", "client_data_db.json"}


@dataclass
class ClientInput:
    """Case inputs: which client, and the source text the report was written from."""

    client: str
    sources: str = ""


@dataclass
class ReportOutput:
    raw: str
    sections: dict[str, str] = field(default_factory=dict)

    @classmethod
    def parse(cls, raw: str) -> ReportOutput:
        return cls(raw=raw, sections=split_sections(raw))

    @classmethod
    def from_file(cls, path: Path) -> ReportOutput:
        return cls.parse(path.read_text(encoding="utf-8"))

    def find_section(self, title_part: str, *, prefix: bool = False) -> str | None:
        """Body of the first section whose title contains (or starts with) `title_part`."""
        part = title_part.lower()
        for title, body in self.sections.items():
            low = title.lower()
            if low.startswith(part) if prefix else part in low:
                return body
        return None

    @property
    def tables(self) -> list[list[list[str]]]:
        return markdown_tables(self.raw)


@dataclass
class CaseMeta:
    notes: str
    request: str
    db: dict
    distractors: str  # text of sources that must not feed the report
    expected: dict  # per-client expected.json (empty if none)
    has_expected: bool  # whether expected.json exists for this client
    config: dict
    config_text: str
    other_client_strings: set[
        str
    ]  # names/ids from other clients, for overfitting checks
    sells_investments: bool | None
    fca_line: str | None

    @property
    def source_text(self) -> str:
        return f"{self.notes}\n{self.request}\n{json.dumps(self.db)}"

    def db_accounts(self) -> dict[str, dict]:
        """Accounts de-duplicated by account_id (joint accounts appear under each holder)."""
        accounts: dict[str, dict] = {}
        for holder in self.db.get("holders", {}).values():
            for acc in holder.get("accounts", []):
                accounts.setdefault(acc["account_id"], acc)
        return accounts


def build_meta(client: str, data_dir: Path, config_path: Path) -> CaseMeta:
    client_dir = data_dir / client
    config_text = config_path.read_text(encoding="utf-8")
    config = json.loads(config_text)
    expected_path = client_dir / "expected.json"

    docs = {p.name: read_file(p) for p in client_dir.glob("*.docx")}
    db = json.loads((client_dir / "client_data_db.json").read_text(encoding="utf-8"))

    other: set[str] = set()
    for other_db in data_dir.glob("*/client_data_db.json"):
        data = json.loads(other_db.read_text(encoding="utf-8"))
        for holder in data.get("holders", {}).values():
            other.add(holder["name"])
            other.update(a["account_id"] for a in holder.get("accounts", []))

    request = docs.get("report_request.docx", "")
    fca_line = next(
        (
            line
            for s in config["sections"]
            if (line := find_line(s.get("template", ""), "authorised and regulated"))
        ),
        None,
    )
    meta = CaseMeta(
        notes=docs.get("meeting_notes.docx", ""),
        request=request,
        db=db,
        distractors="\n".join(t for n, t in docs.items() if n not in CORE_SOURCES),
        expected={},
        has_expected=False,
        config=config,
        config_text=config_text,
        other_client_strings=other,
        sells_investments=sells_investments(request),
        fca_line=fca_line,
    )
    if expected_path.exists():
        meta.expected = resolve(
            load_expected(expected_path, meta), meta
        )  # raises ExpectedError
        meta.has_expected = True
    return meta
