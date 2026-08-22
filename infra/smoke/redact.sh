# Mask the project identifier in raw command output before it enters any report.
# Usage:  source infra/smoke/env.sh; source infra/smoke/redact.sh
#         <command> 2>&1 | redact
redact() {
  sed -E "s#projects/[^/\"',[:space:]]+#projects/<project>#g" \
    | sed "s#${RECALL_GCP_PROJECT}#<project>#g"
}
