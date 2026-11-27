from collections.abc import Callable
from math import isfinite

from app.domain.baseline import MeanBaseline


def submit_summary(measurements: list[float], enqueue: Callable[[list[float]], str]) -> str:
    if not all(isfinite(value) for value in measurements):
        raise ValueError("Todas las mediciones deben ser valores finitos.")
    return enqueue(measurements)


def predict_baseline(y_train: list[float], count: int) -> list[float]:
    baseline = MeanBaseline()
    baseline.fit(y_train)
    return baseline.predict(count)
