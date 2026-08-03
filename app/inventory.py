from pathlib import Path

from models.inventory import AssetInventory


class AssetInventoryRepository:
    """Read-only adapter for a sanitized, version-controlled inventory snapshot."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self) -> AssetInventory:
        return AssetInventory.model_validate_json(self._path.read_text(encoding="utf-8"))
