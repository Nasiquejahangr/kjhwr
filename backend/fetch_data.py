"""Download Elexon FUELHH WIND actuals and WINDFOR forecast history."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
START = datetime(2025, 12, 31, tzinfo=timezone.utc)
# Elexon's upper timestamp bound is inclusive on some streams; this covers Feb 2.
END = datetime(2026, 2, 3, tzinfo=timezone.utc)
CHUNK_DAYS = 7
DATA_DIR = Path(__file__).parent / "data"


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    raise ValueError("Unexpected Elexon response: expected an array or {data: array}")


def fetch_dataset(
    client: httpx.Client, dataset: str, start: datetime, end: datetime
) -> list[dict[str, Any]]:
    """Fetch a dataset in non-overlapping seven-day publication-time windows."""
    rows: list[dict[str, Any]] = []
    chunk_start = start
    while chunk_start < end:
        chunk_end = min(chunk_start + timedelta(days=CHUNK_DAYS), end)
        params: dict[str, str] = {
            "publishDateTimeFrom": chunk_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "publishDateTimeTo": chunk_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        if dataset == "FUELHH":
            params["fuelType"] = "WIND"
        response = client.get(f"{BASE_URL}/{dataset}/stream", params=params)
        response.raise_for_status()
        rows.extend(_rows(response.json()))
        print(f"{dataset}: {params['publishDateTimeFrom']} to "
              f"{params['publishDateTimeTo']} -> {len(rows)} cumulative rows")
        chunk_start = chunk_end

    unique_rows: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = (
            row.get("startTime"),
            row.get("publishTime"),
            row.get("fuelType"),
        )
        unique_rows[key] = row
    return list(unique_rows.values())


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120.0) as client:
        actuals = fetch_dataset(client, "FUELHH", START, END)
        forecasts = fetch_dataset(client, "WINDFOR", START, END)
    for name, rows in (("actual.json", actuals), ("forecast.json", forecasts)):
        path = DATA_DIR / name
        path.write_text(json.dumps(rows, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"Saved {len(rows):,} rows to {path}")


if __name__ == "__main__":
    main()
