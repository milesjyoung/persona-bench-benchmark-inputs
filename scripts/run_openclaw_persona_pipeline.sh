#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  run_openclaw_persona_pipeline.sh --persona PERSONA_SLUG [options]

Required:
  --persona PERSONA_SLUG          Persona slug, e.g. alicia_gonzalez

Options:
  --workspace-dir PATH           OpenClaw workspace dir
                                 Default: $HOME/.openclaw/workspace
  --memory-date YYYY-MM-DD       Daily memory filename to write
                                 Default: today's date
  --start-from TC-XX             Start question run from this test case
  --question-session-mode MODE   Question runner session mode: isolated|shared
                                 Default: isolated
  --resume                       Resume existing answers/eval files
  --skip-questions               Skip answer generation
  --skip-eval                    Skip evaluation
  --scp-target TARGET            Optional scp target, e.g. user@host:/path/
  --openclaw-bin PATH            OpenClaw executable
                                 Default: openclaw

This script assumes the repo has already been cloned and the generated files
for the persona already exist.
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PERSONA=""
WORKSPACE_DIR="${HOME}/.openclaw/workspace"
MEMORY_DATE="$(date +%F)"
START_FROM=""
QUESTION_SESSION_MODE="isolated"
RESUME=0
SKIP_QUESTIONS=0
SKIP_EVAL=0
SCP_TARGET=""
OPENCLAW_BIN="openclaw"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --persona)
      PERSONA="${2:-}"
      shift 2
      ;;
    --workspace-dir)
      WORKSPACE_DIR="${2:-}"
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
    --question-session-mode)
      QUESTION_SESSION_MODE="${2:-}"
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
    --scp-target)
      SCP_TARGET="${2:-}"
      shift 2
      ;;
    --openclaw-bin)
      OPENCLAW_BIN="${2:-}"
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

RESULTS_DIR="${REPO_ROOT}/generated/${PERSONA}"
RAW_LOGS_FILE="${RESULTS_DIR}/${PERSONA}_raw_app_logs.txt"
QUESTIONS_FILE="${RESULTS_DIR}/${PERSONA}_test_questions.json"
ANSWERS_FILE="${RESULTS_DIR}/${PERSONA}_answers.json"
CLEAN_ANSWERS_FILE="${RESULTS_DIR}/${PERSONA}_answers_clean.json"
TEST_CASES_FILE="${REPO_ROOT}/test_cases/${PERSONA}_test_cases.json"
EVAL_FILE="${RESULTS_DIR}/${PERSONA}_eval.json"
ARCHIVE_FILE="${RESULTS_DIR}/${PERSONA}_openclaw_results.tar.gz"

MEMORY_DIR="${WORKSPACE_DIR}/memory"
MEMORY_FILE="${MEMORY_DIR}/${MEMORY_DATE}.md"
AGENTS_FILE="${WORKSPACE_DIR}/AGENTS.md"
BACKUP_DIR="${RESULTS_DIR}/workspace_backups"
mkdir -p "${BACKUP_DIR}" "${MEMORY_DIR}"
ORIGINAL_AGENTS_FILE="${BACKUP_DIR}/AGENTS.original.${timestamp:-pending}.md"

for required in \
  "${RAW_LOGS_FILE}" \
  "${QUESTIONS_FILE}" \
  "${TEST_CASES_FILE}" \
  "${SCRIPT_DIR}/run_openclaw_questions.py" \
  "${SCRIPT_DIR}/clean_openclaw_answers.py" \
  "${SCRIPT_DIR}/run_openclaw_eval.py"
do
  if [[ ! -f "${required}" ]]; then
    echo "Missing required file: ${required}" >&2
    exit 1
  fi
done

timestamp="$(date +%Y%m%d_%H%M%S)"
ORIGINAL_AGENTS_FILE="${BACKUP_DIR}/AGENTS.original.${timestamp}.md"
if [[ -f "${AGENTS_FILE}" ]]; then
  cp "${AGENTS_FILE}" "${BACKUP_DIR}/AGENTS.${timestamp}.bak"
  cp "${AGENTS_FILE}" "${ORIGINAL_AGENTS_FILE}"
else
  : > "${ORIGINAL_AGENTS_FILE}"
fi
if [[ -f "${MEMORY_FILE}" ]]; then
  cp "${MEMORY_FILE}" "${BACKUP_DIR}/memory_${MEMORY_DATE}.${timestamp}.bak"
fi

write_inference_agents() {
  cat "${ORIGINAL_AGENTS_FILE}" > "${AGENTS_FILE}"
  cat >> "${AGENTS_FILE}" <<'EOF'

## Persona-Bench Inference Mode
When answering questions about the user's life, schedule, habits, relationships, or recent events, check memory for relevant messenger and calendar context first.

Treat the stored app-log memory as the primary source of truth for personal questions.
Use only information supported by retrieved memory.
Do not invent facts.
If memory is insufficient, say so briefly.

When the user includes a test case id, always return valid JSON only in exactly this shape:
{
  "test_case_id": "TC-01",
  "answer": "short natural-language answer",
  "confidence": "high|medium|low",
  "evidence": [
    {
      "source": "messenger|calendar|memory",
      "reference": "brief citation with date/time or event title"
    }
  ]
}
EOF
}

