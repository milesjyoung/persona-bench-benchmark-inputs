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


def detect_memory_mentions(stdout_text: str, stderr_text: str) -> dict[str, int]:
    combined = (stdout_text + "\n" + stderr_text).lower()
    return {
        "memory_search_mentions": combined.count("memory_search"),
        "memory_get_mentions": combined.count("memory_get"),
        "memory_index_mentions": combined.count("memory index"),
    }


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

    mentions = detect_memory_mentions(stdout_text, stderr_text)
    flush_suspected = False

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
        "returncode": process.returncode,
        "changed_file_count": len(changed_files),
        "changed_memory_file_count": sum(1 for item in changed_files if item["is_memory_file"]),
        "changed_dream_file_count": sum(1 for item in changed_files if item["is_dream_file"]),
        "flush_suspected": flush_suspected,
        "memory_mentions": mentions,
        "changed_files": changed_files,
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

    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
