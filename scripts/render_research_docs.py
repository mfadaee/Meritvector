"""Render docs generated from data files (keeps docs and data in sync).

python scripts/render_research_docs.py           # write
python scripts/render_research_docs.py --check   # fail if stale
"""

from __future__ import annotations

import sys
from pathlib import Path

from meritvector_analytics.measurement import load_job_family, load_library, load_ontology

ROOT = Path(__file__).resolve().parents[1]
AREAS = {
    "performance_theory": "A. Job performance theory",
    "ratings": "B1. Performance ratings",
    "measurement": "B2. Measurement science",
    "monitoring": "B3. Monitoring and surveillance",
    "statistics": "C1. Statistical reasoning",
    "causal_inference": "C2. Causal inference",
    "machine_learning": "C3. Machine learning practice",
    "governance": "D. Responsible AI, privacy and employment law",
}
VERIF = {
    "doi_confirmed": "DOI confirmed",
    "citation_confirmed": "Citation confirmed (DOI not confirmed)",
    "official_source": "Official source",
}


def literature() -> str:
    lib = load_library()
    out = [
        "# Literature review and evidence library",
        "",
        "> Generated from `research/references/library.json` by `scripts/render_research_docs.py`. Edit the data, not this file.",
        "",
        f"{len(lib['entries'])} sources, checked on {lib['version']} against bibliographic records via web search "
        "(publisher pages, PubMed, RePEc, institutional repositories). Crossref could not be queried from the build "
        "environment, so each entry states what was confirmed. Findings are paraphrased; consult the source before "
        "relying on specific figures.",
        "",
        "## Synthesis",
        "",
        "1. **Performance is behaviour, results are not the same thing.** Campbell's theory separates performance "
        "(behaviour under the person's control) from its results; task, contextual and adaptive performance are "
        "distinct (Campbell 1993; Borman & Motowidlo 1993; Motowidlo & Van Scotter 1994; Pulakos 2000; Griffin 2007). "
        "→ MeritVector separates OUTCOMES from CONTRIBUTION and never collapses dimensions into one score.",
        "2. **Ratings are weak measures of performance.** Interrater reliability of supervisory ratings is about .52 and "
        "idiosyncratic rater effects can exceed ratee effects (Viswesvaran 1996; Scullen 2000; Murphy 2008; Rotundo & "
        "Sackett 2002). → Historical ratings are audited as biased labels, never learned from.",
        "3. **Objective and subjective measures are not interchangeable** (Bommer 1995). → Evidence and human "
        "judgement are shown side by side.",
        "4. **Measures that become targets degrade** (Kerr 1975; Campbell 1979; Strathern 1997). → No activity "
        "counts as merit; no single target metric.",
        "5. **Monitoring can reduce the performance it observes** (Bernstein 2012; Ravid 2020). → No covert "
        "monitoring, assistance-first coordinator, purpose limitation.",
        "6. **Context, confounding and selection dominate observational comparisons** (Simpson 1951; Greenland 1999; "
        "Barnett 2005; Rubin 1976). → Contextual adjustment, explicit DAGs, regression-to-the-mean caveats, "
        "missing-data diagnostics.",
        "7. **Associations need sensitivity analysis and multiplicity control** (VanderWeele & Ding 2017; Cinelli & "
        "Hazlett 2020; Benjamini & Hochberg 1995). → E-values / robustness values and FDR are part of every analysis.",
        "8. **Models need leakage control, stability checks and documentation** (Kaufman 2012; Hennig 2007; "
        "Mitchell 2019). → Point-in-time features, cluster stability, mandatory model specifications.",
        "9. **Employment AI is high-risk and regulated** (NIST AI RMF 2023; ISO/IEC 42001; EU AI Act; NSW Workplace "
        "Surveillance Act; OAIC). → Notice, human review, logging, access and correction rights are product features.",
        "",
        "## Established findings vs hypotheses vs product assumptions",
        "",
        "| Status | Examples |",
        "|---|---|",
        "| Established (replicated, meta-analytic or foundational) | Ratings have low interrater reliability; task vs contextual performance are distinct; confounding and Simpson's paradox; regression to the mean |",
        "| Reasonable hypothesis (supported by theory, untested in our setting) | PMO complexity rubrics capture the main sources of delivery difficulty; milestone schedule variance reflects contribution once context is adjusted |",
        "| Unvalidated product assumption | Mixed-model employee intercepts are useful for development conversations; manager-verified attribution improves accuracy; the coordinator improves follow-through |",
        "",
    ]
    for area, title in AREAS.items():
        rows = [e for e in lib["entries"] if e["area"] == area]
        if not rows:
            continue
        out += [f"## {title}", ""]
        for e in rows:
            link = e["url"] or ""
            ident = f"doi:{e['doi']}" if e["doi"] else link
            out += [
                f"### {e['authors']} ({e['year'] or 'n.d.'}). *{e['title']}*",
                f"{e['venue']}. [{ident}]({link}) — {VERIF[e['verification']]} · {e['evidence_type'].replace('_', ' ')}",
                "",
                f"- **Main finding:** {e['main_finding']}",
                f"- **Limitations:** {e['limitations']}",
                f"- **Relevance:** {e['relevance']}",
                f"- **Design implication:** {e['design_implications']}",
                "",
            ]
    return "\n".join(out)


