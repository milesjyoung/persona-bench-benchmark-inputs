# Memory Experiment Harness

This folder contains an instrumented OpenClaw benchmark harness for studying:

- memory access behavior during benchmark runs
- `MEMORY.md` and daily `memory/YYYY-MM-DD.md` change tracking
- correlated memory updates by benchmark question / test case
- dream-related file changes during separate dreaming-enabled runs
- suspected memory flush calls

It is designed to wrap the existing Persona-Bench OpenClaw pipeline without replacing it.

## Files

- `openclaw_trace_wrapper.py`
  - Wrapper around `openclaw`
  - Captures every OpenClaw invocation used by the benchmark pipeline
  - Saves stdout/stderr, before/after manifests, changed-file diffs, and structured JSONL logs

- `run_memory_experiment.sh`
  - Top-level runner for one persona under one condition
  - Calls the existing `scripts/run_openclaw_persona_pipeline.sh`
  - Injects the trace wrapper via `--openclaw-bin`
  - Supports optional dreaming enable/disable hooks

- `summarize_memory_run.py`
  - Produces `summary.json` from the raw trace logs
  - Computes run-level and per-question memory / dream metrics

- `runs/`
  - Output directory for instrumented runs

## What gets tracked

For every OpenClaw invocation during the run:

- command argv
- command type
  - `agent`
  - `memory_index`
  - `memory_search`
  - etc.
- timestamp
- duration
- return code
- `test_case_id` when the wrapper can extract it from the prompt
- stdout/stderr captures
- before/after manifests of tracked workspace/state files
- changed files and unified diffs

Tracked file classes include:

- `MEMORY.md`
- daily memory files under `workspace/memory/`
- markdown/json/toml/text files under the OpenClaw workspace
- markdown/json/toml/text files under the OpenClaw state dir
- any tracked path containing `memory`, `dream`, or `flush`

The wrapper also emits:

- `memory_calls.jsonl`
  - explicit `openclaw memory ...` CLI calls
- `flush_events.jsonl`
  - any invocation whose argv or output appears to mention `flush`

## What the summary computes

`summary.json` includes:

- total invocation count
- command counts by type
- explicit memory CLI call count
- suspected flush event count
- memory change event count
- dream change event count
- `MEMORY.md` change event count
- daily memory file change event count
- top changed files
- per-question trace:
  - invocation ids
  - command types
  - memory change event count
  - dream change event count
  - flush suspected count
  - changed files
  - memory search/index call counts

## Important limitation

This harness can track:

- explicit OpenClaw memory CLI calls
- workspace/state file mutations
- output text that appears to mention memory tools or flushing

It cannot guarantee perfect visibility into internal tool calls that OpenClaw does not surface in CLI output or files. So the “memory access statistics” are best thought of as:

- exact for explicit CLI-level memory commands
- high-confidence for file mutation tracking
- best-effort proxy for hidden internal retrieval behavior

## Baseline run

```bash
chmod +x ./memory_experiment/run_memory_experiment.sh

./memory_experiment/run_memory_experiment.sh \
  --persona alicia_gonzalez \
  --condition baseline
```

This will:

1. create a run directory under `memory_experiment/runs/`
2. stage the persona logs into OpenClaw memory through the normal pipeline
3. run the question-answer loop
4. run the eval loop
5. collect full trace logs and diffs
6. produce `summary.json`
7. create a `.tar.gz` archive of the entire run

## Dreaming-enabled run

Use the same harness but pass commands that enable and disable dreaming in your OpenClaw environment:

```bash
./memory_experiment/run_memory_experiment.sh \
  --persona alicia_gonzalez \
  --condition dreaming \
  --enable-dreaming-cmd '<your command to enable dreaming>' \
  --disable-dreaming-cmd '<your command to disable dreaming>'
```

The harness does not invent a dreaming command for you because that may vary with your OpenClaw setup. Instead, it gives you hook points and tracks the resulting file changes.

## Resume and partial runs

Resume a run:

```bash
./memory_experiment/run_memory_experiment.sh \
  --persona alicia_gonzalez \
  --condition baseline \
  --resume
```

Resume from a specific test case:

```bash
./memory_experiment/run_memory_experiment.sh \
  --persona alicia_gonzalez \
  --condition baseline \
  --resume \
  --start-from TC-49
```

Skip eval:

```bash
./memory_experiment/run_memory_experiment.sh \
  --persona alicia_gonzalez \
  --condition baseline \
  --skip-eval
```

Skip question generation and run eval only:

```bash
./memory_experiment/run_memory_experiment.sh \
  --persona alicia_gonzalez \
  --condition baseline \
  --skip-questions \
  --resume
```

## Output layout

For a run named `20260423_153000_alicia_gonzalez_baseline`, you will get:

```text
memory_experiment/runs/20260423_153000_alicia_gonzalez_baseline/
  run_metadata.json
  invocations.jsonl
  memory_calls.jsonl
  flush_events.jsonl
  summary.json
  hooks/
  stdout/
  stderr/
  manifests/
  diffs/
  versions/
```

And also:

```text
memory_experiment/runs/20260423_153000_alicia_gonzalez_baseline.tar.gz
```

## Recommended experiment matrix

At minimum:

- baseline, fresh workspace, dreaming off
- dreaming, fresh workspace, dreaming on

For each persona, compare:

- benchmark score
- explicit memory CLI usage
- memory file mutation rate
- dream file mutation rate
- `MEMORY.md` update frequency
- daily memory update frequency
- suspected flush events
- later-question dependence on earlier-run memory changes

## File transfer

The runner prints an `scp` command at the end if it can detect the VM IP.

You can also pull the full run archive manually:

```bash
scp user01@<VM_IP>:/home/user01/Desktop/persona-bench-benchmark-inputs/memory_experiment/runs/<run_name>.tar.gz ~/Downloads/
```
