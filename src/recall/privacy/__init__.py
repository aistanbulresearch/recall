"""Laboratory-local privacy boundary for Recall.

Deterministic detection, deterministic adjudication of local model proposals,
deterministic redaction, and a deterministic outbound gate decide whether a
minimized pseudonymous payload may leave the laboratory. The local model can
only propose spans; it never approves, redacts, or releases anything.

Ownership: lane L3. Related tasks: RCL-401, RCL-402, RCL-403.
"""

from recall.privacy.spans import (
    DIRECT_IDENTIFIER_CLASSES,
    IDENTIFIER_CLASSES,
    QUASI_IDENTIFIER_CLASSES,
    DetectedSpan,
)

__all__ = [
    "DIRECT_IDENTIFIER_CLASSES",
    "IDENTIFIER_CLASSES",
    "QUASI_IDENTIFIER_CLASSES",
    "DetectedSpan",
]
