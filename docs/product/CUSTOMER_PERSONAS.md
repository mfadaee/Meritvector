# Customer personas (hypotheses)

These personas are **assumptions**, built from the problem analysis and the brief. They are not drawn from customer
interviews, because none have been conducted. Each persona lists what we believe, what would prove us wrong, and the
questions to ask in discovery.

---

## 1. PMO director / head of programme delivery — *economic buyer (hypothesis)*

- **Believed situation:**
  - runs a portfolio of 50–500 projects
  - reports delivery performance upward using RAG status and on-time rates
  - knows these numbers penalise teams on hard projects but has no defensible alternative
- **Believed goals:**
  - explain slippage with evidence
  - find bottlenecks (dependencies, staffing)
  - get early warning
  - argue for resources
- **What would disprove it:**
  - existing PPM tools already satisfy them
  - context data such as complexity assessments is not recorded at all
  - delivery analytics are not budgeted
- **Discovery questions:**
  1. How do you currently explain why a project slipped? Who disputes that explanation?
  2. What do you record about a project's difficulty at kick-off, and how consistently?
  3. Tell me about the last time raw delivery numbers led to a decision you later thought was unfair or wrong.
  4. What would you need to see to trust an "adjusted for difficulty" comparison?
  5. Who would pay for this, from which budget, and who could veto it?

## 2. HR analytics / people-analytics lead — *influencer and gatekeeper*

- **Believed situation:**
  - responsible for fair performance processes
  - suspects rating bias
  - is under regulatory pressure (EU AI Act high-risk classification for employment uses; local works councils)
- **Believed goals:** bias audits, defensible evidence for development conversations, governance controls.
- **What would disprove it:**
  - the organisation will not process delivery records for any people purpose
  - legal review blocks the use case outright
- **Discovery questions:**
  1. How do you audit ratings for bias today? What did you last find?
  2. What governance would you require before any analysis touched individuals?
  3. Would an aggregated-only deployment (projects and organisation, no person-level views) still be valuable?
  4. What would your works council or privacy officer ask first?

## 3. Organisational development / transformation leader — *possible buyer*

- **Believed goals:**
  - understand capability across delivery teams
  - target development investment
  - measure whether interventions such as coordination tooling help
- **Discovery questions:**
  1. How do you evaluate whether a delivery-improvement programme worked?
  2. Would you run a randomised or staggered rollout to measure an intervention?

## 4. Project / programme manager — *end user and affected person*

- **Believed situation:** heavy coordination load; judged on numbers that ignore their project's difficulty.
- **Believed goals:**
  - less admin (summaries, actions, reports)
  - being judged fairly
  - seeing and correcting their own records
- **What would disprove it:**
  - users regard any analytics as surveillance, whatever the safeguards
  - coordinator features do not save meaningful time
- **Discovery questions:**
  1. Which coordination tasks take the most of your week?
  2. If a system described your contribution, what would you need to see to consider it fair?
  3. Would you describe your own contributions (self-reported accounts) if your manager reviewed them?
  4. What would make you refuse to use this?

## 5. Privacy officer / works council — *veto holder*

- **Discovery questions:**
  1. Which data categories are acceptable for which purposes?
  2. What notice, consent or agreement would be required?
  3. What retention and access controls are mandatory?

---

### How we will validate personas

We will run 15–25 discovery conversations across the personas before building further commercial features, and
record anonymised notes and findings in a discovery log outside this repository.

A persona is retained only if at least three conversations confirm its core problem and someone with budget
authority recognises it.
