#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  run_memory_experiment.sh --persona PERSONA_SLUG [options]

Required:
  --persona PERSONA_SLUG          Persona slug, e.g. alicia_gonzalez

Options:
  --condition NAME               Condition label. Default: baseline
  --workspace-dir PATH           OpenClaw workspace dir
                                 Default: $HOME/.openclaw/workspace
  --state-dir PATH               OpenClaw state dir
                                 Default: $HOME/.openclaw
  --openclaw-bin PATH            Real OpenClaw binary
                                 Default: openclaw
  --memory-date YYYY-MM-DD       Daily memory file name
                                 Default: today
  --start-from TC-XX             Resume question loop at a test case
  --resume                       Resume answers/eval files
  --skip-questions               Skip benchmark answer generation
  --skip-eval                    Skip eval loop
  --enable-dreaming-cmd CMD      Optional shell command to enable dreaming before run
  --disable-dreaming-cmd CMD     Optional shell command to disable dreaming after run
  --scp-target TARGET            Optional scp destination for final archive

This script wraps the normal OpenClaw persona pipeline with instrumentation.
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PERSONA=""
CONDITION="baseline"
WORKSPACE_DIR="${HOME}/.openclaw/workspace"
STATE_DIR="${HOME}/.openclaw"
OPENCLAW_BIN="openclaw"
MEMORY_DATE="$(date +%F)"
START_FROM=""
RESUME=0
SKIP_QUESTIONS=0
SKIP_EVAL=0
ENABLE_DREAMING_CMD=""
DISABLE_DREAMING_CMD=""
SCP_TARGET=""

json_string_or_null() {
  local value="$1"
  if [[ -z "${value}" ]]; then
    printf 'null'
  else
    python3 - <<PY
import json
print(json.dumps(${value@Q}))
PY
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --persona)
      PERSONA="${2:-}"
      shift 2
      ;;
    --condition)
      CONDITION="${2:-}"
      shift 2
      ;;
    --workspace-dir)
      WORKSPACE_DIR="${2:-}"
      shift 2
      ;;
    --state-dir)
      STATE_DIR="${2:-}"
      shift 2
      ;;
    --openclaw-bin)
      OPENCLAW_BIN="${2:-}"
      shift 2
      ;;
    --memory-date)
      MEMORY_DATE="${2:-}"
      shift 2
      ;;
    --start-from)
      START_FROM="${2:-}"
      shift 2
      ;;
    --resume)
      RESUME=1
      shift
      ;;
    --skip-questions)
      SKIP_QUESTIONS=1
      shift
      ;;
    --skip-eval)
      SKIP_EVAL=1
      shift
      ;;
    --enable-dreaming-cmd)
      ENABLE_DREAMING_CMD="${2:-}"
      shift 2
      ;;
    --disable-dreaming-cmd)
      DISABLE_DREAMING_CMD="${2:-}"
      shift 2
      ;;
    --scp-target)
      SCP_TARGET="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${PERSONA}" ]]; then
  echo "--persona is required" >&2
  usage
  exit 1
fi

RUN_TS="$(date +%Y%m%d_%H%M%S)"
RUN_DIR="${REPO_ROOT}/memory_experiment/runs/${RUN_TS}_${PERSONA}_${CONDITION}"
mkdir -p "${RUN_DIR}/hooks"

PIPELINE_SCRIPT="${REPO_ROOT}/scripts/run_openclaw_persona_pipeline.sh"
TRACE_WRAPPER="${REPO_ROOT}/memory_experiment/openclaw_trace_wrapper.py"
SUMMARY_SCRIPT="${REPO_ROOT}/memory_experiment/summarize_memory_run.py"

for required in "${PIPELINE_SCRIPT}" "${TRACE_WRAPPER}" "${SUMMARY_SCRIPT}"; do
  if [[ ! -f "${required}" ]]; then
    echo "Missing required file: ${required}" >&2
    exit 1
  fi
