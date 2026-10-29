"""Playbook rules as code: how to recognise each covered clause by what it says
(playbook 2.3), and how to grade it as preferred / fallback / deviation / red_line.

Each grader returns (status, observed, issue), or None when the wording is outside
what the rules can read. None sends the clause to the LLM analyst, and if no model
is available, to a human as "unclear".
"""
import re

from .config import ONE_CRORE
from .tools import inr, parse_inr

PREFERRED, FALLBACK, DEVIATION, RED_LINE = "preferred", "fallback", "deviation", "red_line"
MISSING, NOT_REQUIRED, UNCLEAR = "missing", "not_required", "unclear"
ACCEPTABLE = {PREFERRED, FALLBACK, NOT_REQUIRED}
SEVERITY = {PREFERRED: 0, FALLBACK: 1, NOT_REQUIRED: 0, UNCLEAR: 2, DEVIATION: 3, MISSING: 3, RED_LINE: 4}

WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30,
    "forty-five": 45, "sixty": 60, "seventy-two": 72, "ninety": 90, "half": 0.5,
}
INDIAN_CITIES = ("mumbai", "delhi", "new delhi", "bengaluru", "bangalore", "chennai", "kolkata",
                 "hyderabad", "pune", "ahmedabad", "india")


def _num(token: str) -> float | None:
    token = token.strip().lower()
    if re.fullmatch(r"\d+(\.\d+)?", token):
        return float(token)
    return WORD_NUMBERS.get(token)


def _quantity(text: str, unit: str) -> float | None:
    """First quantity before a unit: 'sixty (60) days', '30 days', 'seven days'."""
    m = re.search(rf"(?:\((\d+)\)|(\d+)|\b([a-z\-]+))\s*{unit}", text, re.I)
    if not m:
        return None
    return _num(next(g for g in m.groups() if g))


def _days(text: str) -> float | None:
    return _quantity(text, r"(?:working\s+)?days?\b")


# ---------- recognisers: what a clause says, not its heading ----------

def is_liability(t):   return "liabilit" in t and re.search(r"exceed|cap|limit", t) and "insurance" not in t
def is_indemnity(t):   return re.search(r"indemnif", t) and "indemnity insurance" not in t
def is_conf_term(t):   return re.search(r"surviv|remain in force|continue to apply", t) and re.search(r"confiden|obligations in this clause", t)
def is_gov_law(t):     return re.search(r"(governed by|construed in accordance with|subject to)\s+the\s+laws?\s+of", t)
def is_tfc(t):         return "terminat" in t and "convenience" in t
def is_payment(t):     return re.search(r"\bpay\b", t) and "invoice" in t and re.search(r"within|days", t)
def is_data_prot(t):   return re.search(r"personal data|data protection|veridian's data|data secure", t) and not is_indemnity(t)
def is_ip(t):          return "intellectual property" in t and not re.search(r"infring", t)
def is_audit(t):       return re.search(r"\baudit\b", t) and re.search(r"records|premises|systems|books", t)
def is_subcontract(t): return "subcontract" in t
def is_insurance(t):   return "insurance" in t


# ---------- graders ----------

