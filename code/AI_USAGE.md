# How I used AI coding tools

**Tool:** Claude Code (Claude Opus), in VS Code.

**What it did**

- Read the pack (use case, playbook, rules, clause library, all 24 contracts) and listed the
  paragraphs in each contract that differ from the shared boilerplate, so the deviations and
  traps were visible before any code was written.
- Drafted the code: the rules engine, agents, orchestrator, approval flow, LLM client, scoring,
  tests and these docs.
- Worked out the expected answer for each of the 24 contracts by hand from the playbook. The
  system's output was then compared against those answers, and they were not edited to fit the output.

**What was checked or changed along the way**

- The first run scored 88% on the samples: a word-for-word library *fallback* liability clause
  was accepted without the R-01 condition (fallback isn't acceptable above ₹1 crore). Fixed so
  library matches still go through the rule's conditions.
- A stress test with paraphrased clauses found two gaps ("one and a half times the Fees" read as
  0.5x; "neither party may terminate for convenience" not seen as a red line). Both fixed and kept
  as unit tests.
- The markup's summary table was broken by blank lines, and amounts were in Western digit
  grouping; both fixed (₹1,80,00,000.00).
- `.env.example` comments were moved to their own lines, because the provided `.env` loader would
  have read an inline comment as the model name.
- The LLM path (Groq / Gemini) could not be run end to end without API keys. It is written to
  fail safe: on any failure the clause is marked `unclear` and goes to counsel.

**To check yourself:** run `python -m unittest discover -s tests` and both `eval` commands, and
read a markup in `mock_system/markup/`.
