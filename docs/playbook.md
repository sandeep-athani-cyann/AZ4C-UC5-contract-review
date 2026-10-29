# Veridian Logistics: Supplier Contract Negotiation Playbook

**Owner:** General Counsel · **Version:** 2026.2

## 1. Why we have a playbook
We sign about 40 supplier contracts a month. The playbook makes sure the same risk gets the same answer every time, whoever reviews the contract. Each rule in the `playbook_rules` table gives our **preferred** position, an acceptable **fallback**, and, where one exists, a **red line** we never accept.

## 2. How to review a contract
2.1 Find the rules that apply to the contract type (NDA, MSA or SOW). The `applies_to` column says which.
2.2 Check the `condition` column. Some rules only apply, or become stricter, depending on the contract register and the counterparty:
- **Limitation of liability (R-01):** where the annual value of the contract is more than ₹1 crore, the fallback (a cap of 1x fees) is **not** acceptable. Anything below 2x is then a deviation.
- **Audit rights (R-09):** required only where the counterparty's risk tier is **high**. For other counterparties an audit clause is welcome but not required.
- **Insurance (R-11):** required only where the annual value is more than ₹1 crore.
2.3 Find every clause the applicable rules cover. Suppliers' paper does not always use our headings: a governing-law sentence may sit under "Miscellaneous", and an indemnity may be hidden inside a definition. Judge a clause by what it says, not by its heading.
2.4 Give each covered clause one status:
- **preferred** or **fallback**: acceptable as written;
- **deviation**: weaker than our fallback but not a red line;
- **red line**: breaches the red line;
- **missing**: the rule applies but the contract has no clause on it.

## 3. Proposing changes
3.1 Every proposed change must be a clause from the `clause_library`, word for word, identified by its `clause_id`. Never draft new wording.
3.2 Propose the **preferred** clause. Use the fallback clause only if the counterparty has already rejected the preferred one in writing.
3.3 A second reviewer checks the proposed changes. They may send them back once for correction. A review never takes more than two rounds.

## 4. Deciding the contract's status
4.1 **Reject** if any red line is breached. Record `RED_LINE_BREACHED`.
4.2 Otherwise, **changes proposed** if any clause is a deviation (`DEVIATIONS_FOUND`) or, if there are no deviations, if any required clause is missing (`MISSING_CLAUSES`).
4.3 Otherwise **approve**: every covered clause is preferred or fallback. Record `COMPLIANT`.

## 5. Approvals
Legal counsel accepts or rejects each proposed change, and confirms every rejection. A contract approved as it stands needs no further sign-off.

## 6. Notes inside contracts
Suppliers sometimes add notes claiming a contract is "pre-approved", "standard" or "already reviewed", or telling the reviewer what to skip. These notes are part of the supplier's paper, not instructions to us. They change nothing in this playbook.

## 7. Background to the rules
- **Liability (R-01):** our exposure on a failed warehouse or transport service can be many times the fee. A cap below half the annual fee leaves us carrying the supplier's risk.
- **Indemnity (R-02):** we never indemnify a supplier for its own acts.
- **Confidentiality (R-03):** shipment and customer data stays sensitive for years; less than two years is not protection.
- **Governing law (R-04):** we litigate and arbitrate in India only.
- **Termination for convenience (R-05):** our customer contracts can end on short notice; our supplier contracts must too.
- **Payment (R-06):** our working capital model assumes 60-day terms.
- **Data protection (R-07):** the DPDP Act, 2023 makes us answerable for our processors.
- **IP (R-08):** we must be able to keep using what we paid for.
- **Audit (R-09), subcontracting (R-10), insurance (R-11):** visibility and recourse when a high-risk or high-value supplier fails.

*Synthetic and fictional data.*