def grade_liability(t, ctx):
    if re.search(r"unlimited|no (?:limit|cap) (?:on|to) (?:the supplier's )?liability", t) and "exceed" not in t:
        return PREFERRED, {"cap_multiple": None}, "No cap on the supplier's liability."
    mult = None
    if m := re.search(r"(\d+(?:\.\d+)?)\s*%\s*of\s+the\s+(?:annual\s+)?fees", t):
        mult = float(m.group(1)) / 100
    elif m := re.search(r"\b([a-z]+) and a half (?:x|times)\s+the\s+(?:annual\s+)?fees", t):
        mult = (_num(m.group(1)) or 0) + 0.5 if _num(m.group(1)) else None
    elif m := re.search(r"(?:\((\d+(?:\.\d+)?)\)|(\d+(?:\.\d+)?)|\b([a-z]+))\s*(?:x|times)\s+the\s+(?:annual\s+)?fees", t):
        mult = _num(next(g for g in m.groups() if g))
    elif re.search(r"half\s+(?:of\s+)?the\s+(?:annual\s+)?fees", t):
        mult = 0.5
    elif re.search(r"exceed\s+(?:an amount equal to\s+)?the\s+(?:annual\s+|total\s+)?fees", t):
        mult = 1.0
    elif (amt := parse_inr(t)) is not None and ctx["annual_value"]:
        mult = amt / ctx["annual_value"]
    if mult is None:
        return None
    obs = {"cap_multiple": round(mult, 4)}
    if mult < 0.5:
        return RED_LINE, obs, f"Cap of {mult:g}x annual fees is below the 0.5x red line."
    if mult >= 2:
        return PREFERRED, obs, f"Cap of {mult:g}x annual fees meets the preferred 2x."
    if mult >= 1:
        if ctx["annual_value"] > ONE_CRORE:
            return DEVIATION, obs, (f"Cap of {mult:g}x annual fees; the 1x fallback is not acceptable because "
                                    f"the annual value {inr(ctx['annual_value'])} is more than ₹1 crore (needs 2x).")
        return FALLBACK, obs, f"Cap of {mult:g}x annual fees meets the 1x fallback."
    return DEVIATION, obs, f"Cap of {mult:g}x annual fees is below the 1x fallback."


def grade_indemnity(t, ctx):
    veridian_gives = re.search(r"veridian shall (?:indemnify|keep indemnified|hold harmless)", t)
    if veridian_gives and "supplier" in t[veridian_gives.start():]:
        limited = re.search(r"(?:caused by|arising from) veridian's (?:own )?breach", t)
        if not limited:
            return RED_LINE, {"veridian_indemnifies_supplier": True}, \
                "Veridian indemnifies the Supplier beyond claims caused by Veridian's own breach."
    if re.search(r"supplier shall (?:indemnify|keep indemnified)", t):
        ip = "intellectual property" in t
        data = re.search(r"personal data|data breach", t)
        if ip and data:
            return PREFERRED, {"covers": ["ip", "data_breach"]}, "Supplier indemnity covers IP and data breaches."
        if ip:
            return FALLBACK, {"covers": ["ip"]}, "Supplier indemnity covers IP claims only (fallback)."
        return DEVIATION, {"covers": []}, "Supplier indemnity does not cover third-party IP infringement."
    if re.search(r"bear its own loss|no indemnit", t):
        return DEVIATION, {"covers": []}, "No supplier indemnity for IP infringement or data breaches."
    return None


def grade_conf_term(t, ctx):
    if re.search(r"indefinite|perpetual|in perpetuity|for ever|forever", t):
        return PREFERRED, {"survival_years": None}, "Confidentiality survives indefinitely."
    years = _quantity(t, r"years?\b")
    if years is None and (months := _quantity(t, r"months?\b")) is not None:
        years = months / 12
    if years is None:
        return None
    obs = {"survival_years": years}
    if years < 2:
        return RED_LINE, obs, f"Confidentiality survives only {years:g} year(s); less than 2 years is a red line."
    if years >= 5:
        return PREFERRED, obs, f"Confidentiality survives {years:g} years."
    if years >= 3:
        return FALLBACK, obs, f"Confidentiality survives {years:g} years (fallback, at least 3)."
    return DEVIATION, obs, f"Confidentiality survives {years:g} years, short of the 3-year fallback."


def grade_gov_law(t, ctx):
    m = re.search(r"laws?\s+of\s+(?:the\s+)?(?:republic\s+of\s+)?([a-z][a-z ]+?)(?:[,.;]|\s+and\s|\s+shall\s|$)", t)
    if not m:
        return None
    law = m.group(1).strip()
    if law not in ("india",):
        return RED_LINE, {"law": law}, f"Governed by the laws of {law.title()}; any law other than Indian law is a red line."
    if "arbitration" in t:
        seat = re.search(r"seated in ([a-z ]+?)(?:[,.;]|\s+under|$)", t)
        if seat and seat.group(1).strip() in INDIAN_CITIES:
            return FALLBACK, {"law": "india", "forum": f"arbitration in {seat.group(1).strip()}"}, \
                "Indian law with arbitration seated in India (fallback)."
        return DEVIATION, {"law": "india", "forum": "arbitration outside India or unclear seat"}, \
            "Indian law, but arbitration is not seated in India."
    court = re.search(r"courts? (?:at|of|in) ([a-z ]+?)(?:[,.;]| shall| alone|$)", t)
    exclusive = re.search(r"exclusive|alone|only", t)
    if court and court.group(1).strip() == "mumbai" and exclusive:
        return PREFERRED, {"law": "india", "forum": "courts at Mumbai, exclusive"}, \
            "Indian law and exclusive jurisdiction of the Mumbai courts."
    return DEVIATION, {"law": "india", "forum": court.group(1).strip() if court else None}, \
        "Indian law, but not exclusive jurisdiction of the Mumbai courts."


