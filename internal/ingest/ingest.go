package ingest

import (
	"context"
	"time"

	"eventaggregator/internal/event"
)

type BatchInserter interface {
	InsertBatch(ctx context.Context, events []event.Event) error
}

type Ingester struct {
	eventsQueue          chan event.Event
	inserter             BatchInserter
	workerCount          int
	batchSize            int
	batchFlushIntervalMs int
}

func NewIngester(inserter BatchInserter, queueCapacity int, workerCount int, batchSize int, batchFlushIntervalMs int) Ingester {
	return Ingester{
		eventsQueue:          make(chan event.Event, queueCapacity),
		inserter:             inserter,
		workerCount:          workerCount,
		batchSize:            batchSize,
		batchFlushIntervalMs: batchFlushIntervalMs,
	}
}

func (i *Ingester) QueueDepth() int {
	return len(i.eventsQueue)
}

func (i *Ingester) Enqueue(event event.Event) bool {
	select {
	case i.eventsQueue <- event:
		return true
	default:
		return false
	}
}

func (i *Ingester) Start() {
	for range i.workerCount {
		go i.eventsWorker()
	}
}

func (i *Ingester) eventsWorker() {
	batch := make([]event.Event, 0, i.batchSize)

	ticker := time.NewTicker(time.Duration(i.batchFlushIntervalMs) * time.Millisecond)
	defer ticker.Stop()

	flush := func() {
		if len(batch) == 0 {
			return
		}
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		_ = i.inserter.InsertBatch(ctx, batch)
		batch = batch[:0]
	}

	for {
		select {
		case event := <-i.eventsQueue:
			batch = append(batch, event)
			if len(batch) >= i.batchSize {
				flush()
			}
		case <-ticker.C:
			flush()
		}
	}
}
