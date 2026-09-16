import asyncio
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.config import DownloadStationSettings


SESSION_NAME = "DownloadStation"
SESSION_ERROR_CODES = {106, 107, 119}
REQUEST_TIMEOUT = httpx.Timeout(connect=5.0, read=20.0, write=10.0, pool=5.0)

COMMON_ERRORS = {
    100: "未知错误",
    101: "API、方法或版本参数缺失",
    102: "DSM 不支持请求的 API",
    103: "DSM 不支持请求的方法",
    104: "DSM 不支持请求的 API 版本",
    105: "当前 DSM 账号没有 Download Station 权限",
    106: "DSM 会话已超时",
    107: "DSM 会话被重复登录中断",
    109: "DSM 网络不稳定或系统繁忙",
    110: "DSM 网络不稳定或系统繁忙",
    111: "DSM 网络不稳定或系统繁忙",
    117: "DSM 网络不稳定或系统繁忙",
    118: "DSM 网络不稳定或系统繁忙",
    119: "DSM 会话无效",
    150: "DSM 登录 IP 与请求 IP 不一致",
}

LOGIN_ERRORS = {
    400: "Download Station 登录失败，请检查账号密码",
    401: "Download Station 登录失败：DSM 账号已停用",
    402: "Download Station 登录失败：DSM 账号权限被拒绝",
    403: "Download Station 登录失败：该账号需要两步验证",
    404: "Download Station 登录失败：两步验证失败",
    406: "Download Station 登录失败：该账号强制要求两步验证",
    407: "Download Station 登录失败：来源 IP 已被 DSM 封锁",
    408: "Download Station 登录失败：密码已过期",
    409: "Download Station 登录失败：密码已过期",
    410: "Download Station 登录失败：必须先修改密码",
}

TASK_ERRORS = {
    400: "文件上传失败",
    401: "已达到 Download Station 任务数量上限",
    402: "目标下载目录权限不足",
    403: "目标下载目录不存在",
    404: "任务不存在",
    405: "无效的任务操作",
    406: "未配置默认下载目录",
    407: "无法设置目标下载目录",
    408: "指定文件不存在",
}


class DownloadStationError(RuntimeError):
    """A readable Download Station request or API error."""


class DownloadStationConfigurationError(DownloadStationError):
    """Download Station environment variables are incomplete."""


class DownloadStationAuthenticationError(DownloadStationError):
    """DSM rejected the configured account or authentication flow."""


@dataclass(frozen=True)
class APIInfo:
    path: str
    version: int


