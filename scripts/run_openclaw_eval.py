#!/usr/bin/env python3
"""Evaluate Persona-Bench answers against full test cases using OpenClaw."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--answers-file",
        type=Path,
        required=True,
        help="Path to a cleaned aggregate answers JSON file.",
    )
    parser.add_argument(
        "--test-cases-file",
        type=Path,
        required=True,
        help="Path to the full persona test cases JSON file.",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        required=True,
        help="Path to the aggregate eval JSON file to write.",
    )
    parser.add_argument(
        "--raw-logs-file",
        type=Path,
        help="Optional raw app logs file for metadata.raw_log_tokens approximation.",
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


def atomic_write_json(path: Path, payload: dict[str, Any], indent: int) -> None:
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=indent) + "\n", encoding="utf-8")
    os.replace(temp_path, path)


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


def run_openclaw(openclaw_bin: str, message: str) -> dict[str, Any]:
    cmd = [
        openclaw_bin,
        "agent",
        "--agent",
        "main",
        "--session-id",
        str(uuid.uuid4()),
        "--message",
        message,
        "--json",
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    parsed = extract_openclaw_json(result.stdout, result.stderr)
    if parsed is not None:
        return parsed
    raise RuntimeError(
        "OpenClaw did not return parseable JSON output.\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )


def extract_model_payload(raw_openclaw_json: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    content = None
    if isinstance(raw_openclaw_json.get("payloads"), list):
        payloads = raw_openclaw_json["payloads"]
        if payloads and isinstance(payloads[0], dict):
            content = payloads[0].get("text")
    if content is None and isinstance(raw_openclaw_json.get("content"), str):
        content = raw_openclaw_json["content"]

    if not isinstance(content, str):
        return None, None

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
    except json.JSONDecodeError:
        return None, stripped

    if isinstance(parsed, dict):
        return parsed, stripped
    return None, stripped


def approximate_tokens(path: Path | None) -> int | None:
    if path is None or not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    return max(1, round(len(text) / 4))


def build_eval_message(test_case: dict[str, Any], answer: dict[str, Any]) -> str:
    answer_text = answer.get("answer")
    confidence = answer.get("confidence")
    evidence = answer.get("evidence")
    return f"""Evaluate one Persona-Bench answer against the benchmark ground truth.

Score using only these labels and values:
- CORRECT = 1.0
- PARTIAL = 0.5
- INCORRECT = 0.0

Use these guidelines:
- CORRECT: captures the key facts in the ground truth, even if minor details are missing.
- PARTIAL: gets the right theme/topic but misses significant specifics.
- INCORRECT: wrong, irrelevant, or fails to identify the main point.

Return valid JSON only in exactly this format:
{{
  "score": "CORRECT|PARTIAL|INCORRECT",
  "score_value": 1.0,
  "explanation": "what was right, what was missed, and why"
}}

Question:
{test_case.get("question")}

Ground truth:
{test_case.get("ground_truth")}

Expected evidence:
{test_case.get("expected_evidence")}

Model answer:
{json.dumps(answer_text, ensure_ascii=False)}

Model confidence:
{json.dumps(confidence, ensure_ascii=False)}

Model evidence:
{json.dumps(evidence, ensure_ascii=False)}
"""


def build_empty_evaluation(test_case: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any]:
    return {
        "test_case_id": test_case.get("id"),
        "type": test_case.get("type"),
        "question": test_case.get("question"),
        "answer_from_logs": answer.get("answer"),
        "ground_truth": test_case.get("ground_truth"),
        "score": "INCORRECT",
        "score_value": 0.0,
        "explanation": "No usable answer was available for evaluation.",
    }


def calculate_accuracy(evaluations: list[dict[str, Any]]) -> tuple[str, dict[str, str]]:
    if not evaluations:
        return "0.0%", {}

    total = sum(float(item.get("score_value", 0.0)) for item in evaluations)
    overall = f"{(100.0 * total / len(evaluations)):.1f}%"

    by_type: dict[str, list[float]] = {}
    for item in evaluations:
        by_type.setdefault(item.get("type"), []).append(float(item.get("score_value", 0.0)))

    accuracy_by_type: dict[str, str] = {}
    for test_type, values in by_type.items():
        accuracy_by_type[test_type] = f"{(100.0 * sum(values) / len(values)):.1f}%"

    return overall, accuracy_by_type


def main() -> None:
    args = parse_args()
    answers_file = args.answers_file.resolve()
    test_cases_file = args.test_cases_file.resolve()
    output_file = args.output_file.resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    answers_data = load_json(answers_file)
    test_cases_data = load_json(test_cases_file)
    answers = answers_data.get("answers") or []
    test_case_map = {case["id"]: case for case in (test_cases_data.get("test_cases") or [])}

    existing = load_json(output_file) if args.resume and output_file.exists() else None
    evaluations: list[dict[str, Any]] = []
    completed_ids: set[str] = set()
    model_used = None

    if existing:
        evaluations = list(existing.get("evaluations") or [])
        completed_ids = {item.get("test_case_id") for item in evaluations if item.get("test_case_id")}
        model_used = existing.get("metadata", {}).get("model_used")

    for index, answer in enumerate(answers, start=1):
        test_case_id = answer.get("test_case_id")
        if not test_case_id or test_case_id in completed_ids:
            continue

        test_case = test_case_map.get(test_case_id)
        if test_case is None:
            print(f"Skipping missing test case: {test_case_id}", file=sys.stderr, flush=True)
            continue

        print(f"[{index}/{len(answers)}] Evaluating {test_case_id}", file=sys.stderr, flush=True)

        if answer.get("answer") is None:
            evaluation = build_empty_evaluation(test_case, answer)
        else:
            try:
                raw_result = run_openclaw(args.openclaw_bin, build_eval_message(test_case, answer))
                parsed, _ = extract_model_payload(raw_result)
                if parsed is None:
                    evaluation = build_empty_evaluation(test_case, answer)
                else:
                    evaluation = {
                        "test_case_id": test_case.get("id"),
                        "type": test_case.get("type"),
                        "question": test_case.get("question"),
                        "answer_from_logs": answer.get("answer"),
                        "ground_truth": test_case.get("ground_truth"),
                        "score": parsed.get("score", "INCORRECT"),
                        "score_value": parsed.get("score_value", 0.0),
                        "explanation": parsed.get("explanation", "No explanation returned."),
                    }
                    model_used = raw_result.get("meta", {}).get("agentMeta", {}).get("model", model_used)
            except Exception as exc:
                print(f"Error for {test_case_id}: {exc}", file=sys.stderr, flush=True)
                evaluation = build_empty_evaluation(test_case, answer)

        evaluations.append(evaluation)

        overall_accuracy, accuracy_by_type = calculate_accuracy(evaluations)
        payload = {
            "metadata": {
                "persona": answers_data.get("persona"),
                "test_date": os.environ.get("EVAL_TEST_DATE") or "",
                "cases_evaluated": len(evaluations),
                "model_used": model_used,
                "raw_log_tokens": approximate_tokens(args.raw_logs_file),
            },
            "overall_accuracy": overall_accuracy,
            "accuracy_by_type": accuracy_by_type,
            "evaluations": evaluations,
        }
        atomic_write_json(output_file, payload, args.indent)


if __name__ == "__main__":
    main()
