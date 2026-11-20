# UK Wind Forecast Monitor

The UK Wind Forecast Monitor helps a UK energy buyer review the national wind generation forecast that was available at the day-ahead purchase decision, then compare it with Elexon-reported actual generation. It uses only Elexon BMRS FUELHH WIND actuals and WINDFOR forecasts, stores a reproducible historical snapshot in the backend, and presents forecast error metrics by delivery day and forecast horizon.

## AI tools used

GitHub Copilot and Claude were used to assist with the implementation and documentation.

## Links

- Live demo: <VERCEL_FRONTEND_URL>
- Backend API: <VERCEL_BACKEND_URL>
- Video walkthrough: <YOUTUBE_UNLISTED_URL>

## Files and directories

```text
.
├── backend/                         # FastAPI API and Elexon data processing
│   ├── data/                        # Snapshotted Elexon source records shipped with the app
│   │   ├── actual.json              # FUELHH WIND actual generation records
│   │   └── forecast.json            # WINDFOR forecast publication records
│   ├── tests/                       # Backend logic tests
│   │   └── test_logic.py            # Cutoff selection, metrics, and empty-data tests
│   ├── Dockerfile                   # Python 3.11 API image
│   ├── fetch_data.py                # Seven-day Elexon download and deduplication
│   ├── main.py                      # FastAPI endpoints and forecast analysis functions
│   ├── requirements-dev.txt         # Test dependencies layered over runtime packages
│   ├── requirements.txt             # Minimal backend runtime dependencies
│   └── vercel.json                  # Vercel Python function and data-file configuration
├── docs/                            # Project walkthrough material
│   └── VIDEO_SCRIPT.md              # Timed client pitch and technical walkthrough
├── frontend/                        # Responsive React and Vite application
│   ├── src/                         # Application components and styles
│   │   ├── App.jsx                  # Controls, API requests, cards, and charts
│   │   ├── main.jsx                 # React entry point
│   │   └── styles.css               # Responsive visual styling
│   ├── Dockerfile                   # Multi-stage Vite build and Nginx image
│   ├── index.html                   # Vite HTML entry point
│   ├── package-lock.json            # Locked frontend dependency tree
│   ├── package.json                 # Frontend dependencies and scripts
│   ├── vercel.json                  # Vercel static-site build configuration
│   └── vite.config.js               # Vite and React plugin configuration
├── .gitignore                       # Ignores generated and local-only files
├── README.md                        # Setup, methodology, API, findings, and deployment guide
└── docker-compose.yml               # Local backend and frontend services
```

## Start the application

### Docker

From the project root:

```sh
docker compose up --build
```

