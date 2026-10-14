# Product requirements — MeritVector (PMO edition, v0.2)

Status: **draft for discovery**. Nothing here is validated with customers. Every statement about buyers or value is
a hypothesis to test, listed with how it would be tested in [MVP_SCOPE](MVP_SCOPE.md) and
[COMMERCIAL_STRATEGY](COMMERCIAL_STRATEGY.md).

## 1. Problem

Delivery organisations judge projects and the people who run them on raw signals: on-time rates, tasks closed,
activity, and stakeholder perception. Those signals mix contribution with circumstance. MeritVector's evidence so far:

- **Synthetic organisation** ([FLAGSHIP_REPORT](../research/FLAGSHIP_REPORT.md)):
  - project conditions predict 46% of the spread in raw schedule variance
  - only 54% of the raw "top fifth" are truly above average
  - activity counts point the wrong way
- **Real public project data** ([PUBLIC_DATA_VALIDATION](../research/PUBLIC_DATA_VALIDATION.md)):
  - measured context explains roughly 4–30 times more of the variation in productivity than team or capability indicators
  - raw team comparisons overstate effects: −47% cost per function point raw versus −9% [−38%, +32%] adjusted
  - models do not transfer between organisations

Whether organisations experience this as a problem they would pay to solve is **unknown**. See the discovery
questions in [CUSTOMER_PERSONAS](CUSTOMER_PERSONAS.md).

## 2. Value proposition (hypothesis)

> Understand the factors influencing delivery performance, reveal organisational bottlenecks, and support fairer,
> evidence-based development conversations.

The paid product focuses on five things:

1. PMO intelligence
2. Delivery and complexity analytics
3. Coordinator productivity benefits
4. Organisational capability insights
5. Explainable, evidence-based reviews

## 3. Users and jobs to be done

| User | Job | Primary surfaces |
|---|---|---|
| PMO director / head of delivery | See which conditions drive slippage across the portfolio. Find bottlenecks. Get early warning of milestone risk. | Overview, Project Portfolio, Risk Intelligence, 30-day risk classifier |
| Project / programme manager (employee) | Get the coordination work done. See every record held about them and correct it. Describe their own contribution. | Workspace, AI Coordinator, Contribution Evidence, contribution accounts |
| Line manager | Prepare fair development conversations with context and uncertainty, not raw rankings. | Employee detail, "How was this assessed?", review notes |
| HR reviewer / people analytics | Audit ratings for bias. Govern assessment use. Review contribution accounts and challenges. | Model Validation, fairness audit, Flagship Study, governance |
| Researcher / analyst | Test measurement claims reproducibly before they reach users. | Research Laboratory, public-data studies |
| Administrator | Configure the tenant, retention, connectors and governance. They have no access to individual evidence. | Administration & Privacy |

## 4. Functional requirements

| ID | Requirement | Status in v0.2 |
|---|---|---|
| F1 | Ingest project registers and work records through connectors, with provenance and validation status | Mock connectors; schema and validation exist |
| F2 | Context-adjusted delivery estimates with intervals and explicit abstention | Done (within-person model; 95% intervals; "insufficient evidence") |
| F3 | No rankings, leaderboards, promotion-readiness or dismissal outputs anywhere | Enforced by design and tests |
| F4 | Plain-English narratives with a "How was this assessed?" panel for every metric | Done for delivery metrics |
| F5 | Evidence chains (risk → mitigation → milestone) with inferred-link rules and person-recorded links | Done |
| F6 | Self-reported contribution accounts with manager/HR confirm or dispute; never model input | Done |
| F7 | Employee access to every record held about them, with challenge and correction | Done |
| F8 | Governance gate: assessment off until an administrator *and* an HR reviewer approve | Done |
| F9 | Aggregated fairness audit: ratings, opportunity, missing evidence, model error by group | Done |
| F10 | 30-day milestone-risk early warning at project level | Done (research workstream and registry entry) |
| F11 | Coordinator: meeting extraction, tasks, reports, retrieval over the user's own records; outbound messages off by default | Done (deterministic; no LLM in this build) |
| F12 | Reproducible research runs with dataset/code versions and result hashes | Done |
| F13 | SSO, production connectors, data residency | **Not built** (Phase E) |

## 5. Non-functional requirements

- **Privacy:**
  - no covert monitoring
  - no content of e-mail or chat is read for assessment
  - activity metadata is diagnostic only and is never credit
  - assistance data never becomes assessment evidence
- **Security:**
  - every query is tenant-scoped
  - sensitive reads and all writes are audited
  - role-based access is enforced server-side
- **Explainability:** business users never need model parameters; technical detail is optional.
- **Reproducibility:** fixed seeds, versioned definitions (YAML plus JSON Schema), result hashes.

## 6. Out of scope (this edition)

- automated employment decisions of any kind
- pay recommendations
- covert monitoring
- composite "merit scores"
- generated (LLM) explanations presented as fact
- job families beyond PMO/TPM except the illustrative engineering example

## 7. Success measures

Pilot success criteria are defined in [MVP_SCOPE](MVP_SCOPE.md#pilot-success-criteria). None have been measured yet.

## 8. Risks

| Risk | Mitigation |
|---|---|
| Misuse for ranking or dismissal | No ranking outputs. Prohibited uses are stated in every model card. Governance gate. Human review required. |
| Context poorly or inconsistently recorded | Recording-practice diagnostics (public data shows this happens). Shared rubric. Abstention. |
| Models do not transfer between organisations | Calibrate per tenant. Never pool tenants. Report out-of-time and cross-unit validation. |
| Legal and works-council requirements vary by jurisdiction | Governance documentation. Configurable notice and retention. Legal review before any real deployment. |
| Demand is assumed, not shown | Discovery interviews and paid pilots before further build. See [COMMERCIAL_STRATEGY](COMMERCIAL_STRATEGY.md). |
