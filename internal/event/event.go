package event

import "time"

type Event struct {
	EventTime time.Time         `json:"event_time"`
	Name      string            `json:"name" binding:"required"`
	Type      string            `json:"type" binding:"required"`
	Path      string            `json:"path" binding:"required"`
	Data      map[string]string `json:"data,omitempty"`
}
