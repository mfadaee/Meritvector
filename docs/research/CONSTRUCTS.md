# Construct reference

> Generated from `config/measurement/ontology.yaml` and `config/job_families/pmo/family.yaml`.

**Conceptual model.** Observed results = individual contribution + team contribution + organisational environment + project conditions + opportunity + random variation + measurement error.

*A conceptual decomposition, not a claim that the components are separately identifiable or literally additive. Individual contribution is identifiable only partially, under assumptions, and with uncertainty.*

## Activity (`activity`) — established

Observable work events — meetings, tasks created or closed, messages, time allocation.

- **Observable indicators:** meetings attended, tasks created/closed, updates sent, hours recorded
- **Data sources:** calendar metadata, task tools, (synthetic) Graph activity summaries
- **Measurement assumptions:** Counts are complete for the systems connected.
- **Reliability:** High recording reliability; low construct relevance to merit.
- **Confounders:** role, organisational meeting culture, workload, team size, time zone
- **Known limitations:** Rewards visible busyness (Kerr 1975); easily gamed (Strathern 1997).
- **Intended use:** Organisational context and workload diagnostics.
- **Prohibited interpretations:** higher activity means higher performance; activity as a promotion signal
- **Can increase merit:** no

## Responsibility (`responsibility`) — reasonable hypothesis

What the person is actually accountable for — decision authority, budget, risk ownership, scope, autonomy — independent of job title.

- **Observable indicators:** decision authority level, budget accountability, accountable workstreams, teams coordinated, risk ownership, executive exposure, autonomy
- **Data sources:** PMO register assignment records, RACI, project charter
- **Measurement assumptions:** Assignment records reflect actual not nominal accountability.
- **Reliability:** Moderate; nominal ownership often differs from practice — requires manager verification.
- **Confounders:** job title, visibility, organisational politics
- **Known limitations:** Scale of responsibility is not performance; a small project can demand exceptional judgement.
- **Intended use:** Describe scope so outcomes and contributions are read in proportion.
- **Prohibited interpretations:** larger scope means better performance; responsibility as a ranking key
- **Can increase merit:** no
- **PMO dimensions:** Actual decision authority (recorded); Direct versus indirect influence (recorded); Accountable workstreams (recorded); Budget accountability (recorded); Risk ownership (recorded); Teams coordinated (recorded); Strategic versus tactical scope (recorded); Executive stakeholder exposure (recorded); Technical judgement requirements (recorded); Degree of autonomy (recorded)

## Complexity (`complexity`) — established

Difficulty and uncertainty of the work — technical novelty, dependencies, regulation, scale, resourcing, schedule and integration risk.

- **Observable indicators:** technical complexity, dependency count, resource constraint, scope volatility, regulatory environment, technical uncertainty, integration points
- **Data sources:** PMO complexity assessment at kick-off, change log, dependency register
- **Measurement assumptions:** Assessed at kick-off before outcomes are known; assessors are not anchored on the assigned person.
- **Reliability:** Moderate; rubric-based assessment by the PMO. Inter-assessor reliability not yet measured.
- **Confounders:** assignment of stronger people to harder work, optimistic or pessimistic assessors
- **Known limitations:** Only measured complexity can be adjusted for; unmeasured context remains.
- **Intended use:** Contextual adjustment of outcomes; fair comparison of operating conditions.
- **Prohibited interpretations:** complexity as performance credit by itself
- **Can increase merit:** no
- **PMO dimensions:** Budget and commercial scope (modelled); Technical complexity (modelled); Schedule criticality (recorded); Organisational visibility (recorded); Stakeholder complexity (recorded); Cross-functional dependencies (modelled); Resource availability (modelled); Scope volatility (modelled); Technical uncertainty (recorded); Operational and safety criticality (recorded); Geographic distribution (recorded); Vendor complexity (recorded); Regulatory constraints (modelled); Integration difficulty (recorded); Team size (modelled); Delivery maturity (modelled)

## Quality (`quality`) — reasonable hypothesis

Evidence of correctness, completeness and sustainability of work products.

- **Observable indicators:** deliverable review score, first-pass approval, defects after acceptance, handover acceptance
- **Data sources:** document approval workflow, quality board reviews
- **Measurement assumptions:** Reviews apply a consistent rubric.
- **Reliability:** Reviewer effects likely; scores missing non-randomly (synthetic data — internal projects).
- **Confounders:** reviewer leniency, project environment, missingness
- **Known limitations:** Review score is a judgement not ground truth.
- **Intended use:** Secondary outcome alongside schedule; quality evidence for competencies.
- **Prohibited interpretations:** single review as proof of capability
- **Can increase merit:** yes
- **PMO dimensions:** Quality of accepted deliverables (modelled); Sustainable operational handover (planned)