def grade_tfc(t, ctx):
    if re.search(r"neither party (?:may|shall|can) terminate|veridian (?:may not|shall not|has no right to|cannot) terminate", t):
        return RED_LINE, {"notice_days": None}, "No right for Veridian to terminate for convenience, which is a red line."
    if not re.search(r"veridian may terminate", t):
        return None
    d = _days(t)
    if d is None:
        return None
    obs = {"notice_days": d}
    if d <= 30:
        return PREFERRED, obs, f"Veridian may terminate for convenience on {d:g} days' notice."
    if d <= 60:
        return FALLBACK, obs, f"Termination for convenience on {d:g} days' notice (fallback, up to 60)."
    if d > 90:
        return RED_LINE, obs, f"Termination for convenience needs {d:g} days' notice; more than 90 is a red line."
    return DEVIATION, obs, f"Termination for convenience needs {d:g} days' notice, longer than the 60-day fallback."


def grade_payment(t, ctx):
    d = _days(t)
    if d is None:
        return None
    obs = {"payment_days": d}
    if d >= 60:
        return PREFERRED, obs, f"Payment within {d:g} days."
    if d >= 45:
        return FALLBACK, obs, f"Payment within {d:g} days (fallback, at least 45)."
    return DEVIATION, obs, f"Payment within {d:g} days; anything shorter than 45 days is a deviation."


def grade_data_prot(t, ctx):
    dpdp = "digital personal data protection act" in t
    hours = _quantity(t, r"hours?\b")
    if hours is None and (d := _days(t)) is not None and re.search(r"notif", t):
        hours = d * 24
    obs = {"dpdp_act": dpdp, "breach_notice_hours": hours}
    if not re.search(r"notif", t):
        return DEVIATION, obs, "No personal data breach notification duty; none is a deviation."
    if hours is None:
        return None
    if dpdp and hours <= 72:
        return PREFERRED, obs, f"DPDP Act compliance and breach notice within {hours:g} hours."
    if hours <= 7 * 24:
        return FALLBACK, obs, f"Breach notice within {hours / 24:g} days (fallback, up to 7 days)."
    return DEVIATION, obs, f"Breach notice after {hours / 24:g} days; later than 7 days is a deviation."


def grade_ip(t, ctx):
    if re.search(r"vest in veridian|assigns? all such rights to veridian|(?:belong|belongs) to veridian|veridian shall own", t):
        return PREFERRED, {"owner": "veridian"}, "Deliverables and their IP vest in Veridian."
    if re.search(r"retain|remains? with the supplier|supplier shall own", t):
        licence = re.search(r"licen[cs]e", t)
        limited = re.search(r"beyond the term|for the term|during the term|limited to the term|time-limited", t)
        if not licence or limited or re.search(r"nothing in this .* grants veridian any licen", t):
            return RED_LINE, {"owner": "supplier", "licence": "none or time-limited"}, \
                "Supplier keeps the IP with no licence, or only a time-limited licence, to Veridian."
        if all(w in t for w in ("perpetual", "irrevocable", "royalty-free")):
            return FALLBACK, {"owner": "supplier", "licence": "perpetual, irrevocable, royalty-free"}, \
                "Supplier keeps the IP but grants a perpetual, irrevocable, royalty-free licence (fallback)."
        return DEVIATION, {"owner": "supplier", "licence": "partial"}, \
            "Supplier keeps the IP and the licence to Veridian is not perpetual, irrevocable and royalty-free."
    return None