write_eval_agents() {
  cat "${ORIGINAL_AGENTS_FILE}" > "${AGENTS_FILE}"
  cat >> "${AGENTS_FILE}" <<'EOF'

## Persona-Bench Eval Mode
You are grading benchmark answers against a provided ground truth.

Score each answer using only these labels and values:
- CORRECT = 1.0
- PARTIAL = 0.5
- INCORRECT = 0.0

Use these rules:
- CORRECT: captures the key facts in the ground truth, even if minor details are missing.
- PARTIAL: gets the right theme/topic but misses significant specifics.
- INCORRECT: wrong, irrelevant, unsupported, or missing the main point.

Return valid JSON only in exactly this format:
{
  "score": "CORRECT|PARTIAL|INCORRECT",
  "score_value": 1.0,
  "explanation": "what was right, what was missed, and why"
}
EOF
}

echo "Staging ${PERSONA} raw logs into ${MEMORY_FILE}"
cp "${RAW_LOGS_FILE}" "${MEMORY_FILE}"

echo "Re-indexing OpenClaw memory"
"${OPENCLAW_BIN}" memory index --force

QUESTION_ARGS=(
  python3 "${SCRIPT_DIR}/run_openclaw_questions.py"
  --questions-file "${QUESTIONS_FILE}"
  --output-file "${ANSWERS_FILE}"
  --openclaw-bin "${OPENCLAW_BIN}"
  --session-mode "${QUESTION_SESSION_MODE}"
)
if [[ "${RESUME}" -eq 1 ]]; then
  QUESTION_ARGS+=(--resume)
fi
if [[ -n "${START_FROM}" ]]; then
  QUESTION_ARGS+=(--start-from "${START_FROM}")
fi

EVAL_ARGS=(
  python3 "${SCRIPT_DIR}/run_openclaw_eval.py"
  --answers-file "${CLEAN_ANSWERS_FILE}"
  --test-cases-file "${TEST_CASES_FILE}"
  --output-file "${EVAL_FILE}"
  --raw-logs-file "${RAW_LOGS_FILE}"
  --openclaw-bin "${OPENCLAW_BIN}"
)
if [[ "${RESUME}" -eq 1 ]]; then
  EVAL_ARGS+=(--resume)
fi

if [[ "${SKIP_QUESTIONS}" -eq 0 ]]; then
  echo "Writing inference AGENTS.md"
  write_inference_agents
  echo "Running answer generation"
  "${QUESTION_ARGS[@]}"
  echo "Cleaning answers"
  python3 "${SCRIPT_DIR}/clean_openclaw_answers.py" \
    --input-file "${ANSWERS_FILE}" \
    --output-file "${CLEAN_ANSWERS_FILE}"
fi

if [[ "${SKIP_EVAL}" -eq 0 ]]; then
  if [[ ! -f "${CLEAN_ANSWERS_FILE}" ]]; then
    echo "Missing cleaned answers file: ${CLEAN_ANSWERS_FILE}" >&2
    exit 1
  fi
  echo "Writing eval AGENTS.md"
  write_eval_agents
  echo "Running evaluation"
  "${EVAL_ARGS[@]}"
fi

echo "Packaging outputs"
ARCHIVE_ITEMS=()
for candidate in \
  "${RAW_LOGS_FILE}" \
  "${QUESTIONS_FILE}" \
  "${ANSWERS_FILE}" \
  "${CLEAN_ANSWERS_FILE}" \
  "${EVAL_FILE}"
do
  if [[ -f "${candidate}" ]]; then
    ARCHIVE_ITEMS+=("$(basename "${candidate}")")
  fi
done
tar -czf "${ARCHIVE_FILE}" -C "${RESULTS_DIR}" "${ARCHIVE_ITEMS[@]}"

VM_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
echo "Results ready:"
echo "  ${ANSWERS_FILE}"
echo "  ${CLEAN_ANSWERS_FILE}"
echo "  ${EVAL_FILE}"
echo "  ${ARCHIVE_FILE}"
echo
echo "Workspace backups:"
echo "  ${BACKUP_DIR}"
echo
if [[ -n "${VM_IP}" ]]; then
  echo "Pull from local machine with:"
  echo "  scp \"$(whoami)@${VM_IP}:${ARCHIVE_FILE}\" ~/Downloads/"
  echo
fi

if [[ -n "${SCP_TARGET}" ]]; then
  echo "Pushing archive to ${SCP_TARGET}"
  scp "${ARCHIVE_FILE}" "${SCP_TARGET}"
fi
