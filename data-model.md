# Data Model

## Core entities

### Customer

```text
Customer
- id
- name
- phone/email (optional)
- location
- created_at
```

### Session

```text
Session
- id
- customer_id
- agora_channel
- state
- language
- started_at
- ended_at
```

### Deal

```text
Deal
- id
- customer_id
- stage
- budget_min
- budget_max
- purchase_timeline
- intent_score
- next_action
- created_at
- updated_at
```

### Requirement

```text
Requirement
- id
- deal_id
- key
- value
- confidence
- source_turn_id
- updated_at
```

### Objection

```text
Objection
- id
- deal_id
- category
- text
- severity
- status
- created_at
```

### Vehicle

```text
Vehicle
- id
- brand
- model
- variant
- price_min
- price_max
- seating
- fuel
- transmission
- body_type
- mileage
- features
- availability_status
- updated_at
```

### Appointment

```text
Appointment
- id
- customer_id
- vehicle_id
- dealership_id
- slot_start
- slot_end
- appointment_type
- status
- idempotency_key
```

## Persistence strategy

PostgreSQL is the source of truth for durable state.

Redis is optional for:

- hot catalog cache
- session metadata
- rate limiting
- idempotency

Never use Redis as the only source of truth for appointments or leads.

## Conversation storage

Store:

- turn id
- session id
- speaker
- timestamp
- transcript
- latency metrics
- tool calls

Avoid storing raw audio by default unless explicitly required and consented.

## Privacy

Minimize personal data.

Apply retention policies.

Never log secrets or complete authentication tokens.
