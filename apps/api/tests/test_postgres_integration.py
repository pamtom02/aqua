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
    assert connection.execute("SELECT count(*) AS n FROM public.schema_migrations").fetchone()["n"]==4
try:
    database.table("lakes").insert({"name":"Test Lake","region":"x","geom":polygon}).execute()
except APIError as exc:
    assert exc.code=="23505"
else:
    raise AssertionError("Unique constraint not enforced")

# Exercise actual production enforcement without ever printing test credentials.
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, UTC
from cryptography.fernet import Fernet
from pydantic import SecretStr
import pyotp
from app.config import settings
settings.environment="production"
settings.mfa_encryption_key=SecretStr(Fernet.generate_key().decode())
credentials={"email":"admin@example.invalid","password":"Integration-password-2026!"}
with TestClient(app) as http:
    setup=http.post("/auth/login",json=credentials)
    assert setup.status_code==200
    assert setup.json()["mfa_required"] is True
    setup_headers={"Authorization":"Bearer "+setup.json()["access_token"]}
    assert http.get("/auth/me",headers=setup_headers).status_code==403
    enrollment=http.post("/auth/mfa/enroll",headers=setup_headers)
    assert enrollment.status_code==200
    assert enrollment.headers["cache-control"]=="no-store"
    authenticator=pyotp.parse_uri(enrollment.json()["provisioning_uri"])
    with database.connection() as connection:
        encrypted=connection.execute("SELECT encrypted_secret FROM public.user_mfa WHERE user_id=%s",(admin["id"],)).fetchone()["encrypted_secret"]
        assert authenticator.secret not in encrypted
    confirmed=http.post("/auth/mfa/confirm",headers=setup_headers,json={"code":authenticator.now()})
    assert confirmed.status_code==200
    assert confirmed.json()["mfa_required"] is False
    assert len(confirmed.json()["recovery_codes"])==10
    verified_headers={"Authorization":"Bearer "+confirmed.json()["access_token"]}
    assert http.get("/auth/me",headers=setup_headers).status_code==401
    assert http.get("/auth/me",headers=verified_headers).status_code==200
    assert http.post("/auth/login",json=credentials).status_code==401
    assert http.post("/auth/login",json={**credentials,"second_factor":authenticator.now()}).status_code==401
    counter=authenticator.timecode(datetime.now(UTC))+1
    next_code=authenticator.at(counter*authenticator.interval)
    def concurrent_login(_):
        with TestClient(app) as parallel:
            return parallel.post("/auth/login",json={**credentials,"second_factor":next_code}).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(concurrent_login,range(2)))==[200,401]
    recovery_code=confirmed.json()["recovery_codes"][0]
    recovered=http.post("/auth/login",json={**credentials,"second_factor":recovery_code})
    assert recovered.status_code==200
    assert http.post("/auth/login",json={**credentials,"second_factor":recovery_code}).status_code==401
    assert http.get("/auth/me",headers=verified_headers).status_code==401
    active_headers={"Authorization":"Bearer "+recovered.json()["access_token"]}
    with database.connection() as connection:
        session=connection.execute("SELECT id,last_activity_at FROM public.auth_sessions WHERE user_id=%s",(admin["id"],)).fetchone()
        assert connection.execute("SELECT count(*) AS n FROM public.mfa_recovery_codes WHERE user_id=%s",(admin["id"],)).fetchone()["n"]==9
    assert http.get("/auth/me",headers=active_headers).status_code==200
    with database.connection() as connection:
        assert connection.execute("SELECT last_activity_at FROM public.auth_sessions WHERE id=%s",(session["id"],)).fetchone()["last_activity_at"]==session["last_activity_at"]
        connection.execute("UPDATE public.auth_sessions SET created_at=now()-interval '6 minutes' WHERE id=%s",(session["id"],))
    assert http.post("/api/v1/organizations",headers=active_headers,json={"name":"Recent","identifier":"recent"}).status_code==401
    with database.connection() as connection:
        connection.execute("UPDATE public.auth_sessions SET last_activity_at=now()-interval '21 minutes' WHERE id=%s",(session["id"],))
    assert http.get("/auth/me",headers=active_headers).status_code==401
    assert http.post("/auth/refresh",json={"refresh_token":recovered.json()["refresh_token"]}).status_code==401
    with database.connection() as connection:
        connection.execute("UPDATE public.auth_sessions SET last_activity_at=now(),created_at=now()-interval '9 hours' WHERE id=%s",(session["id"],))
    assert http.get("/auth/me",headers=active_headers).status_code==401
print("PostgreSQL, sessions, roles, isolation, GeoJSON and migrations: OK")
'''
    environment = {**os.environ, "DATABASE_URL": client}
    result = subprocess.run([sys.executable, "-c", script], env=environment, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
