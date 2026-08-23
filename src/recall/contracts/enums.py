from __future__ import annotations

from enum import StrEnum


class DataMode(StrEnum):
    SYNTHETIC = "SYNTHETIC"
    CAPTURED_REPLAY = "CAPTURED_REPLAY"
    LIVE_PUBLIC = "LIVE_PUBLIC"
    MOCK = "MOCK"


class ArtifactStatus(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"
    INCOMPLETE = "INCOMPLETE"
    REJECTED = "REJECTED"
    DEGRADED = "DEGRADED"


class AgentRole(StrEnum):
    FLEET_COORDINATOR = "FLEET_COORDINATOR"
    EVIDENCE_WATCHER = "EVIDENCE_WATCHER"
    EVIDENCE_ASSESSOR = "EVIDENCE_ASSESSOR"
    CITATION_AUDITOR = "CITATION_AUDITOR"


class ToolDecision(StrEnum):
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"


class FactState(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_EVALUATED = "NOT_EVALUATED"


class AuditStatus(StrEnum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


class CitationVerdict(StrEnum):
    VERIFIED = "VERIFIED"
    MISMATCH = "MISMATCH"
    UNAVAILABLE = "UNAVAILABLE"


class ReplayStage(StrEnum):
    STAGE_0 = "stage-0"
    STAGE_1 = "stage-1"
    STAGE_2 = "stage-2"


class ResolutionMode(StrEnum):
    REGISTRY = "REGISTRY"
    MANUAL_SERVICE = "MANUAL_SERVICE"
    PINNED_FALLBACK = "PINNED_FALLBACK"


class PrivacyDecision(StrEnum):
    ACCEPTED = "ACCEPTED"
    QUARANTINED = "QUARANTINED"


class PresenceState(StrEnum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    UNKNOWN = "UNKNOWN"


class PolicyOutcome(StrEnum):
    NO_ACTION = "NO_ACTION"
    ABSTAIN = "ABSTAIN"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class TerminalState(StrEnum):
    NO_ACTION = "NO_ACTION"
    ABSTAIN = "ABSTAIN"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    HALTED = "HALTED"


class FailureTerminal(StrEnum):
    POLICY_BOUND = "POLICY_BOUND"
    RETRY = "RETRY"
    HALTED = "HALTED"


class ScanRunState(StrEnum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    ROUTING = "ROUTING"
    WATCHING = "WATCHING"
    ASSESSING = "ASSESSING"
    AUDITING = "AUDITING"
    POLICY_EVALUATION = "POLICY_EVALUATION"
    NO_ACTION = "NO_ACTION"
    ABSTAIN = "ABSTAIN"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    HALTED = "HALTED"


class ScanRunEventCode(StrEnum):
    RUN_CREATED = "run_created"
    OUTBOX_PUBLISHED = "outbox_published"
    LEASE_ACQUIRED = "lease_acquired"
    LEASE_TAKEN_OVER = "lease_taken_over"
    ROUTE_VALIDATED = "route_validated"
    CANDIDATE_ABSENT = "candidate_absent"
    CANDIDATE_PRESENT = "candidate_present"
    CANDIDATE_UNKNOWN = "candidate_unknown"
    ASSESSMENT_COMPLETED = "assessment_completed"
    AUDIT_COMPLETED = "audit_completed"
    PREREQUISITE_FAILED = "prerequisite_failed"
    RETRY_SCHEDULED = "retry_scheduled"
    STATE_HASH_OBSERVED = "state_hash_observed"
    POLICY_NO_ACTION = "policy_no_action"
    POLICY_ABSTAIN = "policy_abstain"
    POLICY_REVIEW_REQUIRED = "policy_review_required"
    TECHNICAL_HALTED = "technical_halted"
    LOOP_DETECTED = "loop_detected"


class ReviewTaskState(StrEnum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    DISMISSED = "DISMISSED"
    ESCALATED = "ESCALATED"
    CLOSED = "CLOSED"


class WatchCaseState(StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    AWAITING_HUMAN = "AWAITING_HUMAN"
    ATTENTION_REQUIRED = "ATTENTION_REQUIRED"
    CLOSED = "CLOSED"


class DataComposition(StrEnum):
    SYNTHETIC_ONLY = "SYNTHETIC_ONLY"
    CAPTURED_REPLAY_ONLY = "CAPTURED_REPLAY_ONLY"
    LIVE_PUBLIC_ONLY = "LIVE_PUBLIC_ONLY"
    MOCK_ONLY = "MOCK_ONLY"
    SYNTHETIC_WITH_CAPTURED_REPLAY = "SYNTHETIC_WITH_CAPTURED_REPLAY"
