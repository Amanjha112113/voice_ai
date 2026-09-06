# AGENTS.md — EchoDrive Coding Instructions

## Mission

Build a production-oriented, low-latency realtime voice sales agent for automotive dealerships.

The agent must:

- listen continuously
- respond with streamed speech
- support natural turn-taking
- stop speaking immediately on barge-in
- preserve session context
- remember changing customer requirements
- retrieve accurate vehicle/product information
- handle objections without a fixed script
- qualify leads
- book showroom/test-drive appointments
- escalate to humans with context

## Non-negotiable architecture rules

### 1. Separate media plane and control plane

**Media plane**

Customer ↔ Agora ↔ realtime voice runtime

**Control plane**

Frontend ↔ FastAPI ↔ session/business APIs

FastAPI REST/WebSocket must NOT become the primary audio transport.

### 2. Never block the event loop

Use `asyncio` for I/O-bound work.

No synchronous HTTP/database/provider calls inside the realtime turn path.

Use async clients and bounded queues.

### 3. Cancellation is first-class

Every turn owns cancellable tasks.

On interruption:

1. detect speech
2. invalidate current generation
3. stop playback
4. cancel TTS
5. cancel LLM where supported
6. clear stale output
7. return to LISTENING
8. process the new turn

Cancellation must be idempotent.

### 4. No stale audio

Every generated response must have a turn/generation identifier.

Audio from an obsolete generation must never be played.

### 5. No scattered booleans

Do not build logic around combinations such as:

`is_speaking`, `is_processing`, `is_interrupted`.

Use an explicit state machine.

### 6. Provider abstraction

ASR, LLM and TTS must be adapters behind small interfaces.

The voice runtime must not know provider-specific SDK details.

### 7. Deterministic business state

The LLM may interpret language, but authoritative sales state must live in structured objects/database records.

Never let the LLM invent:

- price
- inventory
- appointment slot
- CRM status
- vehicle specification

### 8. Tool safety

Actions such as booking, CRM updates and lead creation require explicit tool contracts.

Use idempotency keys for mutating actions.

### 9. Observability

Every turn should expose:

- speech start
- speech end
- ASR start/first/final
- LLM request/first token
- TTS request/first audio
- first audio played
- interruption detected
- playback stopped
- total turn time
- provider errors

### 10. Test before optimizing

Every latency optimization must have a benchmark.

Track P50/P95/P99.

Primary UX metric: TTFA.

Secondary metric: interruption-stop latency.

## Coding style

- Python 3.11+
- type hints everywhere
- small functions
- dependency injection
- structured logging
- Pydantic models for API/tool contracts
- no hidden global mutable session state
- no provider calls from domain entities
- no business logic in FastAPI routes
- no giant `agent.py` file

## Suggested package boundaries

```text
backend/app/
  api/
  config/
  voice/
  sales/
  catalog/
  integrations/
  persistence/
  observability/
  common/
```

## Definition of done for any feature

A feature is complete only when:

- implementation exists
- unit tests exist
- failure cases are handled
- logs/metrics are emitted where relevant
- cancellation behavior is defined
- API/tool contract is documented
- no regression in voice latency


## Analyze reference/ten-framework-main specifically for:
1. Agora integration
2. VAD
3. turn detection
4. interruption/barge-in
5. audio streaming
6. LLM streaming
7. TTS streaming
8. task cancellation
9. session lifecycle
10. latency optimization

For each relevant component:
- identify the file
- explain what it does
- identify reusable design patterns
- identify dependencies
- check license implications
- determine whether EchoDrive should reuse, adapt, or reimplement it

Do not modify the reference repository.
Do not copy code yet.

Produce TEN_ANALYSIS.md.