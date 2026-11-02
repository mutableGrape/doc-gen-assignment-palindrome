"""Evaluate generated advice reports with pydantic-evals.

uv run python -m report_eval.run --client client_01_clean
uv run python -m report_eval.run --all [--no-judge]
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from report_eval.dataset import build_dataset, clients
from report_eval.models import ClientInput, ReportOutput


def main() -> None:
    p = argparse.ArgumentParser(description="Evaluate generated advice reports.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--client")
    g.add_argument("--all", action="store_true")
    p.add_argument("--data-dir", type=Path, default=Path("data"))
    p.add_argument("--report-dir", default="outputs")
    p.add_argument("--config", type=Path, default=Path("config/template_config.json"))
    args = p.parse_args()
    load_dotenv()

    names = clients(args.data_dir) if args.all else [args.client]
    names = [n for n in names if (Path(args.report_dir) / f"{n}.md").exists()]
    if not names:
        sys.exit("no reports found")

    dataset = build_dataset(
        names,
        args.data_dir,
        args.config,
    )

    def read_report(inp: ClientInput) -> ReportOutput:
        return ReportOutput.from_file(Path(args.report_dir) / f"{inp.client}.md")

    report = dataset.evaluate_sync(read_report)
    report.print(include_input=False, include_output=False, include_reasons=True)
    failed = any(not a.value for case in report.cases for a in case.assertions.values())
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
