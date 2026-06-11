package event

import (
	"fmt"
	"time"
)

type Event struct {
	EventTime time.Time         `json:"event_time"`
	Name      string            `json:"name" binding:"required"`
	Type      string            `json:"type" binding:"required"`
	Path      string            `json:"path" binding:"required"`
	Data      map[string]string `json:"data,omitempty"`
}

// ValidateData bounds the Data map so a single event can't produce an oversized
// row. maxKeys caps the number of entries; maxBytes caps the total size of all
// keys and values combined. A non-positive limit disables that check.
func (e Event) ValidateData(maxKeys, maxBytes int) error {
	if maxKeys > 0 && len(e.Data) > maxKeys {
		return fmt.Errorf("data has %d keys, limit is %d", len(e.Data), maxKeys)
	}

	if maxBytes > 0 {
		total := 0
		for k, v := range e.Data {
			total += len(k) + len(v)
		}
		if total > maxBytes {
			return fmt.Errorf("data is %d bytes, limit is %d", total, maxBytes)
		}
	}

	return nil
}
