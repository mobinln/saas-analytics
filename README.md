# saas-analytics

## Overview

An event-ingestion service for SaaS analytics, in a single Go binary. Clients POST events over HTTP; the server batches them in memory and a worker pool writes them to ClickHouse. It's designed for teams that want analytics infrastructure without standing up a streaming pipeline.

- **Standalone.** One process, one container. No Kafka, no Flink, no microservices.
- **Swappable storage.** ClickHouse by default. The `BatchInserter` interface makes Postgres, Cassandra, or Iceberg a small adapter away.
- **Honest scope.** Targets small-to-medium workloads — see the Benchmark section for measured numbers. Beyond that, you'll want sharded ingestion and a proper streaming pipeline.

## Benchmark

**~65K events/s sustained ingest into ClickHouse, 0% loss, on 2 CPU cores.**

Server: `GOMAXPROCS=2 go run cmd/server/main.go` with tuned drain config (`WORKER_COUNT=16`, `CLICKHOUSE_MAX_OPEN_CONNS=16`, lowered `BATCH_FLUSH_INTERVAL_MS`).
Load: `local_dev/benchmark.sh` — wrk, 4 threads · 1000 connections · 30s.

| Metric                         | Value        |
| ------------------------------ | ------------ |
| Sustained ingest (0% loss)     | 64,850 req/s |
| Dropped (HTTP 503, queue full) | 0            |
| Latency p50                    | 15.78 ms     |
| Latency p90                    | 25.35 ms     |
| Latency p99                    | 38.74 ms     |
| Latency max                    | 110.38 ms    |

## Improvements

- **Top-K events API** — expose an endpoint to report Top-K events.
- **Time-series endpoint** — `GET /events/timeseries?bucket=1m&from=...&to=...` returning counts per bucket — perfect for charts.
- **Anomaly detector** — alert on high or low spikes in event rates.
- **Downsampling** — save events by different granularity (minute or hour) to reduce storage.
- **Pluggable storage backends** — abstract `BatchInserter` is already in place; add adapters for Postgres / Kafka / S3 (Parquet) so the same ingester can fan out to a warehouse or message bus alongside ClickHouse.

## Ideas

- **UI Dashboard** — simple ViteJS app dashboard with charts.
- **Forecasting** — simple Holt-Winters or EWMA baseline alongside the z-score detector.
- **Schema-on-write validation** — let users register named event schemas (JSON Schema or simple field/type maps) and reject events that don't match; emit a `schema_violations_total{schema}` metric.
- **Per-tenant API keys + rate limiting** — header-based auth (`X-API-Key`) mapped to a tenant ID stored as an event column, with a token-bucket rate limiter per tenant. Unblocks multi-tenant SaaS use.
- **Sampling / shedding policies** — when the queue crosses a high-water mark, drop low-priority event types (configurable) before dropping high-priority ones, instead of uniform 503s.
- **Sessionization / enrichment** — derive `session_id` from a sliding window of events per user, or enrich incoming events with GeoIP / UA parsing before the ClickHouse insert.
- **Replay / backfill endpoint** — `POST /events/bulk` accepting newline-delimited JSON or Parquet, useful for migrating from another system or replaying after an outage.
- **Cohort / funnel queries** — `GET /events/funnel?steps=signup,activate,convert&window=7d` returning step-by-step conversion counts. ClickHouse's `windowFunnel` makes this almost free.
- **Materialized views for hot aggregations** — Top-K and time-series queries served from ClickHouse `MATERIALIZED VIEW`s instead of scanning the raw table, dropping query latency from seconds to ms at scale.
- **OpenTelemetry traces** — wrap the ingest path in OTel spans so a slow event can be traced from HTTP receive → queue → batch → ClickHouse insert. Pairs well with the existing Prometheus metrics.
- **Grafana dashboard JSON** — ship a pre-built dashboard in `local_dev/` (queue depth, p99, drop rate, ClickHouse insert duration, rows/s) so new contributors get observability out of the box.
- **Dockerfile + image publish** — multi-stage build, distroless base, GitHub Actions to publish on tag. Pairs with the Makefile in Improvements #6.
- **Config validation at startup** — reject configs where `WORKER_COUNT > CLICKHOUSE_MAX_OPEN_CONNS` (workers will contend) or `BATCH_FLUSH_INTERVAL_MS == 0`, instead of letting them quietly misbehave.
- **Dead letter queue (DLQ) for failed inserts** — when ClickHouse insert fails after retries, write events to a local file, S3, or a fallback table for manual inspection/replay. Track `dlq_events_total` metric.
- **Health check endpoints** — `/live` (always 200) and `/ready` (checks queue depth, ClickHouse connectivity, worker health). Essential for Kubernetes liveness/readiness probes.
