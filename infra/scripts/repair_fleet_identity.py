"""One-time repair: give each engine the agent it claims to be.

On 2026-08-25 the fleet deployed COMPLETE and every engine ran the same agent.
The Vertex SDK stages the pickled agent to a fixed path, so three concurrent
creates raced and each engine loaded whichever pickle won. Display names,
service accounts, resource ids and catalog rows were all correct, which is why
nothing in the deploy report looked wrong.

This updates each existing engine in place with its correct agent and its own
staging directory. Update rather than delete-and-recreate, for two reasons: the
engines are persistent resources whose deletion sits outside this lane's
standing authority, and updating preserves the resource names, service accounts
and catalog registrations that are already correct.

The permanent fix is in fleet_spec (member_staging_dir), so future deploys
cannot race. This script exists to repair engines created before that fix.

Usage:
    python infra/scripts/repair_fleet_identity.py --apply
    python infra/scripts/repair_fleet_identity.py            # interrogate only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from recall.platform.config import PlatformConfig  # noqa: E402
from recall.platform.fleet import (  # noqa: E402
    FLEET_MEMBERS,
    GatewayBinding,
    expected_agent_author,
    fleet_spec,
    member_staging_dir,
    observed_authors,
)
from recall.platform.redaction import redact_identifiers  # noqa: E402
from recall.platform.runtime import TracedRuntimeInvoker  # noqa: E402


def _engine_index(project: str, location: str) -> dict[str, str]:
    """display_name -> resource_name, read back from the API."""

    import vertexai
    from vertexai import agent_engines

    vertexai.init(project=project, location=location)
    index = {}
    for engine in agent_engines.list():
        name = getattr(engine, "display_name", None) or ""
        resource = getattr(engine, "resource_name", None) or getattr(engine, "name", "")
        if name and resource:
            index[name] = resource
    return index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="perform the update")
    parser.add_argument("--redact", action="store_true")
    args = parser.parse_args()

    config = PlatformConfig.from_env()
    gateway = GatewayBinding.from_env()
    index = _engine_index(config.project_id, config.agent_engine_location)
    invoker = TracedRuntimeInvoker(config)

    from vertexai import agent_engines

    from recall.agents import build_agent_bundle

    rows: list[dict[str, Any]] = []
    for member in FLEET_MEMBERS:
        resource = index.get(member.display_name)
        row: dict[str, Any] = {
            "display_name": member.display_name,
            "expected_author": expected_agent_author(member),
            "resource_name": resource,
            "staging_dir": member_staging_dir(member),
        }
        if not resource:
            row["status"] = "MISSING"
            rows.append(row)
            continue

        if args.apply:
            spec = fleet_spec(config, member, gateway=gateway)
            bundle = build_agent_bundle(member.role)
            app = agent_engines.AdkApp(
                agent=bundle.agent,
                app_name=f"recall_{member.role.value.lower()}",
            )
            agent_engines.update(
                resource_name=resource,
                agent_engine=app,
                requirements=list(spec.requirements),
                extra_packages=list(spec.extra_packages),
                env_vars=dict(spec.env_vars),
                service_account=spec.service_account,
                gcs_dir_name=spec.gcs_dir_name,
            )
            row["updated"] = True

        # Interrogate regardless: the point of the exercise is testimony from
        # the running thing, not confirmation that a call returned.
        try:
            invocation = invoker.invoke(
                resource, message="identify yourself", user_id="recall-repair"
            )
            authors = observed_authors(invocation)
            row["observed_authors"] = list(authors)
            row["matches"] = bool(authors) and set(authors) == {row["expected_author"]}
        except Exception as exc:  # noqa: BLE001 - the failure is the finding
            row["observed_authors"] = []
            row["matches"] = False
            row["error"] = f"{type(exc).__name__}:{exc}"[:200]
        rows.append(row)

    observed = [r["observed_authors"][0] for r in rows if r.get("observed_authors")]
    result = {
        "mode": "apply" if args.apply else "interrogate-only",
        "members": rows,
        "all_match": all(r.get("matches") for r in rows),
        "distinct": len(observed) == len(rows) == len(set(observed)),
    }
    rendered = json.dumps(result, indent=2, default=str)
    print(redact_identifiers(rendered, config.project_id) if args.redact else rendered)
    return 0 if result["all_match"] and result["distinct"] else 1


if __name__ == "__main__":
    sys.exit(main())
