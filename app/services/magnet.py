import asyncio
import re
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup, Tag

from app.services.dmhy import DMHY_ORIGIN, DMHYError, checked_html, create_client


ALLOWED_HOSTS = {"share.dmhy.org", "dmhy.org", "www.dmhy.org"}
DETAIL_PATH_RE = re.compile(r"^/topics/view/(\d+)(?:_[^/?#]*)?\.html$")
RESOURCE_ID_RE = re.compile(r"^\d{1,12}$")


def normalize_detail_resource(resource: str) -> tuple[str, str]:
    value = resource.strip()
    if RESOURCE_ID_RE.fullmatch(value):
        return value, f"{DMHY_ORIGIN}/topics/view/{value}_.html"

    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("只允许 HTTP/HTTPS 的 DMHY 详情页地址")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("详情页地址端口无效") from exc
    if parsed.username or parsed.password or port not in {None, 80, 443}:
        raise ValueError("详情页地址包含不允许的认证信息或端口")
    if (parsed.hostname or "").lower() not in ALLOWED_HOSTS:
        raise ValueError("只允许请求 DMHY 官方域名")
    if parsed.query or parsed.fragment:
        raise ValueError("详情页地址不能包含查询参数或片段")

    path_match = DETAIL_PATH_RE.fullmatch(parsed.path)
    if path_match is None:
        raise ValueError("不是合法的 DMHY 资源详情页")

    resource_id = path_match.group(1)
    return resource_id, f"{DMHY_ORIGIN}{parsed.path}"


def parse_magnet_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    anchor = soup.select_one('a.magnet[href^="magnet:?"]')
    if not isinstance(anchor, Tag):
        anchor = soup.select_one('a[href^="magnet:?"]')
    if not isinstance(anchor, Tag):
        raise DMHYError("详情页中未找到 magnet 链接")

    magnet = str(anchor.get("href", "")).strip()
    if not magnet.lower().startswith("magnet:?xt=urn:btih:"):
        raise DMHYError("详情页中的 magnet 链接格式无效")
    return magnet


async def _fetch_magnet(client: httpx.AsyncClient, detail_url: str) -> str:
    try:
        response = await client.get(detail_url)
    except httpx.TimeoutException as exc:
        raise DMHYError("请求详情页超时") from exc
    except httpx.RequestError as exc:
        raise DMHYError("无法连接 DMHY 详情页") from exc
    return parse_magnet_html(checked_html(response))


async def export_magnets(
    items: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    semaphore = asyncio.Semaphore(3)

    async with create_client() as client:

        async def process(item: dict[str, str]) -> tuple[str, dict[str, str]]:
            resource = item["resource"]
            title = item.get("title", "")
            try:
                resource_id, detail_url = normalize_detail_resource(resource)
                async with semaphore:
                    magnet = await _fetch_magnet(client, detail_url)
                return "success", {
                    "resource_id": resource_id,
                    "title": title,
                    "detail_url": detail_url,
                    "magnet": magnet,
                }
            except (ValueError, DMHYError) as exc:
                return "failure", {
                    "resource": resource,
                    "title": title,
                    "reason": str(exc),
                }

        processed = await asyncio.gather(*(process(item) for item in items))

    magnets = [value for status, value in processed if status == "success"]
    failures = [value for status, value in processed if status == "failure"]
    return {"magnets": magnets, "failures": failures}
