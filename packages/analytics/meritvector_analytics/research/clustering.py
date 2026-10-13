"""Workstream 5 — clustering and PCA of project operating environments (exploratory).

Clusters describe *projects*, never people. A cluster solution is reported only if it is stable under bootstrap
resampling (Hennig 2007); otherwise the result is "no stable structure".
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

from meritvector_analytics.research.data import ResearchData, jsonable

DIMENSIONS = [
    "technical_complexity",
    "dependency_count",
    "resource_constraint",
    "size_band",
    "team_size",
    "schedule_criticality",
    "visibility_level",
    "stakeholder_groups",
    "technical_uncertainty",
    "operational_criticality",
    "sites",
    "vendor_count",
    "integration_points",
]
LABELS = {
    "technical_complexity": "complex",
    "dependency_count": "dependency-heavy",
    "resource_constraint": "under-resourced",
    "size_band": "large",
    "team_size": "large-team",
    "schedule_criticality": "deadline-critical",
    "visibility_level": "high-visibility",
    "stakeholder_groups": "many-stakeholder",
    "technical_uncertainty": "novel-technology",
    "operational_criticality": "ops-critical",
    "sites": "multi-site",
    "vendor_count": "vendor-heavy",
    "integration_points": "integration-heavy",
    "regulated": "regulated",
    "greenfield": "greenfield",
}


def _matrix(rd: ResearchData) -> tuple[pd.DataFrame, np.ndarray]:
    p = rd.project_frame.copy()
    p["regulated"] = (p["environment"] == "regulated").astype(float)
    p["greenfield"] = (p["maturity"] == "greenfield").astype(float)
    cols = [c for c in DIMENSIONS if c in p.columns] + ["regulated", "greenfield"]
    X = StandardScaler().fit_transform(p[cols].astype(float).to_numpy())
    return p.assign(**{"_cols": [cols] * len(p)}), X


def _stability(X: np.ndarray, k: int, n_boot: int, seed: int) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    ref = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(X)
    aris, jacc = [], {c: [] for c in range(k)}
    for b in range(n_boot):
        idx = rng.integers(0, len(X), len(X))
        km = KMeans(n_clusters=k, n_init=5, random_state=seed + b + 1).fit(X[idx])
        lab = km.predict(X)
        aris.append(adjusted_rand_score(ref.labels_, lab))
        for c in range(k):
            a = set(np.nonzero(ref.labels_ == c)[0])
            best = max(
                (len(a & set(np.nonzero(lab == j)[0])) / max(1, len(a | set(np.nonzero(lab == j)[0]))) for j in range(k)),
                default=0,
            )
            jacc[c].append(best)
    return {"mean_ari": float(np.mean(aris)), "cluster_jaccard": {int(c): float(np.mean(v)) for c, v in jacc.items()}}


def explore(rd: ResearchData, k_range=range(2, 8), n_boot: int = 20, seed: int = 0, stable_ari: float = 0.6) -> dict[str, Any]:
    p, X = _matrix(rd)
    cols = p["_cols"].iloc[0]
    pca = PCA().fit(X)
    loadings = pd.DataFrame(pca.components_[:3].T, index=cols, columns=["PC1", "PC2", "PC3"])
    candidates = []
    for k in k_range:
        km = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(X)
        stab = _stability(X, k, n_boot, seed)
        hier = AgglomerativeClustering(n_clusters=k, linkage="ward").fit(X)
        candidates.append(
            {
                "k": k,
                "silhouette": float(silhouette_score(X, km.labels_)),
                "inertia": float(km.inertia_),
                "bootstrap_ari": stab["mean_ari"],
                "kmeans_vs_ward_ari": float(adjusted_rand_score(km.labels_, hier.labels_)),
                "cluster_jaccard": stab["cluster_jaccard"],
            }
        )
    stable = [c for c in candidates if c["bootstrap_ari"] >= stable_ari]
    result: dict[str, Any] = {
        "kind": "descriptive",
        "status": "exploratory",
        "question": "Are there recurring project operating environments?",
        "unit": "project",
        "n_projects": int(len(p)),
        "features": cols,
        "pca": {
            "explained_variance_ratio": [float(v) for v in pca.explained_variance_ratio_[:6]],
            "cumulative_3": float(pca.explained_variance_ratio_[:3].sum()),
            "top_loadings": {pc: loadings[pc].abs().sort_values(ascending=False).head(4).index.tolist() for pc in loadings},
        },
        "candidates": candidates,
    }
    if not stable:
        result["selected_k"] = None
        result["conclusion"] = "No stable cluster structure: project environments vary continuously. Do not label projects by cluster."
        return jsonable(result)
    best = max(stable, key=lambda c: c["silhouette"])
    km = KMeans(n_clusters=best["k"], n_init=10, random_state=seed).fit(X)
    p["cluster"] = km.labels_
    z = pd.DataFrame(X, columns=cols).assign(cluster=km.labels_).groupby("cluster").mean()
    profiles = []
    for c, row in z.iterrows():
        sub = p[p["cluster"] == c]
        top = row.sort_values(ascending=False)
        name = ", ".join(LABELS.get(f, f) for f in top.index[:2] if top[f] > 0.4) or "typical conditions"
        profiles.append(
            {
                "cluster": int(c),
                "label": name,
                "n_projects": int(len(sub)),
                "jaccard_stability": best["cluster_jaccard"][int(c)],
                "distinguishing": {f: float(row[f]) for f in top.index[:4]},
                "on_time_rate": float(sub["project_on_time"].mean()),
                "mean_schedule_variance": float(sub["project_mean_svp"].mean()),
                "issues_per_project": float(sub["issues"].mean()),
            }
        )
    result.update(
        {
            "selected_k": best["k"],
            "profiles": profiles,
            "silhouette": best["silhouette"],
            "conclusion": f"{best['k']} stable project environments (bootstrap ARI {best['bootstrap_ari']:.2f}, silhouette "
            f"{best['silhouette']:.2f}). Silhouette is modest: clusters are tendencies, not types.",
        }
    )
    return jsonable(result)
