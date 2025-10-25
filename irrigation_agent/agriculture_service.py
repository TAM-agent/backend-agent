"""USDA Quick Stats API integration service.

Provides access to crop statistics (yield, area planted, generic search)
to enrich irrigation decisions with agricultural context.
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import requests

logger = logging.getLogger(__name__)

QUICKSTATS_BASE = "https://quickstats.nass.usda.gov/api/api_GET/"


def _get_api_key() -> Optional[str]:
    return os.getenv("USDA_QUICKSTATS_API_KEY")


def quickstats_request(params: Dict[str, Any]) -> Dict[str, Any]:
    """Perform a Quick Stats API request with the configured API key.

    Params should match Quick Stats API fields, e.g. commodity_desc, year, state_alpha, statisticcat_desc.
    """
    api_key = _get_api_key()
    if not api_key:
        return {
            "status": "error",
            "error": "USDA_QUICKSTATS_API_KEY not configured",
            "timestamp": datetime.now().isoformat(),
        }

    query = {k: v for k, v in params.items() if v is not None}
    query["key"] = api_key
    query["format"] = "JSON"

    try:
        resp = requests.get(QUICKSTATS_BASE, params=query, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # API returns {"data": [...]} on success
        items = data.get("data", [])
        return {
            "status": "success",
            "count": len(items),
            "params": query,
            "data": items,
            "timestamp": datetime.now().isoformat(),
        }
    except requests.RequestException as e:
        logger.error(f"Quick Stats error: {e}")
        return {
            "status": "error",
            "error": str(e),
            "params": query,
            "timestamp": datetime.now().isoformat(),
        }


def get_crop_yield(commodity_desc: str, year: int, state_alpha: Optional[str] = None) -> Dict[str, Any]:
    """Get yield statistics for a crop (commodity) by year, optionally filtered by state (2-letter)."""
    params = {
        "commodity_desc": commodity_desc.upper(),
        "year": str(year),
        "statisticcat_desc": "YIELD",
        # Common defaults; callers can refine via generic endpoint if needed
        # "unit_desc": "BU / ACRE",
        "state_alpha": state_alpha.upper() if state_alpha else None,
        "source_desc": "SURVEY",
    }
    return quickstats_request(params)


def get_area_planted(commodity_desc: str, year: int, state_alpha: Optional[str] = None) -> Dict[str, Any]:
    """Get area planted (acres) for a crop by year, optionally filtered by state."""
    params = {
        "commodity_desc": commodity_desc.upper(),
        "year": str(year),
        "statisticcat_desc": "AREA PLANTED",
        # "unit_desc": "ACRES",
        "state_alpha": state_alpha.upper() if state_alpha else None,
        "source_desc": "SURVEY",
    }
    return quickstats_request(params)


def search_quickstats(
    commodity_desc: Optional[str] = None,
    year: Optional[int] = None,
    state_alpha: Optional[str] = None,
    statisticcat_desc: Optional[str] = None,
    unit_desc: Optional[str] = None,
    short_desc: Optional[str] = None,
) -> Dict[str, Any]:
    """Generic Quick Stats search with common filters.

    Note: Field names follow the Quick Stats schema exactly.
    """
    params = {
        "commodity_desc": commodity_desc.upper() if commodity_desc else None,
        "year": str(year) if year else None,
        "state_alpha": state_alpha.upper() if state_alpha else None,
        "statisticcat_desc": statisticcat_desc.upper() if statisticcat_desc else None,
        "unit_desc": unit_desc,
        "short_desc": short_desc,
        "source_desc": "SURVEY",
    }
    return quickstats_request(params)

