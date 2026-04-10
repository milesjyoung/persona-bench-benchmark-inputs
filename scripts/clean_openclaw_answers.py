#!/usr/bin/env python3
"""Clean OpenClaw benchmark answer files by removing bulky raw response fields."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-file",
        type=Path,
        required=True,
        help="Path to the existing aggregate answers JSON file.",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        help="Optional output path. If omitted, overwrite the input file.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Indent level for output JSON. Default: 2.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def clean_answer(answer: dict[str, Any]) -> dict[str, Any]:
    cleaned = {
        "test_case_id": answer.get("test_case_id"),
        "answer": answer.get("answer"),
        "confidence": answer.get("confidence"),
        "evidence": answer.get("evidence", []),
    }

    if "parse_error" in answer and answer.get("parse_error"):
        cleaned["parse_error"] = answer["parse_error"]

    return cleaned


def main() -> None:
    args = parse_args()
    input_file = args.input_file.resolve()
    output_file = (args.output_file or input_file).resolve()

    data = load_json(input_file)
    cleaned = {
        "persona": data.get("persona"),
        "persona_id": data.get("persona_id"),
        "source_questions_file": data.get("source_questions_file"),
        "answers": [clean_answer(answer) for answer in data.get("answers", [])],
    }

    output_file.write_text(
        json.dumps(cleaned, indent=args.indent) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
