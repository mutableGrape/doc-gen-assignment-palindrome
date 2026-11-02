"""Every evaluator, one module per theme"""

from report_eval.checks import (
    eval_client_specific,
    eval_fees_tax,
    eval_figures,
    eval_holdings_table,
    eval_scope,
    eval_structure,
    eval_style,
)

_MODULES = [
    eval_structure,
    eval_figures,
    eval_holdings_table,
    eval_fees_tax,
    eval_scope,
    eval_client_specific,
    eval_style,
]


def all_evaluators() -> list:
    """Plain functions; pydantic-evals wraps each, using the function name as its name."""
    return [fn for m in _MODULES for fn in m.EVAL_CHECKS]
