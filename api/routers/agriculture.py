"""USDA Quick Stats agriculture data endpoints."""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agriculture", tags=["Agriculture (USDA)"])


@router.get("/yield")
async def get_crop_yield(
    commodity: str = Query(..., description="Commodity, e.g., CORN, WHEAT"),
    year: int = Query(..., ge=1900, le=2100),
    state: Optional[str] = Query(None, description="State alpha code, e.g., IA"),
):
    """Get crop yield statistics from USDA Quick Stats."""
    try:
        from irrigation_agent.service.agriculture_service import get_crop_yield
        result = get_crop_yield(commodity, year, state)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting crop yield: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/area_planted")
async def get_area_planted(
    commodity: str = Query(..., description="Commodity, e.g., CORN, WHEAT"),
    year: int = Query(..., ge=1900, le=2100),
    state: Optional[str] = Query(None, description="State alpha code, e.g., IA"),
):
    """Get area planted statistics from USDA Quick Stats."""
    try:
        from irrigation_agent.service.agriculture_service import get_area_planted
        result = get_area_planted(commodity, year, state)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting area planted: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_agriculture_data(
    commodity: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    state: Optional[str] = Query(None),
    statistic: Optional[str] = Query(None, description="statisticcat_desc, e.g., YIELD, AREA PLANTED"),
    unit: Optional[str] = Query(None, description="unit_desc"),
    desc: Optional[str] = Query(None, description="short_desc"),
):
    """Generic USDA Quick Stats search with common filters."""
    try:
        from irrigation_agent.service.agriculture_service import search_quickstats
        result = search_quickstats(
            commodity_desc=commodity,
            year=year,
            state_alpha=state,
            statisticcat_desc=statistic,
            unit_desc=unit,
            short_desc=desc,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in Quick Stats search: {e}")
        raise HTTPException(status_code=500, detail=str(e))
