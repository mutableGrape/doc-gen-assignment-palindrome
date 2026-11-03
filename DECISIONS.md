
## 001 - Initial Thoughts and Plan of Action

TL;DR: the project is a report generation pipeline with 4 mocked client data repos and 1 shared generation configuration. Goal is to improve the accuracy of the generation pipeline and increase quality throughout. 

Notes from instructions:
1. Clear focus on reading the data, so I expect there to be quality issues. 
2. Evaluation pipeline is going to be key to asserting we're meeting outcomes.
3. The `template_config.json` contains the instructions. Any changes need to generalise and not be overly constrained. 
4. Requirement for a certain phrase to be deterministic which will need consideration

Initial Actions: 
- [x] Fork the repo, clone it locally, and set the DECISIONS.md file 
- [x] Configure the api key, install deps, run the script on client_01
- [x] Read the data files, understand potential edge cases and gaps
- [x] Initial commit 

Observations:
1. In the generated report there are:
    - A number of string concatenation issues, duplications
    - Some made up facts/statements from the LLM 
    - No sections/placeholders for the advisor to insert factual information 
    - Deviations from the instructions in `fde_notes.md`
2. In the client data, issues can be expected to arise from:
    - Mismatches between e.g. meeting notes and db/statement
    - Stale values (e.g. going by `snapshot_date`) 
    - Null or missing values 
    - Vague phrasing (e.g. 'around' or 'over') 
    - Potentially misleading numbers the LLM should disregard 

Next steps will be to identify and close the gaps on the client-01 case to establish what good looks like before generalising to the other clients. 

NB: w.r.t. WoW, committing straight to main branch and including updates in DECISIONS.md as I go 


## 002 - Setting up the Eval Pipeline

Decisions made:
1. Pipeline should combine deterministic checks (code), LLM-as-Judge, and reference figure checks (treating the dataset as training data). 
2. Placeholders should be human-first, so `[PLACE_HOLDER]` is the chosen format 
3. Eval cases chosen to meet only the defined requirements for client 01 for now (not additional changes yet)
4. Eval cases are grouped by area, file stucture reflects this
5. Opted to use Pydantic Evals to reduce overhead and provide a bit more functionality out of the box. 
6. Included the corresponding pydantic claude plugin marketplace in the repo (makes development easier)

Ran client_01 through evals and hit ~50% pass rate showing issues are being caught correctly.  


## 003 - Improving the Eval Pipeline

Decisions made:
1. A static training-data style object helps with ensuring right values are present. To minimise potential drift, this should be a structured delta on the db rather than a copy of the information. I've added a script to help generate it, but the contents are to be hand-reviewed and updated in this case. 


## 004 - Client 01: Minimal Prompt Changes

Intentionally used minimal prompt changes to take client_01 from ~72% to 100% on 4/4 runs.

## 005 - Client 02: Minimal Prompt Changes

Took client_02 from ~92% to ~98% (4/6 runs at 100%): CGT as a `[TO BE CONFIRMED]`. Ensured client_01 remained at 100%. 


## 006 - Client 03: Context, Placeholders, Bereavement

Decisions:
1. Pipeline only feeds `context_files` (db, notes, request, fde_notes): distractor docs and the image are dropped.
2. Joint accounts are deduped in code (one entry per account_id) instead of asking the model to list it once.
3. No figure inside a `[TO BE CONFIRMED]` placeholder; Recommendations states no account values, sums or splits (allocation is a placeholder) and the new-money amount comes from the request only.
4. Background acknowledges a bereavement gently.
5. Added `forbidden_amounts` £38,000 (client_03) and £45,000 (client_02) to expected.json: vague figures are otherwise "allowed" because they appear in the notes.
6. Decison to allow inclusion of cash account as per a total-wealth approach. Would aim to confirm this real-life scenario. 

Open: judge d5 occasionally rejects the request's 0.5% initial charge

## 007 - Eval flakiness and client_03 coverage

1. d5/d3 judges: the rubric now names the request's initial-charge percentage explicitly as allowed (d5) and says not mentioning it passes (d3). Previously the judge rejected it in ~1 in 4 runs
2. f2 (per-platform charges) is now gated deterministically on the db's platform count
3. New checks: e5 (Introduction covers every requested account, incl. a new one) and client_03 `forbidden_terms` (grandchildren, trip, flowers: small talk the notes say changes nothing)
4. Residual: client_02 states £45,000; client_03 states £120,000 in Background. Now caught in eval. 
5. Refactoring the Judge context to reduce input tokens needed. 


## 008 - Client 04 (stretch): Predicted Issues (pre-run)

Approach for this client: predict issues, improve the eval pipeline first, test on 'ideal' output, then delegate to the coding agent to make the improvements. 

Potential issues identified:

