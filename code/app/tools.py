"""Read-only tools over the data pack. Every tool raises ToolError with a clear message
when data is missing, so the orchestrator can stop or flag the run instead of guessing."""
import re
import sqlite3
from dataclasses import dataclass, field

from .config import data_dir


class ToolError(Exception):
    pass


def _db() -> sqlite3.Connection:
    path = data_dir() / "data" / "legal.sqlite"
    if not path.is_file():
        raise ToolError(f"database not found at {path}; set DATA_DIR to the data pack folder")
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def get_contract_record(contract_id: str) -> dict:
    with _db() as con:
        row = con.execute("SELECT * FROM contract_register WHERE contract_id = ?", (contract_id,)).fetchone()
    if row is None:
        raise ToolError(f"contract {contract_id} is not in the contract register")
    return dict(row)


def get_counterparty(counterparty_id: str) -> dict:
    with _db() as con:
        row = con.execute("SELECT * FROM counterparties WHERE counterparty_id = ?", (counterparty_id,)).fetchone()
    if row is None:
        raise ToolError(f"counterparty {counterparty_id} is not in the counterparties table")
    return dict(row)


def get_rules(contract_type: str) -> list[dict]:
    """Playbook rules whose applies_to column includes this contract type."""
    with _db() as con:
        rows = [dict(r) for r in con.execute("SELECT * FROM playbook_rules ORDER BY rule_id")]
    rules = [r for r in rows if contract_type in [t.strip() for t in r["applies_to"].split(",")]]
    if not rules:
        raise ToolError(f"no playbook rules apply to contract type {contract_type!r}")
    return rules


def get_clause_library() -> dict[str, dict]:
    with _db() as con:
        return {r["clause_id"]: dict(r) for r in con.execute("SELECT * FROM clause_library")}


@dataclass
class Paragraph:
    ref: str          # "4.1", or "Schedule 1" for unnumbered schedule text
    heading: str      # heading of the section it sits under
    text: str         # plain text, markdown bold removed


@dataclass
class Contract:
    contract_id: str
    title: str
    raw: str
    paragraphs: list[Paragraph] = field(default_factory=list)
    annual_fees_in_doc: float | None = None


_SECTION = re.compile(r"^##\s+(?:(\d+)\.\s+)?(.+?)\s*$")
_CLAUSE = re.compile(r"^\*\*(\d+(?:\.\d+)*)\*\*\s*(.*)$", re.S)


def parse_inr(text: str) -> float | None:
    """'₹1,80,00,000.00' -> 18000000.0 (Indian digit grouping)."""
    m = re.search(r"₹\s*([\d,]+(?:\.\d+)?)", text)
    return float(m.group(1).replace(",", "")) if m else None


def inr(amount: float) -> str:
    """18000000 -> '₹1,80,00,000.00' (Indian digit grouping)."""
    whole, frac = f"{amount:.2f}".split(".")
    head, tail = whole[:-3], whole[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return "₹" + ",".join(groups + [tail]) + "." + frac


def load_contract(contract_id: str) -> Contract:
    if not re.fullmatch(r"[A-Z]{3}-\d{3,6}", contract_id):
        raise ToolError(f"invalid contract id {contract_id!r}")
    path = data_dir() / "docs" / "contracts" / f"{contract_id}.md"
    if not path.is_file():
        raise ToolError(f"contract document not found: docs/contracts/{contract_id}.md")
    raw = path.read_text(encoding="utf-8")
    contract = Contract(contract_id=contract_id, title="", raw=raw)
    heading = ""
    for block in (b.strip() for b in raw.split("\n\n")):
        if not block:
            continue
        if block.startswith("# ") and not contract.title:
            contract.title = block[2:].strip()
            continue
        m = _SECTION.match(block)
        if m:
            heading = m.group(2)
            continue
        m = _CLAUSE.match(block)
        if m:
            contract.paragraphs.append(Paragraph(m.group(1), heading, _plain(m.group(2))))
        elif heading.lower().startswith("schedule"):
            ref = heading.split(":")[0].strip()
            contract.paragraphs.append(Paragraph(ref, heading, _plain(block)))
            if block.startswith("Annual Fees"):
                contract.annual_fees_in_doc = parse_inr(block)
    if not contract.paragraphs:
        raise ToolError(f"no numbered clauses found in {contract_id}")
    return contract


def _plain(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("**", "")).strip()
