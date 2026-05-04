#!/usr/bin/env python3
"""Instrumented wrapper around the OpenClaw CLI for memory experiments.

This wrapper proxies every OpenClaw invocation, captures stdout/stderr, snapshots
tracked workspace/state files before and after each call, writes diffs for changed
files, and emits structured JSONL logs that can later be summarized.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any


MAX_DIFF_BYTES = 2 * 1024 * 1024
IGNORE_PARTS = {".git", "__pycache__", "node_modules", ".DS_Store"}
TEST_CASE_PATTERN = re.compile(r"test_case_id:\s*(TC-\d+)", re.IGNORECASE)
DAILY_MEMORY_PATTERN = re.compile(r"(^|[\\/])memory[\\/]\d{4}-\d{2}-\d{2}\.md$", re.IGNORECASE)


def getenv_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value).expanduser().resolve() if value else None


RUN_DIR = getenv_path("PB_TRACE_RUN_DIR")
REAL_OPENCLAW_BIN = os.environ.get("PB_REAL_OPENCLAW_BIN", "openclaw")
WORKSPACE_DIR = getenv_path("PB_TRACE_WORKSPACE_DIR")
STATE_DIR = getenv_path("PB_TRACE_STATE_DIR")
CONDITION = os.environ.get("PB_TRACE_CONDITION", "baseline")
PERSONA = os.environ.get("PB_TRACE_PERSONA", "")


def ensure_run_dir() -> None:
    if RUN_DIR is None:
        raise SystemExit("PB_TRACE_RUN_DIR is required for openclaw_trace_wrapper.py")
    for relative in [
        "manifests",
        "diffs",
        "versions",
    ]:
        (RUN_DIR / relative).mkdir(parents=True, exist_ok=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_name(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "__", path)


def tracked_roots() -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = []
    if WORKSPACE_DIR and WORKSPACE_DIR.exists():
        roots.append(("workspace", WORKSPACE_DIR))
    if STATE_DIR and STATE_DIR.exists():
        roots.append(("state", STATE_DIR))
    return roots


def should_track(path: Path) -> bool:
    if any(part in IGNORE_PARTS for part in path.parts):
        return False
    lower = str(path).lower()
    name = path.name.lower()
    if name == "memory.md":
        return True
    if "/memory/" in lower or "\\memory\\" in lower:
        return True
    if "dream" in lower or ".dreams" in lower:
        return True
    return False


def snapshot_files() -> dict[str, dict[str, Any]]:
    manifest: dict[str, dict[str, Any]] = {}
    for root_name, root_path in tracked_roots():
        for path in root_path.rglob("*"):
            if not path.is_file() or not should_track(path):
                continue
            try:
                stat = path.stat()
                data = path.read_bytes()
            except OSError:
                continue
            rel = f"{root_name}/{path.relative_to(root_path)}"
            manifest[rel] = {
                "root": root_name,
                "absolute_path": str(path),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "sha256": sha256_bytes(data),
            }
    return manifest


def read_text_for_diff(path: Path) -> str:
    try:
        if not path.exists():
            return ""
        if path.stat().st_size > MAX_DIFF_BYTES:
            return f"[omitted: file larger than {MAX_DIFF_BYTES} bytes]\n"
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def classify_path(rel_path: str) -> dict[str, bool]:
    lower = rel_path.lower()
    name = Path(rel_path).name.lower()
    return {
        "is_memory_file": "/memory/" in lower or name == "memory.md",
        "is_dream_file": "dream" in lower,
        "is_flush_related": "flush" in lower,
        "is_daily_memory_file": bool(DAILY_MEMORY_PATTERN.search(rel_path)),
        "is_long_term_memory_file": name == "memory.md",
    }


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")


def extract_test_case_id(argv: list[str]) -> str | None:
    for index, arg in enumerate(argv):
        if arg == "--message" and index + 1 < len(argv):
            match = TEST_CASE_PATTERN.search(argv[index + 1])
            if match:
                return match.group(1).upper()
    return None


def classify_command(argv: list[str]) -> tuple[str, str | None]:
    if not argv:
        return "unknown", None
    if argv[0] == "agent":
        return "agent", None
    if argv[0] == "memory":
        subcommand = argv[1] if len(argv) > 1 else None
        return f"memory_{subcommand or 'unknown'}", (argv[2] if len(argv) > 2 else None)
    return argv[0], None


def extract_session_id(argv: list[str]) -> str | None:
    for index, arg in enumerate(argv):
        if arg == "--session-id" and index + 1 < len(argv):
            return argv[index + 1]
    return None


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


def extract_assistant_text(raw_response: dict[str, Any] | None) -> str | None:
    if not isinstance(raw_response, dict):
        return None
    if isinstance(raw_response.get("assistant"), dict):
        content = raw_response["assistant"].get("content")
        if isinstance(content, str):
            return content
    if isinstance(raw_response.get("message"), dict):
        content = raw_response["message"].get("content")
        if isinstance(content, str):
            return content
    content = raw_response.get("content")
    if isinstance(content, str):
        return content
    payloads = raw_response.get("payloads")
    if isinstance(payloads, list) and payloads and isinstance(payloads[0], dict):
        text = payloads[0].get("text")
        if isinstance(text, str):
            return text
    return None


def session_store_path() -> Path | None:
    if STATE_DIR is None:
        return None
    path = STATE_DIR / "agents" / "main" / "sessions" / "sessions.json"
    return path if path.exists() else None


def session_transcript_path(session_id: str) -> Path | None:
    if STATE_DIR is None:
        return None
    path = STATE_DIR / "agents" / "main" / "sessions" / f"{session_id}.jsonl"
    return path if path.exists() else path


def find_session_record(node: Any, session_id: str, path: str = "") -> tuple[dict[str, Any] | None, str | None]:
    if isinstance(node, dict):
        node_session_id = node.get("sessionId") or node.get("id") or node.get("session_id")
        if node_session_id == session_id:
            return node, path or None
        for key, value in node.items():
            child_path = f"{path}.{key}" if path else str(key)
            found, found_path = find_session_record(value, session_id, child_path)
            if found is not None:
                return found, found_path
    elif isinstance(node, list):
        for index, item in enumerate(node):
            child_path = f"{path}[{index}]"
            found, found_path = find_session_record(item, session_id, child_path)
            if found is not None:
                return found, found_path
    return None, None


def count_transcript_compactions(path: Path | None) -> int:
    if path is None or not path.exists():
        return 0
    count = 0
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and obj.get("type") == "compaction":
                count += 1
    except OSError:
        return 0
    return count


def coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def first_present(mapping: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in mapping:
            return mapping.get(key)
    return None


def get_session_snapshot(session_id: str | None) -> dict[str, Any] | None:
    if not session_id:
        return None

    snapshot: dict[str, Any] = {
        "session_id": session_id,
        "session_store_key": None,
        "compaction_count": 0,
        "memory_flush_at": None,
        "memory_flush_compaction_count": 0,
        "transcript_compaction_entries": 0,
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "context_tokens": None,
        "compaction_checkpoint": None,
    }

    store = session_store_path()
    if store and store.exists():
        try:
            payload = json.loads(store.read_text(encoding="utf-8"))
            record, record_path = find_session_record(payload, session_id)
            if isinstance(record, dict):
                snapshot["session_store_key"] = record_path
                snapshot["compaction_count"] = coerce_int(record.get("compactionCount")) or 0
                snapshot["memory_flush_at"] = record.get("memoryFlushAt")
                snapshot["memory_flush_compaction_count"] = coerce_int(record.get("memoryFlushCompactionCount")) or 0
                snapshot["input_tokens"] = coerce_int(first_present(record, ["inputTokens", "inputTokenCount"]))
                snapshot["output_tokens"] = coerce_int(first_present(record, ["outputTokens", "outputTokenCount"]))
                snapshot["total_tokens"] = coerce_int(first_present(record, ["totalTokens", "totalTokenCount"]))
                snapshot["context_tokens"] = coerce_int(first_present(record, ["contextTokens", "contextTokenCount"]))
                checkpoint = record.get("compactionCheckpoint")
                if isinstance(checkpoint, dict):
                    snapshot["compaction_checkpoint"] = checkpoint
        except (OSError, json.JSONDecodeError):
            pass

    transcript = session_transcript_path(session_id)
    snapshot["transcript_compaction_entries"] = count_transcript_compactions(transcript)
    snapshot["transcript_path"] = str(transcript) if transcript is not None else None
    return snapshot


def compare_session_snapshots(before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, Any]:
    if before is None and after is None:
        return {
            "auto_compaction_observed": False,
            "memory_flush_observed": False,
        }

    before = before or {}
    after = after or {}
    before_compactions = before.get("compaction_count") or 0
    after_compactions = after.get("compaction_count") or 0
    before_transcript = before.get("transcript_compaction_entries") or 0
    after_transcript = after.get("transcript_compaction_entries") or 0
    before_flush_count = before.get("memory_flush_compaction_count") or 0
    after_flush_count = after.get("memory_flush_compaction_count") or 0
    before_flush_at = before.get("memory_flush_at")
    after_flush_at = after.get("memory_flush_at")
    checkpoint = after.get("compaction_checkpoint") or before.get("compaction_checkpoint") or {}
    checkpoint_token_count_before = None
    checkpoint_summary = None
    if isinstance(checkpoint, dict):
        checkpoint_token_count_before = coerce_int(
            first_present(
                checkpoint,
                [
                    "tokenCountBefore",
                    "tokensBefore",
                    "totalTokenCountBefore",
                    "totalTokensBefore",
                    "inputTokensBefore",
                ],
            )
        )
        checkpoint_summary = checkpoint.get("summary")

    return {
        "auto_compaction_observed": (after_compactions > before_compactions) or (after_transcript > before_transcript),
        "memory_flush_observed": (after_flush_count > before_flush_count) or (before_flush_at != after_flush_at and after_flush_at is not None),
        "compaction_count_before": before.get("compaction_count"),
        "compaction_count_after": after.get("compaction_count"),
        "memory_flush_at_before": before.get("memory_flush_at"),
        "memory_flush_at_after": after.get("memory_flush_at"),
        "memory_flush_compaction_count_before": before.get("memory_flush_compaction_count"),
        "memory_flush_compaction_count_after": after.get("memory_flush_compaction_count"),
        "transcript_compaction_entries_before": before.get("transcript_compaction_entries"),
        "transcript_compaction_entries_after": after.get("transcript_compaction_entries"),
        "transcript_path": after.get("transcript_path") or before.get("transcript_path"),
        "session_store_key_before": before.get("session_store_key"),
        "session_store_key_after": after.get("session_store_key"),
        "input_tokens_before": before.get("input_tokens"),
        "input_tokens_after": after.get("input_tokens"),
        "output_tokens_before": before.get("output_tokens"),
        "output_tokens_after": after.get("output_tokens"),
        "total_tokens_before": before.get("total_tokens"),
        "total_tokens_after": after.get("total_tokens"),
        "context_tokens_before": before.get("context_tokens"),
        "context_tokens_after": after.get("context_tokens"),
        "compaction_checkpoint_token_count_before": checkpoint_token_count_before,
        "compaction_checkpoint_summary": checkpoint_summary,
        "compaction_checkpoint": checkpoint if isinstance(checkpoint, dict) else None,
    }


def detect_memory_mentions(stdout_text: str, stderr_text: str) -> dict[str, int]:
    combined = (stdout_text + "\n" + stderr_text).lower()
    return {
        "memory_search_mentions": combined.count("memory_search"),
        "memory_get_mentions": combined.count("memory_get"),
        "memory_index_mentions": combined.count("memory index"),
    }


def extract_message_arg(argv: list[str]) -> str | None:
    for index, arg in enumerate(argv):
        if arg == "--message" and index + 1 < len(argv):
            return argv[index + 1]
    return None


def whitespace_token_estimate(text: str | None) -> int:
    if not text:
        return 0
    return len(text.split())


def write_diff(invocation_id: str, rel_path: str, before_path: Path | None, after_path: Path | None) -> str | None:
    before_text = read_text_for_diff(before_path) if before_path else ""
    after_text = read_text_for_diff(after_path) if after_path else ""
    diff = "".join(
        difflib.unified_diff(
            before_text.splitlines(keepends=True),
            after_text.splitlines(keepends=True),
            fromfile=f"before/{rel_path}",
            tofile=f"after/{rel_path}",
        )
    )
    diff_path = RUN_DIR / "diffs" / f"{invocation_id}__{safe_name(rel_path)}.patch"
    diff_path.write_text(diff, encoding="utf-8")
    return str(diff_path.relative_to(RUN_DIR))


def save_version_copy(invocation_id: str, stage: str, rel_path: str, source: Path) -> str | None:
    if not source.exists():
        return None
    target = RUN_DIR / "versions" / f"{invocation_id}__{stage}__{safe_name(rel_path)}"
    try:
        data = source.read_bytes()
    except OSError:
        return None
    target.write_bytes(data)
    return str(target.relative_to(RUN_DIR))


def compare_manifests(
    invocation_id: str,
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    changed: list[dict[str, Any]] = []
    for rel_path in sorted(set(before) | set(after)):
        before_entry = before.get(rel_path)
        after_entry = after.get(rel_path)
        if before_entry == after_entry:
            continue

        if before_entry is None:
            change_type = "added"
        elif after_entry is None:
            change_type = "removed"
        else:
            change_type = "modified"

        path_info = after_entry or before_entry
        abs_before = Path(before_entry["absolute_path"]) if before_entry else None
        abs_after = Path(after_entry["absolute_path"]) if after_entry else None
        metadata = classify_path(rel_path)
        diff_relpath = write_diff(invocation_id, rel_path, abs_before, abs_after)
        before_copy = save_version_copy(invocation_id, "before", rel_path, abs_before) if abs_before else None
        after_copy = save_version_copy(invocation_id, "after", rel_path, abs_after) if abs_after else None

        changed.append(
            {
                "path": rel_path,
                "absolute_path": path_info["absolute_path"],
                "change_type": change_type,
                "before_sha256": before_entry["sha256"] if before_entry else None,
                "after_sha256": after_entry["sha256"] if after_entry else None,
                "before_size": before_entry["size"] if before_entry else None,
                "after_size": after_entry["size"] if after_entry else None,
                "diff_file": diff_relpath,
                "before_copy": before_copy,
                "after_copy": after_copy,
                **metadata,
            }
        )
    return changed


def main() -> int:
    ensure_run_dir()
    argv = sys.argv[1:]
    invocation_id = f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    started_at = time.time()

    before_manifest = snapshot_files()
    write_json(RUN_DIR / "manifests" / f"{invocation_id}_before.json", before_manifest)

    command_type, memory_query = classify_command(argv)
    test_case_id = extract_test_case_id(argv)
    session_id = extract_session_id(argv)
    message_arg = extract_message_arg(argv)
    session_before = get_session_snapshot(session_id)
    process = subprocess.run(
        [REAL_OPENCLAW_BIN, *argv],
        capture_output=True,
        text=True,
    )

    stdout_text = process.stdout
    stderr_text = process.stderr
    sys.stdout.write(stdout_text)
    sys.stderr.write(stderr_text)
    sys.stdout.flush()
    sys.stderr.flush()

    after_manifest = snapshot_files()
    write_json(RUN_DIR / "manifests" / f"{invocation_id}_after.json", after_manifest)
    changed_files = compare_manifests(invocation_id, before_manifest, after_manifest)
    session_after = get_session_snapshot(session_id)
    session_observation = compare_session_snapshots(session_before, session_after)

    mentions = detect_memory_mentions(stdout_text, stderr_text)
    flush_suspected = False
    raw_response = extract_openclaw_json(stdout_text, stderr_text)
    agent_meta = raw_response.get("meta", {}).get("agentMeta", {}) if isinstance(raw_response, dict) else {}
    usage = agent_meta.get("usage", {}) if isinstance(agent_meta, dict) else {}
    last_call_usage = agent_meta.get("lastCallUsage", {}) if isinstance(agent_meta, dict) else {}
    assistant_text = extract_assistant_text(raw_response)

    event = {
        "invocation_id": invocation_id,
        "timestamp": started_at,
        "duration_seconds": round(time.time() - started_at, 3),
        "persona": PERSONA,
        "condition": CONDITION,
        "command_argv": argv,
        "command_type": command_type,
        "memory_query": memory_query,
        "test_case_id": test_case_id,
        "session_id": session_id,
        "returncode": process.returncode,
        "model_provider": agent_meta.get("provider"),
        "model_name": agent_meta.get("model"),
        "prompt_tokens": agent_meta.get("promptTokens"),
        "usage": usage,
        "last_call_usage": last_call_usage,
        "estimated_input_tokens_whitespace": whitespace_token_estimate(message_arg),
        "estimated_output_tokens_whitespace": whitespace_token_estimate(assistant_text),
        "changed_file_count": len(changed_files),
        "changed_memory_file_count": sum(1 for item in changed_files if item["is_memory_file"]),
        "changed_dream_file_count": sum(1 for item in changed_files if item["is_dream_file"]),
        "flush_suspected": flush_suspected,
        "memory_mentions": mentions,
        "changed_files": changed_files,
        "session_observation": session_observation,
    }
    append_jsonl(RUN_DIR / "invocations.jsonl", event)

    if command_type.startswith("memory_"):
        append_jsonl(
            RUN_DIR / "memory_calls.jsonl",
            {
                "invocation_id": invocation_id,
                "timestamp": started_at,
                "command_type": command_type,
                "memory_query": memory_query,
                "returncode": process.returncode,
            },
        )

    if flush_suspected:
        append_jsonl(
            RUN_DIR / "flush_events.jsonl",
            {
                "invocation_id": invocation_id,
                "timestamp": started_at,
                "command_type": command_type,
                "test_case_id": test_case_id,
                "returncode": process.returncode,
                "changed_files": changed_files,
            },
        )

    if session_observation.get("auto_compaction_observed"):
        append_jsonl(
            RUN_DIR / "compaction_events.jsonl",
            {
                "invocation_id": invocation_id,
                "timestamp": started_at,
                "test_case_id": test_case_id,
                "session_id": session_id,
                **session_observation,
                "prompt_tokens": agent_meta.get("promptTokens"),
                "last_call_usage": last_call_usage,
            },
        )

    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
