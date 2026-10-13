# Product vision

## The problem

Organisations judge delivery staff on what is easy to see: tasks closed, meetings attended, how often someone is
mentioned, whether their project finished on time. Those signals mix a person's contribution with the difficulty of
the work they were given, the resources they had, the dependencies they inherited, how visible they are and plain
luck. People who take on the hardest projects can look worst. People who are busy and visible can look best.

## The research question

> Can we distinguish genuine employee contribution from superficial activity, favourable circumstances, project
> complexity, organisational bias and noise — and know when we cannot?

MeritVector treats this as an empirical question, not a product claim. The synthetic organisation lets us test the
answer against a known truth; the same machinery reports uncertainty and abstains in real use.

## Two products, one platform, a hard wall between them

| | Work Coordinator | Performance-evidence engine |
|---|---|---|
| For | The employee | Employee, manager, HR reviewer |
| Purpose | Get the day done: summaries, actions, reminders, reports | Context-aware, uncertainty-aware evidence for development conversations |
| Data | Assistance data (transcripts, drafts, tasks) | Validated assessment evidence only |
| Switch | On by default | Off until an administrator *and* an HR reviewer approve it |

Coordinator content is never reused for evaluation. The coordinator imports nothing from the analytics package
(tested).

## Principles

* **Decision support, not decisions.** No rankings, no promotion-readiness scores, no dismissal or pay
  recommendations. Managers record their own judgement — including disagreement with the data — in an audited log.
* **Context before conclusions.** Every individual estimate is shown next to the operating conditions behind it.
* **Uncertainty is a feature.** Intervals are always shown; "insufficient evidence" is a first-class answer.
* **Historical ratings are biased labels.** They are audited, never learned from.
* **Transparent by construction.** Employees see every record held about them and can challenge it; challenged
  records leave the analysis until resolved.
* **No covert monitoring.** No message content, keystrokes, screens, browsing or location — ever.
* **Statistics first, AI optional.** The engine is plain, testable statistics. Language models are an optional,
  clearly labelled convenience for the coordinator.

## Initial users

Project, technical project and programme managers, PMO and portfolio leads. The evidence model (events → context →
estimates) generalises to other functions with their own outcome definitions and competency frameworks.
