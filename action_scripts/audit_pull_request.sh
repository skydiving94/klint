#!/usr/bin/env bash
# Audits a pull request's diff with klint and klint-structure, combines their
# findings into one report, and writes the job summary. The exit code goes
# to the step's outputs; the Action's last step passes or fails on it.
set -euo pipefail

# Paths in the diff are from the repository's top.
cd "$(git rev-parse --show-toplevel)"
min_confidence=$MIN_CONFIDENCE
if [ -z "$min_confidence" ]; then
  min_confidence=$(klint-pull-request threshold)
fi
rule_options=()
if [ -n "$RULES" ]; then
  rule_options+=(--rules "$RULES")
fi
folder=$(mktemp -d "$RUNNER_TEMP/klint-pull-request.XXXXXX")
findings_json="$folder/findings.json"
esc=$(printf '\033')

# Runs one audit of the diff, writing its --json report and its log, and
# prints its exit code.
audit_diff() {
  local command=$1 name=$2
  set +e
  "$command" --diff-from "$DIFF_FILE" --min-confidence "$min_confidence" \
    ${rule_options[@]+"${rule_options[@]}"} --json > "$folder/$name.json" 2> "$folder/$name.log"
  local exit_code=$?
  set -e
  sed "s/${esc}\[[0-9;]*[A-Za-z]//g" "$folder/$name.log" >&2
  echo "$exit_code"
}

file_exit=$(audit_diff klint file)
structure_exit=$(audit_diff klint-structure structure)
if [ "$file_exit" -le 1 ] && [ "$structure_exit" -le 1 ]; then
  set +e
  klint-pull-request report \
    --file-report "$folder/file.json" --structure-report "$folder/structure.json" \
    --min-confidence "$min_confidence" --output "$findings_json" > "$folder/summary.md"
  exit_code=$?
  set -e
else
  exit_code=2
fi
{
  echo "exit_code=$exit_code"
  echo "auditor=klint"
  echo "audited=the pull request's diff"
  if [ -f "$findings_json" ]; then
    echo "findings_json=$findings_json"
  fi
} >> "$GITHUB_OUTPUT"

if [ "$exit_code" -le 1 ]; then
  cat "$folder/summary.md" | tee -a "$GITHUB_STEP_SUMMARY"
  echo >> "$GITHUB_STEP_SUMMARY"
  exit 0
fi
{
  echo "### klint: the audit of the pull request's diff could not run"
  echo
  for name in file structure; do
    echo "\`$name\` audit:"
    echo
    echo '````text'
    sed "s/${esc}\[[0-9;]*[A-Za-z]//g" "$folder/$name.log" | tail -n 40
    echo '````'
    echo
  done
} >> "$GITHUB_STEP_SUMMARY"
