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
import os
import subprocess
import sys
import time
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
        "--start-from",
        help="Start asking from this test_case_id (for example: TC-49).",
    )
    parser.add_argument(
        "--session-mode",
        choices=["isolated", "shared"],
        default="isolated",
        help="Use a fresh session per question or a single shared session for the whole run. Default: isolated.",
    )
    parser.add_argument(
        "--session-id",
        help="Optional explicit session ID to use when --session-mode shared.",
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


def run_openclaw(openclaw_bin: str, message: str, session_id: str) -> dict[str, Any]:
    cmd = [
        openclaw_bin, 
        "agent", 
        "--agent", "main", # main -- must specify which agent
        "--session-id", session_id,
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

    parsed = extract_openclaw_json(result.stdout, result.stderr)
    if parsed is not None:
        return parsed

    if result.returncode != 0:
        raise RuntimeError(
            "OpenClaw command failed.\n"
            f"Command: {' '.join(cmd)}\n"
            f"Exit code: {result.returncode}\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    raise RuntimeError(
        "OpenClaw did not return parseable JSON output.\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )


def get_session_record(openclaw_bin: str, session_id: str) -> dict[str, Any] | None:
    result = subprocess.run(
        [openclaw_bin, "sessions", "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    sessions = payload.get("sessions")
    if not isinstance(sessions, list):
        return None
    for session in sessions:
        if isinstance(session, dict) and session.get("sessionId") == session_id:
            return session
    return None


def wait_for_shared_session_idle(
    openclaw_bin: str,
    session_id: str,
    timeout_s: float = 30.0,
    poll_interval_s: float = 1.0,
    quiet_polls: int = 2,
) -> None:
    deadline = time.time() + timeout_s
    last_updated_at: int | None = None
    stable_polls = 0

    while time.time() < deadline:
        session = get_session_record(openclaw_bin, session_id)
        if session is None:
            stable_polls = 0
            last_updated_at = None
            time.sleep(poll_interval_s)
            continue

        updated_at = session.get("updatedAt")
        if isinstance(updated_at, int) and updated_at == last_updated_at:
            stable_polls += 1
            if stable_polls >= quiet_polls:
                return
        else:
            stable_polls = 0
            last_updated_at = updated_at if isinstance(updated_at, int) else None

        time.sleep(poll_interval_s)

    raise RuntimeError(
        f"Timed out waiting for shared session {session_id} to go idle."
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
    if raw_openclaw_json.get("meta", {}).get("stopReason") == "error":
        return build_empty_answer(test_case_id)

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
        return build_empty_answer(test_case_id)

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
                return {
                    "test_case_id": parsed.get("test_case_id", test_case_id),
                    "answer": parsed.get("answer"),
                    "confidence": parsed.get("confidence"),
                    "evidence": parsed.get("evidence"),
                }
        except json.JSONDecodeError:
            return build_empty_answer(test_case_id)

    return build_empty_answer(test_case_id)


def build_empty_answer(test_case_id: str) -> dict[str, Any]:
    return {
        "test_case_id": test_case_id,
        "answer": None,
        "confidence": None,
        "evidence": None,
    }


def atomic_write_json(path: Path, payload: dict[str, Any], indent: int) -> None:
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(
        json.dumps(payload, indent=indent) + "\n",
        encoding="utf-8",
    )
    os.replace(temp_path, path)


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
    started = args.start_from is None
    shared_session_id = args.session_id or str(uuid.uuid4())

    if existing:
        answers = list(existing.get("answers") or [])
        completed_ids = {
            answer.get("test_case_id")
            for answer in answers
            if answer.get("test_case_id")
        }

    for index, test_case in enumerate(test_cases, start=1):
        test_case_id = test_case["id"]
        if not started:
            if test_case_id == args.start_from:
                started = True
            else:
                continue
        if test_case_id in completed_ids:
            continue

        print(
            f"[{index}/{len(test_cases)}] Asking {test_case_id}",
            file=sys.stderr,
            flush=True,
        )
        message = build_message(test_case)
        session_id = shared_session_id if args.session_mode == "shared" else str(uuid.uuid4())
        try:
            raw_result = run_openclaw(args.openclaw_bin, message, session_id)
            parsed_answer = extract_model_payload(raw_result, test_case_id)
        except Exception as exc:
            print(f"Error for {test_case_id}: {exc}", file=sys.stderr, flush=True)
            parsed_answer = build_empty_answer(test_case_id)
        answers.append(parsed_answer)

        payload = {
            "persona": persona,
            "persona_id": persona_id,
            "source_questions_file": str(questions_file),
            "answers": answers,
        }
        atomic_write_json(output_file, payload, args.indent)
        if args.session_mode == "shared":
            wait_for_shared_session_idle(args.openclaw_bin, shared_session_id)

    if args.start_from is not None and not started:
        raise SystemExit(f"start-from test case not found: {args.start_from}")

    print(f"Wrote {output_file}", file=sys.stderr)


if __name__ == "__main__":
    main()
