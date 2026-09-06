# System Design — EchoDrive

## 1. Design principles

### Low latency
Optimize the critical voice path before adding features.

### Correctness
Never generate business facts from model memory.

### Isolation
Each voice session owns its own runtime state.

### Extensibility
Provider adapters and tools must be replaceable.

### Simplicity
Prefer a modular monolith for the hackathon.

## 2. Request categories

### Realtime path

```text
Audio
 → ASR
 → intent/context update
 → LLM
 → TTS
 → Audio
```

This path must remain minimal.

### Business action path

```text
LLM tool decision
 → tool validation
 → service
 → DB/API
 → tool result
 → LLM
```

Do not make slow CRM/calendar calls block the first spoken response when they are not required.

## 3. Parallelism

When safe, execute independent work concurrently.

Example:

Customer asks:
"Show me seven-seat SUVs under 18 lakh with good mileage."

Parallelize:

- structured catalog filter
- semantic retrieval for feature explanations

Merge results before response generation.

## 4. Progressive response

Never wait for the complete LLM answer before starting TTS.

Use:

```text
LLM token stream
   ↓
sentence/phrase chunker
   ↓
TTS stream
   ↓
Agora playback
```

Do not split at arbitrary token boundaries.

## 5. Backpressure

All streaming queues must be bounded.

If downstream is slower:

- apply bounded buffering
- cancel obsolete generation
- drop stale chunks
- never allow unbounded memory growth

## 6. Session isolation

```text
Session
 ├── state
 ├── conversation
 ├── generation_id
 ├── ASR task
 ├── LLM task
 ├── TTS task
 ├── playback controller
 ├── metrics
 └── cancellation controller
```

No mutable global conversation context.

## 7. Failure handling

Provider timeout:

- stop waiting
- use bounded retry only where safe
- transition to recoverable state
- provide concise spoken fallback

CRM failure:

- conversation continues
- action is marked pending
- retry asynchronously when possible

Calendar failure:

- offer alternative manual booking flow

Catalog failure:

- never invent facts
- clearly state that live availability/pricing could not be verified

## 8. Scaling

For the hackathon:

- horizontal replicas
- stateless HTTP control plane
- session affinity only if the selected voice runtime requires it
- external durable DB
- no shared in-process session state between replicas

If the realtime runtime owns long-lived state, route a session consistently to its owning worker.

## 9. Consistency

Strong consistency required for:

- appointment creation
- lead creation
- inventory reservation, if implemented

Eventual consistency acceptable for:

- analytics
- dashboard aggregates
- non-critical transcripts

## 10. Idempotency

Every mutating tool should accept an idempotency key.

Example:

`book_test_drive(session_id, request_id, slot_id)`

A retried request must not create two appointments.
