# Architecture

```mermaid
flowchart TD
    CASE["case.json<br/>{contract_id}"] --> ORCH

    subgraph ORCH["Orchestrator (orchestrator.py)"]
        direction TB
        INTAKE["1. Intake agent<br/>register, counterparty, rules,<br/>clause library, contract text"]
        ANALYST["2. Clause analyst<br/>finds each covered clause by content,<br/>grades it against the rule"]
        DRAFT["3. Drafter<br/>preferred library clause, word for word"]
        REVIEW{"4. Reviewer<br/>proposals valid?"}
        DECIDE["5. Decider<br/>playbook section 4"]
        INTAKE --> ANALYST --> DRAFT --> REVIEW
        REVIEW -- "send back (max 2 rounds)" --> DRAFT
        REVIEW -- ok --> DECIDE
    end

    ANALYST -. "wording the rules can't read,<br/>or no clause found" .-> LLM["LLM analyst<br/>Groq Llama 3.3 70B, then Gemini 2.5 Flash"]
    LLM -. "no model / failure" .-> UNCLEAR["status: unclear<br/>(goes to a human)"]

    DATA[("legal.sqlite<br/>docs/contracts/*.md")] --> INTAKE

    DECIDE --> GATE{"needs_human?<br/>(changes_proposed or reject)"}
    GATE -- "no (approve)" --> WRITE
    GATE -- "yes + --auto-approve" --> WRITE
    GATE -- "yes" --> PAUSE["paused: code/runs/&lt;run_id&gt;.json"]
    PAUSE -- "approve / change" --> WRITE
    PAUSE -- "reject" --> NOTHING["nothing written"]

    WRITE["Mock system<br/>contract_register_updates.jsonl<br/>markup/&lt;contract_id&gt;.md"]

    ORCH -. "every step" .-> TRACE["code/traces/&lt;trace_id&gt;.jsonl"]
```

Contract text only ever reaches the model inside `<contract>` tags, under a system prompt that
says it is data. Notes like "pre-approved, skip the review" are detected, listed in the result
under `ignored_instructions_in_contract`, and change nothing (playbook section 6).
