# eventaggregator

## Improvements

1. Github Repository: make a repository for this project.
2. Benchmark shell script: add a shell script to run `wrk` or `hey` and benchmark the server.
3. Flexible data field: add flexible `data` field to events so a user can send more data.
4. Structured logging: replace the standard `log` package with `log/slog` and emit JSON logs with consistent fields.
5. Prometheus metrics: expose prometheus monitoring metrics.
6. Non-blocking enqueue: replace the blocking channel send in `POST /event` with a `select` that returns 503 when the queue is full.
7. Top-K events: expose an API to report Top-K events.
8. Graceful shutdown: catch SIGINT/SIGTERM, stop accepting requests, close the queue, drain workers, and flush in-flight batches before exit.
9. Time-series endpoint: GET /events/timeseries?bucket=1m&from=...&to=... returning counts per bucket — perfect for charts.
10. Repository: add a repository layer so we can use different storages.
11. Package structure and tests: split ingest, store, and API into `internal/` packages and add unit/integration tests.
12. Anomaly Detector: add anomaly detection to alert high or low spikes in events.


## Ideas

- Persistence layer: swap the in-memory store for a durable backend (SQLite/Postgres/BoltDB) so counts and events survive restarts.
- Forecasting: simple Holt-Winters or EWMA baseline alongside the z-score detector.
- WebSocket / SSE stream at /events/stream that pushes new events (optionally filtered) live — great for dashboards.
- Downsampling: save events by different granularity (minute or hour) to reduce storage.
