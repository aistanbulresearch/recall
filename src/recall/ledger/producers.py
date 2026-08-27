from __future__ import annotations

from collections.abc import Collection, Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class ProducerRule:
    authority_label: str
    identities: frozenset[str]


class ProducerRegistry(Mapping[str, Collection[str]]):
    def __init__(self, rules: Mapping[str, ProducerRule]) -> None:
        self._rules = MappingProxyType(dict(rules))

    def __getitem__(self, schema_name: str) -> Collection[str]:
        return self._rules[schema_name].identities

    def __iter__(self) -> Iterator[str]:
        return iter(self._rules)

    def __len__(self) -> int:
        return len(self._rules)

    def authority_label(self, schema_name: str) -> str:
        return self._rules[schema_name].authority_label


PRODUCER_REGISTRY = ProducerRegistry(
    {
        "PrivacyReceipt": ProducerRule("Local Privacy Gate", frozenset({"privacy-gate"})),
        "WatchCase": ProducerRule("Controller through Ledger", frozenset({"controller"})),
        "ScanRun": ProducerRule("Controller through Ledger", frozenset({"controller"})),
        "ScanRunEvent": ProducerRule("Controller through Ledger", frozenset({"controller"})),
        "RoutingPlan": ProducerRule("Fleet Coordinator", frozenset({"fleet-coordinator"})),
        "RegistryResolutionReceipt": ProducerRule("Controller", frozenset({"controller"})),
        "ToolAuthorizationReceipt": ProducerRule(
            "Gateway or Controller authorizer",
            frozenset({"gateway-authorizer", "controller-authorizer"}),
        ),
        "EvidenceObservation": ProducerRule("Evidence connector", frozenset({"evidence-connector"})),
        "EvidenceSnapshot": ProducerRule("Evidence Watcher", frozenset({"evidence-watcher"})),
        "CandidateDeltaReceipt": ProducerRule(
            "Deterministic Evidence Normalizer", frozenset({"evidence-normalizer"})
        ),
        "EvidenceDelta": ProducerRule("Evidence Assessor", frozenset({"evidence-assessor"})),
        "AssessmentReceipt": ProducerRule("Evidence Assessor", frozenset({"evidence-assessor"})),
        "CitationAuditReceipt": ProducerRule("Citation Auditor", frozenset({"citation-auditor"})),
        "AgentExecutionReceipt": ProducerRule(
            "Controller agent executor", frozenset({"controller-agent-executor"})
        ),
        "MemoryAdmissionReceipt": ProducerRule("MemoryAdmissionGate", frozenset({"memory-admission-gate"})),
        "MemoryRetrievalReceipt": ProducerRule("Memory retrieval gate", frozenset({"memory-retrieval-gate"})),
        "DataModeReceipt": ProducerRule("Deterministic mode gate", frozenset({"controller-mode-gate"})),
        "PolicyDecision": ProducerRule("Deterministic Policy Gate", frozenset({"policy-gate"})),
        "ReviewTask": ProducerRule("Controller transactional outbox", frozenset({"controller"})),
        "HumanDecisionReceipt": ProducerRule("Authenticated reviewer workflow", frozenset({"reviewer-workflow"})),
        "FailureReceipt": ProducerRule(
            "Deterministic component detecting failure",
            frozenset(
                {
                    "controller-failure-recorder",
                    "ledger-failure-recorder",
                    "policy-failure-recorder",
                    "connector-failure-recorder",
                }
            ),
        ),
        "DeploymentReceipt": ProducerRule("Release controller", frozenset({"release-controller"})),
        "ManagedPathReceipt": ProducerRule("Deterministic health aggregator", frozenset({"health-aggregator"})),
        "CohortDayManifest": ProducerRule("Cohort scheduler", frozenset({"cohort-scheduler"})),
        "CohortDayFailureReceipt": ProducerRule(
            "Cohort scheduler", frozenset({"cohort-scheduler"})
        ),
        "CohortExecutionCheckpoint": ProducerRule(
            "Cohort scheduler", frozenset({"cohort-scheduler"})
        ),
        "BatchExecutionReceipt": ProducerRule(
            "Cohort scheduler", frozenset({"cohort-scheduler"})
        ),
        "CohortHistoryReceipt": ProducerRule(
            "Cohort history loader", frozenset({"cohort-history-loader"})
        ),
        "CompressedCycleFailureReceipt": ProducerRule(
            "Cohort scheduler", frozenset({"cohort-scheduler"})
        ),
        "CohortHeadroomReceipt": ProducerRule(
            "Cohort scheduler", frozenset({"cohort-scheduler"})
        ),
        "CohortRampGateReceipt": ProducerRule(
            "Cohort scheduler", frozenset({"cohort-scheduler"})
        ),
        "HistoricalReplayEvaluation": ProducerRule("Evaluation harness", frozenset({"evaluation-harness"})),
        "UtilityEvaluation": ProducerRule("Evaluation harness", frozenset({"evaluation-harness"})),
        "PrivacyEvaluation": ProducerRule("Evaluation harness", frozenset({"evaluation-harness"})),
    }
)
