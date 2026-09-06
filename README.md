# EchoDrive — Antigravity Engineering Specification

## Purpose

This directory contains the implementation contract for **EchoDrive**, a real-time conversational AI sales agent for automotive dealerships.

EchoDrive must feel like a live sales conversation, not a scripted chatbot.

### Core loop

Customer voice → Agora realtime media → voice runtime → conversation intelligence → sales tools/data → streamed voice response → customer

### Primary outcome

Turn a natural conversation into a measurable sales action:

- qualified lead
- recommended vehicle(s)
- showroom appointment
- test-drive booking
- human-sales escalation with full context

## Important implementation rule

Build the system in layers.

1. Stabilize realtime voice, turn-taking and interruption.
2. Add sales state and conversation memory.
3. Add product/pricing retrieval.
4. Add CRM/calendar actions.
5. Add observability, reliability and production hardening.

Do not start with microservices, Kafka, Kubernetes or a complex multi-agent system.

## Reference architecture

- Agora = realtime media / conversational voice layer.
- Voice runtime = session lifecycle, state machine, interruption, cancellation, streaming pipeline.
- FastAPI = control plane and business APIs; never carry primary live audio.
- Sales intelligence = customer/deal state + qualification + objection handling + next-best-action.
- Data layer = PostgreSQL/Redis where justified.
- Product knowledge = structured catalog + retrieval layer.
- Actions = CRM, calendar, inventory/pricing adapters.

See `architecture.md`, `system-design.md`, and `low-latency.md`.

## Repository adoption

The supplied reference repository/documentation corresponds to the TEN Framework ecosystem. TEN provides realtime multimodal voice-agent infrastructure, VAD, turn detection and agent examples.

Use it as a reference and selectively reuse compatible components only after checking the exact component license and integration cost. Do not blindly copy the repository.

For this hackathon, the preferred baseline is to keep **Agora Conversational AI / agora-agents** as the primary realtime integration and borrow proven runtime patterns from TEN where useful.

## Source of truth

Antigravity should treat these documents as engineering constraints, not optional suggestions.

Priority:

1. `AGENTS.md`
2. `PRD.md`
3. `architecture.md`
4. `system-design.md`
5. `voice-runtime.md`
6. `low-latency.md`
7. `sales-agent.md`
8. `data-model.md`
9. `tools-integrations.md`
10. `testing-observability.md`
11. `security.md`
12. `phases.md`
13. `repo-adoption.md`
