import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs

import httpx

from app.config import DownloadStationSettings
from app.download_station import (
    DownloadStationAuthenticationError,
    DownloadStationClient,
    DownloadStationError,
)
from app.services.download import submit_downloads


def settings(download_dir: str = "") -> DownloadStationSettings:
    return DownloadStationSettings(
        url="https://nas.example.com",
        username="test-user",
        password="secret-password",
        download_dir=download_dir,
        verify_ssl=True,
    )


def api_info() -> dict[str, object]:
    return {
        "success": True,
        "data": {
            "SYNO.API.Auth": {"path": "entry.cgi", "maxVersion": 7},
            "SYNO.DownloadStation.Task": {
                "path": "DownloadStation/task.cgi",
                "maxVersion": 3,
            },
        },
    }


class DownloadStationClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_login_and_create_task_with_destination(self) -> None:
        requests: list[dict[str, list[str]]] = []
        task_tokens: list[str | None] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = parse_qs(request.content.decode())
            requests.append(data)
            method = data["method"][0]
            if method == "query":
                payload = api_info()
            elif method == "login":
                payload = {
                    "success": True,
                    "data": {"sid": "test-sid", "synotoken": "test-token"},
                }
            else:
                task_tokens.append(request.headers.get("x-syno-token"))
                payload = {"success": True}
            return httpx.Response(200, json=payload)

        client = DownloadStationClient(
            settings("downloads/anime"), transport=httpx.MockTransport(handler)
        )
        await client.create_task("magnet:?xt=urn:btih:abc")
        await client.create_task("magnet:?xt=urn:btih:def")

        self.assertEqual(
            [item["method"][0] for item in requests],
            ["query", "login", "create", "create"],
        )
        create = requests[-1]
        self.assertEqual(create["_sid"], ["test-sid"])
        self.assertNotIn("SynoToken", create)
        self.assertEqual(create["destination"], ["downloads/anime"])
        self.assertEqual(task_tokens, ["test-token", "test-token"])
        self.assertNotIn("secret-password", repr(client.settings))

    async def test_expired_session_logs_in_again_once(self) -> None:
        login_count = 0
        create_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal login_count, create_count
            data = parse_qs(request.content.decode())
            method = data["method"][0]
            if method == "query":
                payload = api_info()
            elif method == "login":
                login_count += 1
                payload = {"success": True, "data": {"sid": f"sid-{login_count}"}}
            else:
                create_count += 1
                payload = {"success": create_count == 2}
                if not payload["success"]:
                    payload["error"] = {"code": 106}
            return httpx.Response(200, json=payload)

        client = DownloadStationClient(settings(), transport=httpx.MockTransport(handler))
        await client.create_task("magnet:?xt=urn:btih:abc")
        self.assertEqual(login_count, 2)
        self.assertEqual(create_count, 2)

    async def test_login_failure_has_clear_message(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            data = parse_qs(request.content.decode())
            payload = api_info() if data["method"][0] == "query" else {
                "success": False,
                "error": {"code": 400},
            }
            return httpx.Response(200, json=payload)

        client = DownloadStationClient(settings(), transport=httpx.MockTransport(handler))
        with self.assertRaisesRegex(
            DownloadStationAuthenticationError, "请检查账号密码"
        ):
            await client.create_task("magnet:?xt=urn:btih:abc")


class SubmitDownloadsTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_task_failure_does_not_stop_other_tasks(self) -> None:
        client = MagicMock(spec=DownloadStationClient)
        client.require_configuration.return_value = None
        client.create_task = AsyncMock(
            side_effect=[DownloadStationError("API error"), None]
        )
        exported = {
            "magnets": [
                {
                    "resource_id": "1",
                    "title": "first",
                    "detail_url": "https://share.dmhy.org/topics/view/1_a.html",
                    "magnet": "magnet:?xt=urn:btih:first",
                },
                {
                    "resource_id": "2",
                    "title": "second",
                    "detail_url": "https://share.dmhy.org/topics/view/2_b.html",
                    "magnet": "magnet:?xt=urn:btih:second",
                },
            ],
            "failures": [],
        }
        with patch(
            "app.services.download.export_magnets", new=AsyncMock(return_value=exported)
        ):
            result = await submit_downloads([], client)

        self.assertEqual([item["title"] for item in result["success"]], ["second"])
        self.assertEqual([item["title"] for item in result["failed"]], ["first"])
        self.assertEqual(client.create_task.await_count, 2)


if __name__ == "__main__":
    unittest.main()
