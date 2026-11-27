from hashlib import sha256
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest

from app.training_worker import run_one


@pytest.mark.parametrize("valid_checksum", [True, False])
def test_worker_trains_only_after_verifying_published_file(valid_checksum):
    version = str(UUID(int=1))
    job = {"id": str(UUID(int=2)), "status": "queued", "job_type": "training",
           "config": {"version_id": version}}
    data = (
        b"acquisition_date,ndci,chlorophyll_a\n"
        b"2026-01-01,0,1\n2026-01-02,0.2,2\n2026-01-03,0.4,3\n"
    )

    class Query:
        def __init__(self, update=None):
            self.changes = update
            self.filters = {}

        def eq(self, name, value):
            self.filters[name] = value
            return self

        def order(self, _name):
            return self

        def limit(self, _count):
            return self

        def execute(self):
            if any(job[key] != value for key, value in self.filters.items()):
                return SimpleNamespace(data=[])
            if self.changes:
                job.update(self.changes)
            return SimpleNamespace(data=[job.copy()])

    table = SimpleNamespace(select=lambda _: Query(), update=Query)
    database = SimpleNamespace(schema=lambda _: SimpleNamespace(table=lambda _: table))

    def download(request):
        assert request.url.path == f"/api/v1/datasets/training-jobs/{job['id']}/file"
        assert job["status"] == "running"
        checksum = sha256(data).hexdigest() if valid_checksum else "0" * 64
        return httpx.Response(200, content=data, headers={"X-Content-SHA256": checksum})

    with httpx.Client(base_url="http://core", transport=httpx.MockTransport(download)) as core:
        assert run_one(database, core)
        assert not run_one(database, core)

    if valid_checksum:
        assert job["status"] == "completed"
        assert job["result"]["dataset_version_id"] == version
        assert job["result"]["metrics"]["mae"] < 1e-10
    else:
        assert job["status"] == "failed"
        assert "checksum" in job["error_message"]
