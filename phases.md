# Implementation Phases

## Phase 0 — Repository foundation

- project structure
- configuration
- logging
- tests
- Docker
- health endpoint

Definition of done: clean startup and CI checks.

## Phase 1 — Agora voice connectivity

- Agora session
- microphone
- speaker
- clean join/leave
- session lifecycle

Definition of done: stable realtime audio.

## Phase 2 — Basic conversation

- ASR
- LLM
- TTS
- multi-turn context

Definition of done: natural basic conversation.

## Phase 3 — Streaming

- streaming ASR
- streaming LLM
- streaming TTS
- incremental playback

Definition of done: measurable TTFA improvement.

## Phase 4 — Turn taking

- VAD
- turn detection
- speech start/end

## Phase 5 — Barge-in

- interruption controller
- cancellation
- generation IDs
- stale audio protection

Definition of done: repeated interruption tests pass.

## Phase 6 — Sales state

- customer profile
- requirements
- objections
- buying intent
- next-best-action

## Phase 7 — Car intelligence

- vehicle catalog
- structured search
- RAG for unstructured product content
- comparisons
- pricing/availability

## Phase 8 — Actions

- CRM
- calendar
- test-drive booking
- human escalation

## Phase 9 — Observability

- latency dashboard
- tracing
- structured logs
- conversation metrics

## Phase 10 — Reliability/load

- concurrency tests
- provider failure tests
- disconnect tests
- P95/P99 tuning

## Phase 11 — Demo hardening

The golden demo must work repeatedly:

```text
voice
 → interruption
 → comparison
 → requirement change
 → objection
 → recommendation
 → qualification
 → appointment
```

Do not add unrelated features during this phase.
