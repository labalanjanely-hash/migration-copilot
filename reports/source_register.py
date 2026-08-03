import json
from pathlib import Path

from models.records import BatchIngestionResult


class SourceRegisterWriter:
    def write(self, result: BatchIngestionResult, output_path: Path) -> Path:
        if output_path.suffix.casefold() != ".json":
            raise ValueError("Source Register must be a .json file.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "status": "valid" if result.is_valid else "review_required",
            "files": [{
                "manifest": item.manifest.model_dump(mode="json") if item.manifest else None,
                "issues": [issue.model_dump(mode="json") for issue in item.issues],
                "quarantined_rows": [row.model_dump(mode="json") for row in item.quarantined_rows],
            } for item in result.files],
        }
        output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return output_path.resolve()

