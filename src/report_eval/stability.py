"""Aggregate repeated eval runs (`evaluate_sync(repeat=N)`) into per-check stability figures.

A single run can't tell a real defect from judge noise. Over N runs, each assertion gets a pass
count and each score a mean and minimum; an assertion that passes on some runs and fails on others
is flagged as FLAKY so it is fixed (or its rubric tightened) rather than trusted.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

_RUN_SUFFIX = re.compile(r"\s*\[\d+/\d+\]$")


@dataclass
class CheckStats:
    passes: int = 0
    runs: int = 0
    scores: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)  # from failing runs

    @property
    def status(self) -> str:
        if self.passes == self.runs:
            return "PASS"
        return "FAIL" if self.passes == 0 else "FLAKY"


def collect(report) -> dict[str, dict[str, CheckStats]]:
    """{case name: {check name: stats}} from a pydantic-evals EvaluationReport."""
    out: dict[str, dict[str, CheckStats]] = defaultdict(lambda: defaultdict(CheckStats))
    for case in report.cases:
        name = _RUN_SUFFIX.sub("", case.name)
        for check, res in case.assertions.items():
            st = out[name][check]
            st.runs += 1
            st.passes += bool(res.value)
            if not res.value and res.reason:
                st.reasons.append(res.reason)
        for check, res in case.scores.items():
            out[name][check.removesuffix("_score")].scores.append(float(res.value))
        for err in (
            case.evaluator_failures
        ):  # a crashed check is a failed run, not a skipped one
            st = out[name][err.name]
            st.runs += 1
            st.errors.append(err.error_message[:200])
    for case in report.failures:  # task or evaluator crashed: count it, never hide it
        out[_RUN_SUFFIX.sub("", case.name)]["task_error"].runs += 1
    return out


def render(
    stats: dict[str, dict[str, CheckStats]], *, only_unstable: bool = False
) -> str:
    lines = []
    for name, checks in stats.items():
        total = sum(c.runs for c in checks.values() if c.runs)
        passed = sum(c.passes for c in checks.values() if c.runs)
        lines.append(f"\n{name}: {passed}/{total} assertion-runs passed")
        for check, c in sorted(checks.items()):
            if not c.runs or (only_unstable and c.status == "PASS"):
                continue
            score = (
                f"  score mean {sum(c.scores) / len(c.scores):.2f} min {min(c.scores):.2f}"
                if c.scores
                else ""
            )
            lines.append(f"  {c.status:5} {c.passes}/{c.runs}  {check}{score}")
            lines += [f"        error: {e}" for e in sorted(set(c.errors))]
            if c.status == "FLAKY":  # the failing runs' reasons are what needs fixing
                lines += [f"        why: {r[:400]}" for r in sorted(set(c.reasons))]
    return "\n".join(lines)