| # | Issue | Evidence | Correct handling |
|---|---|---|---|
| 1 | Stale joint Holloway GIA | DB £240,000 valued 28 Feb (snapshot 30 Apr); statement PNG repeats £240,000 (28 Feb); notes 20 May: live "around £255,000" | Newer but vague, so `[TO BE CONFIRMED: current value of the Holloway joint GIA]`; never show £240k or £255k |
| 2 | Caroline's Meridian cash: `value: null`, `valuation_date: null` | DB; notes say she will confirm | Row present, Value = TBC; flag as outstanding item |
| 3 | Closed `M4-OLD-C` (£0) | DB status closed; notes say disregard | Absent from table (same platform/owner/type as the live cash account, so a naive prompt can double-list it) |
| 4 | Joint accounts duplicated under both holders (3 of them) | DB | Already deduped in `dedupe_accounts` |
| 5 | Request gives no investment amount ("see meeting notes"); current rule is "amount from request only, else state none" | report_request | Real amounts only in notes: £850,000 received, £200,000 committed to bridging loan. Spec wants amounts in Recommendations, so the current prompt will likely drop them |
| 6 | Earnout up to £400,000 | Notes: contingent, unreceived, up to 2 years | Must not be treated as investable; at most mentioned as excluded/uncertain, never added to the pot |
| 7 | £650,000 available is derived; bridging-loan repayment timing unconfirmed | Notes (adviser action item) | Do not assert as fact; post-repayment amount TBC/pending (matches draft `derived_amounts`) |
| 8 | Distractor figures: Pendle £775k, Sutton £785k | platform_market_update, portfolio_pack | Already excluded via `context_files`; add as `forbidden_amounts` to prove it |
| 9 | Non-advice noise: France property, grandchildren school fees, charity | Notes: "nothing should be actioned" | Keep out of Recommendations/Background (grey area: one-line objective; recommend omit) |
| 10 | Pension allowance worry | Notes: report must not commit to a figure breaching limits | No SIPP/ISA contribution figures; allocation = TBC |
| 11 | Offshore bond in scope but "leave as is" | Notes | Table row plus "no change, revisit at next review"; no sale recommended |
| 12 | Three platforms | DB | Platform charges per platform (Holloway, Brightwell, Meridian), all TBC; 0.5% initial charge one-off (request) |
| 13 | Notes say snapshot was "struck in February", but DB `snapshot_date` is 30 Apr; only one account is Feb-dated | DB vs notes | Rely on per-account `valuation_date`, not `snapshot_date` |
| 14 | fde_notes are thin: mention multi-platform and proceeds-in-several-forms, but not null/closed accounts, stale GIA, missing request amount or earnout | fde_notes.md | Treat as incomplete, as warned |
| 15 | Joint clients; template says "your annual exempt amount" (singular) | config template | Fixed template wording; flag as limitation (two allowances) |
| 16 | Tax section needed: partial sale of Holloway joint GIA | request "Yes" | Include with CGT TBC (`sells_investments` + `use_if` should handle it) |


## 009 - Client 04: Tightened expected.json

Defects found by reading:
1. Recommendations call the full £850,000 "new money to be invested", ignoring the £200,000 already committed to the loan (prediction 5 was half right: the model took £850k from the notes but not the deduction).
2. Background mentions grandchildren's school fees and charity (issue 9) and the "emotional period". Passed only because `forbidden_terms` was empty.
3. "The remaining funds will be added to the joint GIA" misreads the agreed plan (the remaining balance goes to the new joint account).
4. No "offshore bond unchanged, revisit at next review" statement (issue 11).

Additional keys added to `expected.json` to handle required and forbidden statements as well as outstanding items. 


## 010 - Client 04: Eval gaps, new checks, ideal report

Ideal report added to ensure target state is clear and evals are correctly aligned to the goal. 

Using the ideal report and issues context, updates were made to the evals to include more cases while ensuring alignment with previous clients. 

## 011. Client 04 prompt optimisation

Three prompts changed in `config/template_config.json`;
- `summary`: only what bears on the advice; omit unactioned aspirations, tangents and feelings.
- `recommendation`: one paragraph per action in the notes' plan, plus unchanged products ("revisited at next review");
  amount from the request, else the amount received in the notes, naming committed parts; contingent money never counted;
  a specific placeholder per unknown amount; no account values, no invented actions; closing per-platform charge flag.
- `fees`: one placeholder per platform when several, plus the ongoing advice charge.

Results: client_04 86.0% -> 95-100%. Clients 01-03 100%.
One drift caught and fixed mid-way: loosening "do not state account values" made client_03 quote the vague £38,000.
Remaining flake on client_04: occasionally the GIA top-up or one outstanding item is dropped (h1/h3), or charges not per platform (f2).
Not changed: cash accounts stay in the table; generic tax-relief sentences are discouraged by the prompt, not forbidden.
