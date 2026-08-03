from app.inventory import AssetInventoryRepository


def test_inventory_repository_reads_exact_sections(tmp_path) -> None:
    path = tmp_path / "inventory.json"
    path.write_text(
        """{
      "snapshot_date": "2026-08-04", "title": "inventory", "source_url": "https://example.test",
      "release_status": "NO_GO", "baseline": {"contacts": "1,976"},
      "sections": {"gates": [{"classification": "Unresolved Exception", "subject": "approval",
        "observation": "pending", "treatment": "hold"}]}
    }""",
        encoding="utf-8",
    )
    inventory = AssetInventoryRepository(path).get()
    assert inventory.baseline["contacts"] == "1,976"
    assert inventory.section("gates")[0].treatment == "hold"
    assert inventory.section("missing") == ()
