# Operating Principles

## Why these principles exist

Prior hackathon experience showed that technically deep work can lose when its value is difficult to see, when the demo is added at the end, or when a green result does not prove that the safety mechanism actually ran. Recall treats those failures as design inputs.

## Applied lessons

### 1. Optimize for this contest's axes

The working score budget is Innovation 40%, Architecture 30%, and Demo 30%. Architecture is a strength, but invisible architecture earns no points. Every architectural control must have a visible demo moment and a committed proof artifact.

### 2. State the contrast, not only the feature

Do not say only, "Recall is safe." Demonstrate:

1. the standard autonomous-agent failure;
2. the authority that would make the failure dangerous;
3. the Recall boundary that structurally prevents it;
4. the failure receipt, abstention, or denied tool call proving enforcement.

### 3. Explain the human friction without domain jargon

Lead with the human consequence: specialists cannot repeatedly reopen every historical uncertain result as evidence changes. Explain the scale and review burden before variant terminology.

### 4. Make depth visible

One clear visual transition is more valuable than several hidden subsystems. Prefer a reviewer seeing a fake citation rejected, a route denied, and a clinical task withheld over a verbal description of many guardrails.

### 5. Derive every displayed value

Every UI number, threshold, badge, status, chart, and comparison must be generated from the same typed run artifact used by policy and evaluation. No preset-to-label mapping and no hand-entered demo result are allowed.

### 6. Reject green-but-dead verification

A passing report is insufficient when the underlying mechanism did not receive valid input, silently returned null, or never executed. Each critical control requires:

- a positive control;
- a negative or fault-injection control;
- proof that the control was invoked;
- the resulting state transition;
- an assertion that a dangerous downstream action did not occur.

### 7. Separate submission outcome from product value

The objective is to win, but technical and scientific quality are not judged solely by placement. Preserve reusable evidence, architecture, and evaluation artifacts regardless of the result.

### 8. Learn from patterns without importing prior work

Recall is independently designed and implemented in its own repository. A separate codebase may be inspected to understand how it handled a failure mode or engineering problem, but Recall does not copy its code, tests, fixtures, schemas, prompts, configuration, UI, documentation, artifacts, or history. Pattern inspection informs questions and acceptance criteria; Recall's solution must be re-derived, implemented, and verified here.

## Working behavior

- Be concise, direct, honest, and technically independent.
- Ask before long or scope-changing work.
- Do not do work only to tick a platform or bonus box.
- Split complex work into meaningful, reviewable units.
- Maintain design, implementation/TDD, review, and merge gates.
- Update the demo surface during implementation, not after it.
