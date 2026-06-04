package config

import (
	"fmt"
	"os"
	"strconv"
)

type Config struct {
	HTTPAddr string

	ClickHouseAddr     string
	ClickHouseDB       string
	ClickHouseUser     string
	ClickHousePassword string
	ClickHouseMaxOpen  int
	ClickHouseMaxIdle  int

	QueueCapacity      int
	WorkerCount        int
	BatchSize          int
	BatchFlushIntervalMs int
}

func Load() (Config, error) {
	cfg := Config{
		HTTPAddr:           getString("HTTP_ADDR", ":8080"),
		ClickHouseAddr:     getString("CLICKHOUSE_ADDR", "localhost:9000"),
		ClickHouseDB:       getString("CLICKHOUSE_DB", "events"),
		ClickHouseUser:     getString("CLICKHOUSE_USER", "eventaggregator"),
		ClickHousePassword: getString("CLICKHOUSE_PASSWORD", "eventaggregator"),
	}

	var err error
	if cfg.ClickHouseMaxOpen, err = getInt("CLICKHOUSE_MAX_OPEN_CONNS", 8); err != nil {
		return cfg, err
	}
	if cfg.ClickHouseMaxIdle, err = getInt("CLICKHOUSE_MAX_IDLE_CONNS", 4); err != nil {
		return cfg, err
	}
	if cfg.QueueCapacity, err = getInt("QUEUE_CAPACITY", 10000); err != nil {
		return cfg, err
	}
	if cfg.WorkerCount, err = getInt("WORKER_COUNT", 4); err != nil {
		return cfg, err
	}
	if cfg.BatchSize, err = getInt("BATCH_SIZE", 1000); err != nil {
		return cfg, err
	}
	if cfg.BatchFlushIntervalMs, err = getInt("BATCH_FLUSH_INTERVAL_MS", 5000); err != nil {
		return cfg, err
	}
	return cfg, nil
}

func getString(key, def string) string {
	if v, ok := os.LookupEnv(key); ok {
		return v
	}
	return def
}

func getInt(key string, def int) (int, error) {
	v, ok := os.LookupEnv(key)
	if !ok {
		return def, nil
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		return 0, fmt.Errorf("%s: %w", key, err)
	}
	return n, nil
}
