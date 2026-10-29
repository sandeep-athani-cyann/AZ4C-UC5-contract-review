# Use case 5: Contract review

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

*Synthetic and fictional data.*
