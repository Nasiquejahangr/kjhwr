"""API and pure forecast-analysis functions for the UK Wind Forecast Monitor."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

DATA_DIR = Path(__file__).parent / "data"
JANUARY_START = pd.Timestamp("2026-01-02T00:00:00Z")
FEBRUARY_END = pd.Timestamp("2026-02-02T00:00:00Z")
HORIZON_BUCKETS = [
    ("0-6", 0, 6),
    ("6-12", 6, 12),
    ("12-24", 12, 24),
    ("24-36", 24, 36),
    ("36-48", 36, 48),
    ("48+", 48, float("inf")),
]


def _read_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        rows = json.load(file)
    if not isinstance(rows, list):
        raise ValueError(f"{path} must contain a JSON array")
    return rows


def _timestamps(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column in frame:
            frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce")
    return frame


def select_latest_forecast(
    forecast_df: pd.DataFrame, cutoff_hour: int = 9
) -> pd.DataFrame:
    """Choose the latest forecast published by each delivery day's cutoff."""
    if not 0 <= cutoff_hour <= 23:
        raise ValueError("cutoff_hour must be between 0 and 23")
    required = {"startTime", "publishTime"}
    if forecast_df.empty:
        return forecast_df.copy()
    if not required.issubset(forecast_df.columns):
        raise ValueError(f"forecast_df must contain {sorted(required)}")

    forecasts = _timestamps(forecast_df.copy(), ["startTime", "publishTime"])
    forecasts = forecasts.dropna(subset=["startTime", "publishTime"])
    forecasts = forecasts[
        (forecasts["startTime"] >= JANUARY_START)
        & (forecasts["startTime"] < FEBRUARY_END)
    ].copy()
    cutoff = (
        forecasts["startTime"].dt.normalize()
        - timedelta(days=1)
        + timedelta(hours=cutoff_hour)
    )
    forecasts = forecasts[forecasts["publishTime"] <= cutoff]
    return (
        forecasts.sort_values(["publishTime"], kind="stable")
        .drop_duplicates("startTime", keep="last")
        .sort_values("startTime")
        .reset_index(drop=True)
    )


def join_forecast_actuals(
    forecast_df: pd.DataFrame, actual_df: pd.DataFrame, cutoff_hour: int = 9
) -> pd.DataFrame:
    """Select decision-time forecasts and inner-join final actuals by start time."""
    forecasts = select_latest_forecast(forecast_df, cutoff_hour)
    if forecasts.empty or actual_df.empty:
        return pd.DataFrame(
            columns=["startTime", "publishTime", "forecast", "actual", "error"]
        )

    actuals = _timestamps(actual_df.copy(), ["startTime", "publishTime"])
    actuals = actuals.dropna(subset=["startTime"])
    if "publishTime" in actuals:
        actuals = actuals.sort_values("publishTime", kind="stable")
    actuals = actuals.drop_duplicates("startTime", keep="last")
    actuals = actuals.rename(columns={"generation": "actual"})
    forecasts = forecasts.rename(columns={"generation": "forecast"})
    joined = forecasts.merge(
        actuals[["startTime", "actual"]], on="startTime", how="inner"
    )
    joined["error"] = joined["forecast"] - joined["actual"]
    return joined.sort_values("startTime").reset_index(drop=True)


def compute_metrics(frame: pd.DataFrame) -> dict[str, int | float | None]:
    """Calculate forecast error metrics; error is forecast minus actual."""
    if frame.empty:
        return {"n": 0}
    absolute_error = frame["error"].abs()
    actual_total = frame["actual"].sum()
    return {
        "n": int(len(frame)),
        "mae": float(absolute_error.mean()),
        "rmse": float((frame["error"].pow(2).mean()) ** 0.5),
        "bias": float(frame["error"].mean()),
        "p95_absolute_error": float(absolute_error.quantile(0.95)),
        "error_percent": (
            float(absolute_error.sum() / actual_total * 100)
            if actual_total != 0
            else None
        ),
    }


def _day_rows(frame: pd.DataFrame, delivery_day: date | None) -> pd.DataFrame:
    if delivery_day is None or frame.empty:
        return frame
    day_start = pd.Timestamp(delivery_day, tz="UTC")
    return frame[
        (frame["startTime"] >= day_start)
        & (frame["startTime"] < day_start + timedelta(days=1))
    ]