def constructs() -> str:
    o = load_ontology()
    pmo = load_job_family("pmo")
    out = [
        "# Construct reference",
        "",
        "> Generated from `config/measurement/ontology.yaml` and `config/job_families/pmo/family.yaml`.",
        "",
        f"**Conceptual model.** {o.conceptual_model.statement}",
        "",
        f"*{o.conceptual_model.caveat}*",
        "",
    ]
    for cid, c in o.constructs.items():
        dims = [d for d in pmo.context_dimensions + pmo.responsibility_dimensions + pmo.outcome_dimensions if d.construct == cid]
        out += [
            f"## {c.label} (`{cid}`) — {c.evidence_status.replace('_', ' ')}",
            "",
            c.definition,
            "",
            f"- **Observable indicators:** {', '.join(c.indicators)}",
            f"- **Data sources:** {', '.join(c.data_sources)}",
            f"- **Measurement assumptions:** {' '.join(c.assumptions) or '—'}",
            f"- **Reliability:** {c.reliability}",
            f"- **Confounders:** {', '.join(c.confounders)}",
            f"- **Known limitations:** {' '.join(c.limitations)}",
            f"- **Intended use:** {c.intended_use}",
            f"- **Prohibited interpretations:** {'; '.join(c.prohibited_interpretations)}",
            f"- **Can increase merit:** {'yes' if c.may_increase_merit else 'no'}",
        ]
        if dims:
            out.append("- **PMO dimensions:** " + "; ".join(f"{d.label} ({d.status})" for d in dims))
        out.append("")
    return "\n".join(out)


def _yaml(name: str) -> dict:
    import yaml

    from meritvector_analytics.measurement import config_dir

    return yaml.safe_load((config_dir() / "research" / name).read_text())


def questions() -> str:
    q = _yaml("questions.yaml")
    out = [
        "# Research questions",
        "",
        "> Generated from `config/research/questions.yaml`. Each question states its type — descriptive, predictive, "
        "causal, measurement or experimental — because the type determines which conclusions are allowed.",
        "",
        "| ID | Question | Type | Workstream | Hypotheses |",
        "|---|---|---|---|---|",
    ]
    for r in q["questions"]:
        out.append(
            f"| {r['id']} | **{r['title']}** {r['detail']} | {r['type']} | {r['workstream']} | {', '.join(r['hypotheses']) or '—'} |"
        )
    out += [
        "",
        "## What each type may conclude",
        "",
        "- **Descriptive** — what happened and how it is distributed. No causal language.",
        "- **Predictive** — how well something can be forecast out of time. Prediction is not explanation.",
        "- **Causal** — only with an explicit DAG, a stated adjustment set, and sensitivity to unmeasured confounding.",
        "- **Measurement** — whether an indicator measures the intended construct (validity, reliability, bias).",
        "- **Experimental** — effects of randomised interventions on consented participants, with pre-specified "
        "power and outcomes. Never used for employment decisions.",
        "",
    ]
    return "\n".join(out)


def hypotheses() -> str:
    h = _yaml("hypotheses.yaml")
    out = [
        "# Hypotheses",
        "",
        "> Generated from `config/research/hypotheses.yaml`. Results are produced by "
        "`meritvector_analytics.research.hypotheses` and shown in the Research Laboratory; they are not edited here.",
        "",
        f"Significance level α = {h['alpha']}. Multiple-testing families:",
        "",
    ]
    for f in h["families"]:
        out.append(f"- `{f['id']}` ({f['correction']}): {', '.join(f['hypotheses'])}")
    out.append("")
    for r in h["hypotheses"]:
        out += [
            f"## {r['id']} — {r['status']} (answers {r['question']})",
            "",
            f"- **H0:** {r['h0']}",
            f"- **H1:** {r['h1']}",
            f"- **Unit of analysis:** {r['unit']}",
            f"- **Test:** `{r['test']}` on {', '.join(f'{k}={v}' for k, v in r['variables'].items())}",
            f"- **Assumptions:** {' '.join(r['assumptions'])}",
            "- **Reporting:** effect size with confidence interval, assumption checks and adjusted p-value — not a p-value alone.",
            "",
        ]
    return "\n".join(out)


TARGETS = {
    ROOT / "docs" / "research" / "LITERATURE_REVIEW.md": literature,
    ROOT / "docs" / "research" / "CONSTRUCTS.md": constructs,
    ROOT / "docs" / "research" / "RESEARCH_QUESTIONS.md": questions,
    ROOT / "docs" / "research" / "HYPOTHESES.md": hypotheses,
}


def main() -> int:
    check = "--check" in sys.argv
    stale = []
    for path, fn in TARGETS.items():
        text = fn() + "\n"
        if check:
            if not path.exists() or path.read_text() != text:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.write_text(text)
            print(f"wrote {path.relative_to(ROOT)}")
    if stale:
        print("stale:", ", ".join(stale), "— run python scripts/render_research_docs.py")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
