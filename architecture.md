# EchoDrive Architecture

## 1. High-level architecture

```text
                         CUSTOMER
                       🎙️ Browser / App
                             |
                             v
                    +-------------------+
                    |      AGORA        |
                    | Realtime Voice/RTC|
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    |   VOICE RUNTIME   |
                    |-------------------|
                    | VAD / Turn Detect|
                    | ASR               |
                    | State Machine     |
                    | Barge-in          |
                    | Cancellation      |
                    | LLM Streaming     |
                    | TTS Streaming     |
                    +---------+---------+
                              |
                              v
                  +-------------------------+
                  | CONVERSATION MANAGER    |
                  +------------+------------+
                               |
             +-----------------+------------------+
             |                 |                  |
             v                 v                  v
      +-------------+   +-------------+   +-------------+
      | Deal State  |   | Product RAG |   | Strategy    |
      | / Memory    |   | + Catalog   |   | Engine      |
      +------+------+   +------+------+   +------+------+
             |                 |                  |
             +-----------------+------------------+
                               |
                               v
                     +-------------------+
                     |    TOOL LAYER     |
                     +---------+---------+
                               |
              +----------------+----------------+
              |                |                |
              v                v                v
          Inventory          CRM            Calendar
          / Pricing        / Leads       / Test Drive
              |                |                |
              +----------------+----------------+
                               |
                               v
                        HUMAN ESCALATION
```

## 2. Media plane

The media plane is optimized for continuous realtime interaction:

`Customer audio → Agora → Voice Runtime → Agora → Customer audio`

Do not route live audio through REST.

## 3. Control plane

FastAPI handles:

- session creation
- session status
- configuration
- authentication
- CRM actions
- appointments
- catalog APIs
- dashboard events
- health checks

## 4. Data plane

Use PostgreSQL for durable business state.

Use Redis only where it materially improves latency:

- short-lived session metadata
- cache
- distributed locks where needed
- idempotency records

Do not introduce Redis just because it is common.

## 5. Retrieval

Use a hybrid approach:

### Structured lookup

Use PostgreSQL/indexed queries for:

- model
- variant
- price
- fuel
- transmission
- seating
- features
- availability

### Semantic retrieval

Use embeddings/vector search only for unstructured content:

- brochures
- feature explanations
- FAQs
- dealership policies

Structured facts must be authoritative.

## 6. Deployment

Start with a modular monolith:

```text
Browser
  |
Load Balancer
  |
FastAPI + Voice Runtime
  |
PostgreSQL
Redis (optional)
External Providers
```

Split services only after profiling demonstrates a need.
