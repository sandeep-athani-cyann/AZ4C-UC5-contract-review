"""Runs the agents in order, enforces the review-round limit and the approval gate,
and writes to the mock system only once the decision is final."""
import json
import uuid
from datetime import datetime, timezone

from . import agents, llm
from .config import MAX_REVIEW_ROUNDS, RUNS_DIR, mock_system_dir
from .trace import Trace
from .tools import ToolError, inr, load_contract

NEW_STATUS = {"approve": "approved", "changes_proposed": "changes_proposed", "reject": "rejected"}


def run_case(case: dict, auto_approve: bool) -> dict:
    contract_id = (case.get("input") or {}).get("contract_id")
    if not contract_id:
        raise ToolError("case has no input.contract_id")
    run_id = "run-" + uuid.uuid4().hex[:10]
    trace = Trace()
    trace.log("run.start", run_id=run_id, case_id=case.get("case_id"), contract_id=contract_id,
              auto_approve=auto_approve, llm_available=llm.available())

    with trace.timed("intake.done"):
        intake = agents.IntakeAgent().run(contract_id, trace)
    findings = agents.ClauseAnalyst().run(intake, trace)

    drafter, reviewer = agents.Drafter(), agents.Reviewer()
    feedback, rounds = None, 0
    for rounds in range(1, MAX_REVIEW_ROUNDS + 1):
        findings = drafter.run(findings, intake["library"], trace, feedback)
        feedback = reviewer.run(findings, intake["library"], trace)
        if not feedback:
            break
    if feedback:
        trace.log("review.unresolved", problems=feedback)

    decision, reason = agents.Decider().run(findings, trace)
    result = _result(case, run_id, trace, intake, findings, decision, reason, rounds)
    if feedback:
        result["review_problems"] = feedback
        result["needs_human"] = True

    state = {"run_id": run_id, "case": case, "result": result, "contract_status": intake["record"]["status"]}
    if not result["needs_human"]:
        _commit(state, approved_by="not required (compliant as written)", trace=trace)
        result["status"] = "completed"
    elif auto_approve:
        _commit(state, approved_by="auto-approve", trace=trace)
        result["status"] = "approved"
    else:
        result["status"] = "pending_approval"
        trace.log("approval.pending", run_id=run_id)
        print(f"Paused for legal counsel. Resume with: python -m app approve {run_id} --action approve|reject|change")
    _save(state)
    trace.log("run.end", status=result["status"])
    return result


def approve(run_id: str, action: str, reject_changes: list[str] | None = None) -> dict:
    """Legal counsel's decision on a paused run.
    approve  accept every proposed change and record the decision
    reject   reject the outcome; nothing is written
    change   accept some proposed changes and reject others (--reject-changes R-06,R-10);
             a rejected change means counsel accepts the supplier's wording for that rule,
             so the decision is worked out again from what remains."""
    path = RUNS_DIR / f"{run_id}.json"
    if not path.is_file():
        raise ToolError(f"no run {run_id} in {RUNS_DIR}")
    state = json.loads(path.read_text(encoding="utf-8"))
    result = state["result"]
    if result["status"] != "pending_approval":
        raise ToolError(f"run {run_id} is {result['status']}, not waiting for approval")
    trace = Trace(result["trace_id"])
    trace.log("approval.received", action=action, reject_changes=reject_changes or [])

    if action == "reject":
        result["status"] = "rejected_by_counsel"
    elif action == "approve":
        _commit(state, approved_by="legal counsel", trace=trace)
        result["status"] = "approved"
    else:
        wanted = set(reject_changes or [])
        proposed = {f["rule_id"] for f in result["findings"] if f.get("proposed_clause_id")}
        if not wanted or not wanted <= proposed:
            raise ToolError(f"--reject-changes must name proposed changes from {sorted(proposed)}")
        for f in result["findings"]:
            if f["rule_id"] in wanted:
                f["status_before_counsel"] = f["status"]
                f["status"] = "accepted_by_counsel"
                f["counsel_note"] = "Counsel rejected the proposed change and accepts the supplier's wording."
                for k in ("proposed_clause_id", "proposed_text", "proposed_action"):
                    f.pop(k, None)
        decision, reason = agents.Decider().run(
            [{**f, "status": "fallback" if f["status"] == "accepted_by_counsel" else f["status"]}
             for f in result["findings"]], trace)
        result.update(decision=decision, reason_code=reason)
        _commit(state, approved_by="legal counsel (with changes)", trace=trace)
        result["status"] = "approved_with_changes"
    _save(state)
    trace.log("approval.done", status=result["status"])
    print(f"{run_id}: {result['status']} ({result['decision']}, {result['reason_code']})")
    return result


