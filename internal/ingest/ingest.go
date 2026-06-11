package ingest

import (
	"context"
	"sync"
	"time"

	"eventaggregator/internal/event"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"go.uber.org/zap"
)

var (
	eventsLost = promauto.NewCounter(prometheus.CounterOpts{
		Name: "events_lost_total",
		Help: "Events lost because the flush failed.",
	})
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
	maxRetries           int
	sugar                *zap.SugaredLogger
	wg                   sync.WaitGroup
}

func NewIngester(inserter BatchInserter, queueCapacity int, workerCount int, batchSize int, batchFlushIntervalMs int, sugar *zap.SugaredLogger) *Ingester {
	return &Ingester{
		eventsQueue:          make(chan event.Event, queueCapacity),
		inserter:             inserter,
		workerCount:          workerCount,
		batchSize:            batchSize,
		batchFlushIntervalMs: batchFlushIntervalMs,
		sugar:                sugar,
		maxRetries:           2,
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

// Start launches workerCount workers. They run until ctx is cancelled, at
// which point each one drains whatever is left in the queue, flushes its
// in-flight batch, and exits.
func (i *Ingester) Start(ctx context.Context) {
	for range i.workerCount {
		i.wg.Add(1)
		go i.eventsWorker(ctx)
	}
}

// Wait blocks until every worker has exited. Call it after cancelling the
// context passed to Start, so the process doesn't exit mid-flush.
func (i *Ingester) Wait() {
	i.wg.Wait()
}

func (i *Ingester) eventsWorker(ctx context.Context) {
	defer i.wg.Done()

	batch := make([]event.Event, 0, i.batchSize)

	ticker := time.NewTicker(time.Duration(i.batchFlushIntervalMs) * time.Millisecond)
	defer ticker.Stop()

	// flush writes the current batch to storage and resets it. Each insert
	// attempt gets a fresh background context (not the app ctx) so the final
	// flush during shutdown still completes even though the app ctx is
	// cancelled. The backoff between attempts, however, watches the app ctx so
	// a shutting-down worker doesn't sit sleeping.
	flush := func() {
		if len(batch) == 0 {
			return
		}

		var success bool
	retry:
		for attempt := range i.maxRetries {
			insertCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
			err := i.inserter.InsertBatch(insertCtx, batch)
			cancel()
			if err == nil {
				success = true
				break
			}
			i.sugar.Warnf("batch insert failed (attempt %d/%d): %v", attempt+1, i.maxRetries, err)

			// Back off before the next attempt, but bail immediately on
			// shutdown. The labeled break exits the retry loop, not just the
			// select.
			if attempt < i.maxRetries-1 {
				backoff := 100 * time.Millisecond * (1 << attempt) // 100, 200, 400...
				select {
				case <-time.After(backoff):
				case <-ctx.Done():
					break retry
				}
			}
		}

		if !success {
			eventsLost.Add(float64(len(batch)))
			i.sugar.Errorf("batch of %d events lost after %d attempts", len(batch), i.maxRetries)
			// TODO(improvement-2): DLQ / disk spill instead of dropping.
		}
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
		case <-ctx.Done():
			i.drain(&batch, flush)
			return
		}
	}
}

// drain pulls every event still buffered in the queue into the batch (flushing
// whenever it fills up), then does one final flush. The default branch fires as
// soon as the channel is empty, so this returns promptly on shutdown.
func (i *Ingester) drain(batch *[]event.Event, flush func()) {
	for {
		select {
		case event := <-i.eventsQueue:
			*batch = append(*batch, event)
			if len(*batch) >= i.batchSize {
				flush()
			}
		default:
			flush()
			return
		}
	}
}