done

cat > "${RUN_DIR}/run_metadata.json" <<EOF
{
  "persona": "${PERSONA}",
  "condition": "${CONDITION}",
  "run_timestamp": "${RUN_TS}",
  "workspace_dir": "${WORKSPACE_DIR}",
  "state_dir": "${STATE_DIR}",
  "openclaw_bin": "${OPENCLAW_BIN}",
  "memory_date": "${MEMORY_DATE}",
  "resume": ${RESUME},
  "start_from": $(json_string_or_null "${START_FROM}"),
  "skip_questions": ${SKIP_QUESTIONS},
  "skip_eval": ${SKIP_EVAL},
  "enable_dreaming_cmd": $(json_string_or_null "${ENABLE_DREAMING_CMD}"),
  "disable_dreaming_cmd": $(json_string_or_null "${DISABLE_DREAMING_CMD}")
}
EOF

run_hook() {
  local label="$1"
  local command="$2"
  if [[ -z "${command}" ]]; then
    return 0
  fi
  local stdout_file="${RUN_DIR}/hooks/${label}.stdout.txt"
  local stderr_file="${RUN_DIR}/hooks/${label}.stderr.txt"
  echo "Running hook: ${label}"
  bash -lc "${command}" >"${stdout_file}" 2>"${stderr_file}"
}

PIPELINE_ARGS=(
  "${PIPELINE_SCRIPT}"
  --persona "${PERSONA}"
  --workspace-dir "${WORKSPACE_DIR}"
  --memory-date "${MEMORY_DATE}"
  --openclaw-bin "${TRACE_WRAPPER}"
)
if [[ "${RESUME}" -eq 1 ]]; then
  PIPELINE_ARGS+=(--resume)
fi
if [[ -n "${START_FROM}" ]]; then
  PIPELINE_ARGS+=(--start-from "${START_FROM}")
fi
if [[ "${SKIP_QUESTIONS}" -eq 1 ]]; then
  PIPELINE_ARGS+=(--skip-questions)
fi
if [[ "${SKIP_EVAL}" -eq 1 ]]; then
  PIPELINE_ARGS+=(--skip-eval)
fi

export PB_TRACE_RUN_DIR="${RUN_DIR}"
export PB_TRACE_WORKSPACE_DIR="${WORKSPACE_DIR}"
export PB_TRACE_STATE_DIR="${STATE_DIR}"
export PB_TRACE_CONDITION="${CONDITION}"
export PB_TRACE_PERSONA="${PERSONA}"
export PB_REAL_OPENCLAW_BIN="${OPENCLAW_BIN}"

run_hook "enable_dreaming" "${ENABLE_DREAMING_CMD}"

echo "Running instrumented OpenClaw benchmark pipeline"
"${PIPELINE_ARGS[@]}"

run_hook "disable_dreaming" "${DISABLE_DREAMING_CMD}"

echo "Summarizing instrumented run"
python3 "${SUMMARY_SCRIPT}" --run-dir "${RUN_DIR}"

RUN_ARCHIVE="${RUN_DIR}.tar.gz"
tar -czf "${RUN_ARCHIVE}" -C "$(dirname "${RUN_DIR}")" "$(basename "${RUN_DIR}")"

echo
echo "Memory experiment run complete:"
echo "  Run dir:     ${RUN_DIR}"
echo "  Summary:     ${RUN_DIR}/summary.json"
echo "  Archive:     ${RUN_ARCHIVE}"
echo

VM_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
if [[ -n "${VM_IP}" ]]; then
  echo "Pull from local machine with:"
  echo "  scp \"$(whoami)@${VM_IP}:${RUN_ARCHIVE}\" ~/Downloads/"
  echo
fi

if [[ -n "${SCP_TARGET}" ]]; then
  echo "Pushing archive to ${SCP_TARGET}"
  scp "${RUN_ARCHIVE}" "${SCP_TARGET}"
fi