def _result(case, run_id, trace, intake, findings, decision, reason, rounds) -> dict:
    rec, contract_id = intake["record"], intake["record"]["contract_id"]
    citations = [contract_id, rec["counterparty_id"]]
    for f in findings:
        citations.append(f["rule_id"])
        citations += [f"{contract_id} §{loc}" for loc in f.get("all_locations", [])]
        if f.get("proposed_clause_id"):
            citations.append(f["proposed_clause_id"])
    citations.append({"reject": "playbook §4.1", "changes_proposed": "playbook §4.2",
                      "approve": "playbook §4.3"}[decision])
    if intake["injections"]:
        citations.append("playbook §6")
    key_numbers = [float(rec["annual_value_inr"] or 0.0)]
    for f in findings:
        key_numbers += [v for v in f["observed"].values() if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return {
        "case_id": case.get("case_id"),
        "run_id": run_id,
        "trace_id": trace.trace_id,
        "contract_id": contract_id,
        "contract_type": rec["contract_type"],
        "counterparty": {"id": rec["counterparty_id"], "name": intake["counterparty"]["name"],
                         "risk_tier": intake["counterparty"]["risk_tier"]},
        "decision": decision,
        "reason_code": reason,
        "amount": round(float(rec["annual_value_inr"] or 0.0), 2),
        "needs_human": decision != "approve",
        "citations": list(dict.fromkeys(citations)),
        "findings": [{k: v for k, v in f.items() if k != "all_locations"} | {"locations": f.get("all_locations", [])}
                     for f in findings],
        "review_rounds": rounds,
        "key_numbers": list(dict.fromkeys(key_numbers)),
        "ignored_instructions_in_contract": intake["injections"],
        "warnings": intake["warnings"],
    }


def _commit(state: dict, approved_by: str, trace) -> None:
    result = state["result"]
    out = mock_system_dir()
    (out / "markup").mkdir(parents=True, exist_ok=True)
    record = {
        "contract_id": result["contract_id"],
        "previous_status": state["contract_status"],
        "new_status": NEW_STATUS[result["decision"]],
        "decision": result["decision"],
        "reason_code": result["reason_code"],
        "annual_value_inr": result["amount"],
        "proposed_changes": [{"rule_id": f["rule_id"], "section": f["section"], "clause_id": f["proposed_clause_id"]}
                             for f in result["findings"] if f.get("proposed_clause_id")],
        "approved_by": approved_by,
        "run_id": state["run_id"],
        "trace_id": result["trace_id"],
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with (out / "contract_register_updates.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    markup_path = out / "markup" / f"{result['contract_id']}.md"
    markup_path.write_text(_markup(state), encoding="utf-8")
    trace.log("mock_system.write", register=record["new_status"], markup=str(markup_path))


def _markup(state: dict) -> str:
    result = state["result"]
    raw = load_contract(result["contract_id"]).raw
    by_ref = {f["section"]: f for f in result["findings"] if f.get("proposed_clause_id") and f["section"]}
    header = [
        f"> **Review result:** {result['decision']} ({result['reason_code']}). "
        f"Annual value {inr(result['amount'])}. Changes use approved clause library wording only.",
        ">",
        "> | Rule | Clause | Status | Where | Proposed |",
        "> | --- | --- | --- | --- | --- |",
    ]
    for f in result["findings"]:
        header.append(f"> | {f['rule_id']} | {f['clause_type']} | {f['status']} | {f['section'] or '-'} | "
                      f"{f.get('proposed_clause_id') or '-'} |")
    lines = [f"<!-- Marked up by the contract review system. run {state['run_id']}, trace {result['trace_id']} -->",
             "\n".join(header)]
    for block in raw.split("\n\n"):
        stripped = block.strip()
        ref = stripped[2:].split("**")[0] if stripped.startswith("**") else None
        f = by_ref.get(ref)
        if f:
            body = stripped.split("**", 2)[2].strip()
            block = (f"**{ref}** ~~{body}~~\n\n> **Proposed change ({f['rule_id']}, {f['status']}):** "
                     f"{f['issue']} Replace with approved clause **{f['proposed_clause_id']}**:\n>\n> "
                     f"{f['proposed_text']}")
        lines.append(block)
    inserts = [f for f in result["findings"] if f.get("proposed_action") == "insert"]
    if inserts:
        lines.append("## Proposed additions")
        for f in inserts:
            lines.append(f"> **Add ({f['rule_id']}, {f['status']}):** {f['issue']} Insert approved clause "
                         f"**{f['proposed_clause_id']}**:\n>\n> {f['proposed_text']}")
    return "\n\n".join(lines).rstrip() + "\n"


def _save(state: dict) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    (RUNS_DIR / f"{state['run_id']}.json").write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
