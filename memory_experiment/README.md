# Memory Experiment Harness

This folder contains an instrumented OpenClaw benchmark harness for studying:

- memory access behavior during benchmark runs
- `MEMORY.md` and daily `memory/YYYY-MM-DD.md` change tracking
- correlated memory updates by benchmark question / test case
- dream-related file changes during separate dreaming-enabled runs
- suspected memory flush calls

It is designed to wrap the existing Persona-Bench OpenClaw pipeline without replacing it.

## Recommended VM setup

1. Clone the repo on the Ubuntu VM:
```bash
git clone https://github.com/milesjyoung/persona-bench-benchmark-inputs.git
cd persona-bench-benchmark-inputs
chmod +x ./scripts/run_openclaw_persona_pipeline.sh
chmod +x ./memory_experiment/run_memory_experiment.sh
```

2. Install and configure OpenClaw:
   - Follow [OpenClaw install](https://docs.openclaw.ai/install)
   - Complete the quickstart and provider/API key setup
   - You need a model provider and embeddings configured
   - Skip the extra onboarding beyond basic setup
   - If the TUI asks for a wake-up prompt, use the following configure whatever else with what makes sense to you (minimal):
```text
I am {persona_name}, you are OC the helpful and down to business personal agent.
```

3. Prepare the VM and host so long runs do not stop:
   - On the Mac host, keep the machine awake:
```bash
caffeinate -dimsu
```
   - On the Ubuntu VM, disable suspend, screen blanking, and lock:
```bash
gsettings set org.gnome.desktop.session idle-delay 0
gsettings set org.gnome.desktop.screensaver lock-enabled false
gsettings set org.gnome.desktop.screensaver idle-activation-enabled false
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing'
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-battery-type 'nothing'
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
```
   - Run the benchmark inside `tmux` on the VM:
```bash
sudo apt install -y tmux
tmux new -s bench
```


4. Install SSH and `tmux` early so you can reconnect to the VM and keep long runs alive:

```bash
sudo apt update
sudo apt install -y openssh-server tmux
sudo systemctl enable --now ssh
hostname -I
```

Recommended `tmux` flow:

Start a session:

```bash
tmux new -s memorybench
```

Detach and leave the run going:

```text
Ctrl+b d
```

List sessions later:

```bash
tmux ls
```

Reattach:

```bash
tmux attach -t memorybench
```

## Files

- `openclaw_trace_wrapper.py`
  - Wrapper around `openclaw`
  - Captures every OpenClaw invocation used by the benchmark pipeline
  - Saves before/after manifests, changed-file diffs, and structured JSONL logs

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
- before/after manifests of tracked workspace/state files
- changed files and unified diffs

Tracked file classes include:

- `MEMORY.md`
- daily memory files under `workspace/memory/`
- memory database files under the OpenClaw state dir
- dream-related files under `.dreams/` or paths containing `dream`

The wrapper also emits:

- `memory_calls.jsonl`
  - explicit `openclaw memory ...` CLI calls
- `compaction_events.jsonl`
  - invocations where auto-compaction was directly observed from session metadata or transcript entries
- `flush_events.jsonl`
  - currently expected to remain empty unless explicit flush detection is added later

## What the summary computes

`summary.json` includes:

- total invocation count
- command counts by type
- explicit memory CLI call count
- auto-compaction trigger count
- test cases during which auto-compaction was observed
- overall token totals from OpenClaw usage metadata
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

It cannot guarantee perfect visibility into internal tool calls that OpenClaw does not surface in CLI output or files. So the “memory access statistics” are best thought of as:

- exact for explicit CLI-level memory commands
- high-confidence for file mutation tracking
- best-effort proxy for hidden internal retrieval behavior

## Baseline run

```bash
tmux new -s memorybench

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

Use the same harness but pass in dreaming flag. Make sure to configure dreaming first:

```bash
./memory_experiment/run_memory_experiment.sh \
  --persona alicia_gonzalez \
  --condition dreaming
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
  compaction_events.jsonl
  flush_events.jsonl
  summary.json
  hooks/
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
