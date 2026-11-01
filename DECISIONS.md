
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

