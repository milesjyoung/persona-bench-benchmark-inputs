#!/usr/bin/env python3
"""Extract question-only test case files into generated persona folders."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        required=True,
        help="Path to the repo root.",
    )
    parser.add_argument(
        "--generated-dir",
        type=Path,
        required=True,
        help="Path to the generated output directory.",
    )
    parser.add_argument(
        "--persona",
        action="append",
        dest="personas",
        default=[],
        help="Optional persona slug to process. Can be passed multiple times.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Indent level for output JSON.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_question_only_payload(test_case_data: dict[str, Any]) -> dict[str, Any]:
    metadata = test_case_data.get("metadata") or {}
    test_cases = test_case_data.get("test_cases") or []

    return {
        "metadata": {
            "persona": metadata.get("persona"),
            "persona_id": metadata.get("persona_id"),
            "total_test_cases": len(test_cases),
            "source_file_type": "question_only",
        },
        "test_cases": [
            {
                "id": case.get("id"),
                "type": case.get("type"),
                "difficulty": case.get("difficulty"),
                "question": case.get("question"),
            }
            for case in test_cases
        ],
    }


def main() -> None:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    generated_dir = args.generated_dir.resolve()
    selected = set(args.personas)

    test_cases_dir = repo_root / "test_cases"
    found_any = False

    for test_case_path in sorted(test_cases_dir.glob("*_test_cases.json")):
        slug = test_case_path.name.removesuffix("_test_cases.json")
        if selected and slug not in selected:
            continue

        found_any = True
        persona_dir = generated_dir / slug
        persona_dir.mkdir(parents=True, exist_ok=True)

        payload = build_question_only_payload(load_json(test_case_path))
        output_path = persona_dir / f"{slug}_test_questions.json"
        output_path.write_text(
            json.dumps(payload, indent=args.indent) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {output_path}")

    if not found_any:
        raise SystemExit("No matching test case files found.")


if __name__ == "__main__":
    main()
