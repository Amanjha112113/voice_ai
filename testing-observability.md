# Testing and Observability

## 1. Unit tests

Test:

- state transitions
- interruption controller
- generation IDs
- cancellation
- qualification logic
- recommendation scoring
- tool validation
- idempotency
- data models

## 2. Integration tests

Test:

```text
Agora
 → ASR
 → LLM
 → TTS
 → playback
```

and:

```text
Conversation
 → catalog
 → CRM
 → calendar
```

## 3. Barge-in test matrix

Test interruption:

- during TTS
- during LLM generation
- immediately after TTS starts
- repeated interruptions
- very short interruption
- long interruption
- interruption during tool call
- disconnect during interruption

Expected:

- no stale audio
- no duplicate generation
- session remains healthy

## 4. Sales conversation tests

Scenario:

1. budget = 15 lakh
2. asks about Scorpio
3. interrupts
4. asks Toyota comparison
5. changes budget
6. requires seven seats
7. raises price objection
8. requests enterprise/showroom demo
9. books test drive

Validate final structured state.

## 5. Load tests

Measure:

- concurrent sessions
- CPU
- memory
- provider connection count
- P50/P95/P99 TTFA
- interruption latency
- error rate

## 6. Observability

Use structured logs.

Every log should contain:

- request_id
- session_id
- turn_id
- generation_id
- event
- duration_ms
- provider

## 7. Tracing

Trace:

```text
turn
 ├── ASR
 ├── state update
 ├── retrieval
 ├── LLM
 ├── TTS
 ├── playback
 └── tools
```

## 8. Alerts

For production:

- provider error spike
- TTFA P95 regression
- interruption-stop regression
- appointment failure rate
- orphan task count
- database latency
