#!/usr/bin/env python3
"""Prepare sanitized Persona-Bench inputs for benchmark inference.

This script reads:
  - logs/standard/*_app_logs.json
  - test_cases/*_test_cases.json

And writes per-persona artifacts:
  - raw_app_logs.txt        # sanitized logs in the benchmark-runner format
  - test_questions.json     # test cases reduced to question-only payloads

It intentionally strips benchmark-authoring metadata that should not be shown
to the model under test.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PersonaFiles:
    slug: str
    log_path: Path
    test_case_path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        required=True,
        help="Path to the persona-bench-benchmark-inputs repo root.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory where sanitized artifacts will be written.",
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
        help="Indent level for emitted JSON files. Default: 2.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def find_persona_files(repo_root: Path, selected: set[str]) -> list[PersonaFiles]:
    logs_dir = repo_root / "logs" / "standard"
    test_cases_dir = repo_root / "test_cases"

    personas: list[PersonaFiles] = []
    for log_path in sorted(logs_dir.glob("*_app_logs.json")):
        slug = log_path.name.removesuffix("_app_logs.json")
        if selected and slug not in selected:
            continue

        test_case_path = test_cases_dir / f"{slug}_test_cases.json"
        if not test_case_path.exists():
            raise FileNotFoundError(
                f"Missing test cases for persona '{slug}': {test_case_path}"
            )
        personas.append(PersonaFiles(slug=slug, log_path=log_path, test_case_path=test_case_path))

    if selected:
        found = {p.slug for p in personas}
        missing = sorted(selected - found)
        if missing:
            raise FileNotFoundError(
                "Requested persona(s) not found in logs/standard: " + ", ".join(missing)
            )

    if not personas:
        raise FileNotFoundError("No matching persona files found.")

    return personas


def normalize_time(value: Any) -> str:
    return "" if value is None else str(value).strip()


def safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def session_sort_key(session: dict[str, Any]) -> tuple[str, str]:
    messages = session.get("messages") or []
    first_time = normalize_time(messages[0].get("time")) if messages else ""
    return (safe_text(session.get("date")), first_time)


def event_sort_key(event: dict[str, Any]) -> tuple[str, str]:
    return (safe_text(event.get("date")), normalize_time(event.get("start_time")))


def render_messenger(log_data: dict[str, Any], persona_name: str) -> str:
    messenger = log_data.get("messenger", {})
    sessions = []
    sessions.extend(messenger.get("meaningful_sessions") or [])
    sessions.extend(messenger.get("filler_sessions") or [])
    sessions = sorted(sessions, key=session_sort_key)

    lines: list[str] = []
    for session in sessions:
        date = safe_text(session.get("date"))
        participants = session.get("participants") or {}
        other_person = safe_text(participants.get("other_person"))
        lines.append(f"--- {date} | {persona_name} <-> {other_person} ---")
        for message in session.get("messages") or []:
            time = normalize_time(message.get("time"))
            sender = safe_text(message.get("sender"))
            text = safe_text(message.get("text"))
            lines.append(f"[{time}] {sender}: {text}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_calendar(log_data: dict[str, Any]) -> str:
    calendar = log_data.get("calendar", {})
    events = sorted(calendar.get("events") or [], key=event_sort_key)

    lines: list[str] = []
    for event in events:
        date = safe_text(event.get("date"))
        start_time = normalize_time(event.get("start_time"))
        end_time = normalize_time(event.get("end_time"))
        title = safe_text(event.get("title"))
        location = safe_text(event.get("location"))

        participants = event.get("participants")
        if isinstance(participants, list):
            participants_text = ", ".join(str(x).strip() for x in participants if str(x).strip())
        else:
            participants_text = safe_text(participants)

        notes = safe_text(event.get("notes"))
        lines.append(
            f"{date} | {start_time}-{end_time} | {title} | @ {location} | "
            f"with {participants_text} | Notes: {notes}"
        )
    return "\n".join(lines).rstrip() + "\n"


def render_raw_app_logs(log_data: dict[str, Any]) -> str:
    metadata = log_data.get("metadata") or {}
    persona_name = safe_text(metadata.get("persona_name"))
    if not persona_name:
        raise ValueError("Log JSON is missing metadata.persona_name")

    messenger_text = render_messenger(log_data, persona_name)
    calendar_text = render_calendar(log_data)
    return (
        f"MESSENGER LOGS\n\n{messenger_text}\n"
        f"CALENDAR EVENTS\n\n{calendar_text}"
    )


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


def write_outputs(
    persona: PersonaFiles,
    output_dir: Path,
    indent: int,
) -> None:
    log_data = load_json(persona.log_path)
    test_case_data = load_json(persona.test_case_path)

    persona_dir = output_dir / persona.slug
    persona_dir.mkdir(parents=True, exist_ok=True)

    raw_logs_path = persona_dir / f"{persona.slug}_raw_app_logs.txt"
    questions_path = persona_dir / "test_questions.json"

    raw_logs_path.write_text(render_raw_app_logs(log_data), encoding="utf-8")
    questions_path.write_text(
        json.dumps(build_question_only_payload(test_case_data), indent=indent) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    personas = find_persona_files(repo_root, set(args.personas))
    for persona in personas:
        write_outputs(persona, output_dir, args.indent)
        print(f"Prepared {persona.slug} -> {output_dir / persona.slug}")


if __name__ == "__main__":
    main()
