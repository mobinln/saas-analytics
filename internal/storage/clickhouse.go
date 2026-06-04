package storage

import (
	"context"
	"fmt"
	"time"

	"eventaggregator/internal/event"

	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	batchInsertDuration = promauto.NewHistogram(prometheus.HistogramOpts{
		Name:    "clickhouse_batch_insert_duration_seconds",
		Help:    "Time spent sending a batch to ClickHouse.",
		Buckets: prometheus.ExponentialBuckets(0.005, 2, 10),
	})

	batchInsertErrors = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "clickhouse_batch_insert_errors_total",
		Help: "Errors from ClickHouse batch inserts, by stage.",
	}, []string{"stage"})

	batchInsertRows = promauto.NewCounter(prometheus.CounterOpts{
		Name: "clickhouse_batch_insert_rows_total",
		Help: "Rows successfully inserted into ClickHouse.",
	})
)

type ClickHouse struct {
	conn driver.Conn
}

func NewClickHouse(conn driver.Conn) *ClickHouse {
	return &ClickHouse{
		conn: conn,
	}
}

func (c *ClickHouse) InsertBatch(ctx context.Context, events []event.Event) error {
	start := time.Now()
	defer func() { batchInsertDuration.Observe(time.Since(start).Seconds()) }()

	batch, err := c.conn.PrepareBatch(ctx, "INSERT INTO events (name, type, path, data)")
	if err != nil {
		batchInsertErrors.WithLabelValues("prepare").Inc()
		return fmt.Errorf("prepare batch: %w", err)
	}

	for _, e := range events {
		if err := batch.Append(e.Name, e.Type, e.Path, e.Data); err != nil {
			batchInsertErrors.WithLabelValues("append").Inc()
			return fmt.Errorf("append: %w", err)
		}
	}

	if err := batch.Send(); err != nil {
		batchInsertErrors.WithLabelValues("send").Inc()
		return fmt.Errorf("send: %w", err)
	}
	batchInsertRows.Add(float64(len(events)))
	return nil
}

func (c *ClickHouse) GetEvents(ctx context.Context) ([]event.Event, error) {
	rows, err := c.conn.Query(ctx,
		"SELECT event_time, name, type, path, data FROM events.events ORDER BY event_time DESC LIMIT 10")
	if err != nil {
		return nil, fmt.Errorf("GetEvents: %w", err)
	}
	defer rows.Close()

	var out []event.Event
	for rows.Next() {
		var event event.Event
		if err := rows.Scan(&event.EventTime, &event.Name, &event.Type, &event.Path, &event.Data); err != nil {
			return nil, fmt.Errorf("rows.Next: %w", err)
		}
		out = append(out, event)
	}

	return out, nil
}