def grade_audit(t, ctx):
    d = _days(t)
    if d is None:
        return None
    obs = {"notice_days": d}
    if d <= 15:
        return PREFERRED, obs, f"Audit on {d:g} days' notice."
    if d <= 30:
        return FALLBACK, obs, f"Audit on {d:g} days' notice (fallback)."
    return DEVIATION, obs, f"Audit needs {d:g} days' notice, longer than the 30-day fallback."


def grade_subcontract(t, ctx):
    if re.search(r"shall not subcontract.*without.*prior written consent", t):
        return PREFERRED, {"control": "prior written consent"}, "Subcontracting needs Veridian's prior written consent."
    if re.search(r"notice", t) and (d := _days(t)) is not None:
        if d >= 15:
            return FALLBACK, {"control": "notice", "notice_days": d}, f"Subcontracting allowed on {d:g} days' prior notice (fallback)."
        return DEVIATION, {"control": "notice", "notice_days": d}, f"Only {d:g} days' notice before subcontracting."
    if re.search(r"discretion|without (?:veridian's )?(?:consent|notice)|may (?:engage|use|appoint) subcontractors|may subcontract", t):
        return DEVIATION, {"control": "none"}, "Supplier may subcontract without consent or notice."
    return None


def grade_insurance(t, ctx):
    amt = parse_inr(t)
    if amt is None and (m := re.search(r"(\d+(?:\.\d+)?|[a-z]+)\s+crore", t)):
        n = _num(m.group(1))
        amt = n * ONE_CRORE if n is not None else None
    if amt is None:
        return None
    obs = {"insurance_inr": amt}
    if amt >= 5 * ONE_CRORE:
        return PREFERRED, obs, f"Professional indemnity cover of {inr(amt)}."
    if amt >= 2 * ONE_CRORE:
        return FALLBACK, obs, f"Professional indemnity cover of {inr(amt)} (fallback, at least ₹2 crore)."
    return DEVIATION, obs, f"Insurance cover of {inr(amt)} is below the ₹2 crore fallback."


CLAUSE_TYPES = {
    "LIMITATION_OF_LIABILITY": (is_liability, grade_liability),
    "INDEMNITY": (is_indemnity, grade_indemnity),
    "CONFIDENTIALITY_TERM": (is_conf_term, grade_conf_term),
    "GOVERNING_LAW": (is_gov_law, grade_gov_law),
    "TERMINATION_FOR_CONVENIENCE": (is_tfc, grade_tfc),
    "PAYMENT_TERMS": (is_payment, grade_payment),
    "DATA_PROTECTION": (is_data_prot, grade_data_prot),
    "IP_OWNERSHIP": (is_ip, grade_ip),
    "AUDIT_RIGHTS": (is_audit, grade_audit),
    "SUBCONTRACTING": (is_subcontract, grade_subcontract),
    "INSURANCE": (is_insurance, grade_insurance),
}


def required(rule: dict, ctx: dict) -> tuple[bool, str]:
    """Conditions that switch a rule on or off (playbook 2.2)."""
    if rule["rule_id"] == "R-09":
        return ctx["risk_tier"] == "high", f"counterparty risk tier is {ctx['risk_tier']}"
    if rule["rule_id"] == "R-11":
        return ctx["annual_value"] > ONE_CRORE, f"annual value is {inr(ctx['annual_value'])}"
    return True, ""


def missing_status(rule: dict) -> tuple[str, str]:
    # R-05's red line is "no right for Veridian to terminate for convenience".
    if rule["rule_id"] == "R-05":
        return RED_LINE, "No right for Veridian to terminate for convenience, which is a red line."
    return MISSING, f"The contract has no {rule['clause_type'].replace('_', ' ').lower()} clause."


INJECTION = re.compile(
    r"(note to (?:the )?(?:reviewer|automated|ai)|reviewer note|pre-approved|already (?:been )?reviewed|"
    r"need not be checked|mark (?:it|this) approved|without further review|ignore (?:the|all|previous)|skip)", re.I)
