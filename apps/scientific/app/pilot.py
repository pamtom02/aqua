"""Comando local para entrenar y exportar el piloto."""

import argparse
import json
from pathlib import Path
from uuid import UUID

from app.domain.pilot import train_pilot

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("version_id", type=UUID)
    parser.add_argument("--evaluation-fraction", type=float, default=0.25)
    parser.add_argument("--web-report", action="store_true", help="Genera el JSON que importa la pantalla de métricas.")
    args = parser.parse_args()
    result = train_pilot(args.csv.read_bytes(), args.version_id, args.evaluation_fraction)
    if args.web_report:
        metrics = result["metrics"]
        baseline = result["baseline"]["metrics"]
        result = {
            **result,
            "experiment_name": f"Piloto NDCI · {args.version_id}",
            "condition": result["warnings"][0],
            "evaluation_size": metrics["sample_count"],
            "metrics": [
                {
                    "name": name.upper(),
                    "baseline": baseline[name],
                    "experiment": metrics[name],
                    "direction": "higher_is_better" if name == "r2" else "lower_is_better",
                }
                for name in ("mae", "rmse", "r2")
                if name in metrics and name in baseline
            ],
            "detailed_metrics": metrics,
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
