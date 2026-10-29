# Contract review

Reviews one supplier contract against Veridian's negotiation playbook, proposes changes in
approved clause-library wording only, decides the contract's status, pauses for legal counsel
when a decision needs sign-off, and then updates the mock contract register.

## Set up and run

Python 3.12. No packages to install: the code uses only the standard library.

```
cd code
cp .env.example .env             # optional: add GROQ_API_KEY and/or GEMINI_API_KEY
python -m app run --case ../samples/UC5-S02.json --out out/UC5-S02.json
python -m app approve <run_id> --action approve          # the run_id is printed when a run pauses
python -m app run --case ../samples/UC5-S02.json --out out/UC5-S02.json --auto-approve
python -m app eval --cases ../samples
python -m app eval --cases tests/cases                   # writes tests/score.json
python -m unittest discover -s tests                     # unit tests
```

`DATA_DIR` points at the data pack (default: the repository root). Results go where `--out`
says; register updates and markups go to `mock_system/` at the repository root (or
`MOCK_SYSTEM_DIR`); paused runs to `code/runs/`; traces to `code/traces/`.

Approval actions on a paused run:

| Action | Effect |
| --- | --- |
| `approve` | Counsel accepts every proposed change. The register update and markup are written. |
| `reject` | Counsel rejects the outcome. Nothing is written. |
| `change --reject-changes R-06,R-10` | Counsel accepts some changes and rejects others. A rejected change means counsel accepts the supplier's wording for that rule; the decision is worked out again from what remains, then written. |

A contract approved as it stands (`COMPLIANT`) needs no sign-off and is written straight away.

## Design

Five agents run in a fixed order under one orchestrator ([diagram](docs/architecture.md)).
The order is fixed because each step needs the one before; the orchestrator's decisions are
about *whether* to continue: loop back after review, pause for a human, or stop on a tool error.

1. **Intake** reads the register record, counterparty (risk tier), the rules that apply to the
   contract type, the clause library and the contract, parsed into numbered paragraphs. It flags
   paragraphs that try to instruct the reviewer ("pre-approved", "need not be checked").
2. **Clause analyst** handles each applicable rule in turn:
   - checks the rule's condition (R-09 only for high-risk counterparties, R-11 only above
     ₹1 crore, and R-01's fallback isn't acceptable above ₹1 crore);
   - scans **every** paragraph, definitions and "Miscellaneous" included, for text that is
     about this clause type, judged by content, not heading (playbook 2.3);
   - grades each match: a word-for-word library clause is recognised, but still goes through
     the rule's conditions; other wording is read by the rules engine (`rules.py`), which pulls
     out the number that matters (cap multiple, years, days, hours, ₹ cover, governing law,
     forum, IP owner and licence) and compares it with the preferred / fallback / red-line
     thresholds;
   - wording the rules engine can't read goes to the **LLM analyst**; if no clause is found at
     all and a model is configured, the model reads the whole contract in case the clause is
     hidden somewhere unexpected. Any paragraph reference the model returns is checked against
     the real contract;
   - where a rule has several matching paragraphs, the worst status wins (a hidden indemnity in
     a definition beats a harmless section 7).
3. **Drafter** proposes the *preferred* library clause, word for word, for every clause that
   is a deviation, red line, missing or unclear (playbook 3.1–3.2). The fallback is used only
   where the counterparty has rejected the preferred clause in writing; the pack records no
   such rejections.
4. **Reviewer** (the second reviewer of playbook 3.3) checks every proposal is a real library
   clause, word for word, of the right type, and that nothing acceptable is being changed. It may
   send the work back; the orchestrator allows at most two rounds, and anything still wrong goes
   to a human.
5. **Decider** applies playbook section 4: any red line → `reject`; otherwise any deviation (or
   unclear clause) → `changes_proposed / DEVIATIONS_FOUND`; otherwise any missing required clause
   → `changes_proposed / MISSING_CLAUSES`; otherwise `approve / COMPLIANT`.

`needs_human` is true for `changes_proposed` and `reject` (counsel accepts each change and
confirms every rejection) and false for `approve`.

**Why mostly rules, not mostly a model:** the playbook is numeric (2x, 45 days, 72 hours,
₹2 crore) and the same risk must get the same answer every time (playbook section 1). Code makes
those comparisons exactly, reproducibly and offline; the model is kept for reading wording the
code has not seen before. The model never makes the final decision.

