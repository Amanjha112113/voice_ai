# API Contracts

## Control plane

### GET /health

Returns service and dependency health.

### POST /sessions

Creates a voice session.

Request:

```json
{
  "customer_id": "optional",
  "language": "en-IN"
}
```

Response:

```json
{
  "session_id": "...",
  "channel": "...",
  "status": "starting"
}
```

### GET /sessions/{session_id}

Returns session state.

### DELETE /sessions/{session_id}

Terminates a session and cancels all owned tasks.

### GET /vehicles

Structured catalog search.

### POST /appointments

Book appointment after explicit confirmation.

### POST /leads

Create/update qualified lead.

### WS /ws/events

Dashboard-only event stream.

Events:

- session_state
- transcript
- deal_state
- tool_call
- latency
- error
- appointment
- escalation

The WebSocket is NOT the audio transport.

## Event schema

```json
{
  "event_id": "...",
  "session_id": "...",
  "type": "latency",
  "timestamp": "...",
  "payload": {}
}
```

All events should be versionable.

## Error format

```json
{
  "error": {
    "code": "APPOINTMENT_UNAVAILABLE",
    "message": "No matching slot is available.",
    "request_id": "..."
  }
}
```
