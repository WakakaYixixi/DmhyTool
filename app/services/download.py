from app.download_station import (
    DownloadStationAuthenticationError,
    DownloadStationClient,
    DownloadStationError,
)
from app.services.magnet import export_magnets


async def submit_downloads(
    items: list[dict[str, str]], client: DownloadStationClient
) -> dict[str, list[dict[str, str]]]:
    client.require_configuration()
    exported = await export_magnets(items)

    successful: list[dict[str, str]] = []
    failed: list[dict[str, str]] = [
        {
            "resource": item["resource"],
            "title": item.get("title", ""),
            "stage": "magnet",
            "reason": item["reason"],
        }
        for item in exported["failures"]
    ]

    magnets = exported["magnets"]
    for index, item in enumerate(magnets):
        try:
            await client.create_task(item["magnet"])
            successful.append(
                {
                    "resource_id": item["resource_id"],
                    "title": item["title"],
                    "detail_url": item["detail_url"],
                }
            )
        except DownloadStationAuthenticationError as exc:
            # Repeating a known-bad login for every remaining item would only
            # create unnecessary authentication attempts against DSM.
            for remaining in magnets[index:]:
                failed.append(
                    {
                        "resource": remaining["detail_url"],
                        "title": remaining["title"],
                        "stage": "download_station",
                        "reason": str(exc),
                    }
                )
            break
        except DownloadStationError as exc:
            failed.append(
                {
                    "resource": item["detail_url"],
                    "title": item["title"],
                    "stage": "download_station",
                    "reason": str(exc),
                }
            )

    return {"success": successful, "failed": failed}
