#!/usr/bin/env python3
"""Run Persona-Bench question files through OpenClaw sequentially.

This script:
  1. Reads a single persona's question-only JSON file
  2. Sends each question to `openclaw agent --json`
  3. Parses the agent response
  4. Writes one aggregate answers JSON file

It is intentionally simple and sequential. It does not try to isolate sessions
between questions.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
import uuid


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--questions-file",
        type=Path,
        required=True,
        help="Path to a <persona>_test_questions.json file.",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        required=True,
        help="Path to the aggregate answers JSON file to write.",
    )
    parser.add_argument(
        "--openclaw-bin",
        default="openclaw",
        help="OpenClaw executable name or full path. Default: openclaw",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume by skipping test_case_ids already present in the output file.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Indent level for emitted JSON. Default: 2.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_existing_answers(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return load_json(path)


def build_message(test_case: dict[str, Any]) -> str:
    return (
        f"test_case_id: {test_case['id']}\n\n"
        f"Question: {test_case['question']}"
    )


def run_openclaw(openclaw_bin: str, message: str) -> dict[str, Any]:
    cmd = [
        openclaw_bin, 
        "agent", 
        "--agent", "main", # main -- must specify which agent
        "--session-id", str(uuid.uuid4()), # different session for each question reduce answer leakage
        "--message", 
        message, 
        "--json"
        ]
    result = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "OpenClaw command failed.\n"
            f"Command: {' '.join(cmd)}\n"
            f"Exit code: {result.returncode}\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    parsed = extract_openclaw_json(result.stdout, result.stderr)
    if parsed is not None:
        return parsed

    raise RuntimeError(
        "OpenClaw did not return parseable JSON output.\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )


def extract_openclaw_json(stdout_text: str, stderr_text: str) -> dict[str, Any] | None:
    if stdout_text.strip():
        try:
            parsed = json.loads(stdout_text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    stderr_lines = stderr_text.splitlines()
    for index, line in enumerate(stderr_lines):
        if line.strip() == "{":
            candidate = "\n".join(stderr_lines[index:])
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                break

    return None


def extract_model_payload(raw_openclaw_json: dict[str, Any], test_case_id: str) -> dict[str, Any]:
    content = None

    if isinstance(raw_openclaw_json.get("assistant"), dict):
        content = raw_openclaw_json["assistant"].get("content")
    if content is None and isinstance(raw_openclaw_json.get("message"), dict):
        content = raw_openclaw_json["message"].get("content")
    if content is None and isinstance(raw_openclaw_json.get("content"), str):
        content = raw_openclaw_json["content"]
    if content is None and isinstance(raw_openclaw_json.get("payloads"), list):
        payloads = raw_openclaw_json["payloads"]
        if payloads and isinstance(payloads[0], dict):
            content = payloads[0].get("text")

    if content is None:
        # Preserve the raw payload even if the output shape differs from what we expect.
        return {
            "test_case_id": test_case_id,
            "answer": None,
            "confidence": None,
            "evidence": [],
            "raw_response": raw_openclaw_json,
            "parse_error": "Could not find assistant content field in OpenClaw JSON response.",
        }

    # Best case: the model itself returned the requested JSON string.
    if isinstance(content, str):
        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            stripped = "\n".join(lines).strip()
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                parsed.setdefault("test_case_id", test_case_id)
                parsed["raw_response"] = raw_openclaw_json
                return parsed
        except json.JSONDecodeError:
            return {
                "test_case_id": test_case_id,
                "answer": stripped,
                "confidence": None,
                "evidence": [],
                "raw_response": raw_openclaw_json,
                "parse_error": "Assistant content was not valid JSON.",
            }

    return {
        "test_case_id": test_case_id,
        "answer": None,
        "confidence": None,
        "evidence": [],
        "raw_response": raw_openclaw_json,
        "parse_error": "Assistant content field was present but not parseable.",
    }


def main() -> None:
    args = parse_args()
    questions_file = args.questions_file.resolve()
    output_file = args.output_file.resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    question_data = load_json(questions_file)
    persona = question_data.get("metadata", {}).get("persona")
    persona_id = question_data.get("metadata", {}).get("persona_id")
    test_cases = question_data.get("test_cases") or []

    existing = load_existing_answers(output_file) if args.resume else None
    completed_ids = set()
    answers: list[dict[str, Any]] = []

    if existing:
        answers = list(existing.get("answers") or [])
        completed_ids = {
            answer.get("test_case_id")
            for answer in answers
            if answer.get("test_case_id")
        }

    for index, test_case in enumerate(test_cases, start=1):
        test_case_id = test_case["id"]
        if test_case_id in completed_ids:
            continue

        print(
            f"[{index}/{len(test_cases)}] Asking {test_case_id}",
            file=sys.stderr,
            flush=True,
        )
        message = build_message(test_case)
        raw_result = run_openclaw(args.openclaw_bin, message)
        parsed_answer = extract_model_payload(raw_result, test_case_id)
        answers.append(parsed_answer)

        payload = {
            "persona": persona,
            "persona_id": persona_id,
            "source_questions_file": str(questions_file),
            "answers": answers,
        }
        output_file.write_text(
            json.dumps(payload, indent=args.indent) + "\n",
            encoding="utf-8",
        )

    print(f"Wrote {output_file}", file=sys.stderr)


if __name__ == "__main__":
    main()
