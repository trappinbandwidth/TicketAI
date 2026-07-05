"""
Google Places (New) v1 — law-firm location lookup for attorney profile import.

Given a firm name + city/state (or a free-text query), returns the richest set of
fields Google exposes: formatted address + components, phone, website, hours,
rating, lat/lng, maps URL, place_id.

Requires GOOGLE_PLACES_API_KEY (or GOOGLE_MAPS_API_KEY) with the "Places API (New)"
enabled on the GCP project. Returns a structured {configured: False} payload rather
than raising when the key is absent, so callers can degrade gracefully.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Field mask — everything useful for a firm profile.
_FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.addressComponents",
    "places.location",
    "places.nationalPhoneNumber",
    "places.internationalPhoneNumber",
    "places.websiteUri",
    "places.regularOpeningHours",
    "places.rating",
    "places.userRatingCount",
    "places.googleMapsUri",
    "places.businessStatus",
    "places.types",
])


def _api_key() -> Optional[str]:
    return os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY") or None


def _component(components: list, *types: str) -> Optional[str]:
    """Return the short/long text of the first address component matching any type."""
    for c in components or []:
        ctypes = c.get("types", [])
        if any(t in ctypes for t in types):
            return c.get("shortText") or c.get("longText")
    return None


def _normalize(place: dict) -> dict:
    comps = place.get("addressComponents", [])
    loc = place.get("location") or {}
    hours = (place.get("regularOpeningHours") or {}).get("weekdayDescriptions")
    return {
        "place_id": place.get("id"),
        "name": (place.get("displayName") or {}).get("text"),
        "formatted_address": place.get("formattedAddress"),
        "street": " ".join(filter(None, [
            _component(comps, "street_number"), _component(comps, "route")
        ])) or None,
        "city": _component(comps, "locality", "postal_town", "sublocality"),
        "state": _component(comps, "administrative_area_level_1"),
        "postal_code": _component(comps, "postal_code"),
        "country": _component(comps, "country"),
        "phone": place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber"),
        "website": place.get("websiteUri"),
        "hours": hours,
        "rating": place.get("rating"),
        "rating_count": place.get("userRatingCount"),
        "google_maps_uri": place.get("googleMapsUri"),
        "business_status": place.get("businessStatus"),
        "lat": loc.get("latitude"),
        "lng": loc.get("longitude"),
    }


def lookup_firm(query: str, max_results: int = 5) -> dict:
    """
    Text-search Google Places for a law firm.
    Returns {configured, query, results:[normalized...], best: <first or None>}.
    """
    key = _api_key()
    if not key:
        return {"configured": False, "query": query, "results": [],
                "message": "Google Places not configured — set GOOGLE_PLACES_API_KEY."}
    try:
        resp = requests.post(
            _SEARCH_URL,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": key,
                "X-Goog-FieldMask": _FIELD_MASK,
            },
            json={"textQuery": query, "maxResultCount": max_results},
            timeout=12,
        )
        if resp.status_code != 200:
            logger.warning("[places] search failed %s: %s", resp.status_code, resp.text[:300])
            return {"configured": True, "query": query, "results": [],
                    "message": f"Places API error {resp.status_code}."}
        places = resp.json().get("places", [])
        results = [_normalize(p) for p in places]
        return {"configured": True, "query": query, "results": results,
                "best": results[0] if results else None}
    except Exception as exc:
        logger.error("[places] lookup exception: %s", exc)
        return {"configured": True, "query": query, "results": [], "message": str(exc)}


def build_query(name: Optional[str], city: Optional[str], state: Optional[str]) -> str:
    return " ".join(p for p in [name, city, state] if p).strip()