## Outcomes (`outcomes`) — established

What the work achieved — milestones, schedule and cost performance, benefits, risks avoided.

- **Observable indicators:** schedule variance, on-time milestones, budget variance, benefits case met, risk materialisation
- **Data sources:** PMO register, project closure reviews
- **Measurement assumptions:** Baselines were set before execution; re-baselining is recorded.
- **Reliability:** High recording reliability for dates; moderate for benefits.
- **Confounders:** all context variables, team, sponsor, luck, regression to the mean
- **Known limitations:** Results are not behaviour (Campbell 1993); outcomes are shared across teams.
- **Intended use:** Project and portfolio reporting; input to context-adjusted analysis.
- **Prohibited interpretations:** project outcome equals individual performance
- **Can increase merit:** no
- **PMO dimensions:** Delivery objectives achieved (recorded); Schedule performance (modelled); Cost performance (recorded); Risk mitigation effectiveness (recorded); Dependency resolution (recorded); Stakeholder outcomes (recorded); Organisational improvements (planned)

## Contribution (`contribution`) — product assumption

The individual's evidenced role in producing outcomes, relative to what conditions predict, without attributing team results to one person.

- **Observable indicators:** context-adjusted schedule estimate with interval, verified attributions on evidence chains, risk mitigation led
- **Data sources:** engineered features from assessment evidence; manager-verified attributions
- **Measurement assumptions:** Measured context captures the main confounders; attribution is verified by people who know the work.
- **Reliability:** Limited; estimates are shrunk and abstain when evidence is thin.
- **Confounders:** unmeasured context, team quality, non-random assignment
- **Known limitations:** Adjusted associations not causal effects; shared outcomes limit attribution (Scenario F).
- **Intended use:** Evidence for development conversations with human review.
- **Prohibited interpretations:** ranking; promotion or dismissal decisions; causal claims about individuals
- **Can increase merit:** yes

## Development (`development`) — reasonable hypothesis

Demonstrated improvement in capability or performance over time, accounting for changing conditions.

- **Observable indicators:** trend in context-adjusted signal, growth-model slope, competencies newly demonstrated, harder assignments handled
- **Data sources:** longitudinal engineered features
- **Measurement assumptions:** Enough periods with evidence; conditions measured per period.
- **Reliability:** Low per person at current evidence density (see MODEL_CARD — no flags after FDR).
- **Confounders:** regression to the mean, assignment changes, turnover
- **Known limitations:** Under-powered; changes in responsibility confound trends.
- **Intended use:** Development conversations; never a rating.
- **Prohibited interpretations:** lack of detected change means no growth
- **Can increase merit:** yes
- **PMO dimensions:** Evidence of learning and adaptation (recorded)

## Leadership (`leadership`) — reasonable hypothesis

Evidence of coordination, sound judgement, collaboration, influence and enabling others.

- **Observable indicators:** cross-unit dependencies resolved, risks escalated and resolved with others, stakeholder outcomes, attributions as enabler
- **Data sources:** dependency register, RAID log, stakeholder surveys, verified attributions
- **Measurement assumptions:** Leadership leaves traces in coordination records; much of it does not.
- **Reliability:** Low; perception-based and incomplete.
- **Confounders:** visibility, role, survey response bias
- **Known limitations:** Contextual performance is under-recorded (Borman & Motowidlo 1993).
- **Intended use:** Identify evidence and evidence gaps for development.
- **Prohibited interpretations:** absence of records means absence of leadership
- **Can increase merit:** yes

## Career capability evidence (`career_capability_evidence`) — product assumption

Observed capabilities relevant to a separately defined future role.

- **Observable indicators:** competencies demonstrated beyond current level, opportunities offered and taken
- **Data sources:** competency evidence mapping against target-role framework
- **Measurement assumptions:** Target role requirements are defined independently of current performance.
- **Reliability:** Depends on opportunity; gaps often reflect assignment, not capability.
- **Confounders:** opportunity, visibility, sponsorship
- **Known limitations:** Current performance does not imply readiness for a different role.
- **Intended use:** Inform development planning; requires qualified human review.
- **Prohibited interpretations:** promotion readiness score; automatic promotion or rejection
- **Can increase merit:** no

