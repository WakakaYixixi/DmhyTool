import httpx


DMHY_ORIGIN = "https://share.dmhy.org"
USER_AGENT = (
    "Mozilla/5.0 (compatible; DMHYTool/0.2; "
    "+https://dmhy.maskpic.com)"
)
TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)


class DMHYError(RuntimeError):
    """A readable error caused by an upstream DMHY request or response."""


def create_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        timeout=TIMEOUT,
        follow_redirects=False,
    )


def checked_html(response: httpx.Response) -> str:
    if response.status_code != 200:
        raise DMHYError(f"DMHY 返回 HTTP {response.status_code}")
    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type:
        raise DMHYError("DMHY 返回了非 HTML 内容")
    return response.text
