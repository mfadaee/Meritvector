# Literature review and evidence library

> Generated from `research/references/library.json` by `scripts/render_research_docs.py`. Edit the data, not this file.

42 sources, checked on 2026-10-13 against bibliographic records via web search (publisher pages, PubMed, RePEc, institutional repositories). Crossref could not be queried from the build environment, so each entry states what was confirmed. Findings are paraphrased; consult the source before relying on specific figures.

## Synthesis

1. **Performance is behaviour, results are not the same thing.** Campbell's theory separates performance (behaviour under the person's control) from its results; task, contextual and adaptive performance are distinct (Campbell 1993; Borman & Motowidlo 1993; Motowidlo & Van Scotter 1994; Pulakos 2000; Griffin 2007). → MeritVector separates OUTCOMES from CONTRIBUTION and never collapses dimensions into one score.
2. **Ratings are weak measures of performance.** Interrater reliability of supervisory ratings is about .52 and idiosyncratic rater effects can exceed ratee effects (Viswesvaran 1996; Scullen 2000; Murphy 2008; Rotundo & Sackett 2002). → Historical ratings are audited as biased labels, never learned from.
3. **Objective and subjective measures are not interchangeable** (Bommer 1995). → Evidence and human judgement are shown side by side.
4. **Measures that become targets degrade** (Kerr 1975; Campbell 1979; Strathern 1997). → No activity counts as merit; no single target metric.
5. **Monitoring can reduce the performance it observes** (Bernstein 2012; Ravid 2020). → No covert monitoring, assistance-first coordinator, purpose limitation.
6. **Context, confounding and selection dominate observational comparisons** (Simpson 1951; Greenland 1999; Barnett 2005; Rubin 1976). → Contextual adjustment, explicit DAGs, regression-to-the-mean caveats, missing-data diagnostics.
7. **Associations need sensitivity analysis and multiplicity control** (VanderWeele & Ding 2017; Cinelli & Hazlett 2020; Benjamini & Hochberg 1995). → E-values / robustness values and FDR are part of every analysis.
8. **Models need leakage control, stability checks and documentation** (Kaufman 2012; Hennig 2007; Mitchell 2019). → Point-in-time features, cluster stability, mandatory model specifications.
9. **Employment AI is high-risk and regulated** (NIST AI RMF 2023; ISO/IEC 42001; EU AI Act; NSW Workplace Surveillance Act; OAIC). → Notice, human review, logging, access and correction rights are product features.

## Established findings vs hypotheses vs product assumptions

| Status | Examples |
|---|---|
| Established (replicated, meta-analytic or foundational) | Ratings have low interrater reliability; task vs contextual performance are distinct; confounding and Simpson's paradox; regression to the mean |
| Reasonable hypothesis (supported by theory, untested in our setting) | PMO complexity rubrics capture the main sources of delivery difficulty; milestone schedule variance reflects contribution once context is adjusted |
| Unvalidated product assumption | Mixed-model employee intercepts are useful for development conversations; manager-verified attribution improves accuracy; the coordinator improves follow-through |

## A. Job performance theory