def _json_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    output = frame.copy()
    for column in ("startTime", "publishTime"):
        output[column] = output[column].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return output[["startTime", "publishTime", "forecast", "actual", "error"]].to_dict(
        orient="records"
    )


def compute_horizon_metrics(
    forecast_df: pd.DataFrame, actual_df: pd.DataFrame
) -> list[dict[str, int | float | str | None]]:
    """Calculate MAE for every published forecast matching January target times."""
    forecasts = _timestamps(forecast_df.copy(), ["startTime", "publishTime"])
    actuals = _timestamps(actual_df.copy(), ["startTime", "publishTime"])
    if forecasts.empty or actuals.empty:
        return [{"bucket": label, "n": 0, "mae": None} for label, _, _ in HORIZON_BUCKETS]
    forecasts = forecasts.dropna(subset=["startTime", "publishTime"])
    forecasts = forecasts[
        (forecasts["startTime"] >= JANUARY_START)
        & (forecasts["startTime"] < FEBRUARY_END)
    ]
    actuals = actuals.dropna(subset=["startTime"])
    if actuals.empty:
        return [{"bucket": label, "n": 0, "mae": None} for label, _, _ in HORIZON_BUCKETS]
    if "publishTime" in actuals:
        actuals = actuals.sort_values("publishTime", kind="stable")
    actuals = actuals.drop_duplicates("startTime", keep="last")
    forecast_actuals = forecasts.merge(
        actuals[["startTime", "generation"]].rename(columns={"generation": "actual"}),
        on="startTime",
        how="inner",
    )
    forecast_actuals = forecast_actuals.copy()
    forecast_actuals["horizon_hours"] = (
        forecast_actuals["startTime"] - forecast_actuals["publishTime"]
    ).dt.total_seconds() / 3600
    forecast_actuals["absolute_error"] = (
        forecast_actuals["generation"] - forecast_actuals["actual"]
    ).abs()

    results = []
    for label, lower, upper in HORIZON_BUCKETS:
        in_bucket = forecast_actuals[
            (forecast_actuals["horizon_hours"] >= lower)
            & (forecast_actuals["horizon_hours"] < upper)
        ]
        results.append(
            {
                "bucket": label,
                "n": int(len(in_bucket)),
                "mae": (
                    float(in_bucket["absolute_error"].mean())
                    if not in_bucket.empty
                    else None
                ),
            }
        )
    return results


def _load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    actuals = pd.DataFrame(_read_rows(DATA_DIR / "actual.json"))
    forecasts = pd.DataFrame(_read_rows(DATA_DIR / "forecast.json"))
    return actuals, forecasts


@asynccontextmanager
async def lifespan(_: FastAPI):
    global actual_data, forecast_data
    actual_data, forecast_data = _load_data()
    yield


app = FastAPI(title="UK Wind Forecast Monitor API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

actual_data = pd.DataFrame()
forecast_data = pd.DataFrame()


def _validate_day(day: date | None) -> None:
    if day is not None and not (
        date(2026, 1, 2) <= day <= date(2026, 2, 1)
    ):
        raise HTTPException(
            status_code=422, detail="day must be between 2026-01-02 and 2026-02-01"
        )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/series")
def series(
    cutoff_hour: int = Query(default=9, ge=0, le=23),
    day: date = Query(default=date(2026, 1, 2)),
) -> list[dict[str, Any]]:
    _validate_day(day)
    joined = _day_rows(
        join_forecast_actuals(forecast_data, actual_data, cutoff_hour), day
    )
    return _json_records(joined)


@app.get("/api/metrics")
def metrics(
    cutoff_hour: int = Query(default=9, ge=0, le=23),
    day: date | None = Query(default=None),
) -> dict[str, int | float | None]:
    _validate_day(day)
    joined = join_forecast_actuals(forecast_data, actual_data, cutoff_hour)
    return compute_metrics(_day_rows(joined, day))


@app.get("/api/horizon")
def horizon() -> list[dict[str, int | float | str | None]]:
    return compute_horizon_metrics(forecast_data, actual_data)
