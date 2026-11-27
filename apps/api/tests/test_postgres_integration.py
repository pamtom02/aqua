"""Run against a new disposable PostgreSQL database via TEST_DATABASE_URL."""
import os
import subprocess
import sys
from uuid import uuid4

import pytest

pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not set")
    os.environ.update(DATABASE_URL=dsn, ALLOW_REGISTRATION="true",
                      JWT_SECRET="integration-test-key-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                      STORAGE_ROOT=str(tmp_path_factory.mktemp("storage")), ENVIRONMENT="test")
    # Isolate module-level configuration from the unit-test process.
    return dsn


def test_postgres_migrations_auth_catalog_and_isolation(client):
    script = r'''
import os
from uuid import uuid4
from fastapi.testclient import TestClient
from app.start import prepare
prepare()
prepare()
from app.main import app
from app.database import database
from app.auth import create_user
from app.postgres import APIError
admin = create_user("admin@example.invalid","Integration-password-2026!","Admin","administrador")
with TestClient(app) as http:
    assert http.get("/api/v1/health").json()["status"]=="ok"
    assert http.get("/health/live").status_code==200
    login=http.post("/auth/login",json={"email":"admin@example.invalid","password":"Integration-password-2026!"})
    assert login.status_code==200,login.text
    session=login.json()
    headers={"Authorization":"Bearer "+session["access_token"]}
    org=http.post("/api/v1/organizations",json={"name":"Org 1","identifier":"org-1"},headers=headers)
    assert org.status_code==201,org.text
    org_id=org.json()["id"]
    assert len(http.get("/api/v1/organizations/",headers=headers).json())==1
    me=http.get("/auth/me",headers=headers)
    assert me.status_code==200,me.text
    assert me.json()["memberships"][0]["organization"]["id"]==org_id
    polygon={"type":"Polygon","coordinates":[[[-73,-40],[-72,-40],[-72,-39],[-73,-39],[-73,-40]]]}
    lake=http.post("/api/v1/lakes",headers=headers,json={"name":"Test Lake","region":"Los Ríos","geom":polygon})
    assert lake.status_code==201,lake.text
    lake_id=lake.json()["id"]
    listing=http.get("/api/v1/lakes").json()
    assert listing["total"]==1,listing
    assert database.table("lakes").select("id,stations(count)").execute().data[0]["stations"][0]["count"]==0
    assert http.get("/api/v1/lakes/"+lake_id).json()["geom"]["type"]=="Polygon"
    escaped=http.get("/api/v1/lakes",params={"text":"' OR 1=1 --"}).json()
    assert escaped["total"]==0
    reg=http.post("/auth/register",json={"email":"reader@example.invalid","password":"Reader-password-2026!","full_name":"Reader"})
    assert reg.status_code==201,reg.text
    reader={"Authorization":"Bearer "+reg.json()["access_token"]}
    assert http.post("/api/v1/organizations",headers=reader,json={"name":"No","identifier":"no"}).status_code==403
    assert http.get("/api/v1/organizations/"+org_id+"/members",headers=reader).status_code==403
    assert http.post("/auth/register",json={"email":"attacker@example.invalid","password":"Reader-password-2026!","full_name":"Bad","role":"administrador"}).status_code==422
    rejected_password="Rejected-login-secret-82374!"
    bad=http.post("/auth/login",json={"email":"admin@example.invalid","password":rejected_password})
    assert bad.status_code==401
    assert rejected_password not in bad.text
    refreshed=http.post("/auth/refresh",json={"refresh_token":session["refresh_token"]})
    assert refreshed.status_code==200,refreshed.text
    assert http.post("/auth/refresh",json={"refresh_token":session["refresh_token"]}).status_code==401
    assert http.post("/auth/logout",headers=headers).status_code==204
    assert http.get("/auth/me",headers=headers).status_code==401
    assert http.post("/auth/refresh",json={"refresh_token":refreshed.json()["refresh_token"]}).status_code==401
    public=http.get("/openapi.json").json()
    assert public["servers"][0]["url"]=="/"
with database.connection() as connection:
    assert connection.execute("SELECT count(*) AS n FROM public.schema_migrations").fetchone()["n"]==3
try:
    database.table("lakes").insert({"name":"Test Lake","region":"x","geom":polygon}).execute()
except APIError as exc:
    assert exc.code=="23505"
else:
    raise AssertionError("Unique constraint not enforced")
print("PostgreSQL, sessions, roles, isolation, GeoJSON and migrations: OK")
'''
    environment = {**os.environ, "DATABASE_URL": client}
    result = subprocess.run([sys.executable, "-c", script], env=environment, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
