#!/usr/bin/env python3
"""Update eval metadata and compute summary metrics from evaluations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-file", type=Path, required=True, help="Existing eval JSON file.")
    parser.add_argument(
        "--output-file",
        type=Path,
        help="Optional output path. If omitted, overwrite input-file.",
    )
    parser.add_argument("--persona", required=True)
    parser.add_argument("--test-date", default="")
    parser.add_argument("--model-used", required=True)
    parser.add_argument("--raw-log-tokens", type=int, required=True)
    parser.add_argument("--indent", type=int, default=2)
    return parser.parse_args()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def pct(values: list[float]) -> str:
    if not values:
        return "0.0%"
    return f"{(sum(values) / len(values)) * 100:.1f}%"


def calculate_summary(evaluations: list[dict[str, Any]]) -> tuple[str, dict[str, str], int]:
    score_values: list[float] = []
    by_type: dict[str, list[float]] = {}

    for evaluation in evaluations:
        try:
            score = float(evaluation.get("score_value", 0.0))
        except (TypeError, ValueError):
            score = 0.0
        score_values.append(score)
        eval_type = evaluation.get("type")
        if eval_type:
            by_type.setdefault(eval_type, []).append(score)

    overall_accuracy = pct(score_values)
    accuracy_by_type = {eval_type: pct(values) for eval_type, values in by_type.items()}
    return overall_accuracy, accuracy_by_type, len(evaluations)


def main() -> None:
    args = parse_args()
    input_file = args.input_file.resolve()
    output_file = (args.output_file or input_file).resolve()

    data = load_json(input_file)
    if isinstance(data, list):
        evaluations = data
        data = {"evaluations": evaluations}
    elif isinstance(data, dict):
        evaluations = data.get("evaluations", [])
    else:
        raise TypeError("Input JSON must be either an object or a list.")
    overall_accuracy, accuracy_by_type, cases_evaluated = calculate_summary(evaluations)

    data["metadata"] = {
        "persona": args.persona,
        "test_date": args.test_date,
        "cases_evaluated": cases_evaluated,
        "model_used": args.model_used,
        "raw_log_tokens": args.raw_log_tokens,
    }
    data["overall_accuracy"] = overall_accuracy
    data["accuracy_by_type"] = accuracy_by_type

    output_file.write_text(json.dumps(data, indent=args.indent) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
