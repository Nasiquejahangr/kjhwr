import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(
  /\/$/,
  "",
);
const DEFAULT_DAY = "2026-01-02";
const METRICS = [
  ["mae", "MAE", "Average size of the forecast error, in MW."],
  ["rmse", "RMSE", "Penalizes large misses more heavily, in MW."],
  ["bias", "Bias", "Average signed error; positive means wind was over-forecast."],
  [
    "p95_absolute_error",
    "P95 error",
    "95% of absolute errors were at or below this value, in MW.",
  ],
  [
    "error_percent",
    "Error %",
    "Total absolute error as a share of total actual wind generation.",
  ],
];

function number(value, suffix = " MW") {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${value.toLocaleString("en-GB", { maximumFractionDigits: 1 })}${suffix}`;
}

function publishedLabel(value) {
  if (!value) return "No matched forecast";
  return new Date(value).toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }) + " UTC";
}

function MetricCards({ title, data }) {
  return (
    <section className="metric-section" aria-label={title}>
      <div className="section-heading">
        <div>
          <p className="eyebrow">ACCURACY SNAPSHOT</p>
          <h2>{title}</h2>
        </div>
        <span className="sample-count">{data?.n ?? 0} matched periods</span>
      </div>
      <div className="metric-grid">
        {METRICS.map(([key, label, help]) => (
          <article className="metric-card" key={key}>
            <p className="metric-label">{label}</p>
            <p className="metric-value">
              {number(data?.[key], key === "error_percent" ? "%" : " MW")}
            </p>
            <p className="metric-help">{help}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function App() {
  const [day, setDay] = useState(DEFAULT_DAY);
  const [cutoffHour, setCutoffHour] = useState("9");
  const [series, setSeries] = useState([]);
  const [dayMetrics, setDayMetrics] = useState(null);
  const [allMetrics, setAllMetrics] = useState(null);
  const [horizons, setHorizons] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    const params = `cutoff_hour=${cutoffHour}&day=${day}`;
    setLoading(true);
    setError("");

    Promise.all([
      fetch(`${API_URL}/api/series?${params}`, { signal: controller.signal }),
      fetch(`${API_URL}/api/metrics?${params}`, { signal: controller.signal }),
      fetch(`${API_URL}/api/metrics?cutoff_hour=${cutoffHour}`, {
        signal: controller.signal,
      }),
      fetch(`${API_URL}/api/horizon`, { signal: controller.signal }),
    ])
      .then(async (responses) => {
        const failed = responses.find((response) => !response.ok);
        if (failed) throw new Error(`API request failed (${failed.status})`);
        return Promise.all(responses.map((response) => response.json()));
      })
      .then(([daySeries, selectedMetrics, januaryMetrics, horizonMetrics]) => {
        setSeries(daySeries);
        setDayMetrics(selectedMetrics);
        setAllMetrics(januaryMetrics);
        setHorizons(horizonMetrics);
      })
      .catch((requestError) => {
        if (requestError.name !== "AbortError") {
          setError(`${requestError.message}. Check that the backend is running.`);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [day, cutoffHour]);

  const latestPublishTime = useMemo(() => {
    const times = series.map((item) => item.publishTime).filter(Boolean);
    return times.sort().at(-1);
  }, [series]);
  const buyingDecision = useMemo(() => {
    const bias = dayMetrics?.bias;
    const mae = dayMetrics?.mae;
    if (bias === undefined || mae === undefined) {
      return "Matched forecast and actual data are needed before a buying signal can be estimated.";
    }
    if (bias > 0) {
      return `Forecasts over-estimated wind by ${number(bias)} on average. Consider allowing for a shortfall cover buffer around the typical ${number(mae)} MAE; this is a planning signal, not a trade instruction.`;
    }
    if (bias < 0) {
      return `Forecasts under-estimated wind by ${number(Math.abs(bias))} on average. A typical miss is ${number(mae)}; use this uncertainty when sizing cover rather than relying on bias alone.`;
    }
    return `Forecasts were unbiased on average, but still missed by about ${number(mae)} typically. Use that error range when sizing cover.`;
  }, [dayMetrics]);

  const chartData = series.map((item) => ({
    ...item,
    time: new Date(item.startTime).toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "UTC",
    }),
  }));

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#" aria-label="UK Wind Forecast Monitor home">
          <span className="brand-mark">W</span>
          <span>GRID / INSIGHTS</span>
        </a>
        <span className="data-source"><span className="live-dot" /> ELEXON BMRS DATA</span>
      </header>

      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">DAY-AHEAD DECISION SUPPORT · GREAT BRITAIN</p>
          <h1>UK Wind Forecast Monitor</h1>
          <p className="subtitle">
            See the latest wind outlook available at purchase time, and understand
            how far the forecast can deviate from actual generation.
          </p>
        </div>
        <div className="period-chip"><span>ANALYSIS WINDOW</span><strong>JAN — FEB 2026</strong></div>
      </section>

      <section className="control-panel" aria-label="Forecast controls">
        <div className="control-group">
          <label htmlFor="delivery-day">Delivery day</label>
          <input
            id="delivery-day"
            type="date"
            min="2026-01-02"
            max="2026-02-01"
            value={day}
            onChange={(event) => setDay(event.target.value)}
          />
        </div>
        <div className="control-group">
          <label htmlFor="cutoff">Decision cutoff (UK time)</label>
          <select
            id="cutoff"
            value={cutoffHour}
            onChange={(event) => setCutoffHour(event.target.value)}
          >
            {[8, 9, 10, 11, 12].map((hour) => (
              <option value={hour} key={hour}>{String(hour).padStart(2, "0")}:00</option>
            ))}
          </select>
        </div>
        <div className="cutoff-note"><span className="clock-icon">◷</span> Forecasts published after this cutoff are excluded.</div>
      </section>

      {loading && <div className="notice">Loading Elexon wind data…</div>}
      {error && <div className="notice notice-error" role="alert">{error}</div>}

      {!loading && !error && (
        <>
          <section className="chart-panel">
            <div className="section-heading chart-heading">
              <div>
                <p className="eyebrow">DELIVERY DAY · {day}</p>
                <h2>Forecast vs actual generation</h2>
                <p className="chart-subtitle">National wind generation · MW · UTC</p>
              </div>
              <div className="published">
                <span className="published-icon">↗</span>
                <span><small>LATEST FORECAST USED WAS PUBLISHED AT</small><strong>{publishedLabel(latestPublishTime)}</strong></span>
              </div>
            </div>
            {chartData.length ? (
              <div className="line-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 16, right: 12, left: 8, bottom: 4 }}>
                    <CartesianGrid stroke="#e8ece8" vertical={false} />
                    <XAxis dataKey="time" tickLine={false} axisLine={false} tick={{ fill: "#7d8981", fontSize: 11 }} interval="preserveStartEnd" />
                    <YAxis tickLine={false} axisLine={false} tick={{ fill: "#7d8981", fontSize: 11 }} width={60} />
                    <Tooltip formatter={(value) => [`${Number(value).toLocaleString()} MW`]} labelFormatter={(label) => `${label} UTC`} />
                    <Legend verticalAlign="top" align="right" height={36} />
                    <Line name="Forecast" type="monotone" dataKey="forecast" stroke="#286c53" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
                    <Line name="Actual" type="monotone" dataKey="actual" stroke="#e3a34b" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="empty-chart">No matched forecast and actual periods for this delivery day.</div>
            )}
          </section>

          <MetricCards title={`Selected day · ${day}`} data={dayMetrics} />
          <MetricCards title="All January decisions" data={allMetrics} />

          <section className="bottom-grid">
            <div className="chart-panel horizon-panel">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">ALL JANUARY TARGETS</p>
                  <h2>Error by forecast horizon</h2>
                </div>
                <span className="unit-tag">MAE · MW</span>
              </div>
              <p className="chart-subtitle">How forecast error changes with time between publication and delivery.</p>
              {horizons.some((item) => item.mae !== null) ? (
                <div className="bar-chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={horizons} margin={{ top: 14, right: 8, left: 2, bottom: 0 }}>
                      <CartesianGrid stroke="#e8ece8" vertical={false} />
                      <XAxis dataKey="bucket" tickLine={false} axisLine={false} tick={{ fill: "#7d8981", fontSize: 11 }} />
                      <YAxis tickLine={false} axisLine={false} tick={{ fill: "#7d8981", fontSize: 11 }} width={52} />
                      <Tooltip formatter={(value) => [`${Number(value).toLocaleString()} MW`, "MAE"]} labelFormatter={(label) => `${label} hours`} />
                      <Bar dataKey="mae" name="MAE" fill="#43846a" radius={[4, 4, 0, 0]} maxBarSize={48} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : <div className="empty-chart">No matched forecast horizons available.</div>}
            </div>

            <aside className="decision-card">
              <div className="decision-icon">↗</div>
              <p className="eyebrow">PUTTING THE ERROR IN CONTEXT</p>
              <h2>What this means for buying decisions</h2>
              <p>{buyingDecision}</p>
              <div className="decision-footnote">Historical forecast performance is one input to procurement, not a recommendation.</div>
            </aside>
          </section>
          <footer>Source: Elexon BMRS · FUELHH WIND actuals and WINDFOR forecasts · Times shown in UTC</footer>
        </>
      )}
    </main>
  );
}

export default App;