**Prompt injection:** contract text is data. Paragraphs that try to instruct the reviewer are
listed in `ignored_instructions_in_contract` and cite playbook §6; they change nothing.
Contract text sent to a model sits inside `<contract>` tags under a system prompt saying so.

### Result fields

The schema fields, plus `run_id`, `status`, `contract_id`, `contract_type`, `counterparty`,
`findings` (one per applicable rule: `rule_id`, `clause_type`, `status`, `section`, `heading`,
`found_text`, `observed` numbers, `issue`, `source` = library_match | rules | llm | condition |
unclear, and where a change is needed `proposed_clause_id`, `proposed_text`, `proposed_action`),
`review_rounds`, `key_numbers`, `ignored_instructions_in_contract` and `warnings`.

`citations` holds the contract ID, counterparty ID, every rule checked, every contract section
relied on (`CTR-1012 §4.1`), every clause proposed (`CL-06-P`) and the playbook section that
decided the outcome.

## Tools

All in `tools.py`, read-only, opening the SQLite file in read-only mode.

| Tool | Takes | Returns |
| --- | --- | --- |
| `get_contract_record` | contract ID | register row |
| `get_counterparty` | counterparty ID | name, risk tier |
| `get_rules` | contract type | the rules whose `applies_to` includes it |
| `get_clause_library` | – | every approved clause by ID |
| `load_contract` | contract ID | numbered paragraphs with headings, and the schedule's annual fee |

Each raises `ToolError` with a plain message (unknown contract, missing file, no rules for the
type, bad ID format). The CLI prints it and exits with code 2; `eval` scores that case 0 and
carries on. The contract ID is checked against a strict pattern before it is used in a file path.

## Models used and why

| Agent | Model | Why |
| --- | --- | --- |
| Clause analyst (fallback reading) | Groq `llama-3.3-70b-versatile` | strong at reading legal text, fast and cheap on Groq, good JSON mode |
| same, if Groq fails | Gemini `gemini-2.5-flash` | a second provider, so one outage or rate limit doesn't stop a review |
| Intake, drafter, reviewer, decider | none (code) | these follow fixed rules; a model would only add risk |

Temperature 0 and JSON mode. Models can be changed with `GROQ_MODEL` / `GEMINI_MODEL`. With no
key set, the system runs on the rules engine alone, which handles every contract in the pack.

## Failure handling

- **Rate limits and server errors (429, 5xx):** up to 4 tries with exponential backoff,
  honouring `Retry-After`, then the next provider.
- **Bad model replies:** invalid JSON or missing keys get one repair request; an invalid status
  or a paragraph reference that isn't in the contract is thrown away.
- **No model, or every provider failed:** the clause is marked `unclear`, which counts as a
  deviation and goes to counsel. The system never approves what it couldn't read.
- **Failed tools / missing data:** `ToolError` stops the run with a clear message; nothing is
  written to the mock system.
- **Schedule fee differs from the register:** the register value is used and a warning is added.
- **Review not settled after two rounds:** the problems are attached and the run goes to a human.
- **Writes:** only after the decision is final (and approved, where sign-off is needed); a
  rejected approval writes nothing; a run can't be approved twice.

## Tests and score

- `tests/cases/` + `tests/expected/`: 24 cases, one per contract in the pack. Expected answers
  come from reading each contract against the playbook by hand, not from the system's output.
  They cover every outcome and the traps: governing law under "Miscellaneous" (T20), indemnity
  hidden in a definition (T18), foreign law (T15), liability caps at 25% and 40% (T08, T16), the
  >₹1 crore rules R-01 and R-11 (T22, T17), the high-risk audit rule (T07, T06), three deviations
  in one contract (T10) and two contracts with "pre-approved / don't check" notes (T12, T16).
  Several check key numbers (the 0.25x cap, 1-year term, 15 and 30 days).
- `tests/test_rules.py`: 25 paraphrased clauses that don't appear in the pack, the approval gate
  (pause, approve, reject, compliant with no sign-off), word-for-word proposals, injection
  handling and scoring.

**Score:** 100% on `tests/cases` (24 cases, `tests/score.json`) and 100% on `../samples` (5 cases),
running on the rules engine with no model key.
