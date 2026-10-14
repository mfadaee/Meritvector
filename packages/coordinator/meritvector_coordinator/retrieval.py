"""Knowledge retrieval over records the caller may already see (meetings attended, decisions, projects).

A plain TF-IDF ranker with no external service: results are links to source records with the matching passage,
never a generated answer, so every statement can be checked at its source.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

_STOP = set(
    "a an and are as at be by for from has have in is it its of on or that the this to was were will with we our you "
    "your they their i he she not but if then so do does did can could should would".split()
)


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOP and len(t) > 1]


@dataclass
class Document:
    id: str
    kind: str  # meeting | decision | action | project | risk | dependency
    title: str
    text: str
    url: str
    date: str | None = None
    meta: dict = field(default_factory=dict)


def _snippet(text: str, terms: set[str], width: int = 180) -> str:
    low = text.lower()
    pos = min((low.find(t) for t in terms if low.find(t) >= 0), default=0)
    start = max(0, pos - width // 3)
    s = text[start : start + width].replace("\n", " ").strip()
    return ("…" if start > 0 else "") + s + ("…" if start + width < len(text) else "")


def search(docs: list[Document], query: str, k: int = 10) -> list[dict]:
    q = tokens(query)
    if not q or not docs:
        return []
    tfs = [Counter(tokens(d.title + " " + d.title + " " + d.text)) for d in docs]
    df = Counter(t for tf in tfs for t in tf)
    n = len(docs)
    idf = {t: math.log((1 + n) / (1 + df[t])) + 1 for t in df}
    qtf = Counter(q)
    qvec = {t: qtf[t] * idf.get(t, 0.0) for t in qtf}
    qnorm = math.sqrt(sum(v * v for v in qvec.values())) or 1.0
    scored = []
    for d, tf in zip(docs, tfs, strict=True):
        dvec = {t: (1 + math.log(c)) * idf[t] for t, c in tf.items()}
        dot = sum(qvec[t] * dvec.get(t, 0.0) for t in qvec)
        if dot <= 0:
            continue
        dnorm = math.sqrt(sum(v * v for v in dvec.values())) or 1.0
        matched = sorted(t for t in qvec if t in tf)
        scored.append((dot / (qnorm * dnorm), d, matched))
    scored.sort(key=lambda x: (-x[0], x[1].id))
    return [
        {
            "id": d.id,
            "kind": d.kind,
            "title": d.title,
            "url": d.url,
            "date": d.date,
            "score": round(s, 4),
            "matched_terms": matched,
            "snippet": _snippet(d.text or d.title, set(matched)),
            **({"meta": d.meta} if d.meta else {}),
        }
        for s, d, matched in scored[:k]
    ]
