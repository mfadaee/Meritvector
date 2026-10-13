"""Research laboratory: workstreams that answer registered research questions.

Every function returns plain JSON-serialisable results with an explicit ``kind``
(descriptive / predictive / causal / measurement / experimental) and ``status``
(exploratory / confirmatory). Outputs reference people only by pseudonym.
"""

from meritvector_analytics.research.data import ResearchData, pseudonym

__all__ = ["ResearchData", "pseudonym"]
