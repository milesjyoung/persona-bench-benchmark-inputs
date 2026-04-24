#!/usr/bin/env python3
"""Summarize a memory experiment run directory."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-file", type=Path, help="Optional explicit output path.")
    parser.add_argument("--indent", type=int, default=2)
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def pct(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else round((numerator / denominator) * 100.0, 2)


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    invocations = load_jsonl(run_dir / "invocations.jsonl")
    memory_calls = load_jsonl(run_dir / "memory_calls.jsonl")
    flush_events = load_jsonl(run_dir / "flush_events.jsonl")

    command_counts = Counter(item.get("command_type", "unknown") for item in invocations)
    changed_files_counter = Counter()
    per_question: dict[str, dict[str, Any]] = {}
    memory_change_events = 0
    dream_change_events = 0
    memory_md_change_events = 0
    daily_memory_change_events = 0

    for item in invocations:
        test_case_id = item.get("test_case_id")
        changed_files = item.get("changed_files") or []

        if any(change.get("is_memory_file") for change in changed_files):
            memory_change_events += 1
        if any(change.get("is_dream_file") for change in changed_files):
            dream_change_events += 1

        for change in changed_files:
            path = change.get("path")
            if path:
                changed_files_counter[path] += 1
            if path and path.lower().endswith("memory.md"):
                memory_md_change_events += 1
            if path and "/memory/" in path.lower():
                daily_memory_change_events += 1

        if not test_case_id:
            continue

        question_entry = per_question.setdefault(
            test_case_id,
            {
                "test_case_id": test_case_id,
                "invocation_ids": [],
                "command_types": [],
                "memory_change_events": 0,
                "dream_change_events": 0,
                "flush_suspected_count": 0,
                "changed_files": [],
                "memory_search_calls": 0,
                "memory_index_calls": 0,
            },
        )
        question_entry["invocation_ids"].append(item.get("invocation_id"))
        question_entry["command_types"].append(item.get("command_type"))
        question_entry["flush_suspected_count"] += 1 if item.get("flush_suspected") else 0
        question_entry["memory_change_events"] += 1 if any(change.get("is_memory_file") for change in changed_files) else 0
        question_entry["dream_change_events"] += 1 if any(change.get("is_dream_file") for change in changed_files) else 0
        question_entry["changed_files"].extend(change.get("path") for change in changed_files if change.get("path"))

    for item in memory_calls:
        test_case_id = next(
            (inv.get("test_case_id") for inv in invocations if inv.get("invocation_id") == item.get("invocation_id")),
            None,
        )
        if not test_case_id:
            continue
        question_entry = per_question.setdefault(
            test_case_id,
            {
                "test_case_id": test_case_id,
                "invocation_ids": [],
                "command_types": [],
                "memory_change_events": 0,
                "dream_change_events": 0,
                "flush_suspected_count": 0,
                "changed_files": [],
                "memory_search_calls": 0,
                "memory_index_calls": 0,
            },
        )
        if item.get("command_type") == "memory_search":
            question_entry["memory_search_calls"] += 1
        if item.get("command_type") == "memory_index":
            question_entry["memory_index_calls"] += 1

    summary = {
        "run_dir": str(run_dir),
        "total_invocations": len(invocations),
        "command_counts": dict(command_counts),
        "memory_call_count": len(memory_calls),
        "flush_event_count": len(flush_events),
        "memory_change_events": memory_change_events,
        "dream_change_events": dream_change_events,
        "memory_md_change_events": memory_md_change_events,
        "daily_memory_change_events": daily_memory_change_events,
        "unique_test_cases_observed": len(per_question),
        "memory_change_event_rate": pct(memory_change_events, len(invocations)),
        "dream_change_event_rate": pct(dream_change_events, len(invocations)),
        "top_changed_files": changed_files_counter.most_common(25),
        "question_trace": sorted(per_question.values(), key=lambda item: item["test_case_id"]),
    }

    output_file = args.output_file.resolve() if args.output_file else run_dir / "summary.json"
    output_file.write_text(json.dumps(summary, indent=args.indent) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
