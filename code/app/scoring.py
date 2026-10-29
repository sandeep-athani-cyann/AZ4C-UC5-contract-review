"""Scores a result the way README.md describes: decision, reason_code, amount within
tolerance, key_numbers (when the expected file has them), must_cite and needs_human.
Each check present in the expected file counts equally."""


def _numbers(obj) -> list[float]:
    if isinstance(obj, bool):
        return []
    if isinstance(obj, (int, float)):
        return [float(obj)]
    if isinstance(obj, dict):
        return [n for v in obj.values() for n in _numbers(v)]
    if isinstance(obj, list):
        return [n for v in obj for n in _numbers(v)]
    return []


def score_case(result: dict, expected: dict) -> float:
    checks = []
    if "decision" in expected:
        checks.append(result.get("decision") == expected["decision"])
    if "reason_code" in expected:
        codes = expected["reason_code"]
        checks.append(result.get("reason_code") in (codes if isinstance(codes, list) else [codes]))
    if "amount" in expected:
        exp, got = expected["amount"], result.get("amount")
        if isinstance(exp, dict):
            ok = (got is None) if exp.get("value") is None else (
                got is not None and abs(float(got) - float(exp["value"])) <= float(exp.get("tolerance", 0.01)))
        else:
            ok = got == exp
        checks.append(ok)
    if expected.get("key_numbers"):
        have = _numbers(result)
        checks.append(all(any(abs(h - float(k)) <= 0.01 for h in have) for k in expected["key_numbers"]))
    if "must_cite" in expected:
        cited = set(result.get("citations") or [])
        checks.append(all(c in cited for c in expected["must_cite"]))
    if "needs_human" in expected:
        checks.append(result.get("needs_human") == expected["needs_human"])
    return round(sum(checks) / len(checks), 4) if checks else 0.0
