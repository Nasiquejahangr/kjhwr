import pandas as pd
import pytest

from main import compute_metrics, select_latest_forecast


def test_select_latest_forecast_ignores_publications_after_cutoff():
    forecasts = pd.DataFrame(
        [
            {
                "startTime": "2026-01-02T12:00:00Z",
                "publishTime": "2026-01-01T08:00:00Z",
                "generation": 100,
            },
            {
                "startTime": "2026-01-02T12:00:00Z",
                "publishTime": "2026-01-01T09:00:00Z",
                "generation": 110,
            },
            {
                "startTime": "2026-01-02T12:00:00Z",
                "publishTime": "2026-01-01T09:01:00Z",
                "generation": 999,
            },
        ]
    )

    selected = select_latest_forecast(forecasts, cutoff_hour=9)

    assert len(selected) == 1
    assert selected.iloc[0]["generation"] == 110
    assert selected.iloc[0]["publishTime"] == pd.Timestamp("2026-01-01T09:00:00Z")


def test_select_latest_forecast_picks_latest_eligible_publication():
    forecasts = pd.DataFrame(
        [
            {
                "startTime": "2026-01-03T00:00:00Z",
                "publishTime": "2026-01-01T08:00:00Z",
                "generation": 100,
            },
            {
                "startTime": "2026-01-03T00:00:00Z",
                "publishTime": "2026-01-02T08:30:00Z",
                "generation": 120,
            },
            {
                "startTime": "2026-01-03T00:00:00Z",
                "publishTime": "2026-01-02T09:01:00Z",
                "generation": 999,
            },
        ]
    )

    selected = select_latest_forecast(forecasts, cutoff_hour=9)

    assert selected.iloc[0]["generation"] == 120


def test_compute_metrics_hand_calculated_example():
    frame = pd.DataFrame(
        {"forecast": [110, 180], "actual": [100, 200], "error": [10, -20]}
    )

    metrics = compute_metrics(frame)

    assert metrics["n"] == 2
    assert metrics["mae"] == pytest.approx(15)
    assert metrics["rmse"] == pytest.approx((250) ** 0.5)
    assert metrics["bias"] == pytest.approx(-5)
    assert metrics["p95_absolute_error"] == pytest.approx(19.5)
    assert metrics["error_percent"] == pytest.approx(30 / 300 * 100)


def test_compute_metrics_returns_zero_count_for_empty_data():
    assert compute_metrics(pd.DataFrame()) == {"n": 0}
