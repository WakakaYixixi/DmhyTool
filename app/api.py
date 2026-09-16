from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import DownloadStationSettings
from app.download_station import (
    DownloadStationClient,
    DownloadStationConfigurationError,
)
from app.services.dmhy import DMHYError
from app.services.download import submit_downloads
from app.services.magnet import export_magnets
from app.services.search import search_dmhy


router = APIRouter(prefix="/api")


class MagnetItem(BaseModel):
    resource: str = Field(min_length=1, max_length=500)
    title: str = Field(default="", max_length=500)


class MagnetRequest(BaseModel):
    items: list[MagnetItem] = Field(min_length=1, max_length=50)


@lru_cache
def get_download_station_client() -> DownloadStationClient:
    return DownloadStationClient(DownloadStationSettings.from_env())


@router.get("/search")
async def search(
    q: Annotated[str, Query(min_length=1, max_length=100)],
) -> dict[str, object]:
    keyword = q.strip()
    if not keyword:
        raise HTTPException(status_code=422, detail="搜索词不能为空")

    try:
        results = await search_dmhy(keyword)
    except DMHYError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"query": keyword, "count": len(results), "results": results}


@router.post("/magnets")
async def magnets(payload: MagnetRequest) -> dict[str, list[dict[str, str]]]:
    return await export_magnets([item.model_dump() for item in payload.items])


@router.get("/download/status")
async def download_status(
    client: Annotated[DownloadStationClient, Depends(get_download_station_client)],
) -> dict[str, object]:
    return {
        "configured": client.configured,
        "download_dir": client.settings.download_dir,
    }


@router.post("/download")
async def download(
    payload: MagnetRequest,
    client: Annotated[DownloadStationClient, Depends(get_download_station_client)],
) -> dict[str, list[dict[str, str]]]:
    try:
        return await submit_downloads(
            [item.model_dump() for item in payload.items], client
        )
    except DownloadStationConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
