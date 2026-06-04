package main

import (
	"context"
	"log"
	"net/http"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2"
	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"
	"github.com/gin-gonic/gin"
)

type Event struct {
	Name string `json:"name" binding:"required"`
	Type string `json:"type" binding:"required"`
	Path string `json:"path" binding:"required"`
}

var eventsQueue chan Event

func main() {
	conn, err := clickhouse.Open(&clickhouse.Options{
		Addr: []string{"localhost:9000"},
		Auth: clickhouse.Auth{
			Database: "events",
			Username: "default",
			Password: "",
		},
		Compression: &clickhouse.Compression{
			Method: clickhouse.CompressionLZ4,
		},
		MaxOpenConns: 8,
		MaxIdleConns: 4,
	})
	if err != nil {
		log.Fatal(err)
	}
	if err := conn.Ping(context.Background()); err != nil {
		log.Fatal(err)
	}

	eventsQueue = make(chan Event, 10000)

	for range 4 {
		go eventsWorker(conn)
	}

	gin.SetMode(gin.ReleaseMode)
	r := gin.New()
	r.Use(gin.Recovery())

	r.POST("/event", func(c *gin.Context) {
		var event Event

		if err := c.BindJSON(&event); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		eventsQueue <- event

		c.JSON(http.StatusOK, gin.H{
			"message": "queued",
		})
	})

	r.GET("/event", func(c *gin.Context) {
		rows, err := conn.Query(c.Request.Context(),
			"SELECT event_time, name, type, path FROM events.events ORDER BY event_time DESC LIMIT 10")
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		defer rows.Close()

		type Row struct {
			EventTime time.Time `json:"event_time"`
			Name      string    `json:"name"`
			Type      string    `json:"type"`
			Path      string    `json:"path"`
		}
		var out []Row
		for rows.Next() {
			var row Row
			if err := rows.Scan(&row.EventTime, &row.Name, &row.Type, &row.Path); err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
				return
			}
			out = append(out, row)
		}

		c.JSON(http.StatusOK, out)
	})

	if err := r.Run(); err != nil {
		log.Fatalf("failed to run server: %v", err)
	}
}

func eventsWorker(conn driver.Conn) {
	batchSize := 1000
	batch := make([]Event, 0, batchSize)

	ticker := time.NewTicker(1 * time.Second)

	for {
		select {
		case event := <-eventsQueue:
			batch = append(batch, event)

			if len(batch) >= batchSize {
				insertBatch(conn, batch)
				batch = batch[:0]
			}
		case <-ticker.C:
			if len(batch) > 0 {
				insertBatch(conn, batch)
				batch = batch[:0]
			}
		}
	}
}

func insertBatch(conn driver.Conn, events []Event) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	batch, err := conn.PrepareBatch(ctx, "INSERT INTO events.events (name, type, path)")
	if err != nil {
		log.Println("prepare batch error:", err)
		return
	}

	for _, e := range events {
		if err := batch.Append(e.Name, e.Type, e.Path); err != nil {
			log.Println("append error:", err)
			return
		}
	}

	if err := batch.Send(); err != nil {
		log.Println("send batch error:", err)
	}
}
