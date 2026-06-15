"""
BBox Matcher — maps Claude's extracted field values to Textract word positions.

Strategy (in order):
  1. Exact match — value found verbatim in the word list
  2. Normalized match — strip punctuation/spaces from both sides
  3. Multi-word span — value is multiple words; find the span that covers them all
  4. Fuzzy match — Levenshtein distance ≤ 2 for short values (catches OCR noise)
  5. No match — bbox stays None (field card still works, just no zoom target)

The returned bbox is a dict ready to be passed into BoundingBox().
For multi-word spans, the bbox is the union (bounding rectangle) of all words.
"""
import logging
import re
from typing import Optional

from app.services.textract_service import WordPosition

logger = logging.getLogger(__name__)

# Fields we skip matching for — empty strings or single-char values aren't matchable
_MIN_VALUE_LEN = 3


def _normalize(text: str) -> str:
    """Strip punctuation, extra spaces, lowercase."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _union_bbox(words: list[WordPosition]) -> dict:
    """Bounding rectangle that covers all words in the list."""
    x = min(w.x for w in words)
    y = min(w.y for w in words)
    x2 = max(w.x + w.w for w in words)
    y2 = max(w.y + w.h for w in words)
    return {"x": x, "y": y, "w": x2 - x, "h": y2 - y, "page": words[0].page}


def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j] + (ca != cb), curr[j] + 1, prev[j + 1] + 1))
        prev = curr
    return prev[-1]


def find_bbox(value: str, word_positions: list[WordPosition]) -> Optional[dict]:
    """
    Find the bounding box for `value` within the list of word positions.
    Returns a bbox dict or None if no match found.
    """
    if not value or len(value) < _MIN_VALUE_LEN or not word_positions:
        return None

    value_stripped = value.strip()
    value_norm = _normalize(value_stripped)
    value_words = value_stripped.split()

    # ── Pass 1: exact single-word match ──────────────────────────────────
    for wp in word_positions:
        if wp.word == value_stripped:
            return {"x": wp.x, "y": wp.y, "w": wp.w, "h": wp.h, "page": wp.page}

    # ── Pass 2: normalized single-word match ─────────────────────────────
    for wp in word_positions:
        if _normalize(wp.word) == value_norm:
            return {"x": wp.x, "y": wp.y, "w": wp.w, "h": wp.h, "page": wp.page}

    # ── Pass 3: multi-word span match ────────────────────────────────────
    if len(value_words) > 1:
        norm_value_words = [_normalize(v) for v in value_words]
        page_words = {}
        for wp in word_positions:
            page_words.setdefault(wp.page, []).append(wp)

        for page_num, pwords in page_words.items():
            for i in range(len(pwords) - len(norm_value_words) + 1):
                span = pwords[i: i + len(norm_value_words)]
                if [_normalize(w.word) for w in span] == norm_value_words:
                    return _union_bbox(span)

    # ── Pass 4: fuzzy match (short values only, distance ≤ 2) ────────────
    if len(value_norm) <= 12:
        best_dist = 3  # threshold
        best_wp = None
        for wp in word_positions:
            dist = _levenshtein(_normalize(wp.word), value_norm)
            if dist < best_dist:
                best_dist = dist
                best_wp = wp
        if best_wp:
            logger.debug("[bbox_matcher] fuzzy match: %r → %r (dist=%d)", value, best_wp.word, best_dist)
            return {"x": best_wp.x, "y": best_wp.y, "w": best_wp.w, "h": best_wp.h, "page": best_wp.page}

    logger.debug("[bbox_matcher] no match for value=%r", value[:40])
    return None


def attach_bboxes(extraction: dict, word_positions: list[WordPosition]) -> dict:
    """
    Walk every field in the extraction dict and attach a bbox where possible.
    Returns the extraction dict with bbox fields added in-place.
    """
    if not word_positions:
        return extraction

    matched = 0
    total = 0

    for key, field_val in extraction.items():
        if not isinstance(field_val, dict):
            continue
        value = field_val.get("value", "")
        if not value:
            continue
        total += 1
        bbox = find_bbox(value, word_positions)
        if bbox:
            field_val["bbox"] = bbox
            matched += 1

    logger.warning("[bbox_matcher] matched=%d/%d fields", matched, total)
    return extraction
