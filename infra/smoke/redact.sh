# Mask project identifiers in raw command output before it enters any report.
# Both forms must be masked: the project id in `projects/<id>/...` paths, and the
# project number in Agent Registry URNs such as `urn:agent:projects-<number>:...`.
# Usage:  source infra/smoke/env.sh; source infra/smoke/redact.sh
#         <command> 2>&1 | redact
redact() {
  sed -E "s#projects/[^/\"',[:space:]]+#projects/<project>#g" \
    | sed -E "s#projects-[0-9]+#projects-<project>#g" \
    | sed -E "s#(^|[^0-9])[0-9]{10,14}([^0-9]|$)#\1<project-number>\2#g" \
    | sed "s#${RECALL_GCP_PROJECT}#<project>#g"
}
