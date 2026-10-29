# AZ4C assignment data pack: use case 5, Contract review

This pack holds everything you need to build and test your system for this use case.

## What's inside

```
README.md        this file
USE_CASE.md      the use case on its own
COMMON.md        commands, DATA_DIR, result format, mock system
data/            legal.sqlite plus one CSV per table (5 files)
docs/            company documents as Markdown (25 files)
samples/         5 test cases and their expected answers (10 files)
schema/          result.schema.json, the exact result format
```

## The use case

**Who it's for:** legal counsel at Veridian Logistics Pvt Ltd, a fictional freight and warehousing company.

**The problem:** a two-person legal team reviews about 40 supplier contracts a month against the company's negotiation playbook. Each review takes 2 to 4 hours, and deals wait.

## What your system does

Takes one contract, checks every clause the playbook covers, proposes changes using only the company's approved wording, decides the contract's status, and updates the mock contract register.

## How a run starts

```json
{ "case_id": "UC5-S01", "input": { "contract_id": "CTR-1009" } }
```

## What you get

- **Tables** in `data/legal.sqlite` (also as CSV): the contract register, counterparties and their risk rating, the playbook rules, and the library of approved clause wording.
- **Documents** in `docs/`:
  - `contracts/`: the contracts, 2 to 4 pages each.
  - `playbook.md`: the negotiation playbook and the reasons behind it. Your system must follow it.

## What your system returns

- `decision`: `approve`, `changes_proposed` or `reject`
- `reason_code`: `COMPLIANT`, `DEVIATIONS_FOUND`, `MISSING_CLAUSES` or `RED_LINE_BREACHED`
- `findings`: each clause checked: where it is, what's wrong, and the approved clause proposed instead
- `amount`: the contract's annual value
- `citations`: contract sections and playbook rules

## Who approves (Parts B and C)

Legal counsel accepts or rejects each proposed change. A contract you approve as it stands needs no sign-off.

## What it writes

- The contract's new status in `mock_system/contract_register_updates.jsonl`
- The marked-up contract in `mock_system/markup/<contract_id>.md`

## How to load the data

Unzip the pack and set `DATA_DIR` to its folder.

```python
import os, sqlite3
con = sqlite3.connect(os.path.join(os.environ["DATA_DIR"], "data", "legal.sqlite"))
print(con.execute("SELECT * FROM playbook_rules").fetchall())
```

The same tables are in `data/csv/` if you prefer CSV. Each contract is a Markdown file in `docs/contracts/` named by its contract ID, with numbered clauses. The playbook explaining every rule is `docs/playbook.md`.

## Samples and scoring

`samples/` holds 5 test cases. `samples/expected/` holds the expected answer for each. We score these fields: `decision`, `reason_code`, `amount` (within the tolerance shown), `key_numbers` where present (they must appear among the numbers in your result), the IDs in `must_cite` (your `citations` must include them) and `needs_human`. We run our own hidden cases the same way.

The exact result format is in `schema/result.schema.json`, and the shared conventions (commands, `DATA_DIR`, the mock system) are in `COMMON.md`.

*Synthetic and fictional data. All companies, people and figures are invented.*