### Campbell, J. P., McCloy, R. A., Oppler, S. H., & Sager, C. E. (1993). *A theory of performance*
In N. Schmitt & W. C. Borman (Eds.), Personnel Selection in Organizations (pp. 35–70). Jossey-Bass. [https://en.wikipedia.org/wiki/Job_performance](https://en.wikipedia.org/wiki/Job_performance) — Citation confirmed (DOI not confirmed) · conceptual framework

- **Main finding:** Defines performance as behaviour relevant to organisational goals that is under the individual's control, distinct from its results; proposes a multidimensional taxonomy (eight components, some job-specific).
- **Limitations:** Theory chapter; the component structure is derived largely from military (Project A) data.
- **Relevance:** Foundational distinction between behaviour, results and determinants.
- **Design implication:** MeritVector separates OUTCOMES (results) from CONTRIBUTION (the individual's role) and treats results as contaminated by factors outside the person's control.

### Campbell, J. P., & Wiernik, B. M. (2015). *The modeling and assessment of work performance*
Annual Review of Organizational Psychology and Organizational Behavior, 2, 47–74. [doi:10.1146/annurev-orgpsych-032414-111427](https://doi.org/10.1146/annurev-orgpsych-032414-111427) — DOI confirmed · review

- **Main finding:** Reviews the substantive models of individual work performance and how performance is assessed, re-emphasising performance as behaviour and the difficulty of measuring it well.
- **Limitations:** Narrative review; not specific to project-based knowledge work.
- **Relevance:** Up-to-date synthesis for the construct definitions in the ontology.
- **Design implication:** Constructs are defined behaviourally with explicit indicators; outcome metrics are labelled as results, not performance.

### Borman, W. C., & Motowidlo, S. J. (1993). *Expanding the criterion domain to include elements of contextual performance*
In N. Schmitt & W. C. Borman (Eds.), Personnel Selection in Organizations (pp. 71–98). Jossey-Bass. [https://digitalcommons.usf.edu/psy_facpub/1111/](https://digitalcommons.usf.edu/psy_facpub/1111/) — Citation confirmed (DOI not confirmed) · conceptual framework

- **Main finding:** Distinguishes task performance (core technical work) from contextual performance (behaviours supporting the social and organisational environment).
- **Limitations:** Chapter-level argument; empirical support comes from later studies.
- **Relevance:** Project managers' value is heavily contextual (coordination, enabling others).
- **Design implication:** LEADERSHIP and collaboration are separate constructs from delivery outcomes; low evidence coverage for them is reported as a gap, not a deficit.

### Motowidlo, S. J., & Van Scotter, J. R. (1994). *Evidence that task performance should be distinguished from contextual performance*
Journal of Applied Psychology, 79(4), 475–480. [doi:10.1037/0021-9010.79.4.475](https://doi.org/10.1037/0021-9010.79.4.475) — DOI confirmed · empirical

- **Main finding:** Task and contextual performance each contributed independently to supervisors' overall performance judgements; experience related more to task, personality more to contextual performance.
- **Limitations:** US Air Force mechanics; supervisory ratings as the criterion.
- **Relevance:** Supports multidimensional rather than single-score assessment.
- **Design implication:** No single composite merit score; dimensions are reported separately.

### Podsakoff, P. M., MacKenzie, S. B., Paine, J. B., & Bachrach, D. G. (2000). *Organizational citizenship behaviors: A critical review of the theoretical and empirical literature and suggestions for future research*
Journal of Management, 26(3), 513–563. [doi:10.1177/014920630002600307](https://doi.org/10.1177/014920630002600307) — DOI confirmed · review

- **Main finding:** Reviews OCB dimensions, antecedents and consequences and notes conceptual overlap among related constructs.
- **Limitations:** Most evidence is cross-sectional and rating-based.
- **Relevance:** Citizenship-type contributions (helping, enabling other teams) rarely appear in system-of-record data.
- **Design implication:** Evidence gaps for citizenship behaviours are expected; MeritVector does not infer their absence from missing records.

### Pulakos, E. D., Arad, S., Donovan, M. A., & Plamondon, K. E. (2000). *Adaptability in the workplace: Development of a taxonomy of adaptive performance*
Journal of Applied Psychology, 85(4), 612–624. [doi:10.1037/0021-9010.85.4.612](https://doi.org/10.1037/0021-9010.85.4.612) — DOI confirmed · empirical

- **Main finding:** Proposes and supports an eight-dimension taxonomy of adaptive performance (e.g., dealing with uncertain or unpredictable work situations).
- **Limitations:** Taxonomy derived from critical incidents; criterion-related evidence limited.
- **Relevance:** Scope volatility and uncertain projects call for adaptive performance.
- **Design implication:** DEVELOPMENT and adaptation are measured as change under changing conditions (scope changes, complexity), not as raw output.

### Griffin, M. A., Neal, A., & Parker, S. K. (2007). *A new model of work role performance: Positive behavior in uncertain and interdependent contexts*
Academy of Management Journal, 50(2), 327–347. [doi:10.5465/amj.2007.24634438](https://doi.org/10.5465/amj.2007.24634438) — DOI confirmed · empirical

- **Main finding:** Cross-classifies proficiency, adaptivity and proactivity at individual, team and organisation levels; uncertainty and interdependence shape which behaviours matter.
- **Limitations:** Supervisor and self ratings; Australian samples.
- **Relevance:** Directly motivates context variables (uncertainty, interdependence) and the individual/team/organisation split.
- **Design implication:** Contribution is recorded at individual, team and organisation level; attribution to individuals is explicit and reviewable.

### Robinson, S. L., & Bennett, R. J. (1995). *A typology of deviant workplace behavior: A multidimensional scaling study*
Academy of Management Journal, 38(2), 555–572. [doi:10.5465/256693](https://doi.org/10.5465/256693) — DOI confirmed · empirical

- **Main finding:** Deviant workplace behaviours vary on minor–serious and interpersonal–organisational dimensions, giving four categories.
- **Limitations:** Typology of perceived behaviours; not a measurement instrument for operational data.
- **Relevance:** Counterproductive work behaviour is part of the performance domain.
- **Design implication:** Out of scope by design: MeritVector does not detect or score counterproductive behaviour from work data — that would require surveillance and invite false accusations.

### Rotundo, M., & Sackett, P. R. (2002). *The relative importance of task, citizenship, and counterproductive performance to global ratings of job performance: A policy-capturing approach*
Journal of Applied Psychology, 87(1), 66–80. [doi:10.1037/0021-9010.87.1.66](https://doi.org/10.1037/0021-9010.87.1.66) — DOI confirmed · empirical

- **Main finding:** Raters weight task, citizenship and counterproductive performance differently, forming distinct rating policies.
- **Limitations:** Hypothetical profiles; policy capturing may differ from real appraisal.
- **Relevance:** Global ratings embed rater-specific weighting policies.
- **Design implication:** Historical overall ratings are treated as biased labels, never as ground truth.

## B1. Performance ratings

### Viswesvaran, C., Ones, D. S., & Schmidt, F. L. (1996). *Comparative analysis of the reliability of job performance ratings*
Journal of Applied Psychology, 81(5), 557–574. [doi:10.1037/0021-9010.81.5.557](https://doi.org/10.1037/0021-9010.81.5.557) — DOI confirmed · meta analysis

- **Main finding:** Mean interrater reliability of supervisory ratings of overall job performance was about .52; interrater reliability was lower than intrarater reliability.
- **Limitations:** Appropriateness of interrater reliability as the correction coefficient has been debated.
- **Relevance:** A single manager's rating carries large rater-specific error.
- **Design implication:** Ratings are audited, not learned from; review notes are qualitative and multi-source.

### Scullen, S. E., Mount, M. K., & Goff, M. (2000). *Understanding the latent structure of job performance ratings*
Journal of Applied Psychology, 85(6), 956–970. [doi:10.1037/0021-9010.85.6.956](https://doi.org/10.1037/0021-9010.85.6.956) — DOI confirmed · empirical

- **Main finding:** Idiosyncratic rater effects accounted for more variance in multisource ratings (about 62% and 53% in two samples) than the ratee's actual performance.
- **Limitations:** Developmental multisource ratings of managers; may differ for administrative ratings.
- **Relevance:** Motivates Scenario C (rater leniency) and the label audit.
- **Design implication:** Synthetic ratings include rater leniency; MeritVector tests whether rating differences survive context adjustment.

### Murphy, K. R. (2008). *Explaining the weak relationship between job performance and ratings of job performance*
Industrial and Organizational Psychology, 1(2), 148–160. [https://www.cambridge.org/core/journals/industrial-and-organizational-psychology/article/explaining-the-weak-relationship-between-job-performance-and-ratings-of-job-performance/BE95B37E7E559C35C473760C64BC5D34](https://www.cambridge.org/core/journals/industrial-and-organizational-psychology/article/explaining-the-weak-relationship-between-job-performance-and-ratings-of-job-performance/BE95B37E7E559C35C473760C64BC5D34) — Citation confirmed (DOI not confirmed) · conceptual review

- **Main finding:** Ratings are widely viewed as poor measures of performance; systematic non-performance factors and intentional distortion help explain the weak link.
- **Limitations:** Focal argument paper with commentaries; not a single empirical estimate.
- **Relevance:** Justifies not treating manager ratings or promotions as ground truth.
- **Design implication:** Label audit compares ratings with context-adjusted evidence and activity volume.

### Bommer, W. H., Johnson, J. L., Rich, G. A., Podsakoff, P. M., & MacKenzie, S. B. (1995). *On the interchangeability of objective and subjective measures of employee performance: A meta-analysis*
Personnel Psychology, 48(3), 587–605. [doi:10.1111/j.1744-6570.1995.tb01772.x](https://doi.org/10.1111/j.1744-6570.1995.tb01772.x) — DOI confirmed · meta analysis

- **Main finding:** Objective and subjective performance measures are related but not interchangeable (a moderate correlation is reported in secondary summaries).
- **Limitations:** Effect size reported here from secondary sources, not re-checked against the original tables.
- **Relevance:** Objective records and judgements capture different things.
- **Design implication:** Business views show objective evidence and human judgements side by side, never merged into one number.

## B2. Measurement science

### Cronbach, L. J., & Meehl, P. E. (1955). *Construct validity in psychological tests*
Psychological Bulletin, 52(4), 281–302. [doi:10.1037/h0040957](https://doi.org/10.1037/h0040957) — DOI confirmed · conceptual framework

- **Main finding:** Introduces construct validity: a measure is validated by testing a network of theoretical relationships, not by a single criterion.
- **Limitations:** Classical framing; later work (Messick) broadened validity to include consequences.
- **Relevance:** MeritVector's constructs need nomological-network evidence.
- **Design implication:** VALIDITY_FRAMEWORK lists expected convergent/discriminant relations for each construct and tests them on synthetic data.

### Messick, S. (1995). *Validity of psychological assessment: Validation of inferences from persons' responses and performances as scientific inquiry into score meaning*
American Psychologist, 50(9), 741–749. [https://www.ets.org/research/policy_research_reports/publications/article/1995/buwh.html](https://www.ets.org/research/policy_research_reports/publications/article/1995/buwh.html) — Citation confirmed (DOI not confirmed) · conceptual framework

- **Main finding:** Validity is a unified evaluation of the evidence and consequences supporting inferences from scores, including construct-irrelevant variance and construct under-representation.
- **Limitations:** Framework, not a procedure; consequential validity remains debated.
- **Relevance:** Context effects are construct-irrelevant variance in raw delivery metrics.
- **Design implication:** Each metric documents intended and prohibited interpretations and its likely construct-irrelevant variance.

### Shrout, P. E., & Fleiss, J. L. (1979). *Intraclass correlations: Uses in assessing rater reliability*
Psychological Bulletin, 86(2), 420–428. [doi:10.1037/0033-2909.86.2.420](https://doi.org/10.1037/0033-2909.86.2.420) — DOI confirmed · methods

- **Main finding:** Defines six forms of the intraclass correlation and guidance for choosing among them.
- **Limitations:** Assumes the ANOVA model fits the design.
- **Relevance:** Reliability of person-level aggregates (how consistent is a person's evidence across projects?).
- **Design implication:** The research engine reports ICC(1)/ICC(k) for person-level aggregates to show how much evidence a stable estimate needs.

### Vandenberg, R. J., & Lance, C. E. (2000). *A review and synthesis of the measurement invariance literature: Suggestions, practices, and recommendations for organizational research*
Organizational Research Methods, 3(1), 4–70. [doi:10.1177/109442810031002](https://doi.org/10.1177/109442810031002) — DOI confirmed · methods review

- **Main finding:** Cross-group comparisons require tests of measurement invariance; proposes an integrative testing sequence.
- **Limitations:** Developed for latent-variable (SEM) measures; applies only partially to behavioural records.
- **Relevance:** Fairness audits compare groups; indicators must mean the same thing across groups.
- **Design implication:** Fairness audit includes an indicator-structure comparison across groups (invariance-lite), flagged as exploratory.

### Podsakoff, P. M., MacKenzie, S. B., Lee, J.-Y., & Podsakoff, N. P. (2003). *Common method biases in behavioral research: A critical review of the literature and recommended remedies*
Journal of Applied Psychology, 88(5), 879–903. [doi:10.1037/0021-9010.88.5.879](https://doi.org/10.1037/0021-9010.88.5.879) — DOI confirmed · methods review

- **Main finding:** Shared measurement method can inflate or deflate observed relationships; procedural and statistical remedies are reviewed.
- **Limitations:** Focused on survey research.
- **Relevance:** Stakeholder surveys and manager ratings share rater sources.
- **Design implication:** Evidence from the same source (e.g., one stakeholder) is flagged; perception-based indicators never stand alone.

### Strathern, M. (1997). *'Improving ratings': Audit in the British University system*
European Review, 5(3), 305–321. [https://www.cambridge.org/core/journals/european-review/article/improving-ratings-audit-in-the-british-university-system/FC2EE640C0C44E3DB87C29FB666E9AAB](https://www.cambridge.org/core/journals/european-review/article/improving-ratings-audit-in-the-british-university-system/FC2EE640C0C44E3DB87C29FB666E9AAB) — Citation confirmed (DOI not confirmed) · conceptual commentary

- **Main finding:** Anthropological critique of the 'audit explosion': audit procedures take on a life of their own and can jeopardise what they audit (a commonly cited formulation of Goodhart's law is associated with this essay).
- **Limitations:** Commentary on higher-education audit; the Goodhart association is secondary attribution.
- **Relevance:** Any metric MeritVector surfaces can become a target.
- **Design implication:** No single target metric; activity counts are never rewarded; dashboards emphasise context and uncertainty.

### Campbell, D. T. (1979). *Assessing the impact of planned social change*
Evaluation and Program Planning, 2(1), 67–90 (reprinted in Journal of MultiDisciplinary Evaluation, 7(15)). [doi:10.56645/jmde.v7i15.297](https://doi.org/10.56645/jmde.v7i15.297) — DOI confirmed · conceptual commentary

- **Main finding:** Argues for quasi-experimental evaluation of social programmes; source of the observation now called Campbell's law about quantitative indicators being corrupted when used for decisions.
- **Limitations:** The DOI is for the open-access reprint; the law's exact wording should be checked in the text.
- **Relevance:** Indicator corruption under decision pressure.
- **Design implication:** Assessment indicators are separated from assistance data and not used for automated decisions.

### Kerr, S. (1975). *On the folly of rewarding A, while hoping for B*
Academy of Management Journal, 18(4), 769–783. [https://www.talkingaboutorganizations.com/e57-reward-systems-kerr/](https://www.talkingaboutorganizations.com/e57-reward-systems-kerr/) — Citation confirmed (DOI not confirmed) · conceptual commentary

- **Main finding:** Reward systems often reward behaviours different from those the organisation hopes for.
- **Limitations:** Illustrative essay rather than systematic evidence.
- **Relevance:** Counting tasks or meetings would reward visible busyness.
- **Design implication:** Activity is stored as context only and demonstrably uncorrelated (or negatively correlated) with adjusted contribution in the simulation.

## B3. Monitoring and surveillance

### Bernstein, E. S. (2012). *The transparency paradox: A role for privacy in organizational learning and operational control*
Administrative Science Quarterly, 57(2), 181–216. [doi:10.1177/0001839212453028](https://doi.org/10.1177/0001839212453028) — DOI confirmed · field experiment

- **Main finding:** In a factory field experiment, reducing observability (zones of privacy) improved performance; close observation led workers to hide productive deviations.
- **Limitations:** Single manufacturing setting in China.
- **Relevance:** Surveillance can reduce the performance it aims to measure.
- **Design implication:** No covert monitoring; minimal, disclosed data collection; the coordinator is assistance-first.

### Ravid, D. M., Tomczak, D. L., White, J. C., & Behrend, T. S. (2020). *EPM 20/20: A review, framework, and research agenda for electronic performance monitoring*
Journal of Management, 46(1), 100–126. [doi:10.1177/0149206319869435](https://doi.org/10.1177/0149206319869435) — DOI confirmed · review

- **Main finding:** Reviews electronic performance monitoring and proposes a framework of monitoring characteristics (purpose, invasiveness, transparency, etc.).
- **Limitations:** Narrative review.
- **Relevance:** Design characteristics of monitoring shape employee outcomes.
- **Design implication:** Purpose limitation, transparency notices and employee data visibility are implemented as product features.

## C1. Statistical reasoning

### Simpson, E. H. (1951). *The interpretation of interaction in contingency tables*
Journal of the Royal Statistical Society, Series B, 13(2), 238–241. [https://math.bme.hu/~marib/bsmeur/simpson.pdf](https://math.bme.hu/~marib/bsmeur/simpson.pdf) — Citation confirmed (DOI not confirmed) · methods

- **Main finding:** Aggregated associations can reverse within subgroups (Simpson's paradox).
- **Limitations:** —
- **Relevance:** Raw on-time rates aggregated across project types can reverse once complexity strata are considered.
- **Design implication:** EDA reports stratified comparisons alongside pooled ones; the flagship experiment demonstrates reversal risk.

### Barnett, A. G., van der Pols, J. C., & Dobson, A. J. (2005). *Regression to the mean: What it is and how to deal with it*
International Journal of Epidemiology, 34(1), 215–220. [doi:10.1093/ije/dyh299](https://doi.org/10.1093/ije/dyh299) — DOI confirmed · methods review

- **Main finding:** Extreme measurements tend to be followed by values nearer the mean; design and analysis remedies are described.
- **Limitations:** —
- **Relevance:** People flagged after an extreme period will 'improve' or 'decline' by chance.
- **Design implication:** Longitudinal flags use shrinkage and FDR control; 'improvement' after a bad period is reported with RTM caveats.

### Rubin, D. B. (1976). *Inference and missing data*
Biometrika, 63(3), 581–592. [doi:10.1093/biomet/63.3.581](https://doi.org/10.1093/biomet/63.3.581) — DOI confirmed · methods

- **Main finding:** Formalises when the missing-data mechanism can be ignored (missing at random / ignorability), the basis of the MCAR/MAR/MNAR taxonomy.
- **Limitations:** —
- **Relevance:** Quality scores and surveys are missing non-randomly in the simulation.
- **Design implication:** Missing-data diagnostics test whether missingness depends on observed context; MNAR risks are stated.

### Benjamini, Y., & Hochberg, Y. (1995). *Controlling the false discovery rate: A practical and powerful approach to multiple testing*
Journal of the Royal Statistical Society, Series B, 57(1), 289–300. [doi:10.1111/j.2517-6161.1995.tb02031.x](https://doi.org/10.1111/j.2517-6161.1995.tb02031.x) — DOI confirmed · methods

- **Main finding:** Controls the expected proportion of false discoveries with a simple step-up procedure, gaining power over familywise control.
- **Limitations:** Original proof for independent tests.
- **Relevance:** Hundreds of per-person trend tests.
- **Design implication:** Per-person flags use BH-FDR; registered hypothesis families use Holm or BH as declared.

## C2. Causal inference

### Greenland, S., Pearl, J., & Robins, J. M. (1999). *Causal diagrams for epidemiologic research*
Epidemiology, 10(1), 37–48. [doi:10.1097/00001648-199901000-00008](https://doi.org/10.1097/00001648-199901000-00008) — DOI confirmed · methods

- **Main finding:** Causal diagrams identify which variables must be controlled for unconfounded estimates and expose failures of traditional confounder criteria.
- **Limitations:** Requires a correct diagram; unmeasured variables limit identification.
- **Relevance:** Assignment of people to projects is confounded by unobserved skill.
- **Design implication:** Causal questions are stated with explicit DAGs; unobserved confounders are listed and sensitivity analysis is mandatory.

### VanderWeele, T. J., & Ding, P. (2017). *Sensitivity analysis in observational research: Introducing the E-value*
Annals of Internal Medicine, 167(4), 268–274. [doi:10.7326/M16-2607](https://doi.org/10.7326/M16-2607) — DOI confirmed · methods

- **Main finding:** The E-value is the minimum strength of association an unmeasured confounder would need with both treatment and outcome to explain away an observed association.
- **Limitations:** Defined on the risk-ratio scale; conversion for continuous outcomes is approximate.
- **Relevance:** Quantifies robustness of associations such as resources → delivery.
- **Design implication:** Causal workstream reports E-values (approximate for continuous outcomes, labelled as such).

### Cinelli, C., & Hazlett, C. (2020). *Making sense of sensitivity: Extending omitted variable bias*
Journal of the Royal Statistical Society, Series B, 82(1), 39–67. [doi:10.1111/rssb.12348](https://doi.org/10.1111/rssb.12348) — DOI confirmed · methods

- **Main finding:** Introduces the robustness value and partial-R² tools for omitted-variable sensitivity computable from regression output.
- **Limitations:** Linear models; benchmarking against observed covariates needs care.
- **Relevance:** The flagship experiment's omitted-confounder sensitivity.
- **Design implication:** Robustness values are reported for context coefficients in the regression workstream.

## C3. Machine learning practice

### Kaufman, S., Rosset, S., Perlich, C., & Stitelman, O. (2012). *Leakage in data mining: Formulation, detection, and avoidance*
ACM Transactions on Knowledge Discovery from Data, 6(4), Article 15. [doi:10.1145/2382577.2382579](https://doi.org/10.1145/2382577.2382579) — DOI confirmed · methods

- **Main finding:** Formalises data leakage and proposes detection and avoidance practices (e.g., timestamps and legitimacy of features at prediction time).
- **Limitations:** —
- **Relevance:** Milestone-risk classification uses snapshots; features must exist at prediction time.
- **Design implication:** Classifier features are built from point-in-time snapshots and a test asserts every feature timestamp precedes the prediction time.

### Hennig, C. (2007). *Cluster-wise assessment of cluster stability*
Computational Statistics & Data Analysis, 52(1), 258–271. [https://ideas.repec.org/a/eee/csdana/v52y2007i1p258-271.html](https://ideas.repec.org/a/eee/csdana/v52y2007i1p258-271.html) — Citation confirmed (DOI not confirmed) · methods

- **Main finding:** Assesses stability of individual clusters by resampling (Jaccard similarity), the basis of clusterboot.
- **Limitations:** Stability does not imply validity or meaningfulness.
- **Relevance:** Project-environment clusters must be stable to be reported.
- **Design implication:** Clusters are reported only with bootstrap stability; unstable clusters are labelled exploratory.

## D. Responsible AI, privacy and employment law

### Mitchell, M., Wu, S., Zaldivar, A., Barnes, P., Vasserman, L., Hutchinson, B., Spitzer, E., Raji, I. D., & Gebru, T. (2019). *Model cards for model reporting*
Proceedings of FAT* '19. [doi:10.1145/3287560.3287596](https://doi.org/10.1145/3287560.3287596) — DOI confirmed · methods

- **Main finding:** Proposes model cards documenting intended use, performance across conditions and groups, and limitations.
- **Limitations:** Documentation does not guarantee responsible use.
- **Relevance:** Every MeritVector model carries a model card.
- **Design implication:** The model registry refuses registration without a complete specification (question, target, use, prohibited use, baselines, leakage controls, limitations).

### National Institute of Standards and Technology (2023). *Artificial Intelligence Risk Management Framework (AI RMF 1.0), NIST AI 100-1*
NIST. [doi:10.6028/NIST.AI.100-1](https://doi.org/10.6028/NIST.AI.100-1) — Official source · framework

- **Main finding:** Voluntary, sector-agnostic framework organised around Govern, Map, Measure and Manage functions for AI risk.
- **Limitations:** Voluntary; not employment-specific.
- **Relevance:** Structure for MeritVector's risk register and validation gates.
- **Design implication:** Governance docs map controls to Govern/Map/Measure/Manage.

### ISO/IEC (2023). *ISO/IEC 42001:2023 Information technology — Artificial intelligence — Management system*
ISO. [https://www.iso.org/standard/81230.html](https://www.iso.org/standard/81230.html) — Official source · standard

- **Main finding:** Requirements for establishing, implementing, maintaining and continually improving an AI management system.
- **Limitations:** Paywalled; certification is organisational, not product-level.
- **Relevance:** Future enterprise customers may require alignment.
- **Design implication:** Roadmap item: map MeritVector governance artefacts to an AIMS (v0.4).

### European Parliament and Council (2024). *Regulation (EU) 2024/1689 (Artificial Intelligence Act)*
Official Journal of the EU. [https://eur-lex.europa.eu/eli/reg/2024/1689/oj](https://eur-lex.europa.eu/eli/reg/2024/1689/oj) — Official source · law

- **Main finding:** Annex III lists AI used in employment and workers' management (including evaluation of performance and behaviour) among high-risk uses (per legal commentary reviewed; check the official text for exact wording and dates).
- **Limitations:** Exact Annex III wording and application dates were not read from EUR-Lex in this session.
- **Relevance:** If deployed in the EU, assessment features would likely fall in the high-risk category.
- **Design implication:** Human oversight, logging, transparency and data governance are built in; legal review is required before EU deployment.

### Parliament of New South Wales (2005). *Workplace Surveillance Act 2005 (NSW) No 47*
NSW legislation. [https://legislation.nsw.gov.au/view/whole/html/inforce/2024-07-01/act-2005-047](https://legislation.nsw.gov.au/view/whole/html/inforce/2024-07-01/act-2005-047) — Official source · law

- **Main finding:** Regulates camera, computer and tracking surveillance of employees; computer surveillance generally requires prior written notice (commentary describes a 14-day period and required notice content).
- **Limitations:** Notice details summarised from legal commentary; confirm against the Act's text.
- **Relevance:** Any connector that monitors computer use in NSW engages the Act.
- **Design implication:** Configurable surveillance notice; no computer-surveillance connectors in v0.1; notice acknowledgement is audited.

### Office of the Australian Information Commissioner (n.d.). *Australian Privacy Principles and the employee records exemption*
OAIC guidance. [https://www.oaic.gov.au/privacy/privacy-guidance-for-organisations-and-government-agencies/organisations/employee-records-exemption](https://www.oaic.gov.au/privacy/privacy-guidance-for-organisations-and-government-agencies/organisations/employee-records-exemption) — Official source · regulatory guidance

- **Main finding:** Private-sector handling of employee records for current/former employment is exempt from the APPs in certain circumstances (s 7B(3)); the exemption is narrow, and reform to remove it has been recommended.
- **Limitations:** Law reform status not confirmed in this session.
- **Relevance:** MeritVector should not rely on the exemption; it designs to APP standards (notice, use limitation, access, correction).
- **Design implication:** Notice, purpose limitation, access and correction workflows exist regardless of the exemption.

## E. Public real-world datasets

### Huijgens, H. (2017). *Evidence-Based Software Portfolio Management (EBSPM) Research Repository (version 1)*
4TU.ResearchData (dataset). [doi:10.4121/uuid:42fd1be1-325f-47a4-ba39-31af35ca7f75](https://doi.org/10.4121/uuid:42fd1be1-325f-47a4-ba39-31af35ca7f75) — DOI confirmed · dataset

- **Main finding:** Records of finalised software projects from four anonymised companies with size, cost, duration, defects and binary context flags (dependencies, migration, regulation-driven, team stability).
- **Limitations:** Context flags are recorded inconsistently between companies; quality and satisfaction outcomes are sparse. 4TU General Terms of Use apply.
- **Relevance:** Largest public project dataset with organisation identifiers and context flags; tests whether raw comparisons between delivery units survive context adjustment.
- **Design implication:** Used in the real-world validation studies; not redistributed — fetched and checksum-verified at run time.

### Maxwell, K. D. (2002). *Applied Statistics for Software Managers*
Prentice Hall. [https://www.informit.com/store/applied-statistics-for-software-managers-9780130417893](https://www.informit.com/store/applied-statistics-for-software-managers-9780130417893) — Citation confirmed (DOI not confirmed) · dataset

- **Main finding:** Book appendix datasets, including development projects from a large Finnish commercial bank (1985–1993) with size, effort, duration and fifteen 1–5 ratings of project and staff factors.
- **Limitations:** Subjective factor ratings; one organisation; about 62 projects (copies differ by one record).
- **Relevance:** Separates context ratings (requirements volatility, complexity, staff availability) from staff-skill ratings.
- **Design implication:** Used to compare how much productivity variation context explains versus staff skills.

### Desharnais, J.-M. (1989). *Analyse statistique de la productivité des projets informatiques à partir de la technique des points de fonction*
Master's thesis, University of Montreal (dataset distributed via the PROMISE repository). [https://arxiv.org/abs/1405.1131](https://arxiv.org/abs/1405.1131) — Citation confirmed (DOI not confirmed) · dataset

- **Main finding:** 81 management-information-system projects from ten Canadian organisations (1983–1988) with team and manager experience in years, function points, language and effort; 77 complete records.
- **Limitations:** Experience in years is a proxy for capability; pooled organisations; thesis copy not located (citation confirmed through studies that use the data).
- **Relevance:** Rare public data with a project-manager variable; tests whether tenure relates to outcomes once size and context are accounted for.
- **Design implication:** Supports MeritVector's refusal to treat tenure or experience as a proxy for contribution.

### Menzies, T., et al. (PROMISE repository) (2008). *NASA93 software cost estimation data (COCOMO-81 format)*
PROMISE Software Engineering Repository; archived on Zenodo. [https://zenodo.org/record/268419](https://zenodo.org/record/268419) — Citation confirmed (DOI not confirmed) · dataset

- **Main finding:** 93 NASA projects (1971–1987) from five centres with 15 COCOMO effort multipliers, including analyst and programmer capability ratings, size in KLOC and effort in person-months.
- **Limitations:** Capability ratings are estimator judgements; old technology context.
- **Relevance:** Tests whether centres' raw productivity differences survive adjustment and how much capability ratings add.
- **Design implication:** Used in the real-world validation studies.

