#!/usr/bin/env bash
# Audits the Action's target with the command its mode names, and writes the
# report to the job summary. The exit code goes to the step's outputs; the
# Action's last step passes or fails on it.
set -euo pipefail

min_confidence=${MIN_CONFIDENCE:-0.60}
args=("$TARGET" --min-confidence "$min_confidence")
if [ -n "$RULES" ]; then
  args+=(--rules "$RULES")
fi
report=$(mktemp "$RUNNER_TEMP/klint-report.XXXXXX")
set +e
"$COMMAND" "${args[@]}" 2>&1 | tee "$report"
exit_code=${PIPESTATUS[0]}
set -e
{
  echo "exit_code=$exit_code"
  echo "auditor=$COMMAND"
  echo "audited=$TARGET"
} >> "$GITHUB_OUTPUT"

case "$exit_code" in
  0) outcome="No problems found" ;;
  1) outcome="Problems found" ;;
  *) outcome="The audit could not run" ;;
esac
# A step's summary holds at most 1 MiB; the log keeps the whole report.
summary_limit=900000
esc=$(printf '\033')
{
  echo "### klint: \`$COMMAND $TARGET\`"
  echo
  echo "$outcome (exit $exit_code), at a minimum confidence of $min_confidence."
  echo
  echo '````text'
  sed "s/${esc}\[[0-9;]*[A-Za-z]//g" "$report" | head -c "$summary_limit"
  echo
  echo '````'
  if [ "$(wc -c < "$report")" -gt "$summary_limit" ]; then
    echo
    echo "The report is cut short here; the step's log has all of it."
  fi
  echo
} >> "$GITHUB_STEP_SUMMARY"
