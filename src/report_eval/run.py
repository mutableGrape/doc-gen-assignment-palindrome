"""Evaluate generated advice reports with pydantic-evals.

uv run python -m report_eval.run --client client_01_clean
uv run python -m report_eval.run --all
uv run python -m report_eval.run --client client_04_stretch --repeat 3                    # stability
uv run python -m report_eval.run --client client_02_medium --draft-expected   # scaffold expected.json
uv run python -m report_eval.run --all --check-expected                      # validate only
"""

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from report_eval.dataset import build_dataset, clients
from report_eval.expected import ExpectedError, draft_expected
from report_eval.models import ClientInput, ReportOutput, build_meta
from report_eval.stability import collect, render


def expected_tools(names: list[str], args) -> int:
    bad = 0
    for n in names:
        path = args.data_dir / n / "expected.json"
        if args.draft_expected and not path.exists():
            meta = build_meta(n, args.data_dir, args.config)
            path.write_text(
                json.dumps(draft_expected(meta), indent=2, ensure_ascii=False) + "\n",
                "utf-8",
            )
            print(
                f"{n}: wrote draft {path}; review each CONFIRM entry (edit or delete it, then rewrite its why as the evidence)"
            )
        elif args.draft_expected:
            print(f"{n}: {path} exists, not overwriting")
        if args.check_expected or args.draft_expected:
            try:
                build_meta(n, args.data_dir, args.config)
                print(
                    f"{n}: expected.json OK"
                    if path.exists()
                    else f"{n}: no expected.json"
                )
                bad += not path.exists() and args.check_expected
            except ExpectedError as e:
                print(e, file=sys.stderr)
                bad += 1
    return 1 if bad else 0


def main() -> None:
    p = argparse.ArgumentParser(description="Evaluate generated advice reports.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--client")
    g.add_argument("--all", action="store_true")
    p.add_argument("--data-dir", type=Path, default=Path("data"))
    p.add_argument("--report-dir", default="outputs")
    p.add_argument("--config", type=Path, default=Path("config/template_config.json"))
    p.add_argument(
        "--draft-expected",
        action="store_true",
        help="write candidate overrides/amounts to confirm, if absent",
    )
    p.add_argument(
        "--check-expected",
        action="store_true",
        help="validate expected.json against sources and exit",
    )
    p.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="evaluate each report N times and print per-check stability (PASS/FLAKY/FAIL)",
    )
    args = p.parse_args()
    load_dotenv()

    names = clients(args.data_dir) if args.all else [args.client]
    if args.draft_expected or args.check_expected:
        sys.exit(expected_tools(names, args))
    try:
        for n in names:
            if (Path(args.report_dir) / f"{n}.md").exists():
                build_meta(
                    n, args.data_dir, args.config
                )  # fail fast on a bad expected.json
    except ExpectedError as e:
        sys.exit(str(e))
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

    report = dataset.evaluate_sync(read_report, repeat=args.repeat)
    if args.repeat > 1:
        print(render(collect(report)))
    else:
        report.print(include_input=False, include_output=False, include_reasons=True)
    failed = any(not a.value for case in report.cases for a in case.assertions.values())
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
