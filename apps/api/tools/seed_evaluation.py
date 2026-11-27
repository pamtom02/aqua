"""Explicit, additive evaluation fixtures. Never runs during application startup."""
import argparse
import json
import math
import os
from datetime import date
from uuid import NAMESPACE_URL, uuid5

MARKER = "[AQUA-EVAL-V1]"
NOTICE = (
    f"{MARKER} Datos sintéticos para evaluación. Geometría aproximada de demostración; "
    "no representa límites oficiales, mediciones ni resultados científicos reales."
)


def record_id(key):
    return str(uuid5(NAMESPACE_URL, f"https://aquabloom.example/evaluation/v1/{key}"))


def polygon(lon, lat, width=0.045, height=0.025):
    ring = [
        [round(lon + width * math.cos(i * math.pi / 4), 6),
         round(lat + height * math.sin(i * math.pi / 4), 6)]
        for i in range(8)
    ]
    return {"type": "Polygon", "coordinates": [ring + [ring[0]]]}


def fixtures():
    organizations = [
        {"id": record_id(f"organization/{i}"), "name": f"EVAL - Equipo {i}",
         "identifier": f"aqua-eval-v1-equipo-{i}", "description": NOTICE, "status": "active"}
        for i in (1, 2)
    ]
    centers = [
        ("Lago Villarrica", "La Araucanía", -72.10, -39.27),
        ("Lago Ranco", "Los Ríos", -72.35, -40.22),
        ("Lago Llanquihue", "Los Lagos", -72.82, -41.12),
        ("Lago Puyehue", "Los Lagos", -72.48, -40.67),
        ("Lago Rupanco", "Los Lagos", -72.43, -40.83),
        ("Lago Panguipulli", "Los Ríos", -72.27, -39.72),
    ]
    regions = [("La Araucanía", -38.92), ("Los Ríos", -39.92), ("Los Lagos", -41.02)]
    for i in range(18):
        region, latitude = regions[i % 3]
        centers.append((f"Laguna Sintética {i + 1:02d}", region,
                        -72.0 + (i // 3) * 0.13, latitude))
    centers.extend([
        ("Lago Inactivo A", "La Araucanía", -71.95, -39.12),
        ("Lago Inactivo B", "Los Ríos", -72.15, -40.12),
    ])
    lakes, stations, scenes = [], [], []
    for i, (name, region, lon, lat) in enumerate(centers):
        lake_id = record_id(f"lake/{i + 1}")
        lakes.append({
            "id": lake_id, "name": f"EVAL - {name}", "region": region,
            "description": NOTICE, "geom": polygon(lon, lat),
            "status": "active" if i < 24 else "inactive",
            "organization_id": organizations[i % 2]["id"],
        })
        for j, (label, dy) in enumerate([("Norte", 0.010), ("Sur", -0.010), ("Reserva", 0)]):
            stations.append({
                "id": record_id(f"lake/{i + 1}/station/{j + 1}"), "lake_id": lake_id,
                "code": f"EV{i + 1:02d}-{j + 1}", "name": f"EVAL - Estación {label}",
                "point": {"type": "Point", "coordinates": [lon, round(lat + dy, 6)]},
                "description": NOTICE, "status": "active" if j < 2 else "inactive",
            })
        if i < 6:
            for j in (1, 2):
                scenes.append({
                    "id": record_id(f"lake/{i + 1}/scene/{j}"), "lake_id": lake_id,
                    "scene_identifier": f"EVAL-SYNTHETIC-L{i + 1:02d}-{j}",
                    "acquisition_date": date(2026, 11, j).isoformat(),
                    "provider": "SYNTHETIC-EVALUATION",
                    "metadata": {"synthetic": True, "seed": MARKER, "notice": NOTICE},
                    "file_references": [],
                })
    datasets, versions = [], []
    for i, organization in enumerate(organizations, 1):
        dataset_id = record_id(f"dataset/{i}")
        datasets.append({
            "id": dataset_id, "name": f"EVAL - Dataset de práctica {i}",
            "description": NOTICE, "organization_id": organization["id"],
        })
        versions.append({
            "id": record_id(f"dataset/{i}/version/1"), "dataset_id": dataset_id,
            "version_number": 1, "status": "DRAFT", "state": "DRAFT",
        })
    return {"organizations": organizations, "lakes": lakes, "stations": stations,
            "scenes": scenes, "datasets": datasets, "versions": versions}


def validate(data):
    from shapely.geometry import shape

    lakes = {row["id"]: shape(row["geom"]) for row in data["lakes"]}
    for geometry in lakes.values():
        if not geometry.is_valid or geometry.is_empty or geometry.area <= 0:
            raise ValueError("Geometría de evaluación no válida.")
    for row in data["stations"]:
        if not lakes[row["lake_id"]].contains(shape(row["point"])):
            raise ValueError("Una estación de evaluación está fuera de su lago.")


def seed(connection):
    """One transaction; stable IDs; insert only; conflicts never overwrite user data."""
    from psycopg import sql
    from psycopg.types.json import Jsonb

    data = fixtures()
    validate(data)
    targets = {
        "organizations": ("public", "organizations"),
        "lakes": ("public", "lakes"), "stations": ("public", "stations"),
        "scenes": ("satellite", "scenes"),
        "datasets": ("dataset", "datasets"), "versions": ("dataset", "versions"),
    }
    inserted = {}
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(761208214)")
        for group, (schema, table) in targets.items():
            inserted[group] = 0
            for row in data[group]:
                columns = list(row)
                query = sql.SQL(
                    "INSERT INTO {}.{} ({}) VALUES ({}) ON CONFLICT (id) DO NOTHING RETURNING id"
                ).format(sql.Identifier(schema), sql.Identifier(table),
                         sql.SQL(",").join(map(sql.Identifier, columns)),
                         sql.SQL(",").join(sql.Placeholder() for _ in columns))
                values = [Jsonb(v) if isinstance(v, (dict, list)) else v for v in row.values()]
                inserted[group] += int(connection.execute(query, values).fetchone() is not None)
        # Existing administrators can manage the synthetic teams. No accounts,
        # passwords, global roles, MFA credentials or sessions are created/changed.
        inserted["memberships"] = 0
        administrators = connection.execute(
            "SELECT id FROM public.users WHERE role='administrador' AND status='active'"
        ).fetchall()
        for user in administrators:
            user_id = str(user[0])
            organization_id = data["organizations"][0]["id"]
            row = connection.execute(
                """INSERT INTO public.memberships(id,user_id,organization_id,role,status)
                   VALUES(%s,%s,%s,'administrador','active')
                   ON CONFLICT(user_id,organization_id) DO NOTHING RETURNING id""",
                (record_id(f"membership/{user_id}/1"), user_id, organization_id),
            ).fetchone()
            inserted["memberships"] += int(row is not None)
    return {"seed": MARKER, "planned": {k: len(v) for k, v in data.items()},
            "inserted": inserted, "active_lakes": 24, "inactive_lakes": 2}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", choices=["aquabloom-evaluation"])
    args = parser.parse_args()
    data = fixtures()
    validate(data)
    if not args.apply:
        print(json.dumps({"mode": "plan", "seed": MARKER,
                          "records": {key: len(value) for key, value in data.items()}}, sort_keys=True))
        return
    if args.confirm != "aquabloom-evaluation":
        parser.error("La carga requiere --confirm aquabloom-evaluation.")
    import psycopg

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL sin configurar; no se insertó nada.")
    try:
        with psycopg.connect(dsn, connect_timeout=10) as connection:
            if connection.execute("SELECT current_database()").fetchone()[0] != "aquabloom":
                raise ValueError("La base conectada no es aquabloom.")
            result = seed(connection)
        print(json.dumps(result, sort_keys=True))
    except Exception:
        # Connection errors can contain DSN credentials. Never print raw exceptions.
        raise SystemExit("Carga no completada; la transacción fallida se revirtió. Revisar sin revelar credenciales.") from None


if __name__ == "__main__":
    main()
