
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
