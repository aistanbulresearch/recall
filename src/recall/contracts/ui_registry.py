from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class UiFieldContract:
    source_artifact: str
    source_path: str
    missing_behavior: str


GOLDEN_PATH_UI_FIELDS = MappingProxyType(
    {
        "UI-GLOBAL-RUN-ID": UiFieldContract("ScanRun", "$.run_id", "UNKNOWN"),
        "UI-GLOBAL-RUN-STATE": UiFieldContract("ScanRun", "$.state", "UNKNOWN"),
        "UI-GLOBAL-MODE": UiFieldContract(
            "DataModeReceipt", "$.mode_set", "UNKNOWN MODE"
        ),
        "UI-AGENT-ROSTER": UiFieldContract(
            "RegistryResolutionReceipt", "$.bindings[*]", "INCOMPLETE"
        ),
        "UI-POLICY-OUTCOME": UiFieldContract(
            "PolicyDecision", "$.outcome", "INCOMPLETE"
        ),
        "UI-POLICY-REASONS": UiFieldContract(
            "PolicyDecision", "$.reason_codes[*]", "UNKNOWN"
        ),
        "UI-POLICY-MISSING": UiFieldContract(
            "PolicyDecision", "$.missing_prerequisites[*]", "UNKNOWN"
        ),
        "UI-TASK-COUNT-RUN": UiFieldContract(
            "ReviewTask[]", "$[?run_id].artifact_id", "UNKNOWN"
        ),
        "UI-TASK-DATA-MODE": UiFieldContract(
            "DataModeReceipt", "$.mode_set", "INCOMPLETE"
        ),
        "UI-TOOL-DENIAL": UiFieldContract(
            "ToolAuthorizationReceipt", "$.decision", "HIDDEN"
        ),
        "UI-CITATION-STATUS": UiFieldContract(
            "CitationAuditReceipt", "$.audit_status", "INCOMPLETE"
        ),
        "UI-FAILURE-CODE": UiFieldContract(
            "FailureReceipt", "$.failure_code", "NONE_ONLY_IF_NO_RECEIPT"
        ),
    }
)
