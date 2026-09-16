import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from app.services.dmhy import DMHY_ORIGIN, DMHYError, checked_html, create_client


DETAIL_PATH_RE = re.compile(r"^/topics/view/(\d+)(?:_[^/?#]*)?\.html$")
DATE_RE = re.compile(r"\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}")


def _parse_row(row: Tag) -> dict[str, str] | None:
    title_cell = row.select_one("td.title")
    if title_cell is None:
        return None

    detail_anchor = title_cell.find("a", href=DETAIL_PATH_RE)
    if not isinstance(detail_anchor, Tag):
        return None

    href = str(detail_anchor.get("href", ""))
    path_match = DETAIL_PATH_RE.fullmatch(href)
    if path_match is None:
        return None

    cells = row.find_all("td", recursive=False)
    if not cells:
        return None

    date_match = DATE_RE.search(cells[0].get_text(" ", strip=True))
    published_at = date_match.group(0) if date_match else ""

    group_anchor = title_cell.select_one("span.tag a")
    group = group_anchor.get_text(" ", strip=True) if group_anchor else ""

    size = ""
    magnet_anchor = row.select_one("a.arrow-magnet")
    if magnet_anchor and magnet_anchor.parent:
        size_cell = magnet_anchor.parent.find_next_sibling("td")
        if isinstance(size_cell, Tag):
            size = size_cell.get_text(" ", strip=True)

    return {
        "id": path_match.group(1),
        "title": detail_anchor.get_text(" ", strip=True),
        "published_at": published_at,
        "size": size,
        "group": group,
        "detail_url": urljoin(DMHY_ORIGIN, href),
    }


def parse_search_html(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table#topic_list")
    if table is None:
        if soup.select_one('a[href^="/topics/view/"]'):
            raise DMHYError("DMHY 搜索页面结构发生变化，无法解析结果")
        return []

    rows = table.select("tbody tr")
    results = [parsed for row in rows if (parsed := _parse_row(row)) is not None]
    if rows and not results:
        raise DMHYError("DMHY 搜索页面结构发生变化，无法解析结果")
    return results


async def search_dmhy(keyword: str) -> list[dict[str, str]]:
    try:
        async with create_client() as client:
            response = await client.get(
                f"{DMHY_ORIGIN}/topics/list", params={"keyword": keyword}
            )
    except httpx.TimeoutException as exc:
        raise DMHYError("连接 DMHY 超时，请稍后重试") from exc
    except httpx.RequestError as exc:
        raise DMHYError("无法连接 DMHY，请检查网络后重试") from exc

    return parse_search_html(checked_html(response))
