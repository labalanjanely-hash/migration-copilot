import csv
import hashlib
import io
from collections.abc import Sequence
from pathlib import Path

from engines.base import Engine
from models.records import (
    BatchIngestionResult,
    FileIngestionResult,
    IngestionRequest,
    IssueSeverity,
    QuarantinedRow,
    SourceManifest,
    SourceRecord,
    ValidationIssue,
)


class CsvIngestionEngine(Engine[IngestionRequest, BatchIngestionResult]):
    def __init__(self, max_file_size_bytes: int = 250 * 1024 * 1024) -> None:
        self._limit = max_file_size_bytes

    def execute(self, items: Sequence[IngestionRequest]) -> BatchIngestionResult:
        return BatchIngestionResult(files=tuple(self._read(item) for item in items))

    def _read(self, request: IngestionRequest) -> FileIngestionResult:
        path = request.path.expanduser()
        try:
            if path.is_symlink() or not path.is_file() or path.suffix.casefold() != ".csv":
                raise ValueError("Input must be an existing, regular, non-symlink .csv file.")
            path = path.resolve(strict=True)
            payload = path.read_bytes()
            if len(payload) > self._limit:
                raise ValueError("Input exceeds configured file-size limit.")
            text, encoding = self._decode(payload, request.encoding)
            return self._parse(request, path, payload, text, encoding)
        except (OSError, UnicodeError, ValueError, csv.Error) as exc:
            return FileIngestionResult(
                manifest=None,
                issues=(ValidationIssue(
                    severity=IssueSeverity.ERROR,
                    code="SOURCE_READ_FAILED",
                    message=str(exc),
                    source_file=path.name or str(path),
                ),),
            )

    @staticmethod
    def _decode(payload: bytes, requested: str | None) -> tuple[str, str]:
        if requested:
            return payload.decode(requested), requested
        for encoding in ("utf-8-sig", "utf-8", "cp1252"):
            try:
                return payload.decode(encoding), encoding
            except UnicodeDecodeError:
                pass
        raise UnicodeError("Unable to decode CSV.")

    def _parse(
        self, request: IngestionRequest, path: Path, payload: bytes, text: str, encoding: str
    ) -> FileIngestionResult:
        if not text.strip():
            return self._fatal(request, path, payload, encoding, "EMPTY_FILE", "CSV is empty.")
        try:
            delimiter = csv.Sniffer().sniff(text[:65536], delimiters=",;\t|").delimiter
        except csv.Error:
            delimiter = ","
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
        columns = tuple(value.strip() for value in next(reader))
        issues = self._header_issues(request, path.name, columns)
        if any(item.severity is IssueSeverity.ERROR for item in issues):
            return self._result(
                request, path, payload, encoding, delimiter, columns, (), issues, ()
            )
        records: list[SourceRecord] = []
        quarantined: list[QuarantinedRow] = []
        rows_seen = 0
        for source_row, values in enumerate(reader, start=2):
            rows_seen += 1
            if len(values) != len(columns):
                issues.append(ValidationIssue(
                    severity=IssueSeverity.WARNING,
                    code="ROW_WIDTH_MISMATCH",
                    message=f"Expected {len(columns)} fields; found {len(values)}.",
                    source_file=path.name,
                    source_row=source_row,
                ))
                quarantined.append(QuarantinedRow(
                    source_file=path.name,
                    source_row=source_row,
                    reason_codes=("ROW_WIDTH_MISMATCH",),
                ))
                continue
            records.append(SourceRecord(
                source_file=path.name,
                source_row=source_row,
                record_type=request.export_type.value,
                values=dict(zip(columns, values, strict=True)),
            ))
        manifest = SourceManifest(
            source_file=path.name,
            absolute_path=path,
            export_type=request.export_type,
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
            encoding=encoding,
            delimiter=delimiter,
            columns=columns,
            rows_seen=rows_seen,
            rows_accepted=len(records),
            rows_quarantined=len(quarantined),
        )
        return FileIngestionResult(
            manifest=manifest,
            records=tuple(records),
            issues=tuple(issues),
            quarantined_rows=tuple(quarantined),
        )

    @staticmethod
    def _header_issues(
        request: IngestionRequest, source_file: str, columns: tuple[str, ...]
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if not columns or any(not item for item in columns):
            issues.append(ValidationIssue(
                severity=IssueSeverity.ERROR, code="BLANK_HEADER",
                message="Every CSV column requires a non-empty header.",
                source_file=source_file, source_row=1,
            ))
        duplicates = sorted({item for item in columns if columns.count(item) > 1})
        if duplicates:
            issues.append(ValidationIssue(
                severity=IssueSeverity.ERROR, code="DUPLICATE_HEADER",
                message=f"Duplicate columns: {duplicates}.", source_file=source_file, source_row=1,
            ))
        missing = sorted(set(request.required_columns) - set(columns))
        if missing:
            issues.append(ValidationIssue(
                severity=IssueSeverity.ERROR, code="REQUIRED_COLUMNS_MISSING",
                message=f"Missing required columns: {missing}.",
                source_file=source_file,
                source_row=1,
            ))
        unexpected = sorted(set(columns) - set(request.expected_columns))
        if request.expected_columns and unexpected:
            issues.append(ValidationIssue(
                severity=IssueSeverity.WARNING, code="UNEXPECTED_COLUMNS",
                message=f"Unexpected columns preserved: {unexpected}.",
                source_file=source_file, source_row=1,
            ))
        return issues

    def _fatal(
        self, request: IngestionRequest, path: Path, payload: bytes, encoding: str,
        code: str, message: str,
    ) -> FileIngestionResult:
        issue = ValidationIssue(
            severity=IssueSeverity.ERROR, code=code, message=message, source_file=path.name
        )
        return self._result(request, path, payload, encoding, ",", (), (), [issue], ())

    @staticmethod
    def _result(
        request: IngestionRequest, path: Path, payload: bytes, encoding: str,
        delimiter: str, columns: tuple[str, ...], records: tuple[SourceRecord, ...],
        issues: Sequence[ValidationIssue], quarantined: tuple[QuarantinedRow, ...],
    ) -> FileIngestionResult:
        manifest = SourceManifest(
            source_file=path.name, absolute_path=path, export_type=request.export_type,
            sha256=hashlib.sha256(payload).hexdigest(), size_bytes=len(payload),
            encoding=encoding, delimiter=delimiter, columns=columns, rows_seen=0,
            rows_accepted=len(records), rows_quarantined=len(quarantined),
        )
        return FileIngestionResult(
            manifest=manifest, records=records, issues=tuple(issues),
            quarantined_rows=quarantined,
        )
