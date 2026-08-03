from collections.abc import Sequence

from engines.base import Engine
from models.decisions import Decision, DecisionStatus
from models.migration import PreparationInput, PreparedDataset


class DatasetPreparationEngine(Engine[PreparationInput, PreparedDataset]):
    def execute(self, items: Sequence[PreparationInput]) -> PreparedDataset:
        if len(items) != 1:
            raise ValueError("Dataset preparation requires exactly one pipeline input.")
        item = items[0]
        rows: list[dict[str, object]] = []
        excluded: list[Decision] = []
        review_rows: list[dict[str, object]] = []
        duplicate_emails = {decision.subject_id for decision in item.duplicate_decisions}
        for decision in item.entitlement_decisions:
            email, separator, key = decision.subject_id.partition("|")
            if (
                decision.status is not DecisionStatus.VERIFIED
                or not separator
                or not email
                or not key
                or email in duplicate_emails
            ):
                excluded.append(decision)
                identity_conflict = email in duplicate_emails
                review_rows.append({
                    "Subject": decision.subject_id,
                    "Decision Type": decision.decision_type,
                    "Status": "hold" if identity_conflict else decision.status.value,
                    "Rationale": (
                        "Verified purchase evidence exists, but duplicate contact identity "
                        "blocks dataset preparation."
                        if identity_conflict else decision.rationale
                    ),
                    "Conflicts": (
                        "duplicate contact identity"
                        if identity_conflict else "; ".join(decision.conflicts)
                    ),
                    "Evidence Count": len(decision.evidence),
                    "Approved": False,
                    "Reviewer Notes": "",
                })
                continue
            rows.append({
                "Email": email,
                "Entitlement Key": key,
                "Decision Status": decision.status.value,
                "Evidence Count": len(decision.evidence),
                "Activation Authorized": False,
            })
        contact_rows: list[dict[str, object]] = []
        seen: set[str] = set()
        for record in item.records:
            contact_email = record.normalized_email
            if record.record_type not in item.identity_record_types or not contact_email:
                continue
            if (
                contact_email in seen
                or contact_email in duplicate_emails
                or "@" not in contact_email
            ):
                continue
            seen.add(contact_email)
            contact_rows.append({
                "Email": contact_email,
                "Name": record.normalized_name or "",
                "Phone": record.normalized_phone or "",
                "Source File": record.source_file,
                "Source Row": record.source_row,
                "Import Eligible": True,
                "Activation Authorized": False,
            })
        for decision in item.duplicate_decisions:
            review_rows.append({
                "Subject": decision.subject_id,
                "Decision Type": decision.decision_type,
                "Status": decision.status.value,
                "Rationale": decision.rationale,
                "Conflicts": "; ".join(decision.conflicts),
                "Evidence Count": len(decision.evidence),
                "Approved": False,
                "Reviewer Notes": "",
            })
        return PreparedDataset(
            rows=tuple(rows), contact_rows=tuple(contact_rows),
            manual_review_rows=tuple(review_rows), excluded_decisions=tuple(excluded)
        )
