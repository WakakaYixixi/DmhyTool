import os
from dataclasses import dataclass, field


def _env_bool(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


@dataclass(frozen=True)
class DownloadStationSettings:
    url: str
    username: str
    password: str = field(repr=False)
    download_dir: str
    verify_ssl: bool

    @classmethod
    def from_env(cls) -> "DownloadStationSettings":
        return cls(
            url=os.getenv("DSM_URL", "").strip().rstrip("/"),
            username=os.getenv("DSM_USERNAME", "").strip(),
            password=os.getenv("DSM_PASSWORD", ""),
            download_dir=os.getenv("DSM_DOWNLOAD_DIR", "").strip(),
            verify_ssl=_env_bool("DSM_VERIFY_SSL"),
        )

    @property
    def configured(self) -> bool:
        return bool(self.url and self.username and self.password)
