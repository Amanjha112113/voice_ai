# ADR-001 — Realtime Runtime Choice

## Decision

Use Agora Conversational AI / `agora-agents` as the primary realtime voice integration for EchoDrive.

Keep the application domain and control plane in FastAPI.

Use TEN as a reference/source for proven realtime-agent patterns and selectively reusable components.

## Why

- Hackathon explicitly requires Agora as a core component.
- Existing project direction already targets Agora + FastAPI.
- A smaller runtime surface is easier to debug during a hackathon.
- Provider adapters preserve future flexibility.
- TEN is valuable for proven VAD/turn-taking/extension patterns.

## Rejected

### Full TEN adoption immediately

Rejected as the default because introducing a second major runtime framework can increase debugging and integration complexity before the core voice loop is benchmarked.

### Microservices-first

Rejected because network hops increase latency and operational complexity without helping the MVP.

## Revisit when

- concurrent session load requires independent scaling
- voice runtime and business API have conflicting resource profiles
- a TEN component demonstrably improves barge-in or TTFA
