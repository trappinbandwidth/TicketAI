"""
Violation corpus service — Research Ron Phase 2.

Reads data/violation_corpus.json built by scripts/ingest_kaggle_violations.py
and provides fast lookups for state+category patterns.

Loaded once at import time; restart the server after re-running the ingestion script.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CORPUS_PATH = Path(__file__).parent.parent.parent / "data" / "violation_corpus.json"

_CORPUS: dict[str, Any] = {}
_CORPUS_LOADED = False


def _load() -> dict[str, Any]:
    global _CORPUS, _CORPUS_LOADED
    if not _CORPUS_LOADED:
        try:
            _CORPUS = json.loads(_CORPUS_PATH.read_text())
            logger.info(
                "violation_corpus: loaded %d states from %s",
                len(_CORPUS), _CORPUS_PATH.name,
            )
        except FileNotFoundError:
            logger.warning(
                "violation_corpus.json not found — Research Ron Phase 2 disabled. "
                "Run: python scripts/ingest_kaggle_violations.py"
            )
            _CORPUS = {}
        _CORPUS_LOADED = True
    return _CORPUS


def lookup_violation_patterns(
    state: str,
    violation_category: str,
    county: str = "",
) -> dict[str, Any] | None:
    """
    Returns pattern stats for a state + violation category, or None if not in corpus.

    Result shape:
      {
        count          int      — records in corpus matching state+category
        citation_rate  float    — fraction that resulted in a citation (0–1)
        high_risk      bool
        top_counties   list[str]
        county_rank    int|None — how frequently this county appears (1=most common)
        outcome_dist   {citation, warning, arrest, other: int}
        defense_note   str      — human-readable context note for Ron's output
      }
    """
    corpus = _load()
    if not corpus:
        return None

    # Normalize state — try full name first, then abbreviation
    state_data = corpus.get(state)
    if not state_data:
        # Try title-casing
        state_data = corpus.get(state.strip().title())
    if not state_data:
        return None

    cat_data = state_data.get(violation_category)
    if not cat_data:
        return None

    result: dict[str, Any] = {
        "count":         cat_data["count"],
        "citation_rate": cat_data["citation_rate"],
        "high_risk":     cat_data["high_risk"],
        "top_counties":  cat_data.get("top_counties", []),
        "outcome_dist":  cat_data.get("outcome_dist", {}),
        "county_rank":   None,
        "defense_note":  "",
    }

    # County rank
    if county:
        county_stats = cat_data.get("county_stats", {})
        sorted_counties = sorted(county_stats.items(), key=lambda x: -x[1])
        for rank, (c_name, _) in enumerate(sorted_counties, start=1):
            if c_name.lower() == county.strip().lower():
                result["county_rank"] = rank
                break

    # Build a plain-English defense note for Ron's jurisdiction_context
    n = result["count"]
    cit_pct = round(result["citation_rate"] * 100)
    county_note = ""
    if result["county_rank"]:
        county_note = f" ({county} is rank-{result['county_rank']} for this violation in {state}.)"

    if n < 10:
        result["defense_note"] = (
            f"Limited corpus data for {violation_category} in {state} ({n} records)."
        )
    else:
        result["defense_note"] = (
            f"Corpus: {n:,} {violation_category} records in {state} — "
            f"{cit_pct}% resulted in a formal citation.{county_note} "
            f"{'High-risk: attorney strongly recommended.' if result['high_risk'] else ''}"
        ).strip()

    return result


def is_corpus_available() -> bool:
    return bool(_load())
