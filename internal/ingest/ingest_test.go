package ingest

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"eventaggregator/internal/event"

	"go.uber.org/zap"
)

type insertCall struct {
	batch []event.Event
}

type fakeInserter struct {
	mu       sync.Mutex
	calls    []insertCall
	errCount int
	err      error
}

func (f *fakeInserter) InsertBatch(_ context.Context, batch []event.Event) error {
	f.mu.Lock()
	defer f.mu.Unlock()

	cp := make([]event.Event, len(batch))
	copy(cp, batch)
	f.calls = append(f.calls, insertCall{batch: cp})

	if f.errCount > 0 {
		f.errCount--
		return f.err
	}
	return nil
}

func (f *fakeInserter) callCount() int {
	f.mu.Lock()
	defer f.mu.Unlock()
	return len(f.calls)
}

func (f *fakeInserter) totalEvents() int {
	f.mu.Lock()
	defer f.mu.Unlock()
	total := 0
	for _, c := range f.calls {
		total += len(c.batch)
	}
	return total
}

func (f *fakeInserter) eventsInCall(i int) int {
	f.mu.Lock()
	defer f.mu.Unlock()
	if i < 0 || i >= len(f.calls) {
		return 0
	}
	return len(f.calls[i].batch)
}

func waitFor(t *testing.T, cond func() bool, timeout time.Duration) {
	t.Helper()
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		if cond() {
			return
		}
		time.Sleep(5 * time.Millisecond)
	}
	t.Fatalf("condition not met within %v", timeout)
}

func newEvent(name string) event.Event {
	return event.Event{Name: name, Type: "click", Path: "/"}
}

func TestEnqueue(t *testing.T) {
	fake := &fakeInserter{}
	logger := zap.NewNop().Sugar()
	ingester := NewIngester(fake, 2, 1, 10, 1000, logger)

	if !ingester.Enqueue(newEvent("first")) {
		t.Error("expected Enqueue to return true when queue has capacity")
	}

	if ingester.QueueDepth() != 1 {
		t.Errorf("expected queue depth 1, got %d", ingester.QueueDepth())
	}

	if !ingester.Enqueue(newEvent("second")) {
		t.Error("expected second Enqueue to succeed, queue has capacity")
	}

	if ingester.Enqueue(newEvent("third")) {
		t.Error("expected Enqueue to return false when queue is full")
	}

	if ingester.QueueDepth() != 2 {
		t.Errorf("expected queue depth 2 after rejected enqueue, got %d", ingester.QueueDepth())
	}
}

func TestFlushAtBatchSize(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	fake := &fakeInserter{}
	logger := zap.NewNop().Sugar()
	ingester := NewIngester(fake, 100, 1, 3, 10000, logger)
	ingester.Start(ctx)

	for i := range 3 {
		ingester.Enqueue(newEvent(string(rune('a' + i))))
	}

	waitFor(t, func() bool { return fake.callCount() >= 1 }, time.Second)

	cancel()
	ingester.Wait()

	if fake.callCount() != 1 {
		t.Fatalf("expected 1 flush, got %d", fake.callCount())
	}
	if fake.eventsInCall(0) != 3 {
		t.Errorf("expected 3 events in batch, got %d", fake.eventsInCall(0))
	}
}

func TestFlushOnTicker(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	fake := &fakeInserter{}
	logger := zap.NewNop().Sugar()
	ingester := NewIngester(fake, 100, 1, 100, 50, logger)
	ingester.Start(ctx)

	for i := range 4 {
		ingester.Enqueue(newEvent(string(rune('a' + i))))
	}

	waitFor(t, func() bool { return fake.callCount() >= 1 }, 200*time.Millisecond)

	cancel()
	ingester.Wait()

	if fake.totalEvents() < 4 {
		t.Errorf("expected at least 4 events flushed by ticker, got %d", fake.totalEvents())
	}
}

func TestDrainOnShutdown(t *testing.T) {
	fake := &fakeInserter{}
	logger := zap.NewNop().Sugar()
	ingester := NewIngester(fake, 100, 1, 10, 10000, logger)

	ctx, cancel := context.WithCancel(context.Background())
	ingester.Start(ctx)

	for i := range 5 {
		ingester.Enqueue(newEvent(string(rune('a' + i))))
	}

	cancel()
	ingester.Wait()

	if fake.totalEvents() != 5 {
		t.Errorf("expected 5 events drained on shutdown, got %d", fake.totalEvents())
	}
}

func TestRetryOnFailure(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	fake := &fakeInserter{
		errCount: 1,
		err:      errors.New("transient error"),
	}
	logger := zap.NewNop().Sugar()
	ingester := NewIngester(fake, 100, 1, 3, 10000, logger)
	ingester.Start(ctx)

	for i := range 3 {
		ingester.Enqueue(newEvent(string(rune('a' + i))))
	}

	waitFor(t, func() bool { return fake.callCount() >= 2 }, 500*time.Millisecond)

	cancel()
	ingester.Wait()

	if fake.callCount() != 2 {
		t.Fatalf("expected 2 flush attempts (1 fail + 1 success), got %d", fake.callCount())
	}
	if fake.eventsInCall(0) != 3 {
		t.Errorf("expected first call to have 3 events, got %d", fake.eventsInCall(0))
	}
	if fake.eventsInCall(1) != 3 {
		t.Errorf("expected retry call to have 3 events, got %d", fake.eventsInCall(1))
	}
}
