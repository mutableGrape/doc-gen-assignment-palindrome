"""Checks on tone, style and cleanliness of the writing."""

import re

from pydantic_evals.evaluators import EvaluationReason

from report_eval.checks._base import Ctx, Result, judge
from report_eval.text_helpers import prose

# a lowercase word running straight into a capitalised sentence opener: "in relation to This ..."
_SEAM = re.compile(r"\b[a-z]+ (This|We|You|Your|Our|It|The)\b")


def g4_no_template_seams_or_doubled_full_stops(ctx: Ctx) -> Result:
    """No doubled full stops and no sentence dropped into a mid-sentence slot"""
    text = prose(ctx.output.raw)
    problems = [
        f"'..' in: {m.group(0)!r}" for m in re.finditer(r".{20}\.\.(?!\.)", text)
    ]
    problems += [f"seam: {m.group(0)!r}" for m in _SEAM.finditer(text)]
    return EvaluationReason(value=not problems, reason="; ".join(problems) or None)


async def g1_written_in_1st_person_british_english(ctx: Ctx):
    return await judge(
        ctx,
        "Written in British English and in the first person plural ('we'), addressing the client as 'you'.",
    )


async def g2_no_irrelevant_detail(ctx: Ctx):
    return await judge(
        ctx,
        "No irrelevant detail from the meeting note (holidays, unrelated property, etc.) appears in the report.",
    )


async def g3_client_is_addressed_directly(ctx: Ctx):
    return await judge(
        ctx,
        "Ignore the accounts table completely: names in table cells are expected and never a failure. In the running prose (paragraphs and bullets), the client must be referred to as 'you'/'your', never by name and never as 'she', 'he', 'her' or 'his'. Naming one holder of a joint client purely to tell individual accounts apart (e.g. \"David's ISA\") is acceptable. Fail only if you can quote a prose sentence that breaks this, and quote it in your reason; if you cannot quote one, pass.",
    )


async def g5_introduction_is_short_and_well_phrased(ctx: Ctx):
    return await judge(
        ctx,
        "Judge the Introduction section only. It is built from fixed template text: 'Further to our recent discussions, we are writing to set out our advice in relation to <accounts>. This advice is based on the information currently available to us.' followed by the firm's FCA statement as its own paragraph. Both are standard and never a failure, and the FCA paragraph does not count towards length. Pass if the Introduction is short overall (the template text plus at most a couple of extra sentences) and reads smoothly and professionally. Briefly framing the client's situation or goals is fine. Fail only if it is long, rambling or repetitive, or is awkwardly or ungrammatically phrased. Quote the offending text in your reason; if you cannot quote any, pass.",
    )


EVAL_CHECKS = [
    g1_written_in_1st_person_british_english,
    g2_no_irrelevant_detail,
    g4_no_template_seams_or_doubled_full_stops,
    g3_client_is_addressed_directly,
    g5_introduction_is_short_and_well_phrased,
]
