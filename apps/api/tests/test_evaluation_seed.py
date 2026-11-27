from tools.seed_evaluation import fixtures, record_id, validate


def test_seed_geometries_and_relationships_are_valid():
    data = fixtures()
    validate(data)
    assert sum(lake["status"] == "active" for lake in data["lakes"]) == 24
    assert len(data["lakes"]) == 26
    assert len(data["stations"]) == 78
    assert len({row["id"] for rows in data.values() for row in rows}) == 122
    assert all(row["name"].startswith("EVAL - ") for row in data["lakes"])
    assert all(scene["metadata"]["synthetic"] and not scene["file_references"] for scene in data["scenes"])
    assert all(version["status"] == "DRAFT" for version in data["versions"])


def test_repeat_plans_keep_identifiers_and_data_identical():
    assert fixtures() == fixtures()
    assert record_id("lake/1") != record_id("lake/2")