class DownloadStationClient:
    def __init__(
        self,
        settings: DownloadStationSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self._transport = transport
        self._sid = ""
        self._syno_token = ""
        self._auth_info: APIInfo | None = None
        self._task_info: APIInfo | None = None
        self._login_lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return self.settings.configured

    def require_configuration(self) -> None:
        if not self.configured:
            raise DownloadStationConfigurationError(
                "Download Station 尚未配置，请设置 DSM_URL、DSM_USERNAME 和 DSM_PASSWORD"
            )
        parsed = urlsplit(self.settings.url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise DownloadStationConfigurationError(
                "DSM_URL 格式无效，必须是完整的 HTTP/HTTPS 地址"
            )

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=f"{self.settings.url}/webapi/",
            timeout=REQUEST_TIMEOUT,
            verify=self.settings.verify_ssl,
            follow_redirects=False,
            transport=self._transport,
            headers={"Accept": "application/json"},
        )

    async def _post(self, path: str, data: dict[str, str]) -> dict[str, Any]:
        try:
            async with self._client() as client:
                response = await client.post(path, data=data)
        except httpx.TimeoutException as exc:
            raise DownloadStationError("连接 DSM 超时，请稍后重试") from exc
        except httpx.RequestError as exc:
            raise DownloadStationError("无法连接 DSM，请检查 DSM_URL 和网络") from exc

        if response.status_code != 200:
            raise DownloadStationError(f"DSM 返回 HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise DownloadStationError("DSM 返回了无法解析的响应") from exc
        if not isinstance(payload, dict):
            raise DownloadStationError("DSM 返回格式异常")
        return payload

    @staticmethod
    def _error_code(payload: dict[str, Any]) -> int:
        error = payload.get("error")
        if not isinstance(error, dict):
            return 100
        try:
            return int(error.get("code", 100))
        except (TypeError, ValueError):
            return 100

    async def _discover(self) -> None:
        if self._auth_info and self._task_info:
            return
        self.require_configuration()
        payload = await self._post(
            "entry.cgi",
            {
                "api": "SYNO.API.Info",
                "version": "1",
                "method": "query",
                "query": "SYNO.API.Auth,SYNO.DownloadStation.Task",
            },
        )
        if not payload.get("success"):
            code = self._error_code(payload)
            raise DownloadStationError(COMMON_ERRORS.get(code, f"DSM API 查询失败（错误码 {code}）"))

        data = payload.get("data")
        if not isinstance(data, dict):
            raise DownloadStationError("DSM API 查询响应缺少 data")
        auth = data.get("SYNO.API.Auth")
        task = data.get("SYNO.DownloadStation.Task")
        if not isinstance(auth, dict):
            raise DownloadStationError("DSM 未提供登录 API")
        if not isinstance(task, dict):
            raise DownloadStationError("DSM 未安装或未启用 Download Station")

        try:
            auth_version = min(int(auth.get("maxVersion", 0)), 6)
            task_version = min(int(task.get("maxVersion", 0)), 3)
        except (TypeError, ValueError) as exc:
            raise DownloadStationError("DSM API 版本信息格式异常") from exc
        if auth_version < 3:
            raise DownloadStationError("DSM 登录 API 版本过低")
        if task_version < 3:
            raise DownloadStationError("Download Station API 版本过低，不支持 magnet")

        self._auth_info = APIInfo(str(auth.get("path", "entry.cgi")), auth_version)
        self._task_info = APIInfo(str(task.get("path", "entry.cgi")), task_version)

    async def _login(self) -> None:
        async with self._login_lock:
            if self._sid:
                return
            await self._discover()
            assert self._auth_info is not None
            payload = await self._post(
                self._auth_info.path,
                {
                    "api": "SYNO.API.Auth",
                    "version": str(self._auth_info.version),
                    "method": "login",
                    "account": self.settings.username,
                    "passwd": self.settings.password,
                    "session": SESSION_NAME,
                    "format": "sid",
                    "enable_syno_token": "yes",
                },
            )
            if not payload.get("success"):
                code = self._error_code(payload)
                message = LOGIN_ERRORS.get(
                    code, COMMON_ERRORS.get(code, f"Download Station 登录失败（错误码 {code}）")
                )
                raise DownloadStationAuthenticationError(message)

            data = payload.get("data")
            if not isinstance(data, dict) or not data.get("sid"):
                raise DownloadStationAuthenticationError("Download Station 登录响应缺少 session id")
            self._sid = str(data["sid"])
            self._syno_token = str(data.get("synotoken", ""))

    def _clear_session(self) -> None:
        self._sid = ""
        self._syno_token = ""

    async def create_task(self, magnet: str) -> None:
        if not magnet.lower().startswith("magnet:?xt=urn:btih:"):
            raise DownloadStationError("拒绝提交无效的 magnet 链接")

        await self._login()
        assert self._task_info is not None
        for attempt in range(2):
            data = {
                "api": "SYNO.DownloadStation.Task",
                "version": str(self._task_info.version),
                "method": "create",
                "uri": magnet,
                "_sid": self._sid,
            }
            if self._syno_token:
                data["SynoToken"] = self._syno_token
            if self.settings.download_dir:
                data["destination"] = self.settings.download_dir

            payload = await self._post(self._task_info.path, data)
            if payload.get("success"):
                return

            code = self._error_code(payload)
            if code in SESSION_ERROR_CODES and attempt == 0:
                self._clear_session()
                await self._login()
                continue
            message = TASK_ERRORS.get(
                code, COMMON_ERRORS.get(code, f"Download Station API 错误（错误码 {code}）")
            )
            raise DownloadStationError(message)

        raise DownloadStationError("Download Station 会话恢复失败")
