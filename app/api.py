from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.dmhy import DMHYError
from app.services.magnet import export_magnets
from app.services.search import search_dmhy


router = APIRouter(prefix="/api")


class MagnetItem(BaseModel):
    resource: str = Field(min_length=1, max_length=500)
    title: str = Field(default="", max_length=500)


class MagnetRequest(BaseModel):
    items: list[MagnetItem] = Field(min_length=1, max_length=50)


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
