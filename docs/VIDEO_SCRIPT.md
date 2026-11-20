# UK Wind Forecast Monitor — Video Script

**Target runtime: about 10 minutes total.** Replace the URL placeholders in the README and insert the deployed demo before recording.

## Part 1 — Client pitch (about 5 minutes)

### 0:00-0:45 — The buying problem

“When we buy electricity in the day-ahead market, we make the purchase before we know exactly how much wind the system will deliver. That makes the forecast a key part of deciding how much additional cover we may need. This monitor focuses on one narrow question: what national wind forecast was actually available by our assumed decision time, and how accurate was it afterward?”

### 0:45-1:20 — What the monitor includes

“The data here comes only from Elexon BMRS. FUELHH provides the WIND actual generation, and WINDFOR provides the forecast publication history. We focus on decisions made in January 2026, which means delivery periods from 2 January through 1 February. The default decision cutoff is 09:00 UK time on the previous day.”

### 1:20-2:50 — Walk through the live page

“I’ll choose 28 January as the delivery day and leave the cutoff at 09:00. The chart compares the forecast available at decision time with the matched actual generation for the day. The publication label tells us the newest forecast that made it into that selected set. Here, forecasts published after the cutoff are deliberately not allowed into the comparison.

“Below the chart, the first row of cards summarizes this delivery day. MAE is the average miss size. RMSE gives larger misses more weight. Bias shows whether the forecast was systematically high or low. P95 tells us the size of a miss that covers 95 percent of periods, and Error percent compares total absolute miss with total actual wind generation.

“The next row shows the same measures across all January purchase decisions. The horizon chart answers a different question: how does the error vary across all forecast publications as the delivery time gets closer? These are not only the forecasts chosen for the day-ahead decision.”

### 2:50-4:00 — Findings from this snapshot

“Across the 744 matched hourly periods, the January decision-time MAE was 2,022.5 megawatts. Mean bias was positive 1,745.9 megawatts, so the forecasts over-estimated wind on average. The 95th-percentile absolute error was 5,268.4 megawatts.

“The result also varies substantially by delivery day: the daily MAE was 683.6 megawatts on 19 January, compared with 5,329.0 megawatts on 28 January. That is a reminder that one monthly average does not describe every day.

“In the all-publications horizon analysis, the MAE was 1,654.1 megawatts in the 0-to-6-hour bucket and 2,307.4 megawatts at 48 hours or more. This comparison is descriptive; the horizon samples do not represent only the day-ahead decision forecasts.”

### 4:00-5:00 — How it informs buying

“The buying-decision panel translates the selected day’s bias and MAE into plain language. An over-forecast of wind can imply a potential generation shortfall against the forecast, so the typical error helps size uncertainty or cover scenarios. It is not a trade instruction: a decision still needs prices, portfolio position, and wider system context. The value here is a clear, auditable view of forecast vintage and historical error rather than relying on a forecast without its track record.”

## Part 2 — Tech lead review (about 5 minutes)

### 5:00-5:40 — Architecture in words

“The browser runs a React app built with Vite and Recharts. It calls a small FastAPI service. At data refresh time, a Python script downloads Elexon FUELHH and WINDFOR in seven-day publication-time windows, deduplicates rows, and writes JSON snapshots. The API reads those files once at startup, so a deployed service does not need a live upstream call to serve the dashboard.”

### 5:40-6:50 — Decision-time logic in code

“In `backend/main.py`, `select_latest_forecast` parses publication and target timestamps as UTC. For each target start time, it constructs the previous-day cutoff at the selected hour, removes every forecast whose publication time is later than that cutoff, sorts by publication time, and retains the latest eligible row for each target. `join_forecast_actuals` then inner-joins on start time and computes forecast minus actual.

“The metric function operates only on those matched rows. Horizon metrics use all forecast vintages for January target times and the same actual join, then bucket the difference between target time and publication time.”

### 6:50-7:35 — Folders and data flow

“The backend source, tests, fetch script, data, and deployment file live under `backend/`. The React app, styles, package lock, and static deployment file live under `frontend/`. `docker-compose.yml` runs the API on port 8000 and the Nginx-served frontend on port 3000. The API URL for the browser is configurable through `VITE_API_URL`.”

### 7:35-8:15 — Testing and validation

“The focused pytest cases ensure that a forecast after the cutoff is rejected, the newest eligible publication wins, and a small hand-calculated data set produces the expected MAE, RMSE, bias, P95, and error percent. Empty metric input returns a zero count. The frontend is built with Vite as part of the production check.”

### 8:15-9:00 — Deployment and upstream contract

“For Vercel, backend and frontend are two projects with `backend` and `frontend` as their respective root directories. The backend config includes the JSON snapshots in its Python deployment; the frontend project gets `VITE_API_URL` pointing at the backend deployment. The Elexon Swagger contract was checked: both streams accept publication time bounds, FUELHH supports a WIND fuel filter, and the observed stream body is a plain array. The parser also accepts a `data` envelope.”

### 9:00-10:00 — Assumptions, trade-offs, and next steps

“This version assumes one 09:00 cutoff, January UTC equals UK local time, and national-level wind is the scope. WINDFOR is hourly while FUELHH actuals are half-hourly, so the inner join uses the 24 matched hourly periods per day and does not synthesize intermediate values. The data window is a fixed historical snapshot, so refreshing it may update the figures.

“Next, I would review the forecast publication cadence with the trading team, test alternate cutoff times, extend the period for seasonal comparisons, and add price or regional context only if the product scope expands. The present results should be treated as historical forecast-risk evidence, not as a standalone procurement recommendation.”
