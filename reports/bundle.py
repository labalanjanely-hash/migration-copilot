import csv
import json
from pathlib import Path

from openpyxl import Workbook  # type: ignore[import-untyped]
from openpyxl.styles import Font, PatternFill  # type: ignore[import-untyped]
from openpyxl.worksheet.worksheet import Worksheet  # type: ignore[import-untyped]

from models.decisions import Decision
from models.evidence import Evidence
from models.migration import PipelineResult, RiskFinding


class ReportBundleWriter:
    def write(self, result: PipelineResult, directory: Path) -> tuple[Path, ...]:
        directory.mkdir(parents=True, exist_ok=True)
        workbook = directory / f"migration-report-{result.run_id}.xlsx"
        dataset = directory / f"import-candidates-{result.run_id}.csv"
        manifest = directory / f"run-manifest-{result.run_id}.json"
        self._workbook(result, workbook)
        with dataset.open("w", encoding="utf-8-sig", newline="") as handle:
            fields = ["Email", "Entitlement Key", "Decision Status", "Evidence Count",
                      "Activation Authorized"]
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(result.prepared_dataset.rows)
        manifest.write_text(json.dumps({
            "run_id": result.run_id, "release_status": result.release_status,
            "sources": [item.model_dump(mode="json") for item in result.source_manifests],
            "artifacts": [workbook.name, dataset.name],
        }, indent=2) + "\n", encoding="utf-8")
        return tuple(path.resolve() for path in (workbook, dataset, manifest))

    def _workbook(self, result: PipelineResult, path: Path) -> None:
        book = Workbook()
        summary = book.active
        summary.title = "Executive Summary"
        summary.append(["Metric", "Value"])
        for row in (
            ("Run ID", result.run_id), ("Release Status", result.release_status),
            ("Source Files", len(result.source_manifests)),
            ("Normalized Records", len(result.normalized_records)),
            ("Duplicate Candidates", len(result.duplicate_decisions)),
            ("Entitlement Decisions", len(result.entitlement_decisions)),
            ("Risk Findings", len(result.risks)),
            ("Candidate Import Rows", len(result.prepared_dataset.rows)),
            ("Activation Authorized", "NO"),
        ):
            summary.append(row)
        self._style(summary)
        self._decisions(book.create_sheet("Duplicate Review"), result.duplicate_decisions)
        self._decisions(book.create_sheet("Entitlement Ledger"), result.entitlement_decisions)
        self._risks(book.create_sheet("QA & Exceptions"), result.risks)
        book.save(path)

    def _decisions(self, sheet: Worksheet, decisions: tuple[Decision, ...]) -> None:
        sheet.append(["Subject", "Decision Type", "Status", "Rationale", "Evidence", "Conflicts"])
        for item in decisions:
            sheet.append([item.subject_id, item.decision_type, item.status.value, item.rationale,
                          self._evidence(item.evidence), "; ".join(item.conflicts)])
        self._style(sheet)

    def _risks(self, sheet: Worksheet, risks: tuple[RiskFinding, ...]) -> None:
        sheet.append(["Severity", "Code", "Subject", "Summary", "Recommended Action", "Evidence"])
        for item in risks:
            sheet.append([item.severity.value, item.code, item.subject_id, item.summary,
                          item.recommended_action, self._evidence(item.evidence)])
        self._style(sheet)

    @staticmethod
    def _evidence(items: tuple[Evidence, ...]) -> str:
        return "; ".join(f"{x.source_file}:{x.source_row}:{x.source_field}" for x in items)

    @staticmethod
    def _style(sheet: Worksheet) -> None:
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.fill = PatternFill("solid", fgColor="1F4E78")
            cell.font = Font(color="FFFFFF", bold=True)
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = min(
                max(len(str(cell.value or "")) for cell in column) + 2, 60
            )

