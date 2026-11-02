"""The eval dataset: one Case per client.

inputs   - `ClientInput`: client id and source text (what the judge compares against)
metadata - `CaseMeta`: sources, config, expectations and flags such as `sells_investments`
output   - `ReportOutput`, produced by the task passed to `evaluate_sync`
"""

from __future__ import annotations

from pathlib import Path

from pydantic_evals import Case, Dataset

from report_eval.checks import all_evaluators
from report_eval.models import CaseMeta, ClientInput, ReportOutput, build_meta


def clients(data_dir: Path) -> list[str]:
    return sorted(p.parent.name for p in data_dir.glob("*/client_data_db.json"))


def build_dataset(
    names: list[str],
    data_dir: Path,
    config_path: Path,
) -> Dataset[ClientInput, ReportOutput, CaseMeta]:
    cases = []
    for name in names:
        meta = build_meta(name, data_dir, config_path)
        cases.append(
            Case(name=name, inputs=ClientInput(name, meta.source_text), metadata=meta)
        )
    return Dataset(name="report_eval", cases=cases, evaluators=all_evaluators())
