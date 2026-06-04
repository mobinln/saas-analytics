# saas-analytics

## Improvements

- Top-K events: expose an API to report Top-K events.
- Graceful shutdown: catch SIGINT/SIGTERM, stop accepting requests, close the queue, drain workers, and flush in-flight batches before exit.
- Time-series endpoint: GET /events/timeseries?bucket=1m&from=...&to=... returning counts per bucket — perfect for charts.
- Anomaly Detector: add anomaly detection to alert high or low spikes in events.
- Makefile: add makefile

## Ideas

- Persistence layer: swap the in-memory store for a durable backend (SQLite/Postgres/BoltDB) so counts and events survive restarts.
- Forecasting: simple Holt-Winters or EWMA baseline alongside the z-score detector.
- WebSocket / SSE stream at /events/stream that pushes new events (optionally filtered) live — great for dashboards.
- Downsampling: save events by different granularity (minute or hour) to reduce storage.
