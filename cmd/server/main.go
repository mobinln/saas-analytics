package main

import (
	"context"
	"eventaggregator/internal/config"
	"eventaggregator/internal/event"
	"eventaggregator/internal/ingest"
	"eventaggregator/internal/storage"
	"log"
	"net/http"
	"strconv"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2"
	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"go.uber.org/zap"
)

var (
	httpRequests = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "http_requests_total",
		Help: "HTTP requests by route and status.",
	}, []string{"method", "path", "status"})

	httpDuration = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Name:    "http_request_duration_seconds",
		Help:    "HTTP request duration.",
		Buckets: prometheus.DefBuckets,
	}, []string{"method", "path"})

	eventsEnqueued = promauto.NewCounter(prometheus.CounterOpts{
		Name: "events_enqueued_total",
		Help: "Events accepted onto the in-memory queue.",
	})

	eventsDropped = promauto.NewCounter(prometheus.CounterOpts{
		Name: "events_dropped_total",
		Help: "Events rejected because the queue was full.",
	})
)

func main() {
	logger, _ := zap.NewProduction()
	defer logger.Sync()
	sugar := logger.Sugar()

	config, err := config.Load()
	if err != nil {
		sugar.Fatalf("Error loading config: %v", err)
	}

	conn, err := clickhouse.Open(&clickhouse.Options{
		Addr: []string{config.ClickHouseAddr},
		Auth: clickhouse.Auth{
			Database: config.ClickHouseDB,
			Username: config.ClickHouseUser,
			Password: config.ClickHousePassword,
		},
		Compression: &clickhouse.Compression{
			Method: clickhouse.CompressionLZ4,
		},
		MaxOpenConns: config.ClickHouseMaxOpen,
		MaxIdleConns: config.ClickHouseMaxIdle,
	})
	if err != nil {
		log.Fatal(err)
	}
	if err := conn.Ping(context.Background()); err != nil {
		log.Fatal(err)
	}

	clickhouseStorage := storage.NewClickHouse(conn)
	eventIngester := ingest.NewIngester(clickhouseStorage, config.QueueCapacity, config.WorkerCount, config.BatchSize, config.BatchFlushIntervalMs)

	promauto.NewGaugeFunc(prometheus.GaugeOpts{
		Name: "events_queue_depth",
		Help: "Current depth of the in-memory event queue.",
	}, func() float64 { return float64(eventIngester.QueueDepth()) })

	eventIngester.Start()

	gin.SetMode(gin.ReleaseMode)
	r := gin.New()
	r.Use(gin.Recovery())
	r.Use(func(c *gin.Context) {
		start := time.Now()
		c.Next()
		path := c.FullPath()
		if path == "" {
			path = "unknown"
		}
		httpDuration.WithLabelValues(c.Request.Method, path).Observe(time.Since(start).Seconds())
		httpRequests.WithLabelValues(c.Request.Method, path, strconv.Itoa(c.Writer.Status())).Inc()
	})
	sugar.Infof("Server running at: %v", config.HTTPAddr)

	r.GET("/metrics", gin.WrapH(promhttp.Handler()))
	r.POST("/event", func(c *gin.Context) {
		var event event.Event

		if err := c.BindJSON(&event); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		enqueued := eventIngester.Enqueue(event)

		if enqueued {
			eventsEnqueued.Inc()
			c.JSON(http.StatusOK, gin.H{"message": "queued"})
		} else {
			eventsDropped.Inc()
			c.JSON(http.StatusServiceUnavailable, gin.H{"error": "queue full"})
		}
	})
	r.GET("/event", func(c *gin.Context) {
		events, err := clickhouseStorage.GetEvents(c.Request.Context())
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, events)
	})

	if err := r.Run(config.HTTPAddr); err != nil {
		sugar.Infof("failed to run server: %v", err)
	}
}
