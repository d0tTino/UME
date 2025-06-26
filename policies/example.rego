package ume

# Block events with event_type equal to "FORBIDDEN_EVENT"

default allow = false

allow if input.event.event_type != "FORBIDDEN_EVENT"
