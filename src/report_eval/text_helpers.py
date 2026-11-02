"""String processing helpers: normalising, money/percent extraction, markdown parsing."""

from __future__ import annotations

import re

RISK_WARNING = (
    "The value of investments can fall as well as rise and you may get back less than you invest. "
    "Past performance is not a guide to future returns."
)
# Convention the pipeline must use for figures a person finalises.
PLACEHOLDER_RE = re.compile(r"\[TO BE CONFIRMED:[^\]]+\]")

_MONEY_RE = re.compile(r"(?:£|GBP\s?)\s?(\d[\d,]*(?:\.\d+)?)\s?(k|m)?\b", re.I)
_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s?%")
_SELLING_RE = re.compile(r"Selling existing investments\?[\s|]*(yes|no)", re.I)


def norm(text: str) -> str:
    """Collapse whitespace and curly quotes so verbatim comparisons are layout-proof."""
    text = text.replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip()


def money_values(text: str) -> set[float]:
    out: set[float] = set()
    for num, suffix in _MONEY_RE.findall(text):
        value = float(num.replace(",", ""))
        value *= {"k": 1e3, "m": 1e6}.get(suffix.lower(), 1)
        out.add(round(value, 2))
    return out


def parse_expected_money(items: list[str]) -> set[float]:
    return money_values(" ".join(items))


def percent_values(text: str) -> set[float]:
    return {float(p) for p in _PERCENT_RE.findall(text)}


def format_money(values) -> str:
    return ", ".join(f"£{v:,.0f}" for v in sorted(values))


def split_sections(markdown: str) -> dict[str, str]:
    """`## Title` sections of a markdown report, in order, as {title: body}."""
    sections: dict[str, list[str]] = {}
    title = None
    for line in markdown.splitlines():
        if line.startswith("## "):
            title = line[3:].strip()
            sections[title] = []
        elif title is not None:
            sections[title].append(line)
    return {t: "\n".join(lines).strip() for t, lines in sections.items()}


def markdown_tables(text: str) -> list[list[list[str]]]:
    """Markdown tables in `text` as lists of rows (header first, separator dropped)."""
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    for line in text.splitlines() + [""]:
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                current.append(cells)
        elif current:
            tables.append(current)
            current = []
    return tables


def sells_investments(request: str) -> bool | None:
    """The report request's 'Selling existing investments?' answer, if it has one."""
    m = _SELLING_RE.search(request)
    return m.group(1).lower() == "yes" if m else None


def find_line(text: str, needle: str) -> str | None:
    """First line of `text` containing `needle`, normalised."""
    for line in text.splitlines():
        if needle in line:
            return norm(line)
    return None


def sentences(text: str) -> list[str]:
    """Rough sentence split over non-table lines (also splits on blank lines and bullets)."""
    out: list[str] = []
    for line in text.splitlines():
        if line.strip().startswith("|"):
            continue
        out += [x.strip() for x in re.split(r"(?<=[.!?])\s+", line) if x.strip()]
    return out


def paragraphs(text: str) -> list[str]:
    """Non-empty blank-line separated blocks."""
    return [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]


def prose(text: str) -> str:
    """`text` without markdown table lines."""
    return "\n".join(line for line in text.splitlines() if not line.strip().startswith("|"))
