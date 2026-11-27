"""Parameterized PostgreSQL repositories preserving the existing domain contracts.

The fluent interface is local Python code, with no PostgREST or external API.
Identifiers are validated and quoted; all data values use SQL parameters.
"""
import json
import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from app.storage import FileStorage


class APIError(Exception):
    def __init__(self, error=None):
        error = error if isinstance(error, dict) else {}
        self.code = str(error.get("code", "500"))
        super().__init__(error.get("message", "No se pudo completar la operación de datos."))


@dataclass
class QueryResult:
    data: object = None
    count: int | None = None


def identifier(value):
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", value):
        raise ValueError("Identificador SQL no válido.")
    return '"' + value + '"'


def split_fields(value):
    result, part, depth = [], "", 0
    for char in value:
        if char == "," and depth == 0:
            result.append(part.strip())
            part = ""
            continue
        depth += (char == "(") - (char == ")")
        if depth < 0:
            raise ValueError("Selección no válida.")
        part += char
    if depth:
        raise ValueError("Selección no válida.")
    if part.strip():
        result.append(part.strip())
    return result


def clean(value):
    if isinstance(value, (UUID, datetime, date)):
        return str(value) if isinstance(value, UUID) else value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean(item) for item in value]
    return value


class PostgresClient:
    def __init__(self, dsn: str, storage_root=Path("/app/data"), namespace="public"):
        self.dsn = dsn
        self.namespace = namespace
        self.storage = FileStorage(storage_root)

    def schema(self, name: str):
        if name not in {"public", "dataset", "satellite", "scientific"}:
            raise ValueError("Esquema no permitido.")
        return PostgresClient(self.dsn, self.storage.root, name)

    def table(self, name: str):
        identifier(name)
        namespace = "satellite" if self.namespace == "public" and name == "scenes" else self.namespace
        return Query(self, namespace, name)

    @contextmanager
    def connection(self):
        # Lazy import also permits running pure domain tests without libpq.
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=10,
                             options="-c statement_timeout=30000") as connection:
            yield connection


