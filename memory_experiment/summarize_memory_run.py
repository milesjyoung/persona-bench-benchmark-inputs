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


def cumulative_from_resets(values: list[int | None]) -> int | None:
    seen_any = False
    cumulative = 0
    previous = None
    for value in values:
        if value is None:
            continue
        seen_any = True
        if previous is None:
            cumulative += value
        elif value >= previous:
            cumulative += value - previous
        else:
            cumulative += value
        previous = value
    return cumulative if seen_any else None


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    invocations = load_jsonl(run_dir / "invocations.jsonl")
    memory_calls = load_jsonl(run_dir / "memory_calls.jsonl")
    flush_events = load_jsonl(run_dir / "flush_events.jsonl")
    compaction_events = load_jsonl(run_dir / "compaction_events.jsonl")

    command_counts = Counter(item.get("command_type", "unknown") for item in invocations)
    changed_files_counter = Counter()
    per_question: dict[str, dict[str, Any]] = {}
    memory_change_events = 0
    dream_change_events = 0
    memory_md_change_events = 0
    daily_memory_change_events = 0
    total_usage_tokens = 0
    total_last_call_tokens = 0
    total_estimated_input_tokens_whitespace = 0
    total_estimated_output_tokens_whitespace = 0
    models = Counter()
    session_ids_observed: set[str] = set()
    session_store_keys_observed: set[str] = set()
    max_input_tokens = 0
    max_output_tokens = 0
    max_total_tokens = 0
    max_context_tokens = 0
    final_input_tokens = None
    final_output_tokens = None
    final_total_tokens = None
    final_context_tokens = None
    total_after_series: list[int | None] = []
    input_after_series: list[int | None] = []
    output_after_series: list[int | None] = []

    for item in invocations:
        test_case_id = item.get("test_case_id")
        changed_files = item.get("changed_files") or []
        session_observation = item.get("session_observation") or {}
        usage = item.get("usage") or {}
        last_call_usage = item.get("last_call_usage") or {}

        if any(change.get("is_memory_file") for change in changed_files):
            memory_change_events += 1
        if any(change.get("is_dream_file") for change in changed_files):
            dream_change_events += 1
        try:
            total_usage_tokens += int(usage.get("total", 0) or 0)
        except (TypeError, ValueError):
            pass
        try:
            total_last_call_tokens += int(last_call_usage.get("total", 0) or 0)
        except (TypeError, ValueError):
            pass
        if item.get("model_name"):
            models[item["model_name"]] += 1
        if item.get("session_id"):
            session_ids_observed.add(item["session_id"])
        session_observation = item.get("session_observation") or {}
        for key_name in ["session_store_key_before", "session_store_key_after"]:
            value = session_observation.get(key_name)
            if value:
                session_store_keys_observed.add(value)
        try:
            total_estimated_input_tokens_whitespace += int(item.get("estimated_input_tokens_whitespace", 0) or 0)
        except (TypeError, ValueError):
            pass
        try:
            total_estimated_output_tokens_whitespace += int(item.get("estimated_output_tokens_whitespace", 0) or 0)
        except (TypeError, ValueError):
            pass
        for value, assign in [
            (session_observation.get("input_tokens_after"), "input"),
            (session_observation.get("output_tokens_after"), "output"),
            (session_observation.get("total_tokens_after"), "total"),
            (session_observation.get("context_tokens_after"), "context"),
        ]:
            if value is None:
                continue
            try:
                num = int(value)
            except (TypeError, ValueError):
                continue
            if assign == "input":
                max_input_tokens = max(max_input_tokens, num)
                final_input_tokens = num
            elif assign == "output":
                max_output_tokens = max(max_output_tokens, num)
                final_output_tokens = num
            elif assign == "total":
                max_total_tokens = max(max_total_tokens, num)
                final_total_tokens = num
            elif assign == "context":
                max_context_tokens = max(max_context_tokens, num)
                final_context_tokens = num
        input_after_series.append(session_observation.get("input_tokens_after"))
        output_after_series.append(session_observation.get("output_tokens_after"))
        total_after_series.append(session_observation.get("total_tokens_after"))

        for change in changed_files:
            path = change.get("path")
            if path:
                changed_files_counter[path] += 1
            if path and path.lower().endswith("memory.md"):
                memory_md_change_events += 1
            if change.get("is_daily_memory_file"):
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
                "auto_compaction_observed_count": 0,
                "memory_flush_observed_count": 0,
                "changed_files": [],
                "memory_search_calls": 0,
                "memory_index_calls": 0,
                "compaction_counts_before_after": [],
                "session_token_observations": [],
            },
        )
        question_entry["invocation_ids"].append(item.get("invocation_id"))
        question_entry["command_types"].append(item.get("command_type"))
        question_entry["flush_suspected_count"] += 1 if item.get("flush_suspected") else 0
        question_entry["memory_change_events"] += 1 if any(change.get("is_memory_file") for change in changed_files) else 0
        question_entry["dream_change_events"] += 1 if any(change.get("is_dream_file") for change in changed_files) else 0
        question_entry["changed_files"].extend(change.get("path") for change in changed_files if change.get("path"))
        question_entry["auto_compaction_observed_count"] += 1 if session_observation.get("auto_compaction_observed") else 0
        question_entry["memory_flush_observed_count"] += 1 if session_observation.get("memory_flush_observed") else 0
        if session_observation.get("auto_compaction_observed"):
            question_entry["compaction_counts_before_after"].append(
                {
                    "before": session_observation.get("compaction_count_before"),
                    "after": session_observation.get("compaction_count_after"),
                    "transcript_before": session_observation.get("transcript_compaction_entries_before"),
                    "transcript_after": session_observation.get("transcript_compaction_entries_after"),
                    "checkpoint_token_count_before": session_observation.get("compaction_checkpoint_token_count_before"),
                    "checkpoint": session_observation.get("compaction_checkpoint"),
                }
            )
        question_entry["session_token_observations"].append(
            {
                "input_tokens_after": session_observation.get("input_tokens_after"),
                "output_tokens_after": session_observation.get("output_tokens_after"),
                "total_tokens_after": session_observation.get("total_tokens_after"),
                "context_tokens_after": session_observation.get("context_tokens_after"),
            }
        )

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
                "auto_compaction_observed_count": 0,
                "memory_flush_observed_count": 0,
                "changed_files": [],
                "memory_search_calls": 0,
                "memory_index_calls": 0,
                "compaction_counts_before_after": [],
            },
        )
        if item.get("command_type") == "memory_search":
            question_entry["memory_search_calls"] += 1
        if item.get("command_type") == "memory_index":
            question_entry["memory_index_calls"] += 1

    compaction_test_cases = [item.get("test_case_id") for item in compaction_events if item.get("test_case_id")]
    unique_compaction_test_cases = sorted(set(compaction_test_cases))
    compaction_events_by_question = Counter(compaction_test_cases)
    memory_flush_test_cases = sorted(
        set(
            item.get("test_case_id")
            for item in compaction_events
            if item.get("test_case_id") and item.get("memory_flush_observed")
        )
    )
    dominant_model = models.most_common(1)[0][0] if models else None
    compaction_checkpoint_token_values = [
        item.get("compaction_checkpoint_token_count_before")
        for item in compaction_events
        if item.get("compaction_checkpoint_token_count_before") is not None
    ]
    compaction_checkpoint_summaries = [
        {
            "test_case_id": item.get("test_case_id"),
            "token_count_before": item.get("compaction_checkpoint_token_count_before"),
            "summary": item.get("compaction_checkpoint_summary"),
        }
        for item in compaction_events
        if item.get("compaction_checkpoint_summary")
    ]
    cumulative_session_input_tokens = cumulative_from_resets(input_after_series)
    cumulative_session_output_tokens = cumulative_from_resets(output_after_series)
    cumulative_session_total_tokens = cumulative_from_resets(total_after_series)
    overall_benchmark_token_count = cumulative_session_total_tokens
    if overall_benchmark_token_count is None:
        if final_input_tokens is not None and final_output_tokens is not None:
            overall_benchmark_token_count = final_input_tokens + final_output_tokens
        elif max_total_tokens:
            overall_benchmark_token_count = max_total_tokens

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
        "overall_token_count_usage_total": total_usage_tokens,
        "overall_token_count_last_call_total": total_last_call_tokens,
        "overall_estimated_input_tokens_whitespace": total_estimated_input_tokens_whitespace,
        "overall_estimated_output_tokens_whitespace": total_estimated_output_tokens_whitespace,
        "overall_estimated_token_count_whitespace": (
            total_estimated_input_tokens_whitespace + total_estimated_output_tokens_whitespace
        ),
        "overall_benchmark_token_count": overall_benchmark_token_count,
        "cumulative_session_input_tokens": cumulative_session_input_tokens,
        "cumulative_session_output_tokens": cumulative_session_output_tokens,
        "cumulative_session_total_tokens": cumulative_session_total_tokens,
        "final_session_input_tokens": final_input_tokens,
        "final_session_output_tokens": final_output_tokens,
        "final_session_total_tokens": final_total_tokens,
        "final_session_context_tokens": final_context_tokens,
        "max_observed_input_tokens": max_input_tokens,
        "max_observed_output_tokens": max_output_tokens,
        "max_observed_total_tokens": max_total_tokens,
        "max_observed_context_tokens": max_context_tokens,
        "model_names_observed": dict(models),
        "dominant_model_name": dominant_model,
        "session_ids_observed": sorted(session_ids_observed),
        "session_store_keys_observed": sorted(session_store_keys_observed),
        "auto_compaction_trigger_count": len(compaction_events),
        "auto_compaction_test_cases": unique_compaction_test_cases,
        "auto_compaction_events_by_test_case": dict(compaction_events_by_question),
        "memory_flush_observed_test_cases": memory_flush_test_cases,
        "compaction_checkpoint_token_values": compaction_checkpoint_token_values,
        "compaction_checkpoint_summaries": compaction_checkpoint_summaries,
        "top_changed_files": changed_files_counter.most_common(25),
        "question_trace": sorted(per_question.values(), key=lambda item: item["test_case_id"]),
    }

    output_file = args.output_file.resolve() if args.output_file else run_dir / "summary.json"
    output_file.write_text(json.dumps(summary, indent=args.indent) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
