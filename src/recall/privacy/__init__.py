"""Laboratory-local privacy boundary for Recall.

Deterministic detection, deterministic adjudication of local model proposals,
deterministic redaction, and a deterministic outbound gate decide whether a
minimized pseudonymous payload may leave the laboratory. The local model can
only propose spans; it never approves, redacts, or releases anything.

The registered egress profile decides which field paths may exist in that
payload at all. Under the default `STRUCTURED_ONLY` profile no free-text field
is declared, so the boundary does not depend on any detector, deterministic or
model-backed, having found every identifier.

Ownership: lane L3. Related tasks: RCL-401, RCL-402, RCL-403.
"""

from recall.privacy.egress import (
    EGRESS_PROFILES,
    EGRESS_STRUCTURED_ONLY,
    EGRESS_SUMMARY_TEXT,
    EgressProfile,
    UnregisteredEgressProfile,
    resolve_profile,
)
from recall.privacy.spans import (
    DIRECT_IDENTIFIER_CLASSES,
    IDENTIFIER_CLASSES,
    QUASI_IDENTIFIER_CLASSES,
    DetectedSpan,
)

__all__ = [
    "DIRECT_IDENTIFIER_CLASSES",
    "EGRESS_PROFILES",
    "EGRESS_STRUCTURED_ONLY",
    "EGRESS_SUMMARY_TEXT",
    "EgressProfile",
    "UnregisteredEgressProfile",
    "resolve_profile",
    "IDENTIFIER_CLASSES",
    "QUASI_IDENTIFIER_CLASSES",
    "DetectedSpan",
]
