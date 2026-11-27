import json

import pytest

from app.postgres import Query, PostgresClient, identifier, split_fields
from app.storage import FileStorage, StorageException


def test_sql_identifiers_and_projection_parser():
    assert identifier("organization_id") == '"organization_id"'
    assert split_fields("id,organization:organizations!inner(id,name),stations(count)") == [
        "id", "organization:organizations!inner(id,name)", "stations(count)"
    ]
    for value in ("users;DROP TABLE users", "x.y", "id DESC", "id--"):
        with pytest.raises(ValueError):
            identifier(value)


def test_filters_are_parameters_including_injection_and_empty_sets(tmp_path):
    query = PostgresClient("unused", tmp_path).table("lakes")
    query.eq("name", "' OR 1=1 --").in_("id", [])
    params = []
    compiled = query._where(params)
    assert "' OR" not in compiled
    assert params == ["' OR 1=1 --"]
    assert "FALSE" in compiled
    with pytest.raises(ValueError):
        query.eq("id;DROP", "x")
    assert PostgresClient("unused", tmp_path).table("scenes").namespace == "satellite"


def test_storage_persists_and_cannot_escape_or_overwrite(tmp_path):
    storage = FileStorage(tmp_path)
    bucket = storage.from_("training_files")
    bucket.upload("organization/version/data.csv", b"a,b\n1,2")
    with pytest.raises(StorageException):
        bucket.upload("organization/version/data.csv", b"other")
    assert FileStorage(tmp_path).from_("training_files").download("organization/version/data.csv") == b"a,b\n1,2"
    for key in ("../outside", "/outside", "nested/../../outside", "C:\\secret", "nested\\outside", ""):
        with pytest.raises(StorageException):
            bucket.download(key)
    with pytest.raises(StorageException):
        storage.from_("public")
    bucket.remove(["organization/version/data.csv"])
    with pytest.raises(StorageException):
        bucket.download("organization/version/data.csv")