Open the frontend at [http://localhost:3000](http://localhost:3000). The API is at [http://localhost:8000](http://localhost:8000).

### Without Docker

Use Python 3.11 and Node.js 20 or newer. In one terminal:

```sh
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

In another terminal:

```sh
cd frontend
npm ci
VITE_API_URL=http://localhost:8000 npm run dev
```

Open the Vite URL printed in the terminal (normally [http://localhost:5173](http://localhost:5173)).

### Refresh the Elexon snapshot

The included JSON files let the API start without an Elexon call. To refresh them, install the backend runtime dependencies and run:

```sh
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python fetch_data.py
```

The fetcher requests publication-time windows in seven-day chunks from 31 December 2025 through 2 February 2026, requests WIND explicitly for FUELHH, accepts either an array or a `{"data": [...]}` response, and deduplicates by start time and publication time. It replaces `data/actual.json` and `data/forecast.json`.

The live Swagger contract and a sample response were checked. Both stream endpoints accept `publishDateTimeFrom` and `publishDateTimeTo`; FUELHH also supports `fuelType=WIND`. The live stream returned a plain JSON array, and the parser also supports the documented envelope shape. No parameter or response-shape adjustment was needed.

## Methodology

- A purchase decision for delivery day D is taken on D-1. The default cutoff is 09:00 UK time on D-1. The API accepts cutoff hours from 0 to 23; the UI offers 08:00 to 12:00.
- Decisions made in January 2026 cover delivery starts from 2 January through 1 February 2026, inclusive. For each target `startTime`, the app chooses the forecast with the greatest `publishTime` not later than that delivery day's decision cutoff.
- Forecasts after the cutoff are excluded. The selected forecast is inner-joined with FUELHH WIND actuals by `startTime`; if an actual has multiple publications, the latest publication is retained. The signed error is `forecast - actual`, so positive values mean wind was over-forecast.
- Data timestamps are UTC. UTC equals UK local time during this January study period, so no daylight-saving conversion is required.
- Metrics use only target periods with both a selected forecast and an actual:
  - `n`: number of matched target periods.
  - `MAE = sum(abs(error)) / n`.
  - `RMSE = sqrt(sum(error^2) / n)`.
  - `Bias = sum(error) / n`.
  - `P95 absolute error`: 95th percentile of `abs(error)` (pandas' linear quantile).
  - `Error % = sum(abs(error)) / sum(actual) * 100`.
- Horizon analysis uses every downloaded WINDFOR publication for January target periods that has an actual match, not only the decision-time forecast. Horizon is `(startTime - publishTime)` in hours, placed in lower-inclusive, upper-exclusive buckets `0-6`, `6-12`, `12-24`, `24-36`, `36-48`, and `48+`.

## API endpoints

| Method and path | Parameters | Result |
|---|---|---|
| `GET /health` | None | `{"status":"ok"}` |
| `GET /api/series` | `cutoff_hour` (default 9), `day` (default `2026-01-02`; allowed range `2026-01-02` through `2026-02-01`) | Matched daily points: `startTime`, `publishTime`, `forecast`, `actual`, and `error`. |
| `GET /api/metrics` | `cutoff_hour` (default 9), optional `day` (same allowed range) | Metrics for one delivery day, or all January decisions when `day` is omitted. An empty result is `{"n":0}`. |
| `GET /api/horizon` | None | Sample count and MAE for each forecast-horizon bucket. |

Invalid cutoff or day values return HTTP 422; empty series and horizon buckets are returned without failing.

## Key findings (cutoff 09:00 UTC)

The included snapshot contains **1,633 actual rows** and **19,856 forecast rows**. The decision-time join produced **744 matched hourly periods** across all 31 delivery days (24 forecast periods per day):

- January-decision MAE was **2,022.5 MW**, RMSE **2,497.4 MW**, mean bias **+1,745.9 MW**, P95 absolute error **5,268.4 MW**, and absolute error was **17.9%** of total actual generation.
- The selected decision-time forecast publication was **07:30 UTC on every matched period**, the latest publication in the available data before the 09:00 cutoff.
- Daily MAE varied materially: **683.6 MW** on 19 January and **5,329.0 MW** on 28 January. The 2 January delivery-day MAE was **3,070.4 MW**.
- For horizon analysis, MAE increased from **1,654.1 MW** at 0-6 hours (1,488 forecast rows) to **2,307.4 MW** at 48+ hours (2,510 forecast rows). The full bucket values appear in the horizon chart.

These are descriptive results for this Elexon snapshot and this assumed cutoff, not a forward price, trade recommendation, or guarantee of future performance.

## Limitations and future work

- Only national-level Elexon BMRS wind actuals and forecasts are used; there is no weather, regional, price, or other-market data.
- The analysis assumes one daily cutoff (09:00 by default) and treats January UTC as UK time.
- Forecast rows are hourly while FUELHH actuals are half-hourly. The inner join therefore scores the 24 matching hourly targets per delivery day, rather than interpolating forecasts or inventing half-hour values.
- The historical snapshot is limited to publication times from 31 December 2025 through 2 February 2026. A refresh can change source records and resulting metrics.
- Future improvements could include additional months, cutoff sensitivity analysis, a forecast-vintage/quality audit, and richer market context while keeping the current analysis strictly Elexon-only.

## Deployment to Vercel

Deploy as two separate Vercel projects:

1. Create a backend project with **Root Directory** `backend`. The Python function is routed by `backend/vercel.json`, which also includes both JSON data files in the deployment. The backend runtime only needs the packages in `backend/requirements.txt`.
2. Create a frontend project with **Root Directory** `frontend`. Set its environment variable `VITE_API_URL` to the deployed backend base URL (for example, `https://your-backend.vercel.app`, without a trailing slash), then deploy. The frontend Vercel build configuration is in `frontend/vercel.json`.
3. Replace the three placeholders above with the deployed frontend URL, backend URL, and unlisted video URL.

## Tests

From `backend/`, install the test dependencies and run the focused suite:

```sh
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

The tests cover filtering forecasts published after cutoff, choosing the latest eligible publication, hand-calculated error metrics, and the empty-metrics response.
