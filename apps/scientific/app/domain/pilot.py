"""Entrenamiento reproducible de clorofila-a a partir del NDCI del piloto."""

import csv
import hashlib
import io
from math import isfinite
from statistics import fmean, linear_regression
from uuid import UUID

from app.domain.evaluation import split_by_acquisition_date
from app.domain.metrics import calculate_pilot_metrics


def train_pilot(data: bytes, version_id: UUID, evaluation_fraction: float = 0.25) -> dict:
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    columns = {"acquisition_date", "ndci", "chlorophyll_a"}
    if reader.fieldnames is None or not columns.issubset(reader.fieldnames):
        raise ValueError("El CSV requiere acquisition_date, ndci y chlorophyll_a.")

    records = []
    for number, row in enumerate(reader, start=2):
        try:
            ndci = float(row["ndci"])
            chlorophyll = float(row["chlorophyll_a"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Fila {number}: valores numéricos inválidos.") from exc
        if not isfinite(ndci) or not -1 <= ndci <= 1 or not isfinite(chlorophyll) or chlorophyll < 0:
            raise ValueError(f"Fila {number}: NDCI o clorofila-a fuera del dominio.")
        records.append({
            "acquisition_date": row["acquisition_date"],
            "ndci": ndci,
            "chlorophyll_a": chlorophyll,
        })

    partition = split_by_acquisition_date(records, evaluation_fraction)
    train_x = [float(row["ndci"]) for row in partition.training]
    train_y = [float(row["chlorophyll_a"]) for row in partition.training]
    if len(set(train_x)) < 2:
        raise ValueError("El entrenamiento requiere al menos dos valores NDCI distintos.")

    slope, intercept = linear_regression(train_x, train_y)
    baseline = fmean(train_y)
    evaluation_y = [float(row["chlorophyll_a"]) for row in partition.evaluation]
    predictions = [slope * float(row["ndci"]) + intercept for row in partition.evaluation]
    return {
        "experimental": True,
        "dataset_version_id": str(version_id),
        "dataset_sha256": hashlib.sha256(data).hexdigest(),
        "partition": {
            "strategy": partition.strategy,
            "cutoff": partition.cutoff_date.isoformat(),
            "evaluation_fraction": evaluation_fraction,
            "training_rows": len(train_x),
            "evaluation_rows": len(evaluation_y),
        },
        "model": {
            "algorithm": "ordinary_least_squares",
            "index": "NDCI",
            "target": "chlorophyll_a",
            "unit": "µg/L",
            "intercept": intercept,
            "slope": slope,
            "training_ndci_range": [min(train_x), max(train_x)],
        },
        "metrics": calculate_pilot_metrics(evaluation_y, predictions).model_dump(exclude_none=True),
        "baseline": {
            "mean": baseline,
            "metrics": calculate_pilot_metrics(
                evaluation_y, [baseline] * len(evaluation_y)
            ).model_dump(exclude_none=True),
        },
        "warnings": ["Piloto experimental. La evaluación corresponde solo a los datos suministrados."],
    }