class Query:
    JSON_FIELDS = {"metadata", "details", "geom", "point", "bands", "config", "result", "result_metadata"}

    def __init__(self, client, namespace, table):
        self.client, self.namespace, self.name = client, namespace, table
        self.operation, self.fields = "select", "*"
        self.filters, self.orders = [], []
        self.offset, self.size = 0, None
        self.count_mode, self.head, self.one = None, False, False
        self.values, self.conflict, self.ignore_duplicates = None, None, False

    @property
    def target(self):
        return identifier(self.namespace) + "." + identifier(self.name)

    def select(self, fields="*", count=None, head=False):
        self.fields, self.count_mode, self.head = fields, count, head
        return self

    def _filter(self, column, operator, value):
        if column != "organizations.status":
            identifier(column)
        self.filters.append((column, operator, value))
        return self

    def eq(self, column, value): return self._filter(column, "=", value)
    def neq(self, column, value): return self._filter(column, "<>", value)
    def ilike(self, column, value): return self._filter(column, "ILIKE", value)
    def gte(self, column, value): return self._filter(column, ">=", value)
    def lte(self, column, value): return self._filter(column, "<=", value)
    def in_(self, column, values): return self._filter(column, "IN", list(values))

    def order(self, column, desc=False):
        identifier(column)
        self.orders.append(identifier(column) + (" DESC" if desc else " ASC"))
        return self

    def range(self, start, end):
        if start < 0 or end < start: raise ValueError("Rango no válido.")
        self.offset, self.size = int(start), int(end - start + 1)
        return self

    def limit(self, count):
        if count < 0: raise ValueError("Límite no válido.")
        self.size = int(count)
        return self

    def maybe_single(self):
        self.one = True
        return self

    def single(self):
        return self.maybe_single()

    def insert(self, values):
        self.operation, self.values = "insert", values
        return self

    def upsert(self, values, on_conflict="id", ignore_duplicates=False):
        self.operation, self.values = "upsert", values
        self.conflict = [identifier(column.strip()) for column in on_conflict.split(",")]
        self.ignore_duplicates = ignore_duplicates
        return self

    def update(self, values):
        self.operation, self.values = "update", values
        return self

    def delete(self):
        self.operation = "delete"
        return self

    def _where(self, params):
        clauses = []
        for column, operator, value in self.filters:
            if column == "organizations.status":
                clauses.append('EXISTS (SELECT 1 FROM public.organizations o WHERE o.id = t.organization_id AND o.status = %s)')
                params.append(value)
                continue
            field = "t." + identifier(column)
            if value is None and operator in {"=", "<>"}:
                clauses.append(field + (" IS NULL" if operator == "=" else " IS NOT NULL"))
            elif operator == "IN":
                if value:
                    clauses.append(field + " IN (" + ",".join(["%s"] * len(value)) + ")")
                    params.extend(value)
                else:
                    clauses.append("FALSE")
            else:
                clauses.append(field + " " + operator + " %s")
                params.append(value)
        return " WHERE " + " AND ".join(clauses) if clauses else ""

    def _selection(self):
        fields, joins = [], []
        for part in split_fields(self.fields):
            if part == "*":
                fields.append("t.*")
            elif part == "stations(count)" and self.name == "lakes":
                fields.append("""(SELECT jsonb_build_array(jsonb_build_object('count', count(*))) FROM public.stations s WHERE s.lake_id=t.id) AS stations""")
            elif "!inner(" in part and self.name == "memberships":
                outer, inner = part.split("!inner(", 1)
                alias, _, relation = outer.rpartition(":")
                relation = relation or outer
                alias = alias or relation
                if relation != "organizations" or not inner.endswith(")"):
                    raise ValueError("Relación no admitida.")
                keys = [identifier(field.strip()) for field in inner[:-1].split(",")]
                object_fields = ",".join("'" + key.strip('"') + "',o." + key for key in keys)
                fields.append("jsonb_build_object(" + object_fields + ") AS " + identifier(alias))
                joins.append(" JOIN public.organizations o ON o.id=t.organization_id")
            else:
                fields.append("t." + identifier(part))
        return ",".join(fields), "".join(dict.fromkeys(joins))

    def _value(self, column, value):
        if column in self.JSON_FIELDS and value is not None:
            from psycopg.types.json import Jsonb
            if column in {"geom", "point"}:
                from shapely import from_wkt
                from shapely.geometry import mapping, shape
                geometry = from_wkt(value) if isinstance(value, str) else shape(value)
                if not geometry.is_valid or geometry.is_empty:
                    raise ValueError("Geometría no válida.")
                value = mapping(geometry)
            return Jsonb(value)
        return value

    def execute(self):
        import psycopg
        try:
            with self.client.connection() as connection:
                params = []
                where = self._where(params)
                if self.operation == "select":
                    selection, joins = self._selection()
                    total = None
                    if self.count_mode:
                        total = connection.execute("SELECT count(*) AS count FROM " + self.target + " t" + joins + where, params).fetchone()["count"]
                    if self.head:
                        return QueryResult([], total)
                    query = "SELECT " + selection + " FROM " + self.target + " t" + joins + where
                    if self.orders:
                        query += " ORDER BY " + ",".join(self.orders)
                    elif self.size is not None:
                        query += " ORDER BY t.id"
                    if self.size is not None:
                        query += " LIMIT %s OFFSET %s"
                        params.extend([self.size, self.offset])
                    rows = connection.execute(query, params).fetchall()
                elif self.operation in {"insert", "upsert"}:
                    values = self.values if isinstance(self.values, list) else [self.values]
                    if not values:
                        return QueryResult([])
                    columns = list(values[0])
                    if any(set(row) != set(columns) for row in values):
                        raise ValueError("Las filas deben tener las mismas columnas.")
                    names = ",".join(identifier(column) for column in columns)
                    placeholders = "(" + ",".join(["%s"] * len(columns)) + ")"
                    query = "INSERT INTO " + self.target + " (" + names + ") VALUES " + ",".join([placeholders] * len(values))
                    params = [self._value(column, row[column]) for row in values for column in columns]
                    if self.operation == "upsert":
                        query += " ON CONFLICT (" + ",".join(self.conflict) + ") "
                        if self.ignore_duplicates:
                            query += "DO NOTHING"
                        else:
                            query += "DO UPDATE SET " + ",".join(identifier(column) + "=EXCLUDED." + identifier(column) for column in columns)
                    rows = connection.execute(query + " RETURNING *", params).fetchall()
                else:
                    if not self.filters:
                        raise ValueError("Las mutaciones necesitan un filtro explícito.")
                    if self.operation == "update":
                        assignments = ",".join(identifier(column) + "=%s" for column in self.values)
                        params = [self._value(column, value) for column, value in self.values.items()] + params
                        query = "UPDATE " + self.target + " t SET " + assignments + where
                    else:
                        query = "DELETE FROM " + self.target + " t" + where
                    rows = connection.execute(query + " RETURNING *", params).fetchall()
                rows = clean(rows)
                if self.one:
                    if len(rows) > 1:
                        raise APIError({"code": "PGRST116", "message": "Se esperaba una fila."})
                    return QueryResult(rows[0] if rows else None, total if self.operation == "select" else None)
                return QueryResult(rows, total if self.operation == "select" else None)
        except psycopg.Error as exc:
            raise APIError({"code": exc.sqlstate or "08006"}) from exc
